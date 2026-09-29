"""
WTK 2026-09-27 knob-smoothing pass.

Revit tessellated the round brass knobs into coarse ~6-8 sided polyhedra,
baked as brass-material triangles directly into each cabinet's static mesh
alongside the bar pulls (bar pulls look acceptable and must NOT be touched).

This script:
  1. For each Datasmith_v2 static mesh with a brass material slot, selects the
     brass-material triangles (GeometryScript_MeshSelection.
     select_mesh_elements_by_material_id) and splits them into connected
     components (there is no direct "split into components" GeometryScript
     call in this UE 5.7 binding -- confirmed via live introspection,
     tmp/WtkKnobs_20260927/geoscript_introspect.txt/geoscript_sigs.txt -- so
     components are extracted by seeding a single-triangle selection per
     unvisited brass triangle and flood-filling via
     expand_mesh_selection_to_connected(), intersecting back against the
     brass-only selection each time).
  2. Classifies each component as knob (bbox roughly 3.2x3.2cm across the
     face, ~2.2cm deep) or pull (elongated), logging every component (mesh
     name, bbox, classification) to LOG_PATH.
  3. Deletes ONLY the knob triangles (never pull triangles) via
     GeometryScript_MeshEdits.delete_selected_triangles_from_mesh.
  4. Builds one smooth knob static mesh (/Game/WTK/Props/SM_WTK_Knob_Smooth)
     via GeometryScript_Primitives.append_revolve_polygon: stem
     Ø1.27cm x 1.27cm with a small fillet, then cap Ø3.175cm x 0.95cm with a
     ~0.3cm rounded edge, >=48 revolve steps, smooth normals, brass MI
     assigned, Nanite enabled.
  5. Spawns one actor per deleted knob component (WTK_Knob_<cabinet>_<n>),
     oriented along the door-face normal (assumed +/-Y door-face normal per
     this project's coordinate convention -- door fronts face +Y per
     03_Revit/WTK_Cabinet_Spec.json's coordinate_convention), base flush to
     the door face at the original component's centroid location. Idempotent:
     deletes existing WTK_Knob_* actors and respawns fresh each run.

IMPORTANT (per the task spec): since Datasmith reimport re-bakes the old
tessellated knob geometry from Revit every time, this script's mesh-editing
steps (1-3) are NOT durable across a reimport by themselves -- this is
explicitly documented, not assumed to "just survive". See the
"REIMPORT_DURABILITY" note below and Docs/Pipeline.md's updated step list.

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
"""
import unreal
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_IMPORT_DEST as IMPORT_DEST, ACTIVE_MAP_PATH as MAP_PATH

LOG_PATH = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkKnobs_20260927\smooth_knobs_log.txt"
KNOB_MESH_PATH = "/Game/WTK/Props/SM_WTK_Knob_Smooth"
BRASS_KNOB_MI_PATH = "/Game/WTK/Materials/MI_Brass_Knob_Radial"  # cross-referenced from remap_materials_wtk.py RULES table: (r"Knob", "Metal_SatinBrass", ".../MI_Brass_Knob_Radial")
BRASS_SATIN_MI_PATH = "/Game/WTK/Materials/MI_Brass_Satin"  # pulls -- NEVER touched by this script

# --- Classification thresholds (task spec, CALIBRATED against live data) ---
# Live component dump (tmp/WtkKnobs_20260927/smooth_knobs_log.txt, first
# real run against the actual imported casework) showed each Revit knob is
# baked as TWO separate connected-component islands sharing the same brass
# material slot, not one:
#   - a small "base/collar" component: face 1.270x1.270cm, depth 1.270cm
#     (a coarse stem/attachment stub), e.g. Casework_WTK_W30_W30
#     bbox_min=(33.496,30.480,2.381) bbox_max=(34.766,31.750,3.651)
#   - a larger "cap" component: face 3.175x3.175cm, depth 0.952-0.953cm --
#     matching WTK_Cabinet_Spec.json's knob_diameter_in=1.25in=3.175cm
#     almost exactly -- e.g. bbox_min=(32.544,31.750,1.429)
#     bbox_max=(35.719,32.702,4.604).
# Both are square-faced (aspect~1.00) and clearly distinct from the
# elongated bar-pull components (face_b up to 13.97cm, aspect 2.67-14.67,
# confirmed on DB18/DB24/B12 -- pulls correctly classified as PULL below and
# never touched). The task's "3.2x3.2cm face, ~2.2cm deep" description reads
# as the two knob sub-components' combined stack height (1.270 + 0.952 ~=
# 2.2cm) rather than a single island's depth -- adjusted here to classify
# EITHER sub-component as "knob" individually (both are square-faced,
# clearly non-elongated, and clearly distinguishable from pulls purely by
# aspect ratio), since both must be deleted together as part of the same
# physical knob anyway (grouped below by spatial proximity before spawning
# one smooth-knob actor per group).
KNOB_FACE_MIN_CM, KNOB_FACE_MAX_CM = 1.0, 3.9
KNOB_DEPTH_MIN_CM, KNOB_DEPTH_MAX_CM = 0.7, 3.2
KNOB_ASPECT_MAX = 1.6  # face-plane aspect ratio (long/short) must be near-square for a knob; pulls measured at 2.67-14.67, a wide safety margin below that

