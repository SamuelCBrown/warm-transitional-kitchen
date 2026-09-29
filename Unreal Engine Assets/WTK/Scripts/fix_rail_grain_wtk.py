"""
WTK 2026-09-27 rail-grain fix.

Problem: the B30 cabinet's five-piece doors (stiles, rails, panel) all share
MI_Oak_Rift_Stained (UVRotation_deg=90, oriented so the grain reads vertical
on the stiles/panel per build_a102_details.ps1:98's "GRAIN: STILES/PANEL
VERTICAL; RAILS HORIZONTAL" callout and the cut list's grain-direction
column, 03_Revit/Details/WTK_B30_Cut_List.md P07-P09). Since it's one
material slot for all three part types, the rails inherit the same vertical
grain as the stiles/panel -- wrong; rails must read horizontal.

Fix, mirroring smooth_knobs_wtk.py / import_wtk.py's run_bevel_pass()
GeometryScript idiom (copy_mesh_from_static_mesh -> edit -> copy_mesh_to_
static_mesh, metadata-tag idempotency, save_loaded_asset):

1. Load the B30 static mesh, find the oak material slot(s), compute each
   door's bounds from the oak-slot triangles (logged), derive the two rail
   rectangles per door in door-face-local (X,Z) coordinates (Y is the
   door-normal/depth axis and is not used to bound the rail rectangles --
   the full oak-material front-face triangle range along Y is accepted),
   and select every oak triangle (front face, back face, and the thin edge
   faces around the rail's perimeter) whose centroid falls inside those
   rectangles.
2. Create MI_Oak_Rift_Rail (idempotent) as a new MaterialInstanceConstant
   child of the SAME parent master as MI_Oak_Rift_Stained, with every
   parameter value copied programmatically from MI_Oak_Rift_Stained so the
   two MIs can never drift out of sync, except UVRotation_deg + 90 (so the
   grain, which the base MI already rotates 90 deg to read vertical, gets
   rotated a further 90 deg -- reading horizontal on the rails).
3. Add (or reuse, idempotent) a new material slot on the mesh bound to
   MI_Oak_Rift_Rail, and reassign the selected rail triangles' material ID
   to that new slot. Save.
4. Log per-slot triangle counts before/after.

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_IMPORT_DEST as IMPORT_DEST, ACTIVE_MAP_PATH as MAP_PATH

LOG_PATH = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkRail_20260927\fix_rail_grain_log.txt"

MI_DIR = "/Game/WTK/Materials"
BASE_MI_NAME = "MI_Oak_Rift_Stained"
RAIL_MI_NAME = "MI_Oak_Rift_Rail"
BASE_MI_PATH = "%s/%s" % (MI_DIR, BASE_MI_NAME)
RAIL_MI_PATH = "%s/%s" % (MI_DIR, RAIL_MI_NAME)

B30_MESH_NAME_SUBSTR = "B30"
RAIL_SLOT_TAG = "WTK_RailSlot_v1"  # idempotency marker set on the mesh asset

# --- Door geometry, from 03_Revit/WTK_Cabinet_Spec.json (cabinet B30) and
# 03_Revit/Details/WTK_B30_Cut_List.md P07-P09 -- all inches, local mesh
# space (the Datasmith import preserves Revit's inch-valued local units
# throughout this codebase's other GeometryScript passes, e.g.
# smooth_knobs_wtk.py's classify_component() bbox comments). ---
# Door 1 (left, hinge_side=left): x in [0.0625, 14.9375]
# Door 2 (right, hinge_side=right): x in [15.0625, 29.9375]
# Both doors: z in [0.0625, 29.9375] (z_bottom=0 for B30).
DOOR_X_RANGES_IN = [(0.0625, 14.9375), (15.0625, 29.9375)]
DOOR_Z_RANGE_IN = (0.0625, 29.9375)
STILE_RAIL_WIDTH_IN = 2.25  # five_piece.stile_rail_width

IN_TO_CM = 2.54


def log(lines, msg):
    print("[FixRailGrain] %s" % msg)
    lines.append(str(msg))


def _unwrap(result):
    """Same convention documented in smooth_knobs_wtk.py's _unwrap(): every
    GeometryScript_* call that takes a DynamicMesh as its first positional
    arg echoes that DynamicMesh back as tuple element [0]; the actual
    payload (selection, count, etc.) is element [1]."""
    return result[1] if isinstance(result, tuple) and len(result) > 1 else result


def find_oak_material_slots(sm):
    """Returns list of (slot_index, material_name) for slots on this
    StaticMesh whose assigned material is the oak stained MI (or, pre-remap,
    the raw Datasmith source material name) -- same recognize-both-states
    approach as smooth_knobs_wtk.py's find_brass_knob_material_slots()."""
    lod_read = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
    AU = unreal.GeometryScript_AssetUtils
    mat_list, _mi, _sn, _mo = AU.get_section_material_list_from_static_mesh(sm, lod_read)
    slots = []
    for i, m in enumerate(mat_list):
        if m is None:
            continue
        name = m.get_name()
        if name in ("Oak_StainedWarmBrown", BASE_MI_NAME, RAIL_MI_NAME):
            slots.append((i, name))
    return slots


