"""
WTK Phase 5c step 4: UV check on the B30 casework mesh(es) in WTK_Main.

Loads the level, finds actors whose label contains "B30" (Datasmith/Revit
casework naming, matching import_wtk.py's CASEWORK_ID_KEYS convention), reads
each StaticMeshComponent's static mesh, copies it into a GeometryScript
DynamicMesh, and queries UV bounds (whole-mesh via
GeometryScript_MeshQueries.get_uv_set_bounding_box, and a per-material-slot
breakdown via get_section_material_list_from_static_mesh cross-referenced
against per-triangle material IDs) to report whether the Datasmith/Revit UVs
are sane (scaled in real units, consistent orientation).

Run headless:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput

Writes findings to tmp/Wtk5c_20260926/uv_check_b30.txt.
"""
import unreal
import os

MAP_PATH = "/Game/WTK/Maps/WTK_Main"
OUT_PATH = r"C:\Users\Sam\Documents\Chess\tmp\Wtk5c_20260926\uv_check_b30.txt"

AU = unreal.GeometryScript_AssetUtils
MQ = unreal.GeometryScript_MeshQueries


def log(lines, msg):
    print(msg)
    lines.append(msg)


def get_static_mesh_components(actor):
    return list(actor.get_components_by_class(unreal.StaticMeshComponent))


def uv_check_mesh(static_mesh, lines, label):
    dyn = unreal.DynamicMesh()
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    target_lod = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
    try:
        result = AU.copy_mesh_from_static_mesh(static_mesh, dyn, options, target_lod)
        # copy_mesh_from_static_mesh returns (DynamicMesh, EGeometryScriptOutcomePins)
        # as a tuple in this Python binding (out-params come back as a tuple,
        # not as an object to construct beforehand) -- confirmed empirically
        # after unreal.GeometryScriptOutcomePins() raised "Cannot create
        # instances of enum types".
        if isinstance(result, tuple):
            dyn, outcome = result[0], result[1]
        else:
            dyn, outcome = result, None
        log(lines, "  [%s] copy_mesh_from_static_mesh outcome: %s" % (label, outcome))
    except Exception as ex:
        log(lines, "  [%s] copy_mesh_from_static_mesh failed: %s" % (label, ex))
        return

    try:
        num_uv_sets = MQ.get_num_uv_sets(dyn)
    except Exception as ex:
        log(lines, "  [%s] get_num_uv_sets failed: %s" % (label, ex))
        num_uv_sets = 0
    log(lines, "  [%s] UV sets: %d" % (label, num_uv_sets))

    for uv_set in range(max(num_uv_sets, 1)):
        try:
            bbox = MQ.get_uv_set_bounding_box(dyn, uv_set)
            log(lines, "  [%s] UV set %d bounding box: min=%s max=%s" % (label, uv_set, bbox[0], bbox[1]))
        except Exception as ex:
            log(lines, "  [%s] UV set %d bounding box query failed: %s" % (label, uv_set, ex))

    try:
        islands_result = MQ.get_num_uv_islands(dyn, 0)
        num_islands = islands_result[0] if isinstance(islands_result, tuple) else islands_result
        log(lines, "  [%s] UV set 0 island count: %s" % (label, num_islands))
    except Exception as ex:
        log(lines, "  [%s] get_num_uv_islands failed: %s" % (label, ex))

    try:
        has_mat_ids = MQ.get_has_material_i_ds(dyn)
        log(lines, "  [%s] Has per-triangle MaterialIDs: %s" % (label, has_mat_ids))
    except Exception as ex:
        log(lines, "  [%s] get_has_material_i_ds failed: %s" % (label, ex))

    # Per-material-slot breakdown: report the material list on the source
    # asset (slot names), which is the mapping the remap script keys off of.
    try:
        lod0 = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
        mat_list, material_index, slot_names, mat_outcome = AU.get_section_material_list_from_static_mesh(static_mesh, lod0)
        log(lines, "  [%s] Material slots (LOD0 sections): %s" % (label, [m.get_name() if m else "None" for m in mat_list]))
        log(lines, "  [%s] Material indices per section: %s" % (label, list(material_index)))
        log(lines, "  [%s] Slot names: %s" % (label, list(slot_names)))
    except Exception as ex:
        log(lines, "  [%s] get_section_material_list_from_static_mesh failed: %s" % (label, ex))

    # Sample raw triangle UVs across a spread of triangles to sanity-check
    # scale (are UVs in a plausible 0-~10 tile range, or wildly large/degenerate?).
    try:
        num_tris_result = MQ.get_num_triangle_i_ds(dyn)
        num_tris = num_tris_result[0] if isinstance(num_tris_result, tuple) else num_tris_result
        log(lines, "  [%s] Triangle count: %s" % (label, num_tris))
        # For a dense, non-edited DynamicMesh (fresh copy from a StaticMesh,
        # no deletions), triangle IDs are contiguous 0..num_tris-1, so sample
        # by ID directly rather than via get_all_triangle_i_ds (which returns
        # a mesh-bound array type, not a plain Python sequence, in this
        # binding -- confirmed empirically: "object of type 'DynamicMesh' has
        # no len()").
        sample_stride = max(1, num_tris // 20)
        u_vals, v_vals = [], []
        for tid in range(0, num_tris, sample_stride):
            try:
                uv0, uv1, uv2, is_valid = MQ.get_triangle_u_vs(dyn, 0, tid)
                if is_valid:
                    for uv in (uv0, uv1, uv2):
                        u_vals.append(uv.x)
                        v_vals.append(uv.y)
            except Exception:
                continue
        if u_vals:
            log(
                lines,
                "  [%s] Sampled %d triangle-corners: U[%.4f, %.4f]  V[%.4f, %.4f]"
                % (label, len(u_vals), min(u_vals), max(u_vals), min(v_vals), max(v_vals)),
            )
        else:
            log(lines, "  [%s] No UV samples collected from get_triangle_u_vs." % label)
    except Exception as ex:
        log(lines, "  [%s] Triangle UV sampling failed: %s" % (label, ex))


def main():
    lines = []
    log(lines, "=== WTK5c UV check (B30) start ===")

    if not unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        log(lines, "ERROR: map %s does not exist -- run import_wtk.py first." % MAP_PATH)
        return

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()

    b30_actors = [a for a in all_actors if "B30" in (a.get_actor_label() or "")]
    log(lines, "Found %d B30 actor(s): %s" % (len(b30_actors), [a.get_actor_label() for a in b30_actors]))

    # Also check an FX-05 shelf actor if present, per the task's shelf UV question.
    fx05_actors = [a for a in all_actors if "FX-05" in (a.get_actor_label() or "")]
    log(lines, "Found %d FX-05 (shelf) actor(s): %s" % (len(fx05_actors), [a.get_actor_label() for a in fx05_actors]))

    for actor in b30_actors + fx05_actors:
        label = actor.get_actor_label()
        comps = get_static_mesh_components(actor)
        log(lines, "Actor: %s (%d StaticMeshComponent(s))" % (label, len(comps)))
        for comp in comps:
            sm = comp.static_mesh
            if sm is None:
                log(lines, "  (component has no static mesh)")
                continue
            mesh_name = sm.get_name()
            log(lines, " Mesh: %s" % mesh_name)
            uv_check_mesh(sm, lines, mesh_name)

    log(lines, "WTK5C_UV_CHECK_DONE")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))


main()