# --- New smooth knob geometry spec (task spec, exact) ---
STEM_DIAMETER_CM = 0.5 * 2.54  # 0.5in
STEM_PROJECTION_CM = 0.5 * 2.54  # 0.5in
CAP_DIAMETER_CM = 1.25 * 2.54  # 1.25in
CAP_HEIGHT_CM = 0.375 * 2.54  # 0.375in
TOTAL_PROJECTION_CM = 0.875 * 2.54  # 0.875in from the door face
REVOLVE_STEPS = 48
FILLET_RADIUS_CM = 0.15  # small stem fillet
CAP_EDGE_ROUND_CM = 0.3  # ~0.3cm rounded cap edge


def log(lines, msg):
    print("[SmoothKnobs] %s" % msg)
    lines.append(str(msg))


def _unwrap(result):
    """
    Every GeometryScript_* function that takes a DynamicMesh as its first
    positional arg returns that (possibly-mutated) DynamicMesh as element 0
    of its result tuple, with the function's own "documented" return value(s)
    following after -- confirmed live (tmp/WtkKnobs_20260927/geoscript_sigs.txt,
    e.g. select_mesh_elements_by_material_id's actual call signature/doc:
    "-> (DynamicMesh, selection=GeometryScriptMeshSelection)"). So the
    SELECTION (or other real payload) is element [1], not [0] -- [0] is just
    the echoed-back mesh. This was the root cause of an early bug in this
    script (crashed every mesh with "Cannot nativize 'DynamicMesh' as
    'Selection'" because _unwrap was returning the DynamicMesh itself where a
    selection was expected).
    """
    return result[1] if isinstance(result, tuple) and len(result) > 1 else result


def find_brass_knob_material_slots(sm):
    """
    Returns list of (slot_index, material_name) for slots on this StaticMesh
    whose assigned material is the brass knob MI (or, pre-remap, the raw
    Datasmith "Metal_SatinBrass" source material) -- cross-referenced against
    remap_materials_wtk.py's RULES table so this script recognizes brass
    whether or not the remap pass has already run this session.
    """
    lod_read = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
    AU = unreal.GeometryScript_AssetUtils
    mat_list, _mi, _sn, _mo = AU.get_section_material_list_from_static_mesh(sm, lod_read)
    slots = []
    for i, m in enumerate(mat_list):
        if m is None:
            continue
        name = m.get_name()
        if name in ("Metal_SatinBrass", "MI_Brass_Knob_Radial", "MI_Brass_Satin"):
            slots.append((i, name))
    return slots


def classify_component(bmin, bmax):
    """
    Returns ("knob"|"pull"|"unclassified", dims_dict). dims computed in the
    mesh's LOCAL space (cm, matching the rest of this codebase's convention
    of working directly in Datasmith-imported local units).
    """
    dx = bmax.x - bmin.x
    dy = bmax.y - bmin.y
    dz = bmax.z - bmin.z
    dims = sorted([dx, dy, dz])
    depth = dims[0]  # smallest dimension = the door-normal-aligned depth
    face_a, face_b = dims[1], dims[2]
    aspect = face_b / face_a if face_a > 1e-6 else 999.0

    is_knob = (
        KNOB_FACE_MIN_CM <= face_a <= KNOB_FACE_MAX_CM
        and KNOB_FACE_MIN_CM <= face_b <= KNOB_FACE_MAX_CM
        and KNOB_DEPTH_MIN_CM <= depth <= KNOB_DEPTH_MAX_CM
        and aspect <= KNOB_ASPECT_MAX
    )
    classification = "unclassified"
    if is_knob:
        classification = "knob"
    elif aspect > KNOB_ASPECT_MAX or face_b > KNOB_FACE_MAX_CM:
        classification = "pull"

    return classification, {"dx": dx, "dy": dy, "dz": dz, "depth": depth, "face_a": face_a, "face_b": face_b, "aspect": aspect}