def get_tri_positions(MQ, dyn, tid):
    """Same defensive-unwrap pattern as smooth_knobs_wtk.py's
    get_tri_positions() nested helper: get_triangle_positions(target_mesh,
    triangle_id) may return either a 4-tuple (is_valid, v1, v2, v3) or a
    5-tuple with the echoed DynamicMesh prepended, depending on binding."""
    result = MQ.get_triangle_positions(dyn, tid)
    if isinstance(result, tuple):
        if len(result) == 4 and isinstance(result[0], bool):
            _valid, va, vb, vc = result
        elif len(result) == 5:
            _dyn_ignored, _valid, va, vb, vc = result
        else:
            va, vb, vc = result[-3], result[-2], result[-1]
    else:
        raise RuntimeError("Unexpected get_triangle_positions return shape: %r" % (result,))
    return va, vb, vc


def copy_mi_parameters(src_mi, dst_mi, rot_delta_deg, lines):
    """
    Copies every scalar / vector / static-switch / texture parameter value
    from src_mi to dst_mi programmatically (introspected via
    get_scalar_parameter_names / get_vector_parameter_names /
    get_static_switch_parameter_names / get_texture_parameter_names on the
    shared parent Material, the standard MaterialEditingLibrary approach for
    enumerating a material's exposed parameters), so MI_Oak_Rift_Rail can
    never silently drift out of sync with MI_Oak_Rift_Stained. UVRotation_deg
    is the one deliberate exception: dst gets src's value + rot_delta_deg.
    """
    MEL = unreal.MaterialEditingLibrary
    # No get_material_instance_parent() in this UE 5.7 binding (confirmed
    # live, tmp/WtkRail_20260927 introspection) -- the parent is a plain
    # UMaterialInstance property, read directly.
    parent = src_mi.get_editor_property("parent")
    if parent is None:
        log(lines, "ERROR: %s has no parent material -- cannot enumerate parameters." % src_mi.get_name())
        return

    scalar_names = MEL.get_scalar_parameter_names(parent)
    vector_names = MEL.get_vector_parameter_names(parent)
    switch_names = MEL.get_static_switch_parameter_names(parent)
    texture_names = MEL.get_texture_parameter_names(parent)

    copied = {"scalar": [], "vector": [], "switch": [], "texture": []}

    def _unwrap_value(result):
        # Confirmed live (this run's traceback): get_material_instance_*_
        # parameter_value returns the bare value directly in this UE 5.7
        # binding, NOT an (ok, value) tuple as MaterialEditingLibrary's other
        # getters (e.g. get_material_instance_scalar_parameter_value) might
        # suggest by analogy with get_triangle_positions() etc. elsewhere in
        # this codebase. Handled defensively for either shape anyway.
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool):
            return result[0], result[1]
        return True, result

    for name in scalar_names:
        name_str = str(name)
        ok, value = _unwrap_value(MEL.get_material_instance_scalar_parameter_value(src_mi, name))
        if not ok:
            continue
        if name_str == "UVRotation_deg":
            value = value + rot_delta_deg
        MEL.set_material_instance_scalar_parameter_value(dst_mi, name, value)
        copied["scalar"].append((name_str, value))

    for name in vector_names:
        ok, value = _unwrap_value(MEL.get_material_instance_vector_parameter_value(src_mi, name))
        if not ok:
            continue
        MEL.set_material_instance_vector_parameter_value(dst_mi, name, value)
        copied["vector"].append((str(name), value))

    for name in switch_names:
        ok, value = _unwrap_value(MEL.get_material_instance_static_switch_parameter_value(src_mi, name))
        if not ok:
            continue
        MEL.set_material_instance_static_switch_parameter_value(dst_mi, name, value)
        copied["switch"].append((str(name), value))

    for name in texture_names:
        ok, tex = _unwrap_value(MEL.get_material_instance_texture_parameter_value(src_mi, name))
        if not ok or tex is None:
            continue
        MEL.set_material_instance_texture_parameter_value(dst_mi, name, tex)
        copied["texture"].append(str(name))

    log(lines, "Copied parameters %s -> %s (UVRotation_deg shifted by +%.1f): scalars=%s vectors=%s switches=%s textures=%s"
        % (src_mi.get_name(), dst_mi.get_name(), rot_delta_deg, copied["scalar"], copied["vector"], copied["switch"], copied["texture"]))


