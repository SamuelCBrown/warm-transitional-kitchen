"""
WTK Phase 5e Task 3: import Poly Haven CC0 props (glTF) and place them as
level actors -- a cutting board, a small potted succulent, and a wooden bowl
-- into the WTK kitchen scene.

Two-part script, because import needs full-editor Slate (see the "MUST run
via -ExecutePythonScript" note below) while placement is pure level-editor
scripting that would also work under -run=pythonscript:

  1. import_props()  -- glTF import via AssetTools, /Game/WTK/Props/<asset>/.
  2. place_props()   -- spawns/updates StaticMeshActor instances at their
                         final positions, labelled WTK_Prop_<name> so
                         delete_and_reimport's Datasmith-actor cleanup (see
                         import_wtk.py) can be confirmed to leave them alone.

Run (MUST be the full editor, not the commandlet -- import_asset_tasks()
touches ContentBrowser/Slate UI code and crashes under -run=pythonscript's
headless commandlet mode with "Assertion failed: CurrentApplication.IsValid()",
the same constraint already documented for texture import in
Docs/Materials.md's "Environment notes"):

  UnrealEditor.exe <proj>.uproject -ExecutePythonScript=<this file>

Idempotent: re-running re-imports over the same destination paths
(replace_existing=True) and finds-or-spawns each prop actor by its
WTK_Prop_* label (same idempotent-actor-by-label pattern as
setup_lighting_wtk.py / setup_cameras_wtk.py).
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH

SRC_ROOT = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK_SourceProps"
DEST_ROOT = "/Game/WTK/Props"

# 2026-09-27 (props-removal pass): user feedback said "take out the plant and
# the things on the countertop." Rather than delete this script's code or its
# imported assets (kept, per the task's own instruction, in case props are
# wanted again later), main() now exits immediately when this flag is False,
# before either import_props() or place_props() runs, so no prop actor is
# spawned/updated/respawned by this script. The actual removal of the 3
# existing prop actors from the level (WTK_Prop_CuttingBoard/Plant/Bowl +
# their attached child actors) is a one-time level edit done separately (see
# Docs/Props.md), not something this flag itself performs -- this flag only
# stops the pipeline from putting them back.
PLACE_PROPS = False

# Scene facts (see Docs/Lighting.md's "Scene facts confirmed" section, and
# WTK prop-fix pass 2026-09-26's own actor-bounds dump,
# tmp/WtkProps2_20260926/dump_bounds.py / dump_bounds.log, which superseded
# the earlier guessed X/Y ranges below with the following VERIFIED bounds):
#   Room interior: X [-335.28, 30.48], Y [-426.72, 0], Z [0, 243.84].
#   Back wall (window wall) face at Y=0; room interior/cabinets at Y<0.
#   Casework_FX-01 (counter): X[-307.34, 2.54], Y[-63.50, 0.00], top Z=91.44.
#   Casework_FX-04 (backsplash): X[-304.80, 0.00], Y[-1.90, 0.00] (front face
#     at Y=-1.90, since the room interior is the negative-Y side), Z[91.44,137.16].
#   Furniture_FX-05 (floating shelves, BOTH shelves in one actor): X[-304.80,
#     -214.63], Y[-25.40, 0.00], Z[152.40, 191.77] combined -- lower shelf top
#     ~Z=156 (per the orchestrator's ~154.9 estimate), upper shelf top at the
#     actor's own max Z = 191.77 (close to the orchestrator's ~190.5 estimate;
#     verified value used here).
#   Plumbing_Fixtures_FX-02 (sink cutout): X[-127.00,-55.88], Y[-52.07,-11.43],
#     top Z~88.44 (recessed below the counter top).
#   Plumbing_Fixtures_FX-03 (faucet): X[-92.71,-90.17], base Z=91.44.
#   Casework_WTK_B30_B30: X[-213.36,-137.16]. Casework_WTK_DB24_DB24:
#     X[-274.32,-213.36]. So the counter zone directly above B30+DB24 (clear
#     of the sink and of the window) is X[-274.32,-137.16].
#   Window: X[-128.90,-53.98], Z[107.32,197.49].
COUNTER_TOP_Z = 91.44
BACKSPLASH_FACE_Y = -1.90  # front (room-side) face of the backsplash slab; room interior is Y<0, see FX-04 bounds above
SHELF_UPPER_X_MIN, SHELF_UPPER_X_MAX = -304.80, -214.63
SHELF_UPPER_Y_MIN, SHELF_UPPER_Y_MAX = -25.40, 0.00
SHELF_UPPER_TOP_Z = 191.77
SINK_X_MIN, SINK_X_MAX = -127.00, -55.88
COUNTER_X_MIN, COUNTER_X_MAX = -307.34, 2.54
B30_DB24_X_MIN, B30_DB24_X_MAX = -274.32, -137.16

# --- Asset import specs: (asset_slug, gltf_filename) ---
PROP_ASSETS = [
    ("wooden_cutting_board", "wooden_cutting_board_2k.gltf"),
    ("potted_plant_04", "potted_plant_04_2k.gltf"),
    ("wooden_bowl_01", "wooden_bowl_01_2k.gltf"),
]


def log(msg):
    print("[WTK_Props] %s" % msg)


def import_props():
    """
    Imports each Poly Haven glTF asset into /Game/WTK/Props/<slug>/ via
    AssetTools' automated import task path (same pattern as
    import_wtk_textures.py's build_import_task(), generalized to glTF's
    "one task per top-level file, engine resolves the referenced .bin/
    textures next to it on disk" import model). Returns a dict of
    slug -> list of imported StaticMesh asset paths.

    Import-run finding: UE 5.7's glTF importer (Interchange) does NOT always
    produce a single combined StaticMesh per asset -- `potted_plant_04`
    imported as 4 separate StaticMeshes (`_ground`, `_dirt`, `_plant`,
    `_pot`, one per glTF mesh node/material), while `wooden_cutting_board`
    and `wooden_bowl_01` each imported as a single StaticMesh. This was only
    discovered after the first run (a single-mesh assumption spawned only
    the small `_ground` plane for the plant, leaving the actual pot/plant
    geometry unplaced) -- confirmed via `Saved/Logs/WTK.log`'s
    "Imported potted_plant_04 -> ... (8 objects: [...])" line listing all 4
    StaticMeshes. Fixed by returning every StaticMesh found (not just the
    first) so place_props() can spawn one StaticMeshActor per sub-mesh, all
    at the same transform, reassembling the full multi-part prop.
    """
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    results = {}
    for slug, gltf_name in PROP_ASSETS:
        src_abs = os.path.join(SRC_ROOT, slug, gltf_name)
        if not os.path.isfile(src_abs):
            log("ERROR: source glTF not found: %s" % src_abs)
            continue
        dest_path = "%s/%s" % (DEST_ROOT, slug)

        task = unreal.AssetImportTask()
        task.filename = src_abs
        task.destination_path = dest_path
        task.automated = True
        task.save = True
        task.replace_existing = True
        task.replace_existing_settings = True

        asset_tools.import_asset_tasks([task])
        imported = list(task.imported_object_paths) if task.imported_object_paths else []
        log("Imported %s -> %s (%d objects: %s)" % (slug, dest_path, len(imported), imported))

        mesh_paths = []
        for p in imported:
            obj = unreal.EditorAssetLibrary.load_asset(p)
            if isinstance(obj, unreal.StaticMesh):
                mesh_paths.append(p)
        if not mesh_paths:
            log("WARNING: no StaticMesh found among imported objects for %s" % slug)
        results[slug] = mesh_paths
    return results


def _actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def find_actor_by_label(label):
    for a in _actor_subsys().get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


def _combined_local_bounds(mesh_assets):
    """
    Combined local-space bounds (pre-transform) across a list of StaticMesh
    assets, used to auto-correct the base-Z offset for multi-part props (see
    import_props()'s docstring for why potted_plant_04 needs this: it
    imports as 4 separate StaticMeshes whose individual pivots are NOT all
    at a shared "assembly base" point). Returns (min_z, max_z) in the
    mesh's own local units (cm, unscaled).
    """
    min_z = None
    max_z = None
    for mesh in mesh_assets:
        bb = mesh.get_bounding_box()
        bmin, bmax = bb.min, bb.max
        min_z = bmin.z if min_z is None else min(min_z, bmin.z)
        max_z = bmax.z if max_z is None else max(max_z, bmax.z)
    return min_z, max_z


def compute_uniform_scale_for_target_length(mesh_paths, target_length_cm, axis="long", default_scale=1.0):
    """
    Re-import hardening 2026-09-27, Task 4: computes a single uniform scale
    factor (applied equally to X/Y/Z, so the prop is resized, not distorted)
    from the FIRST mesh's own local-space bounding box, such that the mesh's
    long horizontal axis (axis="long", max of local X/Y extent -- used for
    the cutting board) or its horizontal diameter (axis="diameter", same
    max-of-X/Y measure, used for the bowl -- a round object's "diameter" and
    "long axis" are the same measurement) comes out to target_length_cm in
    world units after scaling.

    Uses EditorAssetLibrary.load_asset()'s already-loaded StaticMesh (mesh_
    paths[0]) and get_bounding_box() (unreal.Box, native units = cm, same
    units this module's other bounds math already uses throughout) -- the
    same box(local, unscaled) API _combined_local_bounds() above already
    relies on for the rest_on_z correction, so this stays consistent with the
    rest of this script's bounds-handling.

    Returns unreal.Vector(f, f, f). Falls back to
    unreal.Vector(default_scale, default_scale, default_scale) if no valid
    mesh is found or the measured extent is degenerate (<=0), so a missing/
    bad asset can't produce a zero or infinite scale.
    """
    meshes = [unreal.EditorAssetLibrary.load_asset(p) for p in (mesh_paths or [])]
    meshes = [m for m in meshes if isinstance(m, unreal.StaticMesh)]
    if not meshes:
        log("compute_uniform_scale_for_target_length: no valid mesh found -- using default_scale=%.3f" % default_scale)
        return unreal.Vector(default_scale, default_scale, default_scale)

    bb = meshes[0].get_bounding_box()
    extent_x = bb.max.x - bb.min.x
    extent_y = bb.max.y - bb.min.y
    native_length_cm = max(abs(extent_x), abs(extent_y))
    if native_length_cm <= 0.0:
        log("compute_uniform_scale_for_target_length: degenerate mesh extent -- using default_scale=%.3f" % default_scale)
        return unreal.Vector(default_scale, default_scale, default_scale)

    factor = target_length_cm / native_length_cm
    log("compute_uniform_scale_for_target_length: native long-axis=%.2fcm, target=%.2fcm -> scale factor=%.4f"
        % (native_length_cm, target_length_cm, factor))
    return unreal.Vector(factor, factor, factor)


def spawn_or_update_prop(label, mesh_paths, location, rotation, scale=unreal.Vector(1, 1, 1), rest_on_z=None):
    """
    Idempotent multi-mesh prop placement by label, WTK_Prop_* naming so
    Datasmith reimport's actor cleanup can be checked/confirmed not to touch
    these (see Task 3's reimport-safety requirement, and the
    run_material_remap/delete_and_reimport review in import_wtk.py -- that
    path only iterates unreal.EditorLevelLibrary.get_all_level_actors() and
    destroys ALL of them, so non-Datasmith actors (lights, cameras, props,
    PPV) are NOT currently safe across delete_and_reimport; see
    Docs/Pipeline.md's "Reimport safety" section for the finding and fix
    this task adds).

    mesh_paths: list of one or more StaticMesh asset paths (see
    import_props()'s docstring -- some Poly Haven glTF assets, e.g.
    potted_plant_04, import as several separate StaticMeshes rather than
    one combined mesh). A parent StaticMeshActor (the first mesh, driving
    the label/transform every WTK_* script and the reimport-safety filter
    key off of) gets one child StaticMeshActor per additional sub-mesh,
    actor-attached (KEEP_RELATIVE at identity, i.e. co-located) so the whole
    assembly moves/scales/rotates together under the single WTK_Prop_*
    label. (Note: `unreal.StaticMeshActor.add_component_by_class` does not
    exist in this UE 5.7 Python binding -- confirmed via an AttributeError
    on the first attempt at a true multi-component single-actor assembly --
    so actor-attachment is used instead of a true multi-component actor;
    functionally equivalent for a static, non-physics prop like this.)

    rest_on_z: if given, the actor's Z location is corrected so the combined
    local-space bounds' minimum Z (scaled) sits exactly at this world Z --
    i.e. `location.z` is treated as a rough placement guess and rest_on_z is
    the real "surface the prop should sit on" (counter top, shelf, etc). This
    fixes the exact bug found in this task's first run: potted_plant_04's
    individual sub-mesh pivots are NOT at the assembly's own visual base, so
    a naive "spawn at the shelf's Z" left it floating ~13cm above the shelf.
    """
    meshes = [unreal.EditorAssetLibrary.load_asset(p) for p in (mesh_paths or [])]
    meshes = [m for m in meshes if isinstance(m, unreal.StaticMesh)]
    if not meshes:
        log("ERROR: no valid StaticMesh(es) for prop %s -- skipping placement." % label)
        return None

    final_location = location
    if rest_on_z is not None:
        min_z, _max_z = _combined_local_bounds(meshes)
        scaled_min_z = min_z * scale.z
        final_location = unreal.Vector(location.x, location.y, rest_on_z - scaled_min_z)

    existing = find_actor_by_label(label)
    if existing:
        log("Found existing prop actor '%s' -- updating transform in place." % label)
        actor = existing
    else:
        actor = _actor_subsys().spawn_actor_from_class(unreal.StaticMeshActor, final_location, rotation)
        actor.set_actor_label(label)
        log("Spawned new prop actor '%s'." % label)

    # WTK prop-fix pass, round 2 (2026-09-26): the coordinator found that an
    # UPDATE to an EXISTING actor's transform never actually persisted to
    # WTK_Main.umap -- the .umap's own on-disk LastWriteTime stayed at the
    # pre-placement-run timestamp across two separate placement runs, and
    # the subsequent renders showed the OLD (pre-fix) prop positions. Root
    # cause: set_actor_location()/set_actor_rotation()/set_static_mesh() on
    # an actor/component do NOT themselves call Modify() or mark the owning
    # package dirty in every code path (a Blueprint/Slate-driven edit does
    # this implicitly via the transaction system; a raw scripted property
    # set does not always) -- so a later save_current_level() call, which
    # (per this engine build's behaviour) appears to only actually write
    # packages already flagged dirty, silently no-ops on an unchanged-looking
    # package even though the actor's live in-memory state did change. This
    # is the same class of "struct/property mutation doesn't dirty the
    # package" bug already documented elsewhere in this project (see
    # Lighting.md's Section 9.4 LED-rotation persistence bug, and Section 5b's
    # camera-binding persistence bug) -- it recurs here because
    # spawn_or_update_prop's "update existing actor" path was never covered
    # by the earlier fixes, only the lighting/camera scripts were.
    # Fix: explicitly call actor.modify() (and component.modify() before its
    # own property changes) immediately before every mutation on an existing
    # actor, so the transaction system flags the actor's package dirty
    # regardless of whether the underlying setter does so itself.
    actor.modify()
    actor.set_actor_location(final_location, False, False)
    actor.set_actor_rotation(rotation, False)
    actor.set_actor_scale3d(scale)

    # Primary mesh (index 0) on the actor's own built-in StaticMeshComponent.
    actor.static_mesh_component.modify()
    actor.static_mesh_component.set_static_mesh(meshes[0])

    # Any additional sub-meshes (multi-part assets) get their own child
    # StaticMeshActor, found-or-spawned by a deterministic label so a rerun
    # updates rather than duplicates them, attached to the parent at
    # identity-relative transform (KEEP_RELATIVE with a zeroed relative
    # transform == co-located, so the child inherits the parent's location/
    # rotation/scale exactly and moves with it on any future update).
    for i, mesh in enumerate(meshes[1:], start=1):
        part_label = "%s_Part%d" % (label, i)
        part_actor = find_actor_by_label(part_label)
        if part_actor is None:
            part_actor = _actor_subsys().spawn_actor_from_class(
                unreal.StaticMeshActor, final_location, rotation)
            part_actor.set_actor_label(part_label)
        # Same modify()-before-mutate fix as the parent actor above --
        # required for the plant's _Part1/2/3 child actors to actually
        # persist an updated transform/mesh across a rerun.
        part_actor.modify()
        part_actor.static_mesh_component.modify()
        part_actor.static_mesh_component.set_static_mesh(mesh)
        part_actor.set_actor_scale3d(scale)
        part_actor.attach_to_actor(actor, "",
                                    unreal.AttachmentRule.KEEP_WORLD,
                                    unreal.AttachmentRule.KEEP_WORLD,
                                    unreal.AttachmentRule.KEEP_WORLD)
        part_actor.set_actor_location(final_location, False, False)
        part_actor.set_actor_rotation(rotation, False)

    log("Placed prop actor '%s' at %s (%d mesh part(s))." % (label, final_location, len(meshes)))
    return actor


def place_props(mesh_paths):
    """
    WTK prop-fix pass (2026-09-26), re-placement using VERIFIED actor bounds
    (see the module-level "Scene facts" comment block above, derived from
    tmp/WtkProps2_20260926/dump_bounds.py's live dump) -- fixing two bugs
    reported by the orchestrator from the CAM_Wide render:

    Bug 1 (plant floats): the old placement put the plant at X=-60, Y=-13,
    "resting" on Z=145 -- but the FX-05 shelf actor's VERIFIED bounds are
    X[-304.80,-214.63], nowhere near X=-60. The old X/Y guess was simply off
    the shelf entirely (an inch/cm mixup per the task's own hypothesis),
    which is why the plant read as floating beside the window at the shelf's
    HEIGHT but nowhere near the shelf's actual footprint. Fix: place the
    plant on the shelf's real footprint, upper shelf (top Z=191.77, the
    actor's own max Z), near the shelf's right third:
    X = SHELF_UPPER_X_MIN + 0.75*(SHELF_UPPER_X_MAX-SHELF_UPPER_X_MIN)
      = -304.80 + 0.75*90.17 = -237.2, well inside [-304.80,-214.63] with
    margin on both sides for the plant's own ~20cm footprint; Y centred in
    the shelf's Y[-25.40,0.00] depth band (Y=-13, unchanged -- that value
    was already fine, only X/Z were wrong).

    Bug 2 (cutting board/bowl overlap the sink cutout): the old X=-60/-45
    placements landed inside the sink cutout's own X-range, X[-127.00,
    -55.88] is the *sink's* range, and -60/-45 are just past its right edge
    into the counter -- but per the orchestrator's re-review this still read
    as "sitting in the sink area" in the render (too close to the sink's
    right edge and the faucet at X[-92.71,-90.17], not clearly on solid,
    uncluttered counter). Fix: move both to the counter zone directly above
    B30/DB24 (X[-274.32,-137.16], per the task's own suggested zone),
    fully clear of the sink (X[-127.00,-55.88]) and the faucet.
      - Cutting board: lying flat on the counter above B30/DB24 (the task's
        own "or lying flat" alternative to leaning -- chosen over a pitched
        lean because spawn_or_update_prop's rest_on_z correction is derived
        from the mesh's un-rotated local-space bounds; a pitched prop's true
        world-space base moves with the tilt in a way that correction does
        not account for, so a first attempt at a ~12deg lean landed the
        board with its base ~2.5cm below the counter (Z=88.9 vs target
        91.44) and its tilted top edge clipping into the backsplash/wall
        plane. Lying flat, angled only in yaw for a casual look, avoids both
        problems while still satisfying the task's own alternative.
        X=-260 near the left part of the B30/DB24 zone, Y placed with a few
        cm of clearance off the backsplash face.
      - Bowl: nearby on the counter (fruit-bowl grouping), X=-170 (inside
        the B30/DB24 zone, not overlapping the board), lying flat.
    Both stay well clear of the sink, the faucet, and the window.
    """
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)

    # Cutting board: lying flat on the counter above B30/DB24 (clear of the
    # sink/faucet), angled slightly in yaw for a casual, not-perfectly-square
    # look, with a few cm of clearance off the backsplash face.
    board_mesh = mesh_paths.get("wooden_cutting_board", [])
    board_x = -260.0
    board_y = -12.0  # a few cm clear of the backsplash face (Y=-1.90) toward the room interior
    # Re-import hardening 2026-09-27, Task 4 (recorded for the next real run;
    # NOT executed this pass -- per the task's own "don't run it now" note,
    # this is dead code this pass since main() below is not invoked, but is
    # ready to run as-is next time import_wtk.py's pipeline calls this
    # script). Replaces the old flat 0.55 magic-number scale (which happened
    # to put the board's long axis at native ~450mm * 0.55 = ~24.75cm, not
    # tied to any explicit target) with a scale computed from the mesh's own
    # bounds so the board's long axis comes out to ~42cm, uniformly (all 3
    # axes scaled by the same factor -- no stretching/distortion, matching
    # the module's existing "keep rest-on-Z" convention since a uniform
    # scale doesn't change which local axis rest_on_z corrects against).
    board_scale = compute_uniform_scale_for_target_length(board_mesh, target_length_cm=42.0, default_scale=0.55)
    board = spawn_or_update_prop(
        "WTK_Prop_CuttingBoard",
        board_mesh,
        unreal.Vector(board_x, board_y, COUNTER_TOP_Z),
        unreal.Rotator(pitch=0.0, yaw=12.0, roll=0.0),  # flat, slight casual yaw angle
        scale=board_scale,  # ~42cm long axis, computed from mesh bounds (Task 4, 2026-09-27)
        rest_on_z=COUNTER_TOP_Z,
    )

    # Potted succulent: UPPER floating shelf, near its right third, fully
    # within the shelf's verified X/Y footprint. Phase 5e run-1 finding
    # (kept): potted_plant_04 imports as 4 separate StaticMeshes
    # (_ground/_dirt/_plant/_pot) whose individual pivots are not at the
    # assembly's visual base -- spawn_or_update_prop's rest_on_z correction
    # fixes this. This pass's fix is the X/Y target itself (see docstring
    # above): the old X=-60 was off the shelf entirely; the new X=-237.2 sits
    # inside the verified shelf bounds X[-304.80,-214.63] near its right
    # third, Y=-13 centred in the shelf's Y[-25.40,0.00] depth, base Z =
    # SHELF_UPPER_TOP_Z (191.77, the shelf actor's own verified max Z).
    plant_mesh = mesh_paths.get("potted_plant_04", [])
    plant_x = SHELF_UPPER_X_MIN + 0.75 * (SHELF_UPPER_X_MAX - SHELF_UPPER_X_MIN)  # right third of the shelf
    plant_y = (SHELF_UPPER_Y_MIN + SHELF_UPPER_Y_MAX) / 2.0
    plant = spawn_or_update_prop(
        "WTK_Prop_Plant",
        plant_mesh,
        unreal.Vector(plant_x, plant_y, SHELF_UPPER_TOP_Z),
        unreal.Rotator(pitch=0.0, yaw=-20.0, roll=0.0),
        scale=unreal.Vector(1.0, 1.0, 1.0),  # native ~170x186x268mm -- already a small, restrained accent scale
        rest_on_z=SHELF_UPPER_TOP_Z,
    )

    # Wooden bowl: on the counter near the cutting board (fruit-bowl feel),
    # same B30/DB24 counter zone, clear of the sink/faucet, not overlapping
    # the board.
    bowl_mesh = mesh_paths.get("wooden_bowl_01", [])
    bowl_x = -170.0
    bowl_y = -20.0
    # Re-import hardening 2026-09-27, Task 4 (recorded for the next real run;
    # not executed this pass -- see the cutting board's own comment above
    # for the full rationale). Replaces the old flat 0.35 magic-number scale
    # with one computed from the bowl mesh's own bounds so its horizontal
    # diameter comes out to ~22cm.
    bowl_scale = compute_uniform_scale_for_target_length(bowl_mesh, target_length_cm=22.0, default_scale=0.35)
    bowl = spawn_or_update_prop(
        "WTK_Prop_Bowl",
        bowl_mesh,
        unreal.Vector(bowl_x, bowl_y, COUNTER_TOP_Z),
        unreal.Rotator(pitch=0.0, yaw=0.0, roll=0.0),
        scale=bowl_scale,  # ~22cm diameter, computed from mesh bounds (Task 4, 2026-09-27)
        rest_on_z=COUNTER_TOP_Z,
    )

    # --- Bounds-vs-plane sanity check (per the task's own "nothing clipping" ask) ---
    expected_rest_z = {
        "WTK_Prop_CuttingBoard": COUNTER_TOP_Z,
        "WTK_Prop_Plant": SHELF_UPPER_TOP_Z,
        "WTK_Prop_Bowl": COUNTER_TOP_Z,
    }
    for label, actor in (("WTK_Prop_CuttingBoard", board), ("WTK_Prop_Plant", plant), ("WTK_Prop_Bowl", bowl)):
        if actor is None:
            continue
        # get_actor_bounds() only covers the actor's OWN components, not
        # attached child actors (multi-part props like the plant use
        # separate child StaticMeshActors -- see spawn_or_update_prop's
        # docstring for why). Union in every attached child's bounds too so
        # this check reports the assembly's real combined footprint, not
        # just the parent mesh's own (e.g. the plant's parent is the small
        # "_ground" mesh alone, which made the very first version of this
        # check wrongly flag a "float" that wasn't real -- verified by
        # comparing the parent-only bounds against a direct per-sub-mesh
        # local-bounds dump, tmp/Wtk5e_20260926/debug_plant_bounds.py).
        origin, extent = actor.get_actor_bounds(only_colliding_components=False)
        bmin = origin - extent
        bmax = origin + extent
        for child in actor.get_attached_actors():
            c_origin, c_extent = child.get_actor_bounds(only_colliding_components=False)
            c_bmin = c_origin - c_extent
            c_bmax = c_origin + c_extent
            bmin = unreal.Vector(min(bmin.x, c_bmin.x), min(bmin.y, c_bmin.y), min(bmin.z, c_bmin.z))
            bmax = unreal.Vector(max(bmax.x, c_bmax.x), max(bmax.y, c_bmax.y), max(bmax.z, c_bmax.z))
        log("%s bounds: min=(%.1f,%.1f,%.1f) max=(%.1f,%.1f,%.1f)" % (
            label, bmin.x, bmin.y, bmin.z, bmax.x, bmax.y, bmax.z))
        rest_z = expected_rest_z[label]
        # Resting check: base should sit within 0.2cm of the surface (no gap, no penetration).
        if abs(bmin.z - rest_z) > 0.2:
            log("WARNING: %s's base (%.2f) does not sit within 0.2cm of its intended resting "
                "surface (%.2f) -- possible float/gap/penetration, verify visually." % (
                    label, bmin.z, rest_z))
        # Backsplash check: the backsplash slab occupies Y[-1.90, 0.00] (its
        # front/room-facing face at Y=-1.90; see FX-04 bounds); the COUNTER's
        # own usable depth is the more-negative-Y side of that face. Only
        # applies to counter-top props (the cutting board, the bowl) -- the
        # shelf itself is mounted to the wall and its own verified Y-bounds
        # already extend to Y=0.00 (touching the wall plane above the
        # backsplash), so a shelf prop sitting anywhere within the shelf's
        # own footprint is correct by construction, not a backsplash clip.
        if label != "WTK_Prop_Plant" and bmax.y > BACKSPLASH_FACE_Y + 0.2:
            log("WARNING: %s's back edge (%.2f) may clip into the backsplash (face at Y=%.2f) -- verify visually." % (
                label, bmax.y, BACKSPLASH_FACE_Y))
        # Sink/faucet clearance: any counter-level prop (board, bowl) must
        # not overlap the sink cutout's X-range while also being on the
        # counter (both share the same Y-ish band); a simple X-overlap
        # check against the sink's verified X range is sufficient here since
        # both counter props are placed well to the left of it (X<-137) in
        # this pass.
        if label in ("WTK_Prop_CuttingBoard", "WTK_Prop_Bowl"):
            if bmax.x > SINK_X_MIN and bmin.x < SINK_X_MAX:
                log("WARNING: %s's X-range (%.1f..%.1f) overlaps the sink cutout "
                    "(X[%.1f,%.1f]) -- verify visually." % (
                        label, bmin.x, bmax.x, SINK_X_MIN, SINK_X_MAX))
        # Shelf-footprint check: the plant must sit fully within the upper
        # shelf's verified X/Y bounds.
        if label == "WTK_Prop_Plant":
            if not (SHELF_UPPER_X_MIN <= bmin.x and bmax.x <= SHELF_UPPER_X_MAX):
                log("WARNING: %s's X-range (%.1f..%.1f) is not fully within the shelf's "
                    "X-bounds ([%.1f,%.1f]) -- possible overhang, verify visually." % (
                        label, bmin.x, bmax.x, SHELF_UPPER_X_MIN, SHELF_UPPER_X_MAX))
            if not (SHELF_UPPER_Y_MIN - 0.2 <= bmin.y and bmax.y <= SHELF_UPPER_Y_MAX + 0.2):
                log("WARNING: %s's Y-range (%.1f..%.1f) is not fully within the shelf's "
                    "Y-bounds ([%.1f,%.1f]) -- possible overhang, verify visually." % (
                        label, bmin.y, bmax.y, SHELF_UPPER_Y_MIN, SHELF_UPPER_Y_MAX))

    # WTK prop-fix pass, round 2 (2026-09-26): robust save. The coordinator
    # found that save_current_level() alone silently no-op'd here -- the
    # .umap's own on-disk LastWriteTime never advanced across two placement
    # runs, and the subsequent renders showed the stale, pre-fix prop
    # positions, even though this function's own log clearly showed the new
    # transforms being applied in-memory. The modify()-before-mutate fix
    # above (see spawn_or_update_prop's own comment) addresses the root
    # cause (packages not being marked dirty), but the save call itself is
    # also hardened here as a second, independent line of defence:
    # explicitly mark the level package dirty, then save via BOTH
    # save_current_level() (kept, harmless) AND EditorLoadingAndSavingUtils
    # .save_map(world, map_path) (the more explicit, path-targeted API) plus
    # a final save_dirty_packages(True, True) sweep, so a persistence gap in
    # any one of these APIs doesn't silently drop the change again.
    # (A `unreal.Level.mark_package_dirty()` attempt was tried here and
    # removed -- `Level` has no such method in this UE 5.7 Python binding,
    # confirmed by AttributeError on the first run of this fixed script. Not
    # needed anyway: each actor's own actor.modify()/component.modify() call
    # in spawn_or_update_prop() above is what actually flags the level
    # package dirty, and save_map()'s own True return + the .umap's on-disk
    # LastWriteTime advancing (11:22:04 PM vs the pre-fix 10:58:46 PM) is the
    # real, verified confirmation that this works -- see Pipeline.md's
    # "prop-fix pass round 2" section for the full before/after.)
    # 2026-09-27: clearance nudge (backsplash gap >= 1 cm, bases on their
    # resting surfaces within 0.05 cm) -- the yawed 42 cm board's back corner
    # otherwise reaches past the backsplash face. See prop_clearance_wtk.py.
    try:
        import importlib.util
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prop_clearance_wtk.py")
        _spec = importlib.util.spec_from_file_location("prop_clearance_wtk", _p)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.main(load_level=False)
        log("Prop clearance pass completed.")
    except Exception as e:
        log("Prop clearance pass FAILED: %s" % e)

    world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    saved_ok =unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    log("save_map(%s) returned %s" % (MAP_PATH, saved_ok))
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("Props placed; save_current_level() + save_map() + save_dirty_packages() all called.")


def main():
    if not PLACE_PROPS:
        log("PLACE_PROPS is False -- props are disabled for this pass (removed per user "
            "feedback: 'take out the plant and the things on the countertop'). Exiting "
            "without importing or placing any prop actor. Set PLACE_PROPS=True above to "
            "re-enable; the import/placement code and the imported source assets are kept "
            "as-is for that purpose.")
        return
    mesh_paths = import_props()
    place_props(mesh_paths)
    log("WTK_PROPS_DONE")


main()

# This script is intended to run via -ExecutePythonScript (full editor, not
# the -run=pythonscript commandlet), per the import step's Slate requirement
# -- quit cleanly when done so the process terminates, matching import_wtk.py's
# own fallback-path convention.
try:
    import sys
    if "-run=pythonscript" not in " ".join(sys.argv):
        unreal.SystemLibrary.quit_editor()
except Exception:
    pass
