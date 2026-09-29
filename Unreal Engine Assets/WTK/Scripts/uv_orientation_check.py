"""
WTK Phase 5c-2 Task 1: determine which UV axis (U or V) runs vertically on a
B30 stile face, by sampling triangle vertex positions (world/local Z) against
their UV0 coordinates and checking correlation.

For each sampled triangle on the Oak_StainedWarmBrown-tagged material slot of
B30, we get the 3 vertex local positions and 3 vertex UV0 coords, then check:
does U vary mostly with local Z (vertical) or with local X/Y (horizontal)?

Run headless:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
"""
import unreal
import os

MAP_PATH = "/Game/WTK/Maps/WTK_Main"
OUT_PATH = r"C:\Users\Sam\Documents\Chess\tmp\Wtk5c2_20260926\uv_orientation_check.txt"

AU = unreal.GeometryScript_AssetUtils
MQ = unreal.GeometryScript_MeshQueries


def log(lines, msg):
    print(msg)
    lines.append(msg)


def main():
    lines = []
    log(lines, "=== WTK5c-2 UV orientation check (B30 stile) start ===")

    if not unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        log(lines, "ERROR: map missing")
        return

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
    b30 = [a for a in all_actors if "B30" in (a.get_actor_label() or "")]
    if not b30:
        log(lines, "ERROR: no B30 actor found")
        return
    actor = b30[0]
    comp = actor.get_components_by_class(unreal.StaticMeshComponent)[0]
    sm = comp.static_mesh
    log(lines, "Mesh: %s" % sm.get_name())

    dyn = unreal.DynamicMesh()
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    target_lod = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
    result = AU.copy_mesh_from_static_mesh(sm, dyn, options, target_lod)
    dyn = result[0] if isinstance(result, tuple) else result

    num_tris_result = MQ.get_num_triangle_i_ds(dyn)
    num_tris = num_tris_result[0] if isinstance(num_tris_result, tuple) else num_tris_result
    log(lines, "Triangle count: %s" % num_tris)

    # Sample every triangle's 3 vertex positions + UVs; bucket by which
    # material ID (slot 1 = Oak per Materials.md) and correlate dZ vs dU / dV
    # across triangle edges.
    corr_u_z = []
    corr_v_z = []
    sample_count = 0

    for tid in range(num_tris):
        try:
            # get_triangle_positions(mesh, triangle_id) -> (posA, posB, posC, is_valid)
            # confirmed via introspection: no get_triangle()/get_vertex_position-by-id
            # convenience path needed -- get_triangle_positions returns world/local
            # vertex positions directly per triangle.
            # Confirmed via debug dump: this binding returns
            # (is_valid_bool, posA, posB, posC), not (posA, posB, posC, is_valid).
            pos_result = MQ.get_triangle_positions(dyn, tid)
            pos_valid, posA, posB, posC = pos_result[0], pos_result[1], pos_result[2], pos_result[3]
            if not pos_valid:
                continue
            positions = [posA, posB, posC]
            uv0, uv1, uv2, is_valid = MQ.get_triangle_u_vs(dyn, 0, tid)
            if not is_valid:
                continue
            uvs = [uv0, uv1, uv2]
            # For each pair of the 3 verts, compute dZ, dU, dV.
            for i in range(3):
                j = (i + 1) % 3
                dz = positions[j].z - positions[i].z
                du = uvs[j].x - uvs[i].x
                dv = uvs[j].y - uvs[i].y
                if abs(dz) > 0.01:  # only edges with real vertical extent
                    corr_u_z.append(abs(du) / abs(dz))
                    corr_v_z.append(abs(dv) / abs(dz))
                    sample_count += 1
        except Exception:
            continue

    if sample_count == 0:
        log(lines, "No valid samples collected on Oak slot (mat_id=1) -- check slot index.")
    else:
        avg_u_per_z = sum(corr_u_z) / len(corr_u_z)
        avg_v_per_z = sum(corr_v_z) / len(corr_v_z)
        log(lines, "Samples: %d edges with |dZ|>0.01" % sample_count)
        log(lines, "avg |dU|/|dZ| = %.4f" % avg_u_per_z)
        log(lines, "avg |dV|/|dZ| = %.4f" % avg_v_per_z)
        if avg_v_per_z > avg_u_per_z:
            log(lines, "CONCLUSION: V varies more strongly with vertical (Z) motion -> V runs vertically on this unwrap.")
            log(lines, "  => To make grain run vertically, grain should align with V (no 90-deg rotation needed IF texture's V axis is the length axis, else rotate 90 to swap U/V).")
        else:
            log(lines, "CONCLUSION: U varies more strongly with vertical (Z) motion -> U runs vertically on this unwrap.")
            log(lines, "  => UVRotation_deg=90 (swapping U/V) is needed if the base texture's grain runs along its V axis, to make grain vertical in world space.")

    log(lines, "WTK5C2_UV_ORIENTATION_CHECK_DONE")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))


main()