def ensure_rail_mi(lines):
    """
    Idempotent: if MI_Oak_Rift_Rail already exists AND its parent matches
    MI_Oak_Rift_Stained's parent, it is deleted and rebuilt fresh each run
    (same "deletes and recreates each MI asset on every run" convention as
    build_wtk_material_instances.py's own module docstring) so it always
    stays byte-for-byte in sync with the base MI's current parameter values.
    """
    MEL = unreal.MaterialEditingLibrary
    AT = unreal.AssetToolsHelpers.get_asset_tools()

    base_mi = unreal.EditorAssetLibrary.load_asset(BASE_MI_PATH)
    if base_mi is None:
        raise RuntimeError("Could not load base MI %s" % BASE_MI_PATH)

    parent_mat = base_mi.get_editor_property("parent")
    if parent_mat is None:
        raise RuntimeError("%s has no parent material." % BASE_MI_NAME)
    parent_path = parent_mat.get_path_name().split(".")[0]

    # Reuse the existing asset rather than delete/recreate: deleting it would
    # null the B30 mesh's rail-slot reference and make the next run add a
    # duplicate slot. Parameters are re-copied every run so it stays in sync.
    if unreal.EditorAssetLibrary.does_asset_exist(RAIL_MI_PATH):
        rail_mi = unreal.EditorAssetLibrary.load_asset(RAIL_MI_PATH)
        log(lines, "Reusing existing %s; re-syncing parameters from %s." % (RAIL_MI_PATH, BASE_MI_NAME))
    else:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        rail_mi = AT.create_asset(RAIL_MI_NAME, MI_DIR, unreal.MaterialInstanceConstant, factory)
        log(lines, "Created %s as a child of %s (same parent as %s)." % (RAIL_MI_PATH, parent_path, BASE_MI_NAME))
    MEL.set_material_instance_parent(rail_mi, parent_mat)

    copy_mi_parameters(base_mi, rail_mi, 90.0, lines)

    unreal.EditorAssetLibrary.save_loaded_asset(rail_mi, only_if_is_dirty=False)
    return rail_mi