def find_brass_components(dyn, material_id, lines, mesh_name):
    """
    Splits the mesh's triangles with the given material_id into connected
    components. No direct "connected components split" GeometryScript call
    exists in this UE 5.7 binding (confirmed via live introspection) --
    implemented by seeding a single-triangle selection per unvisited brass
    triangle and flood-filling with expand_mesh_selection_to_connected(),
    intersected back against the brass-only triangle set each time (so the
    flood fill can't leak into a differently-materialed adjacent island).
    Returns a list of (selection, triangle_id_list, bbox_min, bbox_max).
    """
    MS = unreal.GeometryScript_MeshSelection
    MQ = unreal.GeometryScript_MeshQueries

    brass_sel = _unwrap(MS.select_mesh_elements_by_material_id(dyn, material_id, unreal.GeometryScriptMeshSelectionType.TRIANGLES))
    brass_ids_result = MS.convert_mesh_selection_to_index_array(dyn, brass_sel)
    brass_ids = list(_unwrap(brass_ids_result)) if not isinstance(brass_ids_result, tuple) else list(brass_ids_result[1])
    log(lines, "Mesh %s material_id=%d: %d brass triangle(s) selected." % (mesh_name, material_id, len(brass_ids)))

    def to_index_array(sel):
        """
        convert_mesh_selection_to_index_array(target_mesh, selection) ->
        (DynamicMesh, index_array, selection_type) -- confirmed via live
        introspection (tmp/WtkKnobs_20260927/geoscript_sigs.txt). Returns a
        plain list of triangle ids.
        """
        result = MS.convert_mesh_selection_to_index_array(dyn, sel)
        return list(result[1])

    def get_tri_positions(tid):
        """
        get_triangle_positions(target_mesh, triangle_id) -> (DynamicMesh,
        is_valid_triangle, vertex1, vertex2, vertex3) once the leading
        DynamicMesh return is included -- confirmed via live introspection
        (tmp/WtkKnobs_20260927/sig2.txt): the documented return tuple is
        (is_valid_triangle, vertex1, vertex2, vertex3), and this binding's
        convention (seen consistently elsewhere in this codebase's
        import_wtk.py, e.g. copy_mesh_from_static_mesh) is that the mutated
        DynamicMesh is ALSO returned as element 0 ahead of the documented
        tuple when the function takes target_mesh as its first arg. Handled
        defensively for either shape.
        """
        result = MQ.get_triangle_positions(dyn, tid)
        if isinstance(result, tuple):
            if len(result) == 4 and isinstance(result[0], bool):
                _valid, va, vb, vc = result
            elif len(result) == 5:
                _dyn_ignored, _valid, va, vb, vc = result
            else:
                # Fallback: assume last 3 tuple elements are the vertices.
                va, vb, vc = result[-3], result[-2], result[-1]
        else:
            raise RuntimeError("Unexpected get_triangle_positions return shape: %r" % (result,))
        return va, vb, vc

    unvisited = set(brass_ids)
    components = []
    while unvisited:
        seed_tri = next(iter(unvisited))
        v0, v1, v2 = get_tri_positions(seed_tri)
        centroid = unreal.Vector((v0.x + v1.x + v2.x) / 3.0, (v0.y + v1.y + v2.y) / 3.0, (v0.z + v1.z + v2.z) / 3.0)

        # Seed a tiny selection around this single triangle's centroid (a
        # sphere radius small enough it can't reach a neighbouring separate
        # solid on any real hardware part, but large enough to reliably catch
        # the seed triangle itself despite float precision).
        seed_sel = _unwrap(MS.select_mesh_elements_in_sphere(
            dyn, sphere_origin=centroid, sphere_radius=0.05,
            selection_type=unreal.GeometryScriptMeshSelectionType.TRIANGLES, min_num_triangle_points=1))

        seed_ids = to_index_array(seed_sel)
        if not seed_ids:
            # Sphere missed (shouldn't happen at r=0.05cm centered exactly on
            # the triangle's own centroid) -- drop this triangle from the
            # unvisited set to guarantee loop termination and move on; it
            # will simply not be grouped into any component (logged as a
            # gap via the total-vs-processed count check below).
            unvisited.discard(seed_tri)
            continue

        # Flood-fill to the full connected geometric region, iterating to a
        # fixed point (repeat until the selected triangle count stops
        # growing).
        cur_sel = seed_sel
        prev_count = -1
        for _ in range(500):  # hard cap, avoids any pathological infinite loop
            ids = to_index_array(cur_sel)
            if len(ids) == prev_count:
                break
            prev_count = len(ids)
            cur_sel = _unwrap(MS.expand_mesh_selection_to_connected(dyn, cur_sel, unreal.GeometryScriptTopologyConnectionType.GEOMETRIC))

        # Restrict the geometric flood-fill selection back down to
        # brass-material triangles only (the geometric flood-fill can cross
        # material boundaries if two different-material solids touch/share
        # vertices) via an explicit selection INTERSECTION against the
        # brass-only selection, rather than a plain-set intersection --
        # keeps a valid GeometryScriptMeshSelection object around for the
        # eventual deletion call (there is no
        # convert_index_array_to_mesh_selection in this binding, confirmed
        # absent live, so the selection object itself -- not just its index
        # list -- must be carried forward).
        component_sel = MS.combine_mesh_selections(cur_sel, brass_sel, unreal.GeometryScriptCombineSelectionMode.INTERSECTION)
        component_ids = set(to_index_array(component_sel)) & set(brass_ids)

        if not component_ids:
            unvisited.discard(seed_tri)
            continue

        # Compute bbox of this component from its triangle vertex positions.
        bmin = unreal.Vector(1e9, 1e9, 1e9)
        bmax = unreal.Vector(-1e9, -1e9, -1e9)
        for tid in component_ids:
            tv0, tv1, tv2 = get_tri_positions(tid)
            for v in (tv0, tv1, tv2):
                bmin = unreal.Vector(min(bmin.x, v.x), min(bmin.y, v.y), min(bmin.z, v.z))
                bmax = unreal.Vector(max(bmax.x, v.x), max(bmax.y, v.y), max(bmax.z, v.z))

        components.append((component_sel, component_ids, bmin, bmax))

        unvisited -= component_ids

    return components


