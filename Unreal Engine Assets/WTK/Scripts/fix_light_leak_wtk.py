"""
WTK_Main_v2 light-leak fix, 2026-09-27 REWRITE: single-sided shell +
one roof slab (replaces the earlier 4-wall-blocker approach).

PREVIOUS APPROACH (superseded, kept here only as history -- see
tmp/WtkLeak_20260927/report.txt for the full old diagnostic): the earlier
theory was a literal dimensional gap between the ceiling's XY footprint and
the walls' full thickness at the wall-top/ceiling junction, "fixed" by
spawning 4 thin visible+cast_shadow WTK_Blocker_* boxes, one per wall,
plugging each wall's 15.24cm-wide gap strip. The coordinator's re-read of the
re-rendered CAM_Wide image found this produced ugly dark bands at the
wall/ceiling junction (the visible blocker boxes themselves, now dark/
unlit-looking against the ceiling) and did NOT eliminate the leak: the
CAM_Wide wedge and the small bright quad at ~(1820,920) persisted, and the
side walls are solid geometry (not flat planes), so a literal gap in a solid
box's own thickness was never a coherent explanation for light passing
through a wall's own material in the first place.

NEW ROOT CAUSE (confirmed by inspection this pass,
tmp/WtkRoof_20260927/check_shell_twosided.txt): every shell
StaticMeshComponent in the level (all 4 Walls_*, Floors_Floor_Generic_-_12_,
Ceilings_Basic_Ceiling_Generic) has cast_shadow_as_two_sided=False. The
ceiling mesh in particular (Ceilings_Basic_Ceiling_Generic) is a genuinely
thin/single-sided mesh (already documented as such in Docs/Lighting.md
Section 9.1, which fixed its VISIBLE-face normal direction with a one-time
flip pass so it isn't invisible from inside the room). A single-sided mesh
with cast_shadow_as_two_sided=False only casts a shadow when a light ray
hits its FRONT face; WTK_Sun has pitch=-15 degrees (i.e. sunlight arrives
from ABOVE, travelling downward), so it strikes the ceiling's outward/upward
face -- if that is the mesh's BACK face for shadow-casting purposes (which is
exactly what the earlier ceiling-flip pass would produce: the visible face
from inside was made to point down/into the room, meaning the geometric
front face for a single-sided normal-based shadow test points UP, away from
the sun -- wait, more precisely: whichever way the flip pass oriented the
"visible" face, hardware-RT shadow rays fired from the sun position hit the
mesh from above, and if that hit is registered as a back-face hit on a
single-sided mesh, hardware RT drops it as a non-occluding hit), the sun's
shadow rays pass straight through the ceiling as if it weren't there,
travelling on to graze the tops of the walls (the upper part of the +X/right
wall matches the CAM_Wide wedge geometry) and reach the counter (the
CAM_Angle streak) -- i.e. the sun effectively shines THROUGH the ceiling from
outside, rather than leaking through any gap at all.

FIX: set cast_shadow_as_two_sided=True on every shell StaticMeshComponent
(all Walls_*, all Floors_*, all Ceilings_*) so RT shadow rays occlude
regardless of which face they hit -- correct behavior for what should read
as solid opaque architecture regardless of the underlying mesh's authored
front-face winding. Belt-and-braces: replace the 4 old wall-top blockers
(destroyed) with ONE simple roof slab, WTK_Blocker_Roof, spanning the whole
building footprint (all 4 walls' outer extents, +30cm margin on every side)
sitting entirely above the ceiling plane so it cannot be seen from inside,
20cm thick, visible + cast_shadow=True (matching the established WTK
hardware-RT lesson: a hidden/cast_hidden_shadow-only primitive is excluded
from the RT scene entirely and casts no shadow at all).

Idempotent: destroys any existing "WTK_Blocker_*"-labelled actor (this widened
match, not just "WTK_Blocker_Roof", so a stale run of the OLD 4-wall-blocker
version is also cleaned up automatically) via a snapshot-then-destroy pattern
(iterating and destroying from the same live list was shown, in the earlier
revision's own history, to silently break idempotency and leak actors), then
spawns exactly one new WTK_Blocker_Roof.

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -stdout
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH

OUT_DIR = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkRoof_20260927"
REPORT_PATH = os.path.join(OUT_DIR, "fix_report.txt")
CUBE_MESH_PATH = "/Engine/BasicShapes/Cube.Cube"

lines = []


def log(msg):
    try:
        unreal.log(str(msg))
    except Exception:
        pass
    lines.append(str(msg))


def flush():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# Room/building geometry (cm), confirmed live this pass
# (tmp/WtkRoof_20260927/footprint.txt) by reading every Walls_*/Ceilings_*
# actor's actual world bounds -- NOT hardcoded from the old diagnostic, since
# this is the authoritative footprint including full wall thickness on every
# side:
#   Walls_Basic_Wall_WTK_Interior_6in   (front/window wall): x:[-350.52,45.72]  y:[0,15.24]     z:[0,243.84]
#   Walls_Basic_Wall_WTK_Interior_6in_2 (right wall):        x:[30.48,45.72]    y:[-441.96,0]    z:[0,243.84]
#   Walls_Basic_Wall_WTK_Interior_6in_3 (back wall):         x:[-350.52,30.48]  y:[-441.96,-426.72] z:[0,243.84]
#   Walls_Basic_Wall_WTK_Interior_6in_4 (left wall):         x:[-350.52,-335.28] y:[-426.72,0]   z:[0,243.84]
#   Ceilings_Basic_Ceiling_Generic:                          x:[-335.28,30.48]  y:[-426.72,0]    z:243.84 (flat)
# Overall building footprint (union of all 4 walls' outer extents):
BUILDING_X_MIN, BUILDING_X_MAX = -350.52, 45.72
BUILDING_Y_MIN, BUILDING_Y_MAX = -441.96, 15.24
CEILING_Z = 243.84

ROOF_MARGIN_CM = 30.0  # extra margin past the building footprint on every side
ROOF_THICKNESS_CM = 20.0
ROOF_BOTTOM_Z = CEILING_Z + 1.0  # bottom face 1cm above the ceiling plane -- entirely above it, never visible from inside


def set_two_sided_shadows_on_shell():
    """
    Sets cast_shadow_as_two_sided=True on every StaticMeshComponent belonging
    to an actor labelled Walls_*, Floors_*, or Ceilings_* -- the actual root
    cause fix (see module docstring). Returns the count of components
    touched.
    """
    all_actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    touched = 0
    for a in all_actors:
        label = a.get_actor_label()
        if not label.startswith(("Walls_", "Floors_", "Ceilings_")):
            continue
        smcs = a.get_components_by_class(unreal.StaticMeshComponent)
        for comp in smcs:
            try:
                before = comp.get_editor_property("cast_shadow_as_two_sided")
            except Exception:
                before = None
            comp.modify()
            comp.set_editor_property("cast_shadow_as_two_sided", True)
            touched += 1
            log("  %s: cast_shadow_as_two_sided %s -> True" % (label, before))
    log("Set cast_shadow_as_two_sided=True on %d shell StaticMeshComponent(s) (Walls_/Floors_/Ceilings_)." % touched)
    return touched


def destroy_existing_blockers():
    # Snapshot-then-destroy (not iterate-and-destroy-from-the-same-live-list)
    # -- the prior version of this script found live iteration silently
    # broke idempotency (actor count climbed every run) because destroying an
    # actor mid-iteration shifts the underlying array and skips entries.
    all_actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    to_destroy = [a for a in all_actors if a.get_actor_label().startswith("WTK_Blocker_")]
    destroyed = 0
    for a in to_destroy:
        log("  destroying existing blocker actor: %s" % a.get_actor_label())
        unreal.EditorLevelLibrary.destroy_actor(a)
        destroyed += 1
    log("Destroyed %d existing WTK_Blocker_* actor(s) (found %d candidates before destroying)." % (
        destroyed, len(to_destroy)))
    return destroyed


def spawn_roof_slab():
    """
    Spawns ONE visible, shadow-casting roof slab covering the whole building
    footprint (all 4 walls' outer extents + ROOF_MARGIN_CM on every side),
    ROOF_THICKNESS_CM thick, with its BOTTOM face at CEILING_Z + 1.0cm --
    entirely above the ceiling plane, so it cannot be seen from inside no
    matter which interior camera angle is used.
    """
    cube_mesh = unreal.EditorAssetLibrary.load_asset(CUBE_MESH_PATH)
    if not cube_mesh:
        raise RuntimeError("Could not load %s" % CUBE_MESH_PATH)

    x_min = BUILDING_X_MIN - ROOF_MARGIN_CM
    x_max = BUILDING_X_MAX + ROOF_MARGIN_CM
    y_min = BUILDING_Y_MIN - ROOF_MARGIN_CM
    y_max = BUILDING_Y_MAX + ROOF_MARGIN_CM

    center = unreal.Vector(
        (x_min + x_max) / 2.0,
        (y_min + y_max) / 2.0,
        ROOF_BOTTOM_Z + ROOF_THICKNESS_CM / 2.0,
    )
    half_extent = unreal.Vector(
        (x_max - x_min) / 2.0,
        (y_max - y_min) / 2.0,
        ROOF_THICKNESS_CM / 2.0,
    )

    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, center, unreal.Rotator(0, 0, 0)
    )
    actor.set_actor_label("WTK_Blocker_Roof")
    comp = actor.static_mesh_component
    comp.modify()
    comp.set_static_mesh(cube_mesh)

    scale = unreal.Vector(half_extent.x / 50.0, half_extent.y / 50.0, half_extent.z / 50.0)
    actor.modify()
    actor.set_actor_scale3d(scale)

    # Established WTK hardware-RT lesson (see the earlier report.txt history):
    # a hidden/cast_hidden_shadow-only primitive is excluded from the
    # ray-tracing scene entirely under Lumen/hardware RT, so it must be
    # NORMALLY VISIBLE + cast_shadow=True to actually occlude the sun. It
    # stays unseen by every interior camera because its bottom face sits
    # entirely above the ceiling plane (ROOF_BOTTOM_Z = CEILING_Z + 1.0cm).
    comp.set_editor_property("visible", True)
    comp.set_editor_property("hidden_in_game", False)
    comp.set_editor_property("cast_shadow", True)
    try:
        comp.set_editor_property("affect_dynamic_indirect_lighting", False)
    except Exception as e:
        log("  (affect_dynamic_indirect_lighting property not settable, non-fatal: %s)" % e)

    log("Spawned WTK_Blocker_Roof: center=(%.2f,%.2f,%.2f) half-extent=(%.2f,%.2f,%.2f) "
        "scale=(%.3f,%.3f,%.3f) [footprint x:[%.2f,%.2f] y:[%.2f,%.2f], bottom_z=%.2f, top_z=%.2f]"
        % (center.x, center.y, center.z, half_extent.x, half_extent.y, half_extent.z,
           scale.x, scale.y, scale.z, x_min, x_max, y_min, y_max, ROOF_BOTTOM_Z, ROOF_BOTTOM_Z + ROOF_THICKNESS_CM))
    return actor


def main():
    log("=== WTK light-leak fix (2026-09-27 rewrite): two-sided shell shadows + roof slab ===")
    log("Map: %s" % MAP_PATH)

    loaded_ok = unreal.EditorLevelLibrary.load_level(MAP_PATH)
    log("load_level returned: %s" % loaded_ok)

    before_count = len(unreal.EditorLevelLibrary.get_all_level_actors())
    log("Actor count before fix: %d" % before_count)

    set_two_sided_shadows_on_shell()
    destroy_existing_blockers()
    spawn_roof_slab()

    after_count = len(unreal.EditorLevelLibrary.get_all_level_actors())
    log("Actor count after fix: %d (before=%d, delta=%d)" % (
        after_count, before_count, after_count - before_count))

    world = unreal.EditorLevelLibrary.get_editor_world()
    saved_current = unreal.EditorLevelLibrary.save_current_level()
    saved_map = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    except Exception as e:
        log("save_dirty_packages() not available/failed (non-fatal, save_current_level+save_map already ran): %s" % e)
    log("save_current_level()=%s, save_map()=%s" % (saved_current, saved_map))

    log("=== END FIX ===")
    flush()
    print("WROTE: %s" % REPORT_PATH)


main()