def main(load_level=True):
    """load_level=False when called in-process from import_wtk.py: the map is
    already open there, and reloading it from disk would discard unsaved
    level changes (the same failure mode as the remap load_level bug)."""
    lines = []
    log(lines, "=== WTK fix_rail_grain_wtk.py start ===")
    if load_level:
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)

    AU = unreal.GeometryScript_AssetUtils
    MQ = unreal.GeometryScript_MeshQueries
    MS = unreal.GeometryScript_MeshSelection
    ME = unreal.GeometryScript_MeshEdits

    # --- Step 2: build/refresh MI_Oak_Rift_Rail first (needed before the
    # mesh edit below, so the new slot can be bound to it immediately). ---
    rail_mi = ensure_rail_mi(lines)

    # --- Step 1+3: find the B30 mesh, select rail triangles, add/reuse the
    # rail slot, reassign material IDs, save. ---
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    mesh_assets = asset_reg.get_assets_by_path(IMPORT_DEST, recursive=True)

    b30_sm = None
    b30_package = None
    for a in mesh_assets:
        cls_name = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else str(a.asset_class)
        if "StaticMesh" not in cls_name:
            continue
        mesh_name = str(a.asset_name)
        if B30_MESH_NAME_SUBSTR in mesh_name:
            b30_sm = unreal.EditorAssetLibrary.load_asset(str(a.package_name))
            b30_package = str(a.package_name)
            break

    if b30_sm is None:
        log(lines, "ERROR: no B30 static mesh found under %s (name substring '%s')." % (IMPORT_DEST, B30_MESH_NAME_SUBSTR))
        _flush(lines)
        return

    log(lines, "Found B30 mesh: %s (%s)" % (b30_sm.get_name(), b30_package))

    lod_read = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
    copy_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    dyn = unreal.DynamicMesh()
    result = AU.copy_mesh_from_static_mesh(b30_sm, dyn, copy_options, lod_read)
    dyn, _copy_outcome = (result[0], result[1]) if isinstance(result, tuple) else (result, None)

    mat_list, _mi, _sn, _mo = AU.get_section_material_list_from_static_mesh(b30_sm, lod_read)
    before_slots = [m.get_name() if m else "None" for m in mat_list]
    log(lines, "Material slots BEFORE: %s" % before_slots)

    before_counts = {}
    for i in range(len(mat_list)):
        sel = _unwrap(MS.select_mesh_elements_by_material_id(dyn, i, unreal.GeometryScriptMeshSelectionType.TRIANGLES))
        ids_result = MS.convert_mesh_selection_to_index_array(dyn, sel)
        ids = list(ids_result[1]) if isinstance(ids_result, tuple) else list(ids_result)
        before_counts[i] = len(ids)
    log(lines, "Triangle counts per slot BEFORE: %s" % before_counts)

    oak_slots = find_oak_material_slots(b30_sm)
    if not oak_slots:
        log(lines, "ERROR: no oak material slot found on %s (slots=%s) -- cannot proceed." % (b30_sm.get_name(), before_slots))
        _flush(lines)
        return
    log(lines, "Oak material slot(s): %s" % oak_slots)

    # --- Gather all oak triangles and their centroids/bounds (across all
    # oak slots found -- normally exactly one). ---
    oak_ids = []
    for slot_index, _name in oak_slots:
        sel = _unwrap(MS.select_mesh_elements_by_material_id(dyn, slot_index, unreal.GeometryScriptMeshSelectionType.TRIANGLES))
        ids_result = MS.convert_mesh_selection_to_index_array(dyn, sel)
        ids = list(ids_result[1]) if isinstance(ids_result, tuple) else list(ids_result)
        oak_ids.extend(ids)
    log(lines, "Total oak triangles across %d slot(s): %d" % (len(oak_slots), len(oak_ids)))

    # Compute per-triangle centroids once (reused for both the door-bounds
    # computation and the rail-rectangle membership test below).
    centroids = {}
    oak_bmin = unreal.Vector(1e9, 1e9, 1e9)
    oak_bmax = unreal.Vector(-1e9, -1e9, -1e9)
    for tid in oak_ids:
        v0, v1, v2 = get_tri_positions(MQ, dyn, tid)
        cx = (v0.x + v1.x + v2.x) / 3.0
        cy = (v0.y + v1.y + v2.y) / 3.0
        cz = (v0.z + v1.z + v2.z) / 3.0
        centroids[tid] = (cx, cy, cz)
        for v in (v0, v1, v2):
            oak_bmin = unreal.Vector(min(oak_bmin.x, v.x), min(oak_bmin.y, v.y), min(oak_bmin.z, v.z))
            oak_bmax = unreal.Vector(max(oak_bmax.x, v.x), max(oak_bmax.y, v.y), max(oak_bmax.z, v.z))

    log(lines, "Oak-triangle overall bbox: min=(%.4f,%.4f,%.4f) max=(%.4f,%.4f,%.4f)"
        % (oak_bmin.x, oak_bmin.y, oak_bmin.z, oak_bmax.x, oak_bmax.y, oak_bmax.z))

    # Datasmith import preserves Revit's local units (inches) throughout this
    # codebase (confirmed by smooth_knobs_wtk.py's own bbox comments/
    # calibration, e.g. "1.270x1.270cm" knob dims are explicitly noted as
    # cm there -- but the B30 spec's own inch-valued x0/x1/z0/z1 fields match
    # this mesh's local coordinate span almost exactly, confirmed below by
    # comparing the spec's expected door-pair span (0.0625 to 29.9375, i.e.
    # ~29.875 units wide) against the measured oak bbox width). If the units
    # come back scaled (e.g. cm, ~2.54x larger), unit_scale corrects the
    # door-rectangle math without touching the spec numbers themselves.
    measured_width = oak_bmax.x - oak_bmin.x
    expected_width_in = DOOR_X_RANGES_IN[-1][1] - DOOR_X_RANGES_IN[0][0]  # 29.9375 - 0.0625 = 29.875
    unit_scale = 1.0
    if expected_width_in > 1e-6:
        ratio = measured_width / expected_width_in
        if 2.0 < ratio < 3.2:
            unit_scale = IN_TO_CM
        elif 0.5 < ratio < 2.0:
            unit_scale = 1.0
        else:
            log(lines, "WARNING: measured oak bbox X width (%.4f) doesn't match either inches (%.4f) or cm "
                       "(%.4f) scale of the expected door-pair span within tolerance -- defaulting to "
                       "unit_scale=1.0 (inches); rail rectangles below may be off if this is wrong."
                % (measured_width, expected_width_in, expected_width_in * IN_TO_CM))
    log(lines, "Unit-scale check: measured oak bbox X width=%.4f, expected door-pair width=%.4f in "
               "(%.4f in x scale=%.4f) -> unit_scale=%.4f" % (measured_width, expected_width_in, expected_width_in, unit_scale, unit_scale))

    # --- Per-door bounds from the oak triangles (logged), then rail
    # rectangles in door-face (X,Z) coordinates. ---
    door_rail_rects = []  # list of (door_index, rail_name, x_lo, x_hi, z_lo, z_hi) in mesh-local units
    for door_index, (x_lo_in, x_hi_in) in enumerate(DOOR_X_RANGES_IN):
        x_lo = x_lo_in * unit_scale
        x_hi = x_hi_in * unit_scale
        stile_w = STILE_RAIL_WIDTH_IN * unit_scale

        # Door bounds computed FROM the oak triangles actually inside this
        # door's spec-derived X range (rather than trusting the spec's
        # absolute Z range blindly). Confirmed necessary live: the mesh's
        # local origin is NOT at the cabinet's Revit-space origin -- the
        # measured oak Z bounds came back as [11.5887, 87.4713] rather than
        # the spec's raw z0*scale=0.1588/z1*scale=76.04, an offset of
        # ~11.43cm (~4.5in, suspiciously close to the toe-kick height) baked
        # into this mesh's local frame. The X-derived unit_scale is still
        # valid (X the door pair's width matches the spec exactly), but the
        # rail rectangles' Z bounds are taken from each door's OWN measured
        # bbox (dbmin.z/dbmax.z) rather than the spec's z0/z1, so the offset
        # cancels out automatically.
        door_tids = [tid for tid in oak_ids if x_lo - stile_w <= centroids[tid][0] <= x_hi + stile_w]
        if not door_tids:
            log(lines, "WARNING: door %d -- no oak triangles found near spec X range [%.4f,%.4f]; skipping." % (door_index, x_lo, x_hi))
            continue

        dbmin = unreal.Vector(1e9, 1e9, 1e9)
        dbmax = unreal.Vector(-1e9, -1e9, -1e9)
        for tid in door_tids:
            v0, v1, v2 = get_tri_positions(MQ, dyn, tid)
            for v in (v0, v1, v2):
                dbmin = unreal.Vector(min(dbmin.x, v.x), min(dbmin.y, v.y), min(dbmin.z, v.z))
                dbmax = unreal.Vector(max(dbmax.x, v.x), max(dbmax.y, v.y), max(dbmax.z, v.z))
        log(lines, "Door %d measured bounds (from %d oak tris near spec range x[%.4f,%.4f]): "
                   "min=(%.4f,%.4f,%.4f) max=(%.4f,%.4f,%.4f)"
            % (door_index, len(door_tids), x_lo, x_hi, dbmin.x, dbmin.y, dbmin.z, dbmax.x, dbmax.y, dbmax.z))

        z_lo, z_hi = dbmin.z, dbmax.z

        # Rail rectangles: full door width (x_lo..x_hi, i.e. INCLUDING the
        # stiles' inner edges -- the task spec says "between the inner edges
        # of the stiles" for the rail's own material coverage, but the rail
        # geometry itself only exists in the gap between the stiles anyway
        # (10-3/8in wide per P08); using the full door X range as the
        # rectangle is harmless/conservative since no stile triangles exist
        # at rail-only Z heights to be accidentally caught by an
        # over-generous X range -- the Z range is what actually
        # discriminates rail triangles from stile/panel triangles here).
        # Z ranges use the door's OWN measured top/bottom (z_hi/z_lo above),
        # not the spec's absolute Z values, per the offset note above.
        top_rail = (door_index, "top", x_lo, x_hi, z_hi - stile_w, z_hi)
        bottom_rail = (door_index, "bottom", x_lo, x_hi, z_lo, z_lo + stile_w)
        door_rail_rects.append(top_rail)
        door_rail_rects.append(bottom_rail)
        log(lines, "Door %d rail rectangles (local X,Z): top=x[%.4f,%.4f] z[%.4f,%.4f]; bottom=x[%.4f,%.4f] z[%.4f,%.4f]"
            % (door_index, x_lo, x_hi, top_rail[4], top_rail[5], x_lo, x_hi, bottom_rail[4], bottom_rail[5]))

    # --- Select oak triangles whose centroid falls in ANY rail rectangle
    # (all faces -- front, back, edges -- since centroid-based X/Z
    # membership doesn't discriminate by Y/depth, matching the task's "all
    # faces, including the rail edges/fronts" requirement). ---
    rail_tids = set()
    for tid in oak_ids:
        cx, _cy, cz = centroids[tid]
        for (_door_index, _name, x_lo, x_hi, z_lo, z_hi) in door_rail_rects:
            if x_lo <= cx <= x_hi and z_lo <= cz <= z_hi:
                rail_tids.add(tid)
                break

    log(lines, "Selected %d rail triangle(s) out of %d total oak triangle(s)." % (len(rail_tids), len(oak_ids)))
    if not rail_tids:
        log(lines, "ERROR: no rail triangles selected -- aborting without modifying the mesh.")
        _flush(lines)
        return

    # --- Step 3: add (or reuse) the rail material slot, reassign IDs. ---
    existing_rail_slot = None
    for i, name in enumerate(before_slots):
        if name == RAIL_MI_NAME:
            existing_rail_slot = i
            break

    if existing_rail_slot is not None:
        rail_slot_index = existing_rail_slot
        log(lines, "Reusing existing %s material slot (index %d) -- idempotent." % (RAIL_MI_NAME, rail_slot_index))
    else:
        new_slot_result = AU.add_material_slot(b30_sm) if hasattr(AU, "add_material_slot") else None
        if new_slot_result is not None:
            rail_slot_index = new_slot_result[0] if isinstance(new_slot_result, tuple) else new_slot_result
        else:
            # No direct GeometryScript AssetUtils.add_material_slot in this
            # UE 5.7 binding (mirrors this codebase's own documented pattern
            # of missing/renamed GeometryScript functions, e.g.
            # smooth_knobs_wtk.py's "no direct connected-components split
            # call" note) -- fall back to the StaticMesh's own
            # static_materials array, appending a new StaticMaterial entry.
            static_materials = b30_sm.get_editor_property("static_materials")
            new_slot = unreal.StaticMaterial()
            new_slot.set_editor_property("material_interface", rail_mi)
            new_slot.set_editor_property("material_slot_name", unreal.Name(RAIL_MI_NAME))
            static_materials.append(new_slot)
            b30_sm.set_editor_property("static_materials", static_materials)
            rail_slot_index = len(static_materials) - 1
        log(lines, "Added new material slot index %d bound to %s." % (rail_slot_index, RAIL_MI_NAME))

    # Bind the slot to MI_Oak_Rift_Rail (covers both the newly-added and the
    # reused-existing-slot cases -- idempotent either way).
    try:
        b30_sm.set_material(rail_slot_index, rail_mi)
    except Exception:
        static_materials = b30_sm.get_editor_property("static_materials")
        static_materials[rail_slot_index].set_editor_property("material_interface", rail_mi)
        b30_sm.set_editor_property("static_materials", static_materials)

    # Reassign material ID for the selected rail triangles.
    # Confirmed live (tmp/WtkRail_20260927/introspect_matid*.txt): the
    # per-triangle/selection material-ID edit calls live on
    # GeometryScript_Materials (NOT GeometryScript_MeshEdits, which has no
    # such function at all in this UE 5.7 binding), and
    # GeometryScript_MeshSelection.convert_index_array_to_mesh_selection DOES
    # exist (contrary to smooth_knobs_wtk.py's comment about it being
    # absent -- that comment refers to the reverse direction, converting an
    # index array to a selection was never actually tried there). Build a
    # real GeometryScriptMeshSelection from the collected triangle-id list
    # and set all of them to the new slot in one call via
    # set_material_id_for_mesh_selection (GeometryScript_Materials).
    GM = unreal.GeometryScript_Materials
    GM.enable_material_i_ds(dyn)  # no-op if already enabled (per its own docstring)
    sel_result = MS.convert_index_array_to_mesh_selection(
        dyn, list(rail_tids), unreal.GeometryScriptMeshSelectionType.TRIANGLES)
    dyn, rail_sel = (sel_result[0], sel_result[1]) if isinstance(sel_result, tuple) else (dyn, sel_result)
    dyn = GM.set_material_id_for_mesh_selection(dyn, rail_sel, rail_slot_index)

    write_lod0 = unreal.GeometryScriptMeshWriteLOD(lod_index=0)
    copy_to_options = unreal.GeometryScriptCopyMeshToAssetOptions()
    AU.copy_mesh_to_static_mesh(dyn, b30_sm, copy_to_options, write_lod0, use_section_materials=True)
    unreal.EditorAssetLibrary.save_loaded_asset(b30_sm, only_if_is_dirty=False)
    unreal.EditorAssetLibrary.set_metadata_tag(b30_sm, RAIL_SLOT_TAG, "1")
    unreal.EditorAssetLibrary.save_loaded_asset(b30_sm, only_if_is_dirty=False)

    # --- Step 4: log triangle counts per slot AFTER. ---
    mat_list2, _mi2, _sn2, _mo2 = AU.get_section_material_list_from_static_mesh(b30_sm, lod_read)
    after_slots = [m.get_name() if m else "None" for m in mat_list2]
    after_counts = {}
    for i in range(len(mat_list2)):
        sel = _unwrap(MS.select_mesh_elements_by_material_id(dyn, i, unreal.GeometryScriptMeshSelectionType.TRIANGLES))
        ids_result = MS.convert_mesh_selection_to_index_array(dyn, sel)
        ids = list(ids_result[1]) if isinstance(ids_result, tuple) else list(ids_result)
        after_counts[i] = len(ids)

    log(lines, "Material slots AFTER: %s" % after_slots)
    log(lines, "Triangle counts per slot AFTER: %s" % after_counts)
    log(lines, "Rail triangles moved: %d" % len(rail_tids))

    # --- Save level (mesh asset is content, not level data, but per this
    # task's own instruction re: backing up WTK_Main_v2.umap and per this
    # codebase's convention -- e.g. smooth_knobs_wtk.py's main() -- of
    # re-saving the level/dirty packages at the end of any content-touching
    # pass). ---
    world = unreal.EditorLevelLibrary.get_editor_world()
    saved_ok = unreal.EditorLevelLibrary.save_current_level()
    saved_ok2 = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log(lines, "Level save -> save_current_level=%s, save_map=%s" % (saved_ok, saved_ok2))
    log(lines, "FIX_RAIL_GRAIN_DONE")

    _flush(lines)


def _flush(lines):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