def build_smooth_knob_mesh(lines):
    """
    Builds /Game/WTK/Props/SM_WTK_Knob_Smooth: two stacked, fully-capped
    GeometryScript cylinder primitives (stem + cap) plus a shallow flattened
    dome on the front face, split normals (smooth sides, crisp cap edges via
    a 60-degree opening-angle threshold), cylindrical UVs, brass MI assigned,
    Nanite enabled. Idempotent: overwrites/rebuilds the asset each run
    (matches this codebase's own documented convention for
    build_wtk_material_instances.py -- "deletes and recreates each asset on
    every run").
    """
    AU = unreal.GeometryScript_AssetUtils
    PR = unreal.GeometryScript_Primitives
    NM = unreal.GeometryScript_Normals
    MS = unreal.GeometryScript_MeshSelection
    MQ = unreal.GeometryScript_MeshQueries

    dyn = unreal.DynamicMesh()
    primitive_options = unreal.GeometryScriptPrimitiveOptions()

    stem_r = STEM_DIAMETER_CM / 2.0
    cap_r = CAP_DIAMETER_CM / 2.0
    stem_h = STEM_PROJECTION_CM
    cap_h = CAP_HEIGHT_CM
    fillet_r = min(FILLET_RADIUS_CM, stem_r * 0.6)
    round_r = min(CAP_EDGE_ROUND_CM, cap_h * 0.5, (cap_r - stem_r) * 0.6 if cap_r > stem_r else CAP_EDGE_ROUND_CM)

    # ROOT-CAUSE HISTORY (2026-09-27): two earlier approaches in this
    # function both produced a "donut" knob (dark hollow center) in
    # WTK_Test_CAM_Detail_0000.png:
    #   1. An open-tube revolve + two separate append_disc() end caps --
    #      the discs were topologically DISCONNECTED from the tube even
    #      when positioned coincident, leaving 96 real boundary edges that
    #      weld_mesh_edges could not close at any tolerance (confirmed live,
    #      tmp/WtkRoof_20260927/debug_weld.txt).
    #   2. A single append_revolve_polygon() with a small-but-nonzero-radius
    #      profile at both ends -- this WAS watertight (0 boundary edges,
    #      tmp/WtkRoof_20260927/tubeonly_normals.txt) but its own
    #      auto-generated end-cap fan triangulation wound the top cap
    #      backwards (confirmed live: all 288 top-cap triangles facing -Z
    #      instead of +Z).
    # Per the coordinator's direction, REPLACED ENTIRELY with GeometryScript
    # PRIMITIVES (append_cylinder x2, capped=True), which are purpose-built
    # closed/capped solids and don't have either failure mode: no manual
    # end-cap inference, no separate disconnected disc pieces to weld.
    #
    # Orientation/pivot, matched to what the spawn code in main() expects
    # (unchanged from before): local +Z is the knob's projection axis (the
    # spawn code aligns local Z to the door-face world normal via
    # make_rot_from_z()), and the mesh origin (0,0,0) is the BASE, flush
    # with the door face (the spawn code positions actors at the deleted
    # knob component's door-face centroid, i.e. the base location) --
    # append_cylinder's origin=BASE places the cylinder's base exactly at
    # the transform origin and extends it along +Z by `height`, matching
    # this convention exactly with no change needed to the spawn code.
    stem_height = STEM_PROJECTION_CM
    cap_height = CAP_HEIGHT_CM

    stem_transform = unreal.Transform()
    stem_transform.translation = unreal.Vector(0, 0, 0)
    dyn = PR.append_cylinder(
        dyn, primitive_options, stem_transform,
        radius=stem_r, height=stem_height, radial_steps=REVOLVE_STEPS, height_steps=0,
        capped=True, origin=unreal.GeometryScriptPrimitiveOriginMode.BASE,
    )

    cap_transform = unreal.Transform()
    cap_transform.translation = unreal.Vector(0, 0, stem_height)
    dyn = PR.append_cylinder(
        dyn, primitive_options, cap_transform,
        radius=cap_r, height=cap_height, radial_steps=REVOLVE_STEPS, height_steps=0,
        capped=True, origin=unreal.GeometryScriptPrimitiveOriginMode.BASE,
    )

    # Optional shallow dome on the front (outward-facing) face: a
    # sphere-lat-long primitive flattened along the axis direction (Z scaled
    # down relative to X/Y) so it reads as a gentle rounded bulge rather than
    # a hemisphere, overlapping the cap's top face so it welds into one
    # solid rather than floating disconnected above it.
    dome_flatten_z = 0.35  # squashes the sphere to ~35% height along the axis
    dome_overlap = cap_r * 0.15  # sink the dome slightly into the cap face so there's no seam gap
    dome_transform = unreal.Transform()
    dome_transform.scale3d = unreal.Vector(1.0, 1.0, dome_flatten_z)
    dome_transform.translation = unreal.Vector(0, 0, stem_height + cap_height - dome_overlap)
    dyn = PR.append_sphere_lat_long(
        dyn, primitive_options, dome_transform,
        radius=cap_r, steps_phi=12, steps_theta=REVOLVE_STEPS,
        origin=unreal.GeometryScriptPrimitiveOriginMode.BASE,
    )

    # Split normals: smooth around the sides (round knob silhouette) but a
    # crisp/hard edge at the stem/cap and cap/dome junctions, via an opening
    # angle threshold -- faces meeting at less than ~60 degrees stay smooth
    # (the cylinders' own rounded sides plus the shallow dome blend), faces
    # meeting at a sharper angle (the flat cap-top/cylinder-side edge, before
    # the dome overlap smooths it further) get a hard split. This replaces
    # the earlier plain recompute_normals() call with the coordinator's
    # requested split-normals pass.
    split_options = unreal.GeometryScriptSplitNormalsOptions()
    split_options.set_editor_property("split_by_opening_angle", True)
    split_options.set_editor_property("opening_angle_deg", 60.0)
    calc_options = unreal.GeometryScriptCalculateNormalsOptions()
    dyn = NM.compute_split_normals(dyn, split_options, calc_options)

    # UV generation: cylindrical projection aligned to the same local-Z axis
    # as the geometry itself, giving clean continuous UVs around the
    # circumference and up the height (avoids the degenerate-UV-at-the-pole
    # issue a revolve's auto end caps could produce).
    UV = unreal.GeometryScript_UVs
    all_sel = unreal.GeometryScriptMeshSelection()
    cyl_transform = unreal.Transform()
    dyn = UV.set_mesh_u_vs_from_cylinder_projection(dyn, 0, cyl_transform, all_sel, split_angle=45.0)

    # Verify: 0 open boundary edges, as required.
    MS_LOCAL = unreal.GeometryScript_MeshSelection
    bsel_result = MS_LOCAL.select_mesh_boundary_edges(dyn)
    dyn_b, bsel = (bsel_result[0], bsel_result[1]) if isinstance(bsel_result, tuple) else (dyn, bsel_result)
    boundary_info = MS_LOCAL.get_mesh_unique_selection_info(dyn_b, bsel)
    log(lines, "Post-build boundary-edge check: %s (expect 0 open edges for a closed solid)" % (boundary_info,))
    bbox_result = MQ.get_mesh_bounding_box(dyn)
    bbox = bbox_result[0] if isinstance(bbox_result, tuple) else bbox_result
    log(lines, "Knob mesh bounds: min=(%.4f,%.4f,%.4f) max=(%.4f,%.4f,%.4f) (base at origin, projecting +Z)"
        % (bbox.min.x, bbox.min.y, bbox.min.z, bbox.max.x, bbox.max.y, bbox.max.z))

    # Save as a new StaticMesh asset. This UE 5.7 GeometryScript Python
    # binding has NO direct "create new StaticMesh asset from DynamicMesh"
    # function (confirmed absent via live introspection --
    # tmp/WtkKnobs_20260927/create_mesh_fn.txt/factory.txt/factory2.txt/
    # factory4.txt -- no create_new_static_mesh_asset_from_mesh,  no exposed
    # UStaticMeshFactory, and unreal.Factory() itself is abstract and can't
    # be instantiated from Python). Confirmed-working alternative (tested
    # standalone, tmp/WtkKnobs_20260927/try_create4.txt): duplicate an
    # existing trivial engine StaticMesh asset (/Engine/BasicShapes/Cube) as
    # a template via EditorAssetLibrary.duplicate_asset(), save it once to
    # register it in the asset registry, then overwrite ITS geometry via
    # copy_mesh_to_static_mesh -- the same underlying write call already
    # proven throughout this codebase's own bevel/ceiling-flip/nanite passes.
    pkg_path = KNOB_MESH_PATH
    if unreal.EditorAssetLibrary.does_asset_exist(pkg_path):
        unreal.EditorAssetLibrary.delete_asset(pkg_path)

    template_path = "/Engine/BasicShapes/Cube.Cube"
    sm = unreal.EditorAssetLibrary.duplicate_asset(template_path, pkg_path)
    if sm is None:
        log(lines, "ERROR: duplicate_asset(%s -> %s) returned None" % (template_path, pkg_path))
        return None
    unreal.EditorAssetLibrary.save_asset(pkg_path, only_if_is_dirty=False)
    sm = unreal.EditorAssetLibrary.load_asset(pkg_path)  # reload post-save, matching the confirmed-working standalone test

    # Overwrite the duplicated template's geometry with the revolved knob
    # DynamicMesh (confirmed-working pattern, tmp/WtkKnobs_20260927/
    # try_create4.txt: copy_mesh_to_static_mesh succeeded with
    # GeometryScriptOutcomePins.SUCCESS against a duplicated-and-saved
    # template asset).
    write_lod0 = unreal.GeometryScriptMeshWriteLOD(lod_index=0)
    copy_to_options = unreal.GeometryScriptCopyMeshToAssetOptions()
    copy_result = AU.copy_mesh_to_static_mesh(dyn, sm, copy_to_options, write_lod0, use_section_materials=False)
    log(lines, "copy_mesh_to_static_mesh outcome: %s" % (copy_result[1] if isinstance(copy_result, tuple) and len(copy_result) > 1 else copy_result))

    # Assign brass MI to the single material slot.
    if unreal.EditorAssetLibrary.does_asset_exist(BRASS_KNOB_MI_PATH):
        brass_mi = unreal.EditorAssetLibrary.load_asset(BRASS_KNOB_MI_PATH)
        try:
            sm.set_material(0, brass_mi)
        except Exception:
            slot = unreal.StaticMaterial()
            try:
                slot.set_editor_property("material_interface", brass_mi)
                static_materials = sm.get_editor_property("static_materials")
                static_materials[0] = slot
                sm.set_editor_property("static_materials", static_materials)
            except Exception as e2:
                log(lines, "WARNING: could not assign brass MI to new knob mesh material slot 0: %s" % e2)
    else:
        log(lines, "WARNING: brass MI %s not found -- new knob mesh left with default material." % BRASS_KNOB_MI_PATH)

    # Nanite.
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    sm.set_editor_property("nanite_settings", ns)

    unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)
    log(lines, "Built smooth knob mesh %s: stem d=%.3fcm h=%.3fcm, cap d=%.3fcm h=%.3fcm, %d revolve steps, "
               "Nanite enabled, brass MI assigned=%s"
        % (pkg_path, STEM_DIAMETER_CM, stem_h, CAP_DIAMETER_CM, cap_h, REVOLVE_STEPS,
           unreal.EditorAssetLibrary.does_asset_exist(BRASS_KNOB_MI_PATH)))
    return sm


