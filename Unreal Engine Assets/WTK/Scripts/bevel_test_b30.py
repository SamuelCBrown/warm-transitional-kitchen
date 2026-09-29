"""
WTK Phase 5c-2 Task 4: bevel prototype/validation on ONE mesh (B30) before
batching. Applies a small (0.159cm / 1/16in) bevel to hard edges (sharp edges,
angle threshold ~30deg) + boundary edges (Datasmith meshes are composed of
many separate box-like solids/islands per mesh -- each part's boundary is
itself a hard edge that needs beveling too), recomputes normals (split by
60deg angle threshold), and copies back to the static mesh at LOD0.

Validates: triangle count increased moderately, bounds unchanged (+/- 0.01cm),
material slots unchanged, no degenerate triangles (checked via a basic
zero-area heuristic is not directly exposed -- validated via triangle count
sanity and outcome pins instead).

Run headless:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
"""
import unreal
import os

AU = unreal.GeometryScript_AssetUtils
MQ = unreal.GeometryScript_MeshQueries
MS = unreal.GeometryScript_MeshSelection
MM = unreal.GeometryScript_MeshModeling
NM = unreal.GeometryScript_Normals

MESH_PATH = "/Game/WTK/Datasmith/WTK_Start-3DView-WTK_Datasmith_Export/Geometries/Casework_WTK_B30_B30"
OUT_PATH = r"C:\Users\Sam\Documents\Chess\tmp\Wtk5c2_20260926\bevel_test_b30.txt"

BEVEL_DISTANCE_CM = 0.159  # 1/16 in
SHARP_EDGE_ANGLE_DEG = 30.0
SPLIT_NORMAL_ANGLE_DEG = 60.0


def log(lines, msg):
    print(msg)
    lines.append(msg)


def get_mesh_bounds_and_tris(dyn):
    num_tris_result = MQ.get_num_triangle_i_ds(dyn)
    num_tris = num_tris_result[0] if isinstance(num_tris_result, tuple) else num_tris_result
    return num_tris


