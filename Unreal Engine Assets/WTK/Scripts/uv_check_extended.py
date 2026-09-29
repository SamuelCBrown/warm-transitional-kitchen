"""
WTK Phase 5c-2 Task 1: UV extent check on additional meshes (wall, floor,
FX-01 counter, a painted cabinet, FX-04 backsplash), to confirm the same
real-unit-scale UV set 0 pattern found on B30/FX-05 in Phase 5c.

Reuses the same GeometryScript approach as uv_check_b30.py (copy_mesh_from_static_mesh
+ get_uv_set_bounding_box), applied to a small target list of actor-label substrings.

Run headless:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput

Writes findings to tmp/Wtk5c2_20260926/uv_check_extended.txt.
"""
import unreal
import os

MAP_PATH = "/Game/WTK/Maps/WTK_Main"
OUT_PATH = r"C:\Users\Sam\Documents\Chess\tmp\Wtk5c2_20260926\uv_check_extended.txt"

AU = unreal.GeometryScript_AssetUtils
MQ = unreal.GeometryScript_MeshQueries

# (search substring, friendly label, approx physical dimension for sanity check in cm)
TARGETS = [
    ("Wall", "wall", None),
    ("Floor", "floor", None),
    ("FX-01", "FX-01 counter", 91.44),
    ("DB18", "painted cabinet (DB18)", None),
    ("SB36", "painted cabinet (SB36)", None),
    ("FX-04", "FX-04 backsplash", None),
]


def log(lines, msg):
    print(msg)
    lines.append(msg)


def get_static_mesh_components(actor):
    return list(actor.get_components_by_class(unreal.StaticMeshComponent))


def get_actor_bounds_cm(actor):
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    size = extent * 2.0
    return size


def uv_check_mesh(static_mesh, lines, label):
    dyn = unreal.DynamicMesh()
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    target_lod = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
    try:
        result = AU.copy_mesh_from_static_mesh(static_mesh, dyn, options, target_lod)
        if isinstance(result, tuple):
            dyn, outcome = result[0], result[1]
        else:
            dyn, outcome = result, None
        log(lines, "  [%s] copy_mesh_from_static_mesh outcome: %s" % (label, outcome))
    except Exception as ex:
        log(lines, "  [%s] copy_mesh_from_static_mesh failed: %s" % (label, ex))
        return None

    uv0_bbox = None
    try:
        result = MQ.get_uv_set_bounding_box(dyn, 0)
        # Confirmed empirically: this binding returns (Box2D, is_valid_bool) --
        # a 2-tuple where element 0 is the FBox2D struct itself (with .min/.max
        # sub-fields), not (min_vec, max_vec) as might be assumed.
        box2d, is_valid = result[0], result[1]
        uv0_bbox = (box2d.min, box2d.max)
        log(lines, "  [%s] UV set 0 bounding box: min=%s max=%s is_valid=%s" % (label, box2d.min, box2d.max, is_valid))
    except Exception as ex:
        log(lines, "  [%s] UV set 0 bounding box query failed: %s" % (label, ex))

    try:
        num_uv_sets = MQ.get_num_uv_sets(dyn)
        log(lines, "  [%s] UV sets: %d" % (label, num_uv_sets))
    except Exception as ex:
        log(lines, "  [%s] get_num_uv_sets failed: %s" % (label, ex))

    return uv0_bbox


def main():
    lines = []
    log(lines, "=== WTK5c-2 UV extended check start ===")

    if not unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        log(lines, "ERROR: map %s does not exist -- run import_wtk.py first." % MAP_PATH)
        return

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()

    for substring, friendly, approx_dim in TARGETS:
        matches = [a for a in all_actors if substring in (a.get_actor_label() or "")]
        log(lines, "")
        log(lines, "--- Target: %s (%s) -- %d actor(s) found ---" % (friendly, substring, len(matches)))
        if not matches:
            log(lines, "  NO MATCHING ACTOR FOUND for substring '%s'" % substring)
            continue

        # Cap to first 2 matches to keep this bounded/quick.
        for actor in matches[:2]:
            label = actor.get_actor_label()
            size = get_actor_bounds_cm(actor)
            log(lines, "Actor: %s  physical bounds size (cm): (%.2f, %.2f, %.2f)" % (label, size.x, size.y, size.z))
            comps = get_static_mesh_components(actor)
            for comp in comps:
                sm = comp.static_mesh
                if sm is None:
                    continue
                mesh_name = sm.get_name()
                log(lines, " Mesh: %s" % mesh_name)
                uv0_bbox = uv_check_mesh(sm, lines, mesh_name)
                if uv0_bbox is not None:
                    umin, umax = uv0_bbox[0], uv0_bbox[1]
                    u_extent = umax.x - umin.x
                    v_extent = umax.y - umin.y
                    log(lines, "  [%s] UV0 extent: U=%.4f V=%.4f  (vs physical size cm: %.2f x %.2f x %.2f)"
                        % (mesh_name, u_extent, v_extent, size.x, size.y, size.z))

    log(lines, "")
    log(lines, "WTK5C2_UV_EXTENDED_CHECK_DONE")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))


main()