def main():
    lines = []
    log(lines, "=== WTK smooth_knobs_wtk.py start ===")
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)

    AU = unreal.GeometryScript_AssetUtils
    MQ = unreal.GeometryScript_MeshQueries
    MS = unreal.GeometryScript_MeshSelection
    ME = unreal.GeometryScript_MeshEdits

    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    mesh_assets = asset_reg.get_assets_by_path(IMPORT_DEST, recursive=True)

    knob_specs = []  # list of dicts: mesh_name, cabinet_label, world_location, world_normal
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()

    total_components_logged = 0
    total_knobs_found = 0
    total_pulls_skipped = 0
    total_unclassified = 0
    meshes_processed = 0
    meshes_failed = []

    for a in mesh_assets:
        cls_name = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else str(a.asset_class)
        if "StaticMesh" not in cls_name:
            continue
        mesh_name = str(a.asset_name)
        sm = unreal.EditorAssetLibrary.load_asset(str(a.package_name))
        if sm is None:
            continue

        brass_slots = find_brass_knob_material_slots(sm)
        if not brass_slots:
            continue

        # Find the actor(s) in the level using this mesh, to get world
        # transform (for step 5's actor placement) and a friendly cabinet
        # label for naming.
        owning_actors = []
        for actor in all_actors:
            smcs = actor.get_components_by_class(unreal.StaticMeshComponent)
            for comp in smcs:
                if comp.static_mesh is not None and comp.static_mesh.get_name() == mesh_name:
                    owning_actors.append(actor)
                    break

        try:
            lod_read = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
            copy_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
            dyn = unreal.DynamicMesh()
            result = AU.copy_mesh_from_static_mesh(sm, dyn, copy_options, lod_read)
            dyn, _copy_outcome = (result[0], result[1]) if isinstance(result, tuple) else (result, None)

            before_tris_result = MQ.get_num_triangle_i_ds(dyn)
            before_tris = before_tris_result[0] if isinstance(before_tris_result, tuple) else before_tris_result

            mat_list, _mi, _sn, _mo = AU.get_section_material_list_from_static_mesh(sm, lod_read)
            before_slots = [m.get_name() if m else "None" for m in mat_list]

            all_knob_components = []  # (comp_sel, ids, bmin, bmax)

            for slot_index, mat_name in brass_slots:
                components = find_brass_components(dyn, slot_index, lines, mesh_name)
                for comp_sel, ids, bmin, bmax in components:
                    classification, dims = classify_component(bmin, bmax)
                    total_components_logged += 1
                    log(lines, "COMPONENT mesh=%s slot=%d(%s) tris=%d bbox_min=(%.3f,%.3f,%.3f) bbox_max=(%.3f,%.3f,%.3f) "
                               "dims(sorted)=depth=%.3f face_a=%.3f face_b=%.3f aspect=%.2f -> CLASSIFICATION=%s"
                        % (mesh_name, slot_index, mat_name, len(ids), bmin.x, bmin.y, bmin.z, bmax.x, bmax.y, bmax.z,
                           dims["depth"], dims["face_a"], dims["face_b"], dims["aspect"], classification.upper()))

                    if classification == "knob":
                        total_knobs_found += 1
                        all_knob_components.append((comp_sel, ids, bmin, bmax))
                    elif classification == "pull":
                        total_pulls_skipped += 1
                    else:
                        total_unclassified += 1
                        log(lines, "  -> UNCLASSIFIED component NOT deleted (safety: only confirmed knobs are removed).")

            if not all_knob_components:
                log(lines, "Mesh %s: no knob components found among brass triangles (only pulls/unclassified) -- nothing deleted." % mesh_name)
                continue

            # Merge all knob-component selections into one (union via
            # combine_mesh_selections/ADD -- no convert_index_array_to_mesh_
            # selection exists in this binding, confirmed absent live, so
            # selections are combined as selection OBJECTS, not index sets)
            # and delete them together in a single call.
            combined_ids = set()
            combined_sel = None
            for sel, ids, _bmin, _bmax in all_knob_components:
                combined_ids |= ids
                combined_sel = sel if combined_sel is None else MS.combine_mesh_selections(combined_sel, sel, unreal.GeometryScriptCombineSelectionMode.ADD)

            del_result = ME.delete_selected_triangles_from_mesh(dyn, combined_sel)
            dyn, num_deleted = (del_result[0], del_result[1]) if isinstance(del_result, tuple) else (dyn, del_result)

            after_tris_result = MQ.get_num_triangle_i_ds(dyn)
            after_tris = after_tris_result[0] if isinstance(after_tris_result, tuple) else after_tris_result

            mat_list2, _mi2, _sn2, _mo2 = AU.get_section_material_list_from_static_mesh(sm, lod_read)
            after_slots_probe = [m.get_name() if m else "None" for m in mat_list2]  # NOTE: material slot LIST on the asset is unaffected by triangle deletion (slots persist even if 0 triangles use them) -- expected, logged for the record, not a failure condition.

            write_lod0 = unreal.GeometryScriptMeshWriteLOD(lod_index=0)
            copy_to_options = unreal.GeometryScriptCopyMeshToAssetOptions()
            AU.copy_mesh_to_static_mesh(dyn, sm, copy_to_options, write_lod0, use_section_materials=True)
            unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)

            log(lines, "Mesh %s: deleted %d knob triangle(s) (%d -> %d total tris); material slots before=%s after=%s "
                       "(slot list unchanged is expected/correct -- pull triangles in the same brass slot remain)."
                % (mesh_name, num_deleted, before_tris, after_tris, before_slots, after_slots_probe))

            meshes_processed += 1

            # Group knob sub-components spatially before spawning: the live
            # data (see the calibration comment on KNOB_FACE_MIN_CM etc.)
            # showed each real physical knob is baked as TWO separate
            # connected-component islands sharing the brass slot (a small
            # "base/collar" stub + a larger "cap") that sit directly on top
            # of each other along the door-normal axis at the SAME (x,y)
            # footprint -- grouped here by simple 2D (in-plane) centroid
            # proximity so each physical knob yields exactly ONE spawned
            # actor, not two.
            # Calibrated against live data (tmp/WtkKnobs_20260927/
            # smooth_knobs_stdout4.txt): e.g. W30's first knob pair centroids
            # are (34.131, 31.115) [base] and (34.132, 32.226) [cap] -- 1.11cm
            # apart in Y (the door-normal-ish axis where the base sits
            # slightly recessed and the cap sits slightly proud of it) but
            # ~0.001cm apart in X. Distinct knobs on the same cabinet are
            # always tens of cm apart in X (e.g. 34.13 vs 41.43+ on W30).
            # Widened from an initial 1.0cm (too tight -- missed the 1.11cm Y
            # offset) to 2.0cm, still far below the smallest real inter-knob
            # spacing seen in any mesh.
            GROUP_DIST_CM = 2.0
            groups = []  # list of lists of (sel, ids, bmin, bmax)
            for comp in all_knob_components:
                _sel, _ids, bmin, bmax = comp
                cx = (bmin.x + bmax.x) / 2.0
                cy = (bmin.y + bmax.y) / 2.0
                placed = False
                for g in groups:
                    gbmin, gbmax = g[0][2], g[0][3]
                    gcx = (gbmin.x + gbmax.x) / 2.0
                    gcy = (gbmin.y + gbmax.y) / 2.0
                    if abs(cx - gcx) <= GROUP_DIST_CM and abs(cy - gcy) <= GROUP_DIST_CM:
                        g.append(comp)
                        placed = True
                        break
                if not placed:
                    groups.append([comp])
            log(lines, "Mesh %s: grouped %d knob sub-component(s) into %d physical knob group(s)." % (mesh_name, len(all_knob_components), len(groups)))

            # Record knob world positions for actor spawning (step 5).
            # Door face normal per WTK_Cabinet_Spec.json's coordinate
            # convention: "Fronts face +Y" in Revit/local coordinate space;
            # after Datasmith import the mesh's local +Y axis maps through
            # the owning actor's world transform.
            for actor in owning_actors:
                actor_transform = actor.get_actor_transform()
                cabinet_label = actor.get_actor_label()
                for group in groups:
                    # Combined bbox across the group's sub-components.
                    gbmin = unreal.Vector(
                        min(c[2].x for c in group), min(c[2].y for c in group), min(c[2].z for c in group))
                    gbmax = unreal.Vector(
                        max(c[3].x for c in group), max(c[3].y for c in group), max(c[3].z for c in group))
                    # Base flush to the door face: the door-facing side of the
                    # combined bbox along local Y (the shallowest/min-Y face,
                    # per this project's "Fronts face +Y" convention -- the
                    # door surface itself is at the group's MIN local Y, with
                    # the knob's stem/cap projecting toward +Y away from it).
                    local_base = unreal.Vector((gbmin.x + gbmax.x) / 2.0, gbmin.y, (gbmin.z + gbmax.z) / 2.0)
                    world_center = actor_transform.transform_location(local_base)
                    # Door-face normal: local +Y transformed by the actor's
                    # rotation only (direction, not a location).
                    local_normal = unreal.Vector(0.0, 1.0, 0.0)
                    world_normal_point = actor_transform.transform_location(local_normal)
                    world_origin_point = actor_transform.transform_location(unreal.Vector(0, 0, 0))
                    world_normal = (world_normal_point - world_origin_point)
                    norm_len = math.sqrt(world_normal.x ** 2 + world_normal.y ** 2 + world_normal.z ** 2)
                    if norm_len > 1e-6:
                        world_normal = unreal.Vector(world_normal.x / norm_len, world_normal.y / norm_len, world_normal.z / norm_len)
                    knob_specs.append({
                        "cabinet_label": cabinet_label,
                        "mesh_name": mesh_name,
                        "world_location": world_center,
                        "world_normal": world_normal,
                    })
        except Exception as ex:
            log(lines, "FAILED processing mesh %s: %s" % (mesh_name, ex))
            meshes_failed.append(mesh_name)

    log(lines, "")
    log(lines, "--- Summary ---")
    log(lines, "Meshes with a brass slot processed: %d (failed: %d %s)" % (meshes_processed, len(meshes_failed), meshes_failed))
    log(lines, "Total brass components found: %d" % total_components_logged)
    log(lines, "Classified as KNOB (deleted): %d" % total_knobs_found)
    log(lines, "Classified as PULL (kept, untouched): %d" % total_pulls_skipped)
    log(lines, "UNCLASSIFIED (kept, untouched, needs review): %d" % total_unclassified)

    # --- Step 4: build the one smooth knob mesh ---
    knob_sm = build_smooth_knob_mesh(lines)

    # --- Step 5: spawn one actor per knob, idempotent ---
    actor_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = actor_subsys.get_all_level_actors()
    deleted_knob_actors = 0
    for a in existing:
        if a.get_actor_label().startswith("WTK_Knob_"):
            actor_subsys.destroy_actor(a)
            deleted_knob_actors += 1
    log(lines, "Deleted %d existing WTK_Knob_* actor(s) before respawn (idempotent)." % deleted_knob_actors)

    spawned_count = 0
    if knob_sm is not None:
        by_cabinet = {}
        for spec in knob_specs:
            by_cabinet.setdefault(spec["cabinet_label"], []).append(spec)

        for cabinet_label, specs in by_cabinet.items():
            for i, spec in enumerate(specs):
                label = "WTK_Knob_%s_%d" % (cabinet_label, i + 1)
                normal = spec["world_normal"]
                # Base flush to the door face at the original component's
                # location: spawn AT the deleted component's centroid
                # (world_location), oriented so the mesh's local +Z (the
                # revolve's "up"/projection axis) points along the door-face
                # normal, projecting the cap OUT from the face rather than
                # into it.
                # The knob mesh (build_smooth_knob_mesh) is a revolve of a 2D
                # profile whose local Y-axis becomes the DynamicMesh's local
                # Z axis after append_revolve_polygon (per that function's
                # own docstring: "+Y is up" in profile space, i.e. the
                # stem-to-cap projection direction is the mesh's local Z).
                # Align local Z to the world door-face normal so the knob
                # projects outward from the door, not sideways.
                rotation = unreal.MathLibrary.make_rot_from_z(normal)
                spawn_rot = unreal.Rotator(pitch=rotation.pitch, yaw=rotation.yaw, roll=rotation.roll)
                actor = actor_subsys.spawn_actor_from_class(unreal.StaticMeshActor, spec["world_location"], spawn_rot)
                actor.set_actor_label(label)
                smc = actor.static_mesh_component
                smc.modify()
                smc.set_static_mesh(knob_sm)
                spawned_count += 1
                log(lines, "Spawned %s at (%.3f,%.3f,%.3f) rot(pitch=%.1f,yaw=%.1f,roll=%.1f) from mesh %s"
                    % (label, spec["world_location"].x, spec["world_location"].y, spec["world_location"].z,
                       spawn_rot.pitch, spawn_rot.yaw, spawn_rot.roll, spec["mesh_name"]))

    log(lines, "")
    log(lines, "Spawned %d WTK_Knob_* actor(s) (expected 7 per 03_Revit/WTK_Cabinet_Spec.json: "
               "SB36=2, B30=2, W18=1, W30=2)." % spawned_count)
    if spawned_count != 7:
        log(lines, "*** KNOB COUNT MISMATCH: expected 7, got %d -- see COMPONENT log lines above for per-mesh detail. ***" % spawned_count)

    # --- Save ---
    world = unreal.EditorLevelLibrary.get_editor_world()
    saved_ok = unreal.EditorLevelLibrary.save_current_level()
    saved_ok2 = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log(lines, "Level save -> save_current_level=%s, save_map=%s" % (saved_ok, saved_ok2))
    log(lines, "SMOOTH_KNOBS_DONE")

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