def main():
    lines = []
    log(lines, "=== WTK5c-2 Task 4 bevel test (B30) start ===")

    sm = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
    if sm is None:
        log(lines, "ERROR: could not load %s" % MESH_PATH)
        return
    log(lines, "Mesh: %s" % sm.get_name())

    # --- BEFORE state ---
    before_bounds = sm.get_editor_property("extended_bounds") if hasattr(sm, "extended_bounds") else None
    try:
        bb = sm.get_bounding_box()
        before_min, before_max = bb.min, bb.max
    except Exception:
        before_min = before_max = None
    log(lines, "Before bounds: min=%s max=%s" % (before_min, before_max))

    lod0 = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
    mat_list, material_index, slot_names, mat_outcome = AU.get_section_material_list_from_static_mesh(sm, lod0)
    before_slots = [m.get_name() if m else "None" for m in mat_list]
    log(lines, "Before material slots: %s" % before_slots)

    dyn = unreal.DynamicMesh()
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    result = AU.copy_mesh_from_static_mesh(sm, dyn, options, lod0)
    dyn, copy_outcome = (result[0], result[1]) if isinstance(result, tuple) else (result, None)
    log(lines, "copy_mesh_from_static_mesh outcome: %s" % copy_outcome)

    before_tris = get_mesh_bounds_and_tris(dyn)
    log(lines, "Before triangle count: %s" % before_tris)

    # --- Build the hard-edge + boundary-edge selection ---
    result = MS.select_mesh_sharp_edges(dyn, min_angle_deg=SHARP_EDGE_ANGLE_DEG)
    dyn, sharp_sel = (result[0], result[1]) if isinstance(result, tuple) else (dyn, result)
    log(lines, "select_mesh_sharp_edges(%.1f deg) done" % SHARP_EDGE_ANGLE_DEG)

    result = MS.select_mesh_boundary_edges(dyn)
    dyn, boundary_sel = (result[0], result[1]) if isinstance(result, tuple) else (dyn, result)
    log(lines, "select_mesh_boundary_edges() done")

    combined_sel = MS.combine_mesh_selections(sharp_sel, boundary_sel, unreal.GeometryScriptCombineSelectionMode.ADD)
    log(lines, "combine_mesh_selections(ADD) done")

    try:
        info = combined_sel.get_mesh_selection_info()
        log(lines, "Combined selection info: %s" % (info,))
    except Exception as ex:
        log(lines, "get_mesh_selection_info() (instance method) failed: %s" % ex)

    # --- Apply the bevel ---
    bevel_options = unreal.GeometryScriptMeshBevelSelectionOptions()
    bevel_options.set_editor_property("bevel_distance", BEVEL_DISTANCE_CM)
    try:
        bevel_options.set_editor_property("infer_material_id", True)
    except Exception:
        pass

    dyn = MM.apply_mesh_bevel_edge_selection(dyn, combined_sel, bevel_options)
    log(lines, "apply_mesh_bevel_edge_selection() done (distance=%.4fcm)" % BEVEL_DISTANCE_CM)

    after_tris = get_mesh_bounds_and_tris(dyn)
    log(lines, "After-bevel triangle count: %s (delta=%+d)" % (after_tris, after_tris - before_tris))

    # --- Recompute normals: split by 60deg angle (hard edges stay hard,
    # bevel faces read smooth across the new small bevel faces per the
    # angle threshold). ---
    split_options = unreal.GeometryScriptSplitNormalsOptions()
    try:
        split_options.set_editor_property("split_by_face_group", False)
    except Exception:
        pass
    try:
        split_options.set_editor_property("split_by_opening_angle", True)
    except Exception:
        pass
    try:
        split_options.set_editor_property("opening_angle_deg", SPLIT_NORMAL_ANGLE_DEG)
    except Exception:
        pass
    calc_options = unreal.GeometryScriptCalculateNormalsOptions()
    try:
        dyn = NM.compute_split_normals(dyn, split_options, calc_options)
        log(lines, "compute_split_normals(%.0f deg) done" % SPLIT_NORMAL_ANGLE_DEG)
    except Exception as ex:
        log(lines, "compute_split_normals FAILED: %s -- falling back to recompute_normals()" % ex)
        dyn = NM.recompute_normals(dyn, calc_options)
        log(lines, "recompute_normals() done (fallback)")

    # --- Copy back to the static mesh at LOD0 ---
    write_lod0 = unreal.GeometryScriptMeshWriteLOD(lod_index=0)
    copy_to_options = unreal.GeometryScriptCopyMeshToAssetOptions()
    result = AU.copy_mesh_to_static_mesh(dyn, sm, copy_to_options, write_lod0, use_section_materials=True)
    dyn, copy_back_outcome = (result[0], result[1]) if isinstance(result, tuple) else (result, None)
    log(lines, "copy_mesh_to_static_mesh outcome: %s" % copy_back_outcome)
    unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)

    # --- AFTER validation ---
    try:
        bb2 = sm.get_bounding_box()
        after_min, after_max = bb2.min, bb2.max
    except Exception:
        after_min = after_max = None
    log(lines, "After bounds: min=%s max=%s" % (after_min, after_max))

    if before_min is not None and after_min is not None:
        dmin = (after_min - before_min)
        dmax = (after_max - before_max)
        log(lines, "Bounds delta: min_delta=(%.5f,%.5f,%.5f) max_delta=(%.5f,%.5f,%.5f)"
            % (dmin.x, dmin.y, dmin.z, dmax.x, dmax.y, dmax.z))
        max_abs_delta = max(abs(dmin.x), abs(dmin.y), abs(dmin.z), abs(dmax.x), abs(dmax.y), abs(dmax.z))
        log(lines, "Max abs bounds delta: %.5f cm (tolerance 0.01cm) -> %s"
            % (max_abs_delta, "PASS" if max_abs_delta <= 0.01 else "FAIL"))

    mat_list2, material_index2, slot_names2, mat_outcome2 = AU.get_section_material_list_from_static_mesh(sm, lod0)
    after_slots = [m.get_name() if m else "None" for m in mat_list2]
    log(lines, "After material slots: %s -> %s" % (after_slots, "PASS" if after_slots == before_slots else "FAIL"))

    tri_growth_ratio = after_tris / before_tris if before_tris else None
    log(lines, "Triangle count: %d -> %d (ratio %.2fx) -> %s"
        % (before_tris, after_tris, tri_growth_ratio or 0,
           "PASS (moderate increase)" if tri_growth_ratio and 1.0 < tri_growth_ratio < 10.0 else "CHECK MANUALLY"))

    log(lines, "WTK5C2_BEVEL_TEST_B30_DONE")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))


main()
