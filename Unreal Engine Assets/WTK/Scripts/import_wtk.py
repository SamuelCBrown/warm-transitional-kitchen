"""
WTK Datasmith headless import + geometry checks.

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput

Fallback (if commandlet mode can't import/save levels):
  UnrealEditor.exe <proj>.uproject -ExecutePythonScript=<this file>
  (this script calls unreal.SystemLibrary.quit_editor() at the end in that case)
"""
import unreal
import os
import re
import sys
import importlib.util

# The exporter names the output <document>-3DView-<view>.udatasmith. This is
# the actual output file from the Revit "WTK Datasmith Export" 3D view
# export; kept as a variable so a future re-export (same name, same path)
# needs no code change here.
DATASMITH_FILE = r"C:\Users\Sam\Documents\Chess\04_Exchange\WTK_Start-3DView-WTK_Datasmith_Export.udatasmith"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_IMPORT_DEST as IMPORT_DEST, ACTIVE_MAP_PATH as MAP_PATH
OUT_DIR = r"C:\Users\Sam\Documents\Chess\tmp\WtkUnreal_20260925"
RESULTS_PATH = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\Saved\WTK_Import_Check.txt"
ACTORS_LOG = os.path.join(OUT_DIR, "actors.txt")

TOL_CM = 0.5

# Base cabinets only: labels containing one of these IDs AND not containing
# "FX-" (the fixture actors, e.g. Casework_FX-01 / Casework_FX-04, share the
# "Casework" category prefix with the real cabinets but are not part of the
# 5-cabinet base run and were previously pulled in by a bare "Casework"
# substring match, inflating the run from 304.8 to 309.88 cm).
CASEWORK_ID_KEYS = ["DB18", "SB36", "B30", "DB24", "B12"]


def log(msg):
    # print() alone was found (WtkReimp3_20260927) to not reliably reach the
    # captured console output under `-run=pythonscript`: a full pipeline run
    # produced only 7 unrelated engine-init LogPython lines and none of this
    # script's own diagnostics (e.g. "Deleted N previous-import actors" never
    # appeared even though the delete loop demonstrably ran). unreal.log()
    # reliably shows up as `LogPython: Display:` in that same environment, so
    # route through both: unreal.log() for the reliable captured trail, print()
    # kept for the -ExecutePythonScript/interactive-console case.
    try:
        unreal.log(str(msg))
    except Exception:
        pass
    print(msg)


def is_base_cabinet_label(label):
    if not label:
        return False
    if "FX-" in label:
        return False
    return any(k in label for k in CASEWORK_ID_KEYS)


def is_counter_label(label):
    # The countertop actor is not labeled "countertop" in the Datasmith
    # export; it comes in as Casework_FX-01 (the countertop fixture),
    # verified against expected top-Z-above-floor = 91.44 cm.
    if not label:
        return False
    return "FX-01" in label


def is_ceiling_label(label):
    if not label:
        return False
    return "ceiling" in label.lower()


# --- Re-import hardening 2026-09-27, Task 3: hardened category/label selectors ---
# The corrupted reimport (tmp/WtkReimp2_20260927/before.txt vs
# inspect_hardware.txt) showed the floor/counter/ceiling detection getting
# fooled by ~20 stray exploded-B30 DirectShape actors ("Generic_Models_*")
# that leaked into the export -- e.g. a generic-models container with
# degenerate or slightly-off bounds got picked up by the old substring
# ("floor" in label.lower()) match and skewed the counter/ceiling height
# checks by exactly 25.40cm (10 inches -- almost certainly one exploded
# part's own bounding box getting unioned in by mistake). Hardened here with
# stricter selectors PLUS a room-footprint filter so any actor sitting
# outside the room's real XY envelope (including a stray part left at the
# Datasmith assembly origin, as seen in inspect_hardware.txt -- most of the
# stray Generic_Models_* actors sit at loc=(0,0,0), well outside the room)
# cannot contribute to any of the four measurements even if its label
# happened to match.
ROOM_FOOTPRINT_X_MIN, ROOM_FOOTPRINT_X_MAX = -340.0, 35.0
ROOM_FOOTPRINT_Y_MIN, ROOM_FOOTPRINT_Y_MAX = -430.0, 5.0


def is_floor_label(label):
    # Hardened: the floor's real Datasmith label is "Floors_Floor_Generic_-_12_"
    # (per import_run.log's LogStaticMesh build line) -- i.e. it starts with
    # the category prefix "Floors_", not just any label containing the
    # substring "floor" anywhere (which could also match an unrelated
    # Generic_Models_* stray part whose name happens to contain "floor").
    if not label:
        return False
    return label.startswith("Floors_")


def is_hardened_counter_label(label):
    # Same "FX-01" substring rule as before (this one wasn't implicated in
    # the stray-actor bug, but hardened to require it not also be a
    # Generic_Models_* stray -- see is_unexpected_actor_label below -- via
    # the room-footprint filter applied at the call site instead of here, to
    # keep this predicate a pure label check like the others).
    if not label:
        return False
    return "FX-01" in label


def is_hardened_ceiling_label(label):
    # Hardened: exact category-prefix match on "Ceilings_" (the real label
    # is "Ceilings_Basic_Ceiling_Generic"), not a loose "ceiling" substring
    # anywhere in the label -- the loose match was one of the two selectors
    # (along with the old floor check) most likely to accidentally include a
    # stray Generic_Models_* part if its name ever happened to contain
    # "ceiling" as a substring (it didn't in this particular corrupted
    # export, but the counter/ceiling delta was exactly 25.40cm = 10in on
    # both counter AND ceiling per the task brief, meaning at least one of
    # these two measurements was being polluted by the same stray-actor bounds).
    if not label:
        return False
    return label.startswith("Ceilings_")


def is_wall_label(label):
    if not label:
        return False
    return label.startswith("Walls_")


def is_in_room_footprint(bmin, bmax):
    """
    True if the actor's XY bounds overlap the room's real footprint
    (ROOM_FOOTPRINT_X_MIN..MAX, Y_MIN..MAX). A stray actor sitting entirely
    outside this box (e.g. left at the Datasmith assembly origin (0,0,0), as
    the ~20 exploded-B30 parts in inspect_hardware.txt were, per their
    loc=<...x:0,y:0,z:0...> dump) cannot contribute to any measurement even
    if its label happens to pass one of the selectors above.
    """
    if bmax.x < ROOM_FOOTPRINT_X_MIN or bmin.x > ROOM_FOOTPRINT_X_MAX:
        return False
    if bmax.y < ROOM_FOOTPRINT_Y_MIN or bmin.y > ROOM_FOOTPRINT_Y_MAX:
        return False
    return True


# --- Re-import hardening 2026-09-27, Task 2: unexpected-actor import guard ---
# Root cause (task brief item (a)): ~20 exploded-B30 DirectShape actors
# leaked into the export (a Revit-side bug being fixed separately) and came
# in as "Generic_Models_<PartName>" actors -- confirmed in
# tmp/WtkReimp2_20260927/inspect_hardware.txt: Generic_Models_Back,
# Generic_Models_Bottom, Generic_Models_Front0_door_Panel/RailBottom/
# RailTop/StileL/StileR, Generic_Models_Front1_door_* (same set), Generic_
# Models_Hardware0_Knob, Generic_Models_Hardware1_Knob, Generic_Models_
# Shelf_1, Generic_Models_Side_Left/Right, Generic_Models_Stretcher_Back/
# Front, Generic_Models_ToeKick -- 20 actors total (matches the task brief's
# "~20"). Two of that same dump's Generic_Models_* actors are legitimate
# known fixtures (Generic_Models_FX-06) and must NOT be flagged.
#
# The known WTK fixtures are FX-01..FX-07, which can appear in the Casework,
# Plumbing (Fixtures), Furniture, Generic Models, or Lighting categories --
# any actor label containing "FX-" is always allowed regardless of category
# prefix.
EXPECTED_FX_PATTERN = re.compile(r"FX-0[1-7]\b")

# 2026-09-27 fix (first-ever WTK_Main_v2 clean-room import): the window
# muntin sub-assembly (Generic_Models_Muntin_Pattern_2x2_Muntin_Pattern_2x2)
# is a genuine, expected Datasmith actor -- confirmed present, alone, with
# no other stray labels, in the Step 1 clean-room import test
# (tmp/WtkClean_20260927/cleanroom_actors.txt, 29 actors / 0 strays) -- but
# it also starts with "Generic_Models_" and has no "FX-" in it, so the
# broad first check in is_unexpected_actor_label() below flagged it as a
# false positive (it is NOT one of the 20 known exploded-B30 stray parts
# named in the task brief). Explicitly excluded here rather than relying on
# an allow-list, since it's a structural/known-legitimate actor type, not a
# per-run exception.
EXPECTED_GENERIC_MODELS_PATTERN = re.compile(r"^Generic_Models_Muntin_Pattern")

# Exploded-B30-part name patterns (task spec, item 2): any of these matching
# is unexpected UNLESS the label also matches EXPECTED_FX_PATTERN (checked
# first, below, since the two are mutually exclusive per the actual Revit
# fixture naming -- none of the FX-01..FX-07 fixtures use these part-name
# words).
EXPLODED_PART_PATTERNS = [
    re.compile(r"Hardware\d+_"),
    re.compile(r"Front\d+_door_"),
    re.compile(r"Side_(Left|Right)\b"),
    re.compile(r"Stretcher_"),
    re.compile(r"ToeKick\b"),
    re.compile(r"Shelf_\d"),
    re.compile(r"^Generic_Models_(Bottom|Back)$"),
]

UNEXPECTED_ACTOR_ALLOWLIST = set()  # explicit allow-list; empty by default -- see run_import_guard()'s allowlist_labels param


def is_unexpected_actor_label(label):
    """
    Returns True if `label` matches the "unexpected" pattern per the task
    spec: any Generic_Models_* actor whose label doesn't contain "FX-", OR
    any actor (regardless of category prefix) whose label matches one of the
    known exploded-B30 part-name patterns. A label matching EXPECTED_FX_
    PATTERN is never flagged, checked first.
    """
    if not label:
        return False
    if EXPECTED_FX_PATTERN.search(label):
        return False
    if EXPECTED_GENERIC_MODELS_PATTERN.search(label):
        return False
    if label.startswith("Generic_Models_") and "FX-" not in label:
        return True
    for pat in EXPLODED_PART_PATTERNS:
        if pat.search(label):
            return True
    return False


def run_import_guard(all_actors, allowlist_labels=None):
    """
    Re-import hardening 2026-09-27, Task 2: after the import, list every
    actor whose label matches the "unexpected" pattern (see
    is_unexpected_actor_label above). Logs each as UNEXPECTED_ACTOR (does
    NOT delete anything -- flag only, per the task spec). Returns
    (unexpected_labels, guard_passed) -- guard_passed is False (guard
    FAILS the import check) if any unexpected actor is found and not covered
    by allowlist_labels; True otherwise.
    """
    allowlist_labels = set(allowlist_labels or UNEXPECTED_ACTOR_ALLOWLIST)
    unexpected = []
    allowlisted_count = 0
    for actor in all_actors:
        label = actor.get_actor_label()
        if not is_unexpected_actor_label(label):
            continue
        if label in allowlist_labels:
            log("UNEXPECTED_ACTOR (allow-listed, not failing): %s" % label)
            allowlisted_count += 1
            continue
        log("UNEXPECTED_ACTOR: %s" % label)
        unexpected.append(label)
    guard_passed = len(unexpected) == 0
    log("Import guard: %d unexpected actor(s) found (failing), %d allow-listed, guard %s"
        % (len(unexpected), allowlisted_count, "PASSED" if guard_passed else "FAILED"))
    return unexpected, guard_passed


def save_imported_assets():
    """
    scene.import_scene() only creates in-memory packages for the imported
    meshes/materials under IMPORT_DEST; save_current_level() alone does not
    write them to disk. Without this, does_directory_exist(IMPORT_DEST)
    reports no content on the next run (nothing under Content/WTK/Datasmith
    on disk), so ensure_map_and_import() always takes the first_import path
    and the reimport/duplicate-actor-cleanup logic below is never exercised.
    Returns the count of assets saved.
    """
    editor_asset_lib = unreal.EditorAssetLibrary
    if not editor_asset_lib.does_directory_exist(IMPORT_DEST):
        return 0
    asset_paths = editor_asset_lib.list_assets(IMPORT_DEST, recursive=True, include_folder=False)
    saved = 0
    for asset_path in asset_paths:
        try:
            if editor_asset_lib.save_asset(asset_path, only_if_is_dirty=False):
                saved += 1
        except Exception as e:
            log("Could not save asset %s: %s" % (asset_path, e))
    log("Saved %d/%d imported assets under %s to disk." % (saved, len(asset_paths), IMPORT_DEST))
    return saved


# Meshes to skip for Nanite: glass/translucent (Nanite doesn't support
# masked/translucent materials well and the window glass pane is tiny/thin)
# and any mesh whose name matches a "tiny mesh" exclusion (Nanite's per-mesh
# overhead isn't worth it below a small triangle/size threshold). Matched by
# substring against the StaticMesh asset name.
NANITE_EXCLUDE_NAME_SUBSTRINGS = ["Glass", "Window"]
NANITE_MIN_TRIANGLES = 12  # meshes below this triangle count are considered "tiny" (e.g. simple glass panes, small hardware)


def run_nanite_pass():
    """
    Phase 5c-2 Task 3: enable Nanite on every StaticMesh under
    /Game/WTK/Datasmith, except glass/translucent meshes and tiny meshes.
    Idempotent: skips meshes that already have nanite_settings.enabled=True.
    Uses the StaticMesh's nanite_settings property directly (read-modify-set)
    rather than StaticMeshEditorSubsystem.set_nanite_settings, since
    unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) returns
    None in headless -run=pythonscript commandlet mode in this UE 5.7 build
    (confirmed via introspection, tmp/Wtk5c2_20260926/introspect_nanite.py,
    test_nanite_direct.py) -- the direct nanite_settings struct
    get/set_editor_property path works in both commandlet and
    -ExecutePythonScript modes and needs no subsystem.
    Returns (enabled_count, skipped_count, already_enabled_count).
    """
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    mesh_assets = asset_reg.get_assets_by_path(IMPORT_DEST, recursive=True)
    enabled = 0
    skipped = 0
    already = 0
    for a in mesh_assets:
        cls_name = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else str(a.asset_class)
        if "StaticMesh" not in cls_name:
            continue
        mesh_name = str(a.asset_name)
        if any(sub in mesh_name for sub in NANITE_EXCLUDE_NAME_SUBSTRINGS):
            skipped += 1
            continue
        sm = unreal.EditorAssetLibrary.load_asset(str(a.package_name))
        if sm is None:
            continue
        try:
            # StaticMesh has no get_number_of_triangles() in this UE 5.7
            # Python binding (confirmed via introspection,
            # tmp/Wtk5c2_20260926/test_tricount.py) -- use the same
            # GeometryScript copy-to-DynamicMesh + get_num_triangle_i_ds
            # path already proven in uv_check_b30.py/uv_check_extended.py.
            dyn = unreal.DynamicMesh()
            options = unreal.GeometryScriptCopyMeshFromAssetOptions()
            target_lod = unreal.GeometryScriptMeshReadLOD(
                lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
            result = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(sm, dyn, options, target_lod)
            dyn = result[0] if isinstance(result, tuple) else result
            num_tris_result = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dyn)
            num_tris = num_tris_result[0] if isinstance(num_tris_result, tuple) else num_tris_result
        except Exception:
            num_tris = None
        if num_tris is not None and num_tris < NANITE_MIN_TRIANGLES:
            skipped += 1
            continue

        ns = sm.get_editor_property("nanite_settings")
        if ns.enabled:
            already += 1
            continue
        ns.set_editor_property("enabled", True)
        sm.set_editor_property("nanite_settings", ns)
        unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)
        enabled += 1

    log("Nanite pass: enabled=%d skipped(excluded/tiny)=%d already_enabled=%d" % (enabled, skipped, already))
    return enabled, skipped, already


# --- Phase 5d round 6: ceiling normal flip ---
# Ceilings_Basic_Ceiling_Generic is a single-sided, zero-thickness plane
# (confirmed via actor bounds: extent.z == 0.0). Its face normal points UP,
# so it's invisible from inside the room looking up -- the room appeared to
# have open sky above the walls in every Phase 5d test render until this was
# found (2026-09-26, prompted by a coordinator review of a test render).
# Fixed here (not just as a one-off MI/material tweak) so it survives every
# future Datasmith reimport: GeometryScript-flip the mesh's normals (and
# winding, via flip_normals -- confirmed it flips both, not just the shading
# normals) so the correct face is what's culled/shown.
CEILING_NAME_SUBSTRINGS = ["Ceiling"]
CEILING_FLIP_MARKER_TAG = "WTK_CeilingFlipped_v1"


def run_ceiling_flip_pass():
    """
    Flips normals (via GeometryScript_Normals.flip_normals) on every
    StaticMesh whose name contains "Ceiling", idempotent via an
    EditorAssetLibrary metadata tag (same pattern as run_bevel_pass's
    BEVEL_MARKER_TAG) so a rerun against an unchanged Datasmith source
    doesn't flip an already-flipped mesh back to wrong-side-up. If the
    source geometry actually changes on a real Revit edit, the underlying
    StaticMesh package is rewritten and the tag doesn't carry over, so the
    next reimport correctly re-flips the new geometry.
    Returns (flipped_count, already_done_count, failed_count).
    """
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    mesh_assets = asset_reg.get_assets_by_path(IMPORT_DEST, recursive=True)

    AU = unreal.GeometryScript_AssetUtils
    MQ = unreal.GeometryScript_MeshQueries
    NM = unreal.GeometryScript_Normals

    flipped = 0
    already_done = 0
    failed = 0

    for a in mesh_assets:
        cls_name = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else str(a.asset_class)
        if "StaticMesh" not in cls_name:
            continue
        mesh_name = str(a.asset_name)
        if not any(sub in mesh_name for sub in CEILING_NAME_SUBSTRINGS):
            continue

        sm = unreal.EditorAssetLibrary.load_asset(str(a.package_name))
        if sm is None:
            continue

        existing_tag = unreal.EditorAssetLibrary.get_metadata_tag(sm, CEILING_FLIP_MARKER_TAG)
        if existing_tag == "1":
            already_done += 1
            continue

        try:
            lod_read = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)
            mat_list, _mi, _sn, _mo = AU.get_section_material_list_from_static_mesh(sm, lod_read)
            before_slots = [m.get_name() if m else "None" for m in mat_list]

            dyn = unreal.DynamicMesh()
            options = unreal.GeometryScriptCopyMeshFromAssetOptions()
            result = AU.copy_mesh_from_static_mesh(sm, dyn, options, lod_read)
            dyn, _copy_outcome = (result[0], result[1]) if isinstance(result, tuple) else (result, None)

            num_tris_result = MQ.get_num_triangle_i_ds(dyn)
            before_tris = num_tris_result[0] if isinstance(num_tris_result, tuple) else num_tris_result

            result = NM.flip_normals(dyn)
            dyn = result[0] if isinstance(result, tuple) else result

            write_lod0 = unreal.GeometryScriptMeshWriteLOD(lod_index=0)
            copy_to_options = unreal.GeometryScriptCopyMeshToAssetOptions()
            AU.copy_mesh_to_static_mesh(dyn, sm, copy_to_options, write_lod0, use_section_materials=True)

            mat_list2, _mi2, _sn2, _mo2 = AU.get_section_material_list_from_static_mesh(sm, lod_read)
            after_slots = [m.get_name() if m else "None" for m in mat_list2]
            num_tris_result2 = MQ.get_num_triangle_i_ds(dyn)
            after_tris = num_tris_result2[0] if isinstance(num_tris_result2, tuple) else num_tris_result2

            if after_slots != before_slots:
                log("Ceiling flip SKIPPED (material slots changed unexpectedly) for %s" % mesh_name)
                failed += 1
                continue
            if after_tris != before_tris:
                log("Ceiling flip SKIPPED (triangle count changed -- flip_normals shouldn't change topology) for %s (%d -> %d)" % (mesh_name, before_tris, after_tris))
                failed += 1
                continue

            unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)
            unreal.EditorAssetLibrary.set_metadata_tag(sm, CEILING_FLIP_MARKER_TAG, "1")
            unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)
            flipped += 1
            log("Flipped normals for ceiling mesh %s (%d triangles, material slots unchanged)" % (mesh_name, after_tris))
        except Exception as ex:
            log("Ceiling flip FAILED for %s: %s" % (mesh_name, ex))
            failed += 1

    log("Ceiling flip pass: flipped=%d already_done=%d failed=%d" % (flipped, already_done, failed))
    return flipped, already_done, failed


# --- Task 4: edge bevels ---
BEVEL_DISTANCE_CM = 0.159  # 1/16 in
BEVEL_SHARP_EDGE_ANGLE_DEG = 30.0
BEVEL_SPLIT_NORMAL_ANGLE_DEG = 60.0
BEVEL_MARKER_TAG = "WTK_Beveled_v1"  # deprecated plain marker -- superseded by
# WTK_Bevel_Fingerprint below (kept as a constant only so old assets that
# still carry it are recognized as legacy/stale, never trusted as "done").

# Re-import hardening 2026-09-27, Task 1: the plain WTK_Beveled_v1 tag was
# found to survive a Datasmith in-place scene-update reimport even when the
# underlying mesh geometry was fully replaced (B30 came back with 256
# triangles -- its pre-bevel, unbeveled count -- while still carrying
# WTK_Beveled_v1="1" from the PREVIOUS import's already-beveled 745-triangle
# mesh; see tmp/WtkReimp2_20260927/check_b30_tag.log). A plain boolean tag
# can't distinguish "this exact mesh was already beveled" from "some mesh
# that used to live at this asset path was beveled once". Fixed by replacing
# it with a fingerprint of the SOURCE (pre-bevel) mesh: triangle count +
# rounded bounds (+ a coarse vertex-position hash), stored as a single
# "|"-delimited string. On each run:
#   - compute the CURRENT mesh's fingerprint (as if it were about to be
#     beveled from scratch, i.e. its fingerprint AS THE SOURCE mesh right now).
#   - compare it to WTK_Bevel_Fingerprint_Post (the fingerprint the mesh had
#     immediately AFTER the last successful bevel this pipeline ran).
#   - equal -> this is the same already-beveled mesh, skip.
#   - different (including "no tag at all") -> treat as fresh: bevel it, then
#     store BOTH the pre-bevel fingerprint (WTK_Bevel_Fingerprint_Pre, the
#     value just computed) and the post-bevel fingerprint
#     (WTK_Bevel_Fingerprint_Post, computed after the bevel geometry is
#     written back) so the very next run's "is this the same beveled mesh"
#     check has the right post-bevel value to compare against.
# This correctly classifies the corrupted-reimport B30 (256 tris, unbeveled,
# stale WTK_Beveled_v1="1") as fresh: its live fingerprint (256 tris + its
# own bounds) does not equal the stored Post fingerprint (745 tris + the
# beveled mesh's bounds from the prior run), so it is re-beveled -- exactly
# the desired behavior for a real geometry replacement.
BEVEL_FP_PRE_TAG = "WTK_Bevel_Fingerprint_Pre"
BEVEL_FP_POST_TAG = "WTK_Bevel_Fingerprint_Post"
BEVEL_FP_BOUNDS_ROUND_DP = 2  # round bounds to 0.01cm before hashing/storing -- absorbs float noise between runs
BEVEL_FP_VERTEX_SAMPLE_STRIDE = 7  # sample every Nth vertex (coarse hash) rather than hashing all of them -- cheap, still change-sensitive


def _mesh_fingerprint(dyn, tri_count):
    """
    Builds the "WTK_Bevel_Fingerprint"-style string for a DynamicMesh already
    loaded into memory: pre-bevel (or current) triangle count, rounded
    bounding-box min/max, and a coarse hash of a stride-sampled subset of
    vertex positions (cheap -- avoids hashing every vertex on a dense mesh --
    while still changing if the geometry is meaningfully different). Format:
    "tris=<n>|bounds=<x0>,<y0>,<z0>,<x1>,<y1>,<z1>|vhash=<hex>".
    """
    import hashlib

    MQ = unreal.GeometryScript_MeshQueries
    try:
        bbox_result = MQ.get_mesh_bounding_box(dyn)
        bbox = bbox_result[0] if isinstance(bbox_result, tuple) else bbox_result
        bmin, bmax = bbox.min, bbox.max
    except Exception:
        bmin = bmax = unreal.Vector(0.0, 0.0, 0.0)

    def r(v):
        return round(v, BEVEL_FP_BOUNDS_ROUND_DP)

    bounds_str = "%.2f,%.2f,%.2f,%.2f,%.2f,%.2f" % (
        r(bmin.x), r(bmin.y), r(bmin.z), r(bmax.x), r(bmax.y), r(bmax.z))

    vhash = hashlib.md5()
    try:
        num_verts_result = MQ.get_num_vertex_i_ds(dyn)
        num_verts = num_verts_result[0] if isinstance(num_verts_result, tuple) else num_verts_result
        vids_result = MQ.get_all_vertex_i_ds(dyn, num_verts)
        vids = vids_result[0] if isinstance(vids_result, tuple) else vids_result
        for i in range(0, len(vids), BEVEL_FP_VERTEX_SAMPLE_STRIDE):
            vpos_result = MQ.get_vertex_position(dyn, vids[i])
            vpos = vpos_result[0] if isinstance(vpos_result, tuple) else vpos_result
            vhash.update(("%.2f,%.2f,%.2f;" % (r(vpos.x), r(vpos.y), r(vpos.z))).encode("utf-8"))
    except Exception:
        # If vertex sampling isn't available in this binding, fall back to
        # tri_count + bounds alone -- still detects a geometry-replaced
        # reimport in the overwhelming majority of cases (a mesh keeping the
        # exact same triangle count AND exact same bounds after a real Revit
        # edit would be a near-impossible coincidence).
        pass

    return "tris=%d|bounds=%s|vhash=%s" % (tri_count, bounds_str, vhash.hexdigest())


# Hardware cylinders (knobs, pulls) are small, highly-tessellated round parts
# -- beveling their edges (every triangle boundary on a cylinder reads as a
# "sharp" or "boundary" edge to the selector) produces visible faceting
# artifacts and doesn't read as a bevel at all on a rounded part. Excluded by
# two independent, purely-geometric signals (no name-matching, since not
# every hardware mesh is named "Knob"/"Hardware"):
#   (1) short-edge filter: an edge selection filtered to only edges LONGER
#       than BEVEL_MIN_EDGE_LENGTH_CM survives on planar box-like parts (long
#       straight edges) but drops most of a small cylinder's tessellation
#       edges (short chords around the round profile).
#   (2) planar/large-face filter: an edge is only kept if at least one
#       adjacent triangle's face area is above BEVEL_MIN_ADJACENT_FACE_AREA_CM2
#       -- a cylinder's tessellated side faces are individually tiny, so this
#       independently suppresses them even if a particular chord happens to
#       be longer than the length threshold on a bigger hardware part.
BEVEL_MIN_EDGE_LENGTH_CM = 1.0
BEVEL_MIN_ADJACENT_FACE_AREA_CM2 = 0.5

# Meshes eligible for bevel per the task spec: casework (Casework_WTK_*), the
# counter (FX-01), the shelves (FX-05), and the backsplash top edge (FX-04)
# if easy (treated the same as the others -- the full-mesh bevel already
# covers "top edge" as part of its hard-edge selection, no special-casing
# needed). Glass/translucent meshes are excluded (bevel is a purely
# geometric operation and wouldn't be visually meaningful on a thin glass
# pane, and it's excluded from Nanite for the same category of reason).
BEVEL_TARGET_NAME_SUBSTRINGS = ["Casework", "FX-01", "FX-05", "FX-04"]
BEVEL_EXCLUDE_NAME_SUBSTRINGS = ["Glass"]


def run_bevel_pass():
    """
    Phase 5c-2 Task 4: apply a small (0.159cm / 1/16in) bevel to hard edges
    (sharp edges by angle >=30deg, PLUS boundary edges -- Datasmith meshes
    are composed of many separate box-like solids/islands per mesh, so each
    part's own boundary needs beveling too, confirmed on B30 where the
    combined selection was 518 edges), on every mesh matching
    BEVEL_TARGET_NAME_SUBSTRINGS (casework, counter, shelf, backsplash),
    skipping glass. Idempotent via an EditorAssetLibrary metadata tag
    (BEVEL_MARKER_TAG) set on each mesh after a successful bevel -- checked
    before beveling so a rerun doesn't double-bevel (which would keep
    growing the edge distance/triangle count on every reimport).

    Validated first on B30 alone (see Materials.md / Pipeline.md and
    tmp/Wtk5c2_20260926/bevel_test_b30.txt): 240 -> 745 triangles (3.10x,
    a moderate increase), bounds delta exactly 0.00000cm (tolerance
    0.01cm), material slots unchanged. This function reuses that exact
    method, batched.

    Ordering note: this runs BEFORE run_nanite_pass() in the pipeline.
    Nanite builds its own high-detail cluster representation from the
    source mesh's geometry at the time Nanite is enabled/the asset is
    saved; since bevel changes the actual LOD0 mesh geometry (adds small
    new bevel faces), running the bevel BEFORE Nanite is enabled ensures
    Nanite's clusters are built from the already-beveled geometry, not the
    sharp original -- beveling AFTER Nanite was already enabled would
    require an explicit Nanite rebuild trigger to pick up the geometry
    change, and no separate "force Nanite rebuild" call was found in this
    UE 5.7 Python API beyond re-saving the asset (which this pipeline does
    anyway after each step, so the risk is more about clarity of intent
    than a hard technical requirement -- bevel-then-Nanite is still the
    safer, simpler-to-reason-about order and is what import_wtk.py's
    ensure_map_and_import() call sites use).
    Returns (beveled_count, skipped_count, already_done_count, failed_count).
    """
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    mesh_assets = asset_reg.get_assets_by_path(IMPORT_DEST, recursive=True)

    AU = unreal.GeometryScript_AssetUtils
    MQ = unreal.GeometryScript_MeshQueries
    MS = unreal.GeometryScript_MeshSelection
    MM = unreal.GeometryScript_MeshModeling
    NM = unreal.GeometryScript_Normals

    beveled = 0
    skipped = 0
    already_done = 0
    failed = 0

    for a in mesh_assets:
        cls_name = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else str(a.asset_class)
        if "StaticMesh" not in cls_name:
            continue
        mesh_name = str(a.asset_name)

        if not any(sub in mesh_name for sub in BEVEL_TARGET_NAME_SUBSTRINGS):
            continue
        if any(sub in mesh_name for sub in BEVEL_EXCLUDE_NAME_SUBSTRINGS):
            skipped += 1
            continue

        sm = unreal.EditorAssetLibrary.load_asset(str(a.package_name))
        if sm is None:
            continue

        try:
            lod_read = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.MAX_AVAILABLE, lod_index=0)

            mat_list, material_index, slot_names, mat_outcome = AU.get_section_material_list_from_static_mesh(sm, lod_read)
            before_slots = [m.get_name() if m else "None" for m in mat_list]

            dyn = unreal.DynamicMesh()
            options = unreal.GeometryScriptCopyMeshFromAssetOptions()
            result = AU.copy_mesh_from_static_mesh(sm, dyn, options, lod_read)
            dyn, _copy_outcome = (result[0], result[1]) if isinstance(result, tuple) else (result, None)

            num_tris_result = MQ.get_num_triangle_i_ds(dyn)
            before_tris = num_tris_result[0] if isinstance(num_tris_result, tuple) else num_tris_result

            # Re-import hardening 2026-09-27, Task 1: fingerprint-based
            # idempotency, replacing the plain WTK_Beveled_v1 boolean tag.
            # Compute the CURRENT (pre-bevel-this-run) mesh's fingerprint and
            # compare it to the stored POST-bevel fingerprint from the last
            # successful bevel of this asset. Equal => same already-beveled
            # mesh, skip. Different (or missing) => fresh geometry (a real
            # reimport replaced it, or it's genuinely never been beveled) --
            # bevel it below and store both fingerprints at the end.
            current_fp = _mesh_fingerprint(dyn, before_tris)
            stored_post_fp = unreal.EditorAssetLibrary.get_metadata_tag(sm, BEVEL_FP_POST_TAG)
            legacy_tag = unreal.EditorAssetLibrary.get_metadata_tag(sm, BEVEL_MARKER_TAG)
            if stored_post_fp and current_fp == stored_post_fp:
                already_done += 1
                continue
            if legacy_tag == "1" and not stored_post_fp:
                # Legacy-tagged asset from before this fingerprint scheme
                # existed, with no fingerprint recorded yet -- can't verify
                # it's the same mesh that was actually beveled, so treat as
                # fresh and re-bevel/re-fingerprint rather than trusting the
                # unverifiable plain tag (this is exactly the corrupted-B30
                # case: legacy_tag=="1" but the geometry is the pre-bevel
                # source, 256 tris).
                log("Mesh %s carries legacy WTK_Beveled_v1 tag with no verifiable fingerprint -- "
                    "treating as fresh (re-bevel/re-fingerprint)." % mesh_name)

            result = MS.select_mesh_sharp_edges(dyn, min_angle_deg=BEVEL_SHARP_EDGE_ANGLE_DEG)
            dyn, sharp_sel = (result[0], result[1]) if isinstance(result, tuple) else (dyn, result)
            result = MS.select_mesh_boundary_edges(dyn)
            dyn, boundary_sel = (result[0], result[1]) if isinstance(result, tuple) else (dyn, result)
            combined_sel = MS.combine_mesh_selections(sharp_sel, boundary_sel, unreal.GeometryScriptCombineSelectionMode.ADD)

            # Re-import hardening 2026-09-27, Task 1: exclude small hardware
            # cylinders from the bevel selection -- see the module-level
            # comment above BEVEL_MIN_EDGE_LENGTH_CM/BEVEL_MIN_ADJACENT_FACE_
            # AREA_CM2 for why (tessellated cylinder edges are short and their
            # adjacent faces are tiny; beveling them produces faceting
            # artifacts and isn't meaningful on a rounded part anyway).
            # Filtered via GeometryScript's edge-length and triangle-area
            # selection primitives, ANDed against the sharp+boundary selection
            # already built above, rather than a mesh-name match (a hardware
            # part isn't reliably named "Knob"/"Hardware" on every asset).
            try:
                long_edges_result = MS.select_mesh_edges_by_length(
                    dyn, min_length=BEVEL_MIN_EDGE_LENGTH_CM, max_length=1.0e9)
                dyn, long_edge_sel = (long_edges_result[0], long_edges_result[1]) if isinstance(long_edges_result, tuple) else (dyn, long_edges_result)
                combined_sel = MS.combine_mesh_selections(
                    combined_sel, long_edge_sel, unreal.GeometryScriptCombineSelectionMode.INTERSECTION)
            except Exception:
                # select_mesh_edges_by_length isn't in every UE 5.7 Python
                # binding revision -- if unavailable, fall back to the
                # large-planar-face filter alone (still suppresses cylinders).
                pass
            try:
                large_face_result = MS.select_mesh_edges_by_adjacent_face_area(
                    dyn, min_area=BEVEL_MIN_ADJACENT_FACE_AREA_CM2)
                dyn, large_face_sel = (large_face_result[0], large_face_result[1]) if isinstance(large_face_result, tuple) else (dyn, large_face_result)
                combined_sel = MS.combine_mesh_selections(
                    combined_sel, large_face_sel, unreal.GeometryScriptCombineSelectionMode.INTERSECTION)
            except Exception:
                pass

            bevel_options = unreal.GeometryScriptMeshBevelSelectionOptions()
            bevel_options.set_editor_property("bevel_distance", BEVEL_DISTANCE_CM)
            try:
                bevel_options.set_editor_property("infer_material_id", True)
            except Exception:
                pass
            dyn = MM.apply_mesh_bevel_edge_selection(dyn, combined_sel, bevel_options)

            split_options = unreal.GeometryScriptSplitNormalsOptions()
            try:
                split_options.set_editor_property("split_by_opening_angle", True)
                split_options.set_editor_property("opening_angle_deg", BEVEL_SPLIT_NORMAL_ANGLE_DEG)
            except Exception:
                pass
            calc_options = unreal.GeometryScriptCalculateNormalsOptions()
            try:
                dyn = NM.compute_split_normals(dyn, split_options, calc_options)
            except Exception:
                dyn = NM.recompute_normals(dyn, calc_options)

            write_lod0 = unreal.GeometryScriptMeshWriteLOD(lod_index=0)
            copy_to_options = unreal.GeometryScriptCopyMeshToAssetOptions()
            result = AU.copy_mesh_to_static_mesh(dyn, sm, copy_to_options, write_lod0, use_section_materials=True)

            # Validate before committing the marker tag: material slots
            # unchanged and triangle count actually grew (a bevel that
            # produced zero new triangles likely means the selection was
            # empty / the bevel silently no-op'd, which shouldn't be marked
            # as done).
            mat_list2, _mi2, _sn2, _mo2 = AU.get_section_material_list_from_static_mesh(sm, lod_read)
            after_slots = [m.get_name() if m else "None" for m in mat_list2]
            num_tris_result2 = MQ.get_num_triangle_i_ds(dyn)
            after_tris = num_tris_result2[0] if isinstance(num_tris_result2, tuple) else num_tris_result2

            if after_slots != before_slots:
                log("Bevel SKIPPED (material slots changed unexpectedly) for %s" % mesh_name)
                failed += 1
                continue
            if after_tris <= before_tris:
                log("Bevel SKIPPED (no triangle growth -- likely empty edge selection, e.g. an "
                    "all-hardware-cylinder mesh with nothing left after the length/area filters) "
                    "for %s (%d -> %d)" % (mesh_name, before_tris, after_tris))
                failed += 1
                continue

            # Re-import hardening 2026-09-27, Task 1: store BOTH the pre-bevel
            # fingerprint (the source-mesh fingerprint computed above, before
            # any bevel geometry was added) and the post-bevel fingerprint
            # (recomputed now, against the final beveled dyn) -- the Post
            # value is what the NEXT run's idempotency check compares its own
            # current-mesh fingerprint against. The legacy WTK_Beveled_v1 tag
            # is still set too (harmless, kept for any external tooling that
            # might still read it), but it is no longer trusted on read.
            post_fp = _mesh_fingerprint(dyn, after_tris)
            unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)
            unreal.EditorAssetLibrary.set_metadata_tag(sm, BEVEL_MARKER_TAG, "1")
            unreal.EditorAssetLibrary.set_metadata_tag(sm, BEVEL_FP_PRE_TAG, current_fp)
            unreal.EditorAssetLibrary.set_metadata_tag(sm, BEVEL_FP_POST_TAG, post_fp)
            unreal.EditorAssetLibrary.save_loaded_asset(sm, only_if_is_dirty=False)
            beveled += 1
            log("Beveled %s: %d -> %d triangles (%.2fx); fingerprint stored (pre=%s..., post=%s...)" % (
                mesh_name, before_tris, after_tris, after_tris / before_tris if before_tris else 0,
                current_fp[:40], post_fp[:40]))
        except Exception as ex:
            log("Bevel FAILED for %s: %s" % (mesh_name, ex))
            failed += 1

    log("Bevel pass: beveled=%d skipped(excluded)=%d already_done=%d failed=%d" % (beveled, skipped, already_done, failed))
    return beveled, skipped, already_done, failed


REMAP_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remap_materials_wtk.py")


def run_material_remap():
    """
    Loads and runs remap_materials_wtk.py's main() in-process (after
    save_imported_assets(), before save_current_level(), per the Phase 5c
    task spec) so every reimport re-applies the WTK Material Instance
    mapping. Idempotent: remap_materials_wtk.py itself is a pure by-name
    reassignment, safe to run repeatedly against the same level state.
    """
    try:
        spec = importlib.util.spec_from_file_location("remap_materials_wtk", REMAP_SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main()
        log("Material remap step completed.")
    except Exception as e:
        log("Material remap step FAILED (non-fatal to import): %s" % e)


SMOOTH_KNOBS_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smooth_knobs_wtk.py")


def run_knob_smoothing_pass():
    """
    2026-09-27 WtkKnobs pass: loads and runs smooth_knobs_wtk.py's main()
    in-process, AFTER run_nanite_pass() (needs the final, Nanite-enabled
    casework meshes so the newly-authored knob mesh isn't the only Nanite
    asset in the scene) and AFTER run_material_remap() (needs the brass MI
    already assigned so its brass-slot lookup finds the correct material,
    though the function also recognizes the raw pre-remap
    "Metal_SatinBrass" source name defensively -- see
    find_brass_knob_material_slots()'s own docstring).

    REIMPORT_DURABILITY (explicit, per the task spec -- do not assume this
    survives a reimport silently): every Datasmith reimport (datasmith_scene_
    update OR delete_and_reimport) re-bakes the ORIGINAL Revit-tessellated
    knob geometry from the .udatasmith source into the casework StaticMesh
    assets under IMPORT_DEST -- confirmed by the same mechanism already
    documented for the bevel pass's fingerprinting (a reimport that replaces
    a mesh's underlying geometry produces a NEW triangle set at the same
    asset path). smooth_knobs_wtk.py's triangle deletion/component
    classification has NO idempotency-skip tag (unlike bevel/ceiling-flip/
    Nanite) precisely because it MUST re-run and re-delete the freshly
    re-baked faceted knob triangles every single time this pipeline runs,
    not just once -- it is intentionally NOT cached/skipped. Wired in here
    (called every run, at every ensure_map_and_import() return path) rather
    than left as a manual follow-up step specifically so this durability
    requirement is enforced automatically rather than relying on a human to
    remember to re-run it after every reimport.
    """
    try:
        spec = importlib.util.spec_from_file_location("smooth_knobs_wtk", SMOOTH_KNOBS_SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main()
        log("Knob smoothing pass completed.")
    except Exception as e:
        log("Knob smoothing pass FAILED (non-fatal to import): %s" % e)


RAIL_GRAIN_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fix_rail_grain_wtk.py")


def run_rail_grain_pass():
    """
    2026-09-27: moves the B30 door-rail triangles into their own
    MI_Oak_Rift_Rail slot (UV rotated +90 deg) so the rails read horizontal.
    Must run after every reimport (a reimport re-bakes the single oak slot),
    after run_knob_smoothing_pass(). Called with load_level=False so the
    in-memory level isn't reloaded from disk mid-pipeline.
    """
    try:
        spec = importlib.util.spec_from_file_location("fix_rail_grain_wtk", RAIL_GRAIN_SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main(load_level=False)
        log("Rail grain pass completed.")
    except Exception as e:
        log("Rail grain pass FAILED (non-fatal to import): %s" % e)


def ensure_map_and_import():
    """
    Idempotent import: if /Game/WTK/Datasmith already has content, prefer the
    Datasmith reimport/scene-update API (preserves per-slot material
    overrides). Falls back to deleting the previous import's actors in
    WTK_Main and re-importing to the same folder if that API isn't
    available. Returns (path_used, saved_ok, scene_or_none).
    """
    editor_asset_lib = unreal.EditorAssetLibrary

    dest_has_content = editor_asset_lib.does_directory_exist(IMPORT_DEST) and len(
        editor_asset_lib.list_assets(IMPORT_DEST, recursive=True, include_folder=False)
    ) > 0
    log("Destination %s has existing content: %s" % (IMPORT_DEST, dest_has_content))

    map_exists = editor_asset_lib.does_asset_exist(MAP_PATH)

    if dest_has_content and map_exists:
        # Try the Datasmith reimport / scene-update path first.
        try:
            unreal.EditorLevelLibrary.load_level(MAP_PATH)
            all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
            scene_actors = [a for a in all_actors if a.get_class().get_name() == "DatasmithSceneActor"]
            if scene_actors:
                scene_actor = scene_actors[0]
                datasmith_scene = None
                try:
                    datasmith_scene = scene_actor.get_editor_property("scene")
                except Exception:
                    datasmith_scene = None

                if datasmith_scene is not None and hasattr(datasmith_scene, "import_scene"):
                    # Re-point the scene element at the (possibly newer) file and re-run
                    # import_scene onto the same destination; the Datasmith scene's own
                    # override machinery preserves per-slot material overrides on
                    # elements that already existed, per the reimport note in
                    # WTK_Revit_Setup_Note.md.
                    log("Using DatasmithSceneElement reimport/update path.")
                    new_scene = unreal.DatasmithSceneElement.construct_datasmith_scene_from_file(DATASMITH_FILE)
                    if new_scene is not None:
                        new_scene.import_scene(IMPORT_DEST)
                        try:
                            new_scene.destroy_scene()
                        except Exception:
                            pass
                        save_imported_assets()
                        run_material_remap()
                        run_ceiling_flip_pass()
                        run_bevel_pass()
                        run_nanite_pass()
                        run_knob_smoothing_pass()
                        run_rail_grain_pass()
                        # WTK prop-fix pass round 2 (2026-09-26) audit finding:
                        # place_props_wtk.py's save_current_level()-only call
                        # was found to silently no-op (the .umap's on-disk
                        # timestamp never advanced) because the mutated
                        # actors were never explicitly modify()'d first.
                        # Hardened the same way here as a second, independent
                        # line of defence -- NOT independently re-verified by
                        # a live before/after .umap-timestamp check this pass
                        # (no Datasmith reimport was exercised this pass).
                        world = unreal.EditorLevelLibrary.get_editor_world()
                        saved_ok = unreal.EditorLevelLibrary.save_current_level()
                        saved_ok2 = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
                        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
                        log("REIMPORT_PATH_USED=datasmith_scene_update saved(save_current_level=%s, save_map=%s)" % (saved_ok, saved_ok2))
                        return "datasmith_scene_update", (saved_ok or saved_ok2), new_scene
        except Exception as e:
            log("Datasmith reimport/update path failed or unavailable (%s); falling back to delete+reimport." % e)

        # Fallback: delete the previous Datasmith import's actors in WTK_Main
        # and re-import to the same folder.
        #
        # Phase 5e reimport-safety fix: this loop used to call
        # unreal.EditorLevelLibrary.get_all_level_actors() and destroy EVERY
        # actor unconditionally, on the theory that "this is a full
        # delete+reimport of the prior import's actors". That was true only
        # as long as nothing non-Datasmith had ever been added to the level.
        # Once Phase 5d/5e added hand-authored level actors that are NOT part
        # of the Datasmith import -- lights (WTK_Sun, WTK_SkyLight,
        # WTK_LED_W18/W30, WTK_Fill_Room), cameras (CAM_Wide/Angle/Detail),
        # the PostProcessVolume (WTK_PPV), and now props
        # (WTK_Prop_CuttingBoard/Plant/Bowl) -- an unconditional
        # delete-everything pass here would silently wipe all of them on the
        # next delete_and_reimport fallback run, forcing a full re-run of
        # setup_lighting_wtk.py / setup_cameras_wtk.py / place_props_wtk.py
        # just to get back to the current look. Fixed: skip any actor whose
        # label starts with "WTK_" or "CAM_" (the two label prefixes used by
        # every hand-authored WTK actor in this project -- see
        # setup_lighting_wtk.py, setup_cameras_wtk.py, place_props_wtk.py) so
        # only the actual Datasmith-imported actors (which carry Revit/
        # Datasmith's own auto-generated labels, e.g. "Casework_WTK_B30_B30",
        # "Walls_Basic_Wall_...", "Windows_Window-Fixed_...") are destroyed
        # and re-created. Confirmed by inspection that none of the
        # Datasmith-imported actor labels in this project's WTK_Import_Check
        # actor dump (Casework_*, Walls_*, Windows_*, Ceilings_*,
        # Furniture_FX-*, Generic_Models_*, Site_Location, Survey_Point, the
        # DatasmithSceneActor itself, etc.) start with "WTK_" or "CAM_", so
        # this filter cannot accidentally spare a Datasmith actor.
        # WtkReimp3_20260927 fix: this used to only delete LEVEL ACTORS and
        # then call scene.import_scene(IMPORT_DEST) straight onto the SAME,
        # still-populated /Game/WTK/Datasmith content folder. Root-caused
        # (tmp/WtkReimp3_20260927/all_actors_run1.txt): 20 stray exploded-B30
        # part actors from a PRIOR broken import survived a full pipeline run
        # against a verified-clean re-export. All 20 were StaticMeshActors
        # attached to the same DatasmithSceneActor
        # (WTK_Start-3DView-WTK_Datasmith_Export, related_actors_count=47,
        # not the true fresh-scene actor count), sharing one Revit
        # UniqueId prefix (29d25a25-...) -- i.e. genuine children re-spawned
        # from a stale on-disk DatasmithScene asset/StaticMesh packages under
        # IMPORT_DEST, not new geometry from the current .udatasmith (which
        # was independently confirmed clean by grep). destroy_actor() on a
        # DatasmithSceneActor's children does not reliably clear it from
        # that scene actor's own tracked actor list, and import_scene()
        # re-adds an actor for every asset still present under IMPORT_DEST --
        # so a level-actor-only delete is not sufficient for a truly fresh
        # reimport. Fix: delete ALL non-preserved level actors first (as
        # before), THEN delete the entire IMPORT_DEST content folder from
        # disk before calling import_scene() again, so no stale
        # DatasmithScene asset, StaticMesh, or Material package can be
        # re-spawned/re-referenced. Verified before this fix that nothing
        # else under /Game/WTK references IMPORT_DEST except this script
        # itself and the standalone (non-pipeline) bevel_test_b30.py
        # diagnostic script -- materials, props, cameras, and lighting all
        # live under separate /Game/WTK/{Materials,Props,...} paths.
        # WtkReimp3_20260927 second fix: the "WTK_"/"CAM_" label-PREFIX rule
        # above is exactly what broke the first fix. The level's
        # DatasmithSceneActor is auto-labelled after the export file itself
        # -- "WTK_Start-3DView-WTK_Datasmith_Export" -- which also starts
        # with "WTK_", so the old preserve rule spared it from destruction.
        # A stale DatasmithSceneActor left in the level keeps its own
        # related_actors list (confirmed: related_actors_count=47 on both
        # the broken run-1 and run-2 imports, with all 20 stray actors'
        # Revit UniqueIds identical across both runs, byte-for-byte the same
        # GUIDs -- proving they were never re-parsed from the .udatasmith
        # file at all, which independently grepped clean of those labels/
        # IDs both times) -- so import_scene() re-spawns its 20 tracked
        # stray children regardless of the content-folder delete added
        # above. Fixed by replacing the prefix match with (1) an explicit
        # allow-list of this project's actual authored actor labels, and
        # (2) an unconditional class-name check that destroys anything
        # Datasmith-related (DatasmithSceneActor and friends) no matter
        # what it's labelled, since a Datasmith-origin actor should never be
        # preserved across a delete_and_reimport pass by definition.
        WTK_PRESERVE_LABELS_EXACT = frozenset([
            "WTK_Sun", "WTK_SkyAtmosphere", "WTK_SkyLight", "WTK_HeightFog",
            "WTK_GroundPlane_Outside", "WTK_LED_W18", "WTK_LED_W30",
            "WTK_Fill_Room", "WTK_PPV",
        ])
        WTK_PRESERVE_LABEL_EXACT_PREFIXES = (
            "WTK_Prop_",  # WTK_Prop_CuttingBoard/Plant/Bowl(_PartN)
            "WTK_Blocker_",  # 2026-09-27 light-leak fix: hidden shadow-casting
            # blocker boxes plugging the ceiling/side-wall gap (see
            # setup_lighting_wtk.py's setup_light_leak_blockers() and
            # Docs/Pipeline.md's light-leak section).
            "WTK_Knob_",  # 2026-09-27 knob-smoothing pass: hand-spawned smooth
            # knob actors (smooth_knobs_wtk.py) -- not Datasmith-origin, must
            # survive delete_and_reimport the same way props/blockers do.
            # Confirmed safe: no genuine Datasmith actor label in this
            # project starts with "WTK_Knob_" (hardware comes in as e.g.
            # "Casework_WTK_B30_B30", never "WTK_Knob_*").
        )
        CAM_PRESERVE_PREFIX = "CAM_"

        def is_datasmith_class(cls_name):
            return "Datasmith" in cls_name

        def is_preserved_authored_actor(label, cls_name):
            if is_datasmith_class(cls_name):
                # Never preserve a Datasmith-origin actor by label, even if
                # its auto-generated label happens to start with "WTK_" (the
                # DatasmithSceneActor is named after the export file, e.g.
                # "WTK_Start-3DView-WTK_Datasmith_Export").
                return False
            if label in WTK_PRESERVE_LABELS_EXACT:
                return True
            if label.startswith(WTK_PRESERVE_LABEL_EXACT_PREFIXES):
                return True
            if label.startswith(CAM_PRESERVE_PREFIX):
                return True
            return False

        # Engine-infrastructure classes that either can't be usefully
        # destroyed or shouldn't be (WorldSettings, the default brush/physics
        # volume UE creates in every new level) -- skip these by class name
        # rather than trying and swallowing the resulting exception, so the
        # destroyed/preserved counts stay meaningful.
        ENGINE_INFRA_CLASSES = ("WorldSettings", "Brush", "DefaultPhysicsVolume")
        try:
            unreal.EditorLevelLibrary.load_level(MAP_PATH)
            all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
            destroyed = 0
            preserved = 0
            skipped_infra = 0
            failed = 0
            destroyed_datasmith_scene_actors = 0
            for a in all_actors:
                cls = a.get_class().get_name()
                label = a.get_actor_label()
                if is_preserved_authored_actor(label, cls):
                    preserved += 1
                    continue
                if cls in ENGINE_INFRA_CLASSES:
                    skipped_infra += 1
                    continue
                if is_datasmith_class(cls):
                    destroyed_datasmith_scene_actors += 1
                try:
                    unreal.EditorLevelLibrary.destroy_actor(a)
                    destroyed += 1
                except Exception as dex:
                    failed += 1
                    log("Could not destroy actor %s (%s): %s" % (label, cls, dex))
            log("Deleted %d previous-import actors from %s (preserved %d authored WTK_*/CAM_* actors "
                "via allow-list; %d of the deleted actors were Datasmith-class, e.g. stale "
                "DatasmithSceneActor; skipped %d engine-infra actors; %d failed to destroy)."
                % (destroyed, MAP_PATH, preserved, destroyed_datasmith_scene_actors, skipped_infra, failed))

            # 2026-09-27 fix (WTK_Main_v2 rebuild, actor-count-doubling bug):
            # the destroy_actor() loop above only changes the level IN
            # MEMORY. A few lines below, this function switches to a
            # transient scratch level (new_level("_WtkReimportScratch"),
            # never saved -- deliberately, per the comment above) so the
            # about-to-be-deleted content folder's packages are fully
            # unloaded, then calls load_level(MAP_PATH) to switch back.
            # load_level() always reloads from disk -- if the just-destroyed
            # actors were never saved, the reload silently undoes every
            # destroy_actor() call above, and the subsequent import_scene()
            # then adds a second full set of actors on top of the
            # never-actually-removed first set (live-reproduced this pass:
            # 29 actors before, "Deleted 29 previous-import actors" logged,
            # then 58 actors after -- exactly double). Fixed: save the
            # destroy-loop's changes to disk now, before switching to the
            # scratch level, so the later load_level(MAP_PATH) reloads the
            # already-emptied level, not the stale pre-destroy one.
            world_after_destroy = unreal.EditorLevelLibrary.get_editor_world()
            destroy_saved_ok = unreal.EditorLevelLibrary.save_current_level()
            destroy_saved_ok2 = (
                unreal.EditorLoadingAndSavingUtils.save_map(world_after_destroy, MAP_PATH)
                if world_after_destroy else False
            )
            log("Saved post-destroy level state before scratch-level switch: "
                "save_current_level=%s save_map=%s" % (destroy_saved_ok, destroy_saved_ok2))

            # Second half of the fix: clear the stale Datasmith content
            # folder from disk so nothing can be re-spawned/re-referenced by
            # the fresh import_scene() call below.
            #
            # WtkReimp3_20260927 THIRD fix, live-verified as necessary: the
            # very first attempt at this (delete_directory() called
            # immediately after the actor-destroy loop, no GC in between)
            # crashed the whole process (import_run3.log): "ForceDeleteObject
            # failed ... this package is now potentially corrupt" for every
            # asset under IMPORT_DEST, "DeleteDirectory: Not all assets were
            # deleted", followed by "Error opening file" on the very next
            # import_scene() call trying to read those now-half-deleted
            # .uasset files, ending in a hard crash (Assertion failed:
            # !bHasFailed, AsyncLoading2.cpp -- process exit code 3, the
            # WTK_Import_Check.txt report never got written that run). Root
            # cause: the just-destroyed actors' StaticMeshComponents/scene
            # actor still held in-memory references to these packages at the
            # moment delete_directory() ran, so ForceDeleteObjects couldn't
            # fully unload them before overwriting/removing the files on
            # disk. Fixed by forcing a GC pass (collect_garbage()) after the
            # actor-destroy loop and before the directory delete, and by
            # making the whole block fail SAFE: if the directory still has
            # assets left after the delete attempt, treat that as fatal for
            # THIS run (don't proceed to import_scene() against a
            # partially-deleted, possibly corrupt content folder) rather than
            # crashing further downstream.
            #
            # WtkReimp3_20260927 FOURTH fix, live-verified as necessary:
            # collect_garbage() alone (previous attempt, import_run4.log)
            # was NOT sufficient -- every asset still failed to
            # ForceDeleteObject with the same "potentially corrupt" warning.
            # Root cause: WTK_Main itself is still the loaded/current level
            # at this point, and even after destroy_actor() on every
            # Datasmith-origin actor, the level's own transient references
            # (undo buffer, editor selection state, and the DatasmithScene
            # asset's own internal Actor-element bookkeeping) still pin the
            # StaticMesh/Material packages in memory until the level that
            # was referencing them is no longer the loaded level. Fixed by
            # switching to a transient empty level (new_level on a temp
            # path, not saved) before the directory delete, then switching
            # back to WTK_Main right after -- this fully unloads WTK_Main's
            # references first, per the same pattern the "first-time import"
            # path already uses (new_level() then import onto it).
            try:
                unreal.EditorLevelLibrary.new_level("/Game/WTK/Maps/_WtkReimportScratch")
            except Exception as scratch_ex:
                log("Could not switch to scratch level before content delete: %s" % scratch_ex)
            unreal.SystemLibrary.collect_garbage()
            editor_asset_lib = unreal.EditorAssetLibrary
            if editor_asset_lib.does_directory_exist(IMPORT_DEST):
                pre_delete_assets = editor_asset_lib.list_assets(IMPORT_DEST, recursive=True, include_folder=False)
                dir_deleted = editor_asset_lib.delete_directory(IMPORT_DEST)
                still_exists = editor_asset_lib.does_directory_exist(IMPORT_DEST)
                remaining_assets = (
                    editor_asset_lib.list_assets(IMPORT_DEST, recursive=True, include_folder=False)
                    if still_exists else []
                )
                log("Deleted stale Datasmith content folder %s (had %d assets on disk): delete_directory=%s, "
                    "still_exists=%s, remaining_assets=%d"
                    % (IMPORT_DEST, len(pre_delete_assets), dir_deleted, still_exists, len(remaining_assets)))
                if still_exists and len(remaining_assets) > 0:
                    log("ABORTING delete_and_reimport: %d asset(s) survived the content-folder delete "
                        "(likely still referenced in memory) -- proceeding to import_scene() against a "
                        "partially-deleted folder previously crashed the process (Assertion failed: "
                        "!bHasFailed, AsyncLoading2.cpp). Not attempting the reimport this run." % len(remaining_assets))
                    try:
                        unreal.EditorLevelLibrary.load_level(MAP_PATH)
                    except Exception:
                        pass
                    return "delete_and_reimport_ABORTED_unsafe_content_delete", False, None
            else:
                log("Datasmith content folder %s did not exist; nothing to delete." % IMPORT_DEST)
            # Switch back from the scratch level to WTK_Main before
            # importing -- import_scene() operates on whatever level is
            # currently loaded/active.
            unreal.EditorLevelLibrary.load_level(MAP_PATH)
        except Exception as e:
            log("Delete-previous-actors/content step failed: %s" % e)
            try:
                unreal.EditorLevelLibrary.load_level(MAP_PATH)
            except Exception:
                pass
            return "delete_and_reimport_ABORTED_exception", False, None

        scene = unreal.DatasmithSceneElement.construct_datasmith_scene_from_file(DATASMITH_FILE)
        if scene is None:
            log("ERROR: construct_datasmith_scene_from_file returned None (fallback path)")
            return "delete_and_reimport", False, None
        scene.import_scene(IMPORT_DEST)
        try:
            scene.destroy_scene()
        except Exception:
            pass
        save_imported_assets()
        run_material_remap()
        run_ceiling_flip_pass()
        run_bevel_pass()
        run_nanite_pass()
        run_knob_smoothing_pass()
        run_rail_grain_pass()
        # WTK prop-fix pass round 2 (2026-09-26): same robust-save hardening
        # as the datasmith_scene_update path above -- see that call site's
        # comment for the full rationale.
        world = unreal.EditorLevelLibrary.get_editor_world()
        saved_ok = unreal.EditorLevelLibrary.save_current_level()
        saved_ok2 = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log("REIMPORT_PATH_USED=delete_and_reimport saved(save_current_level=%s, save_map=%s)" % (saved_ok, saved_ok2))
        return "delete_and_reimport", (saved_ok or saved_ok2), scene

    # First-time import: fresh level, then straight import_scene.
    if map_exists:
        editor_asset_lib.delete_asset(MAP_PATH)
    unreal.EditorLevelLibrary.new_level(MAP_PATH)
    log("Created/level set: %s" % MAP_PATH)

    scene = unreal.DatasmithSceneElement.construct_datasmith_scene_from_file(DATASMITH_FILE)
    if scene is None:
        log("ERROR: construct_datasmith_scene_from_file returned None")
        return "first_import", False, None
    scene.import_scene(IMPORT_DEST)
    try:
        scene.destroy_scene()
    except Exception:
        pass
    save_imported_assets()
    run_material_remap()
    run_ceiling_flip_pass()
    run_bevel_pass()
    run_nanite_pass()
    run_knob_smoothing_pass()
    run_rail_grain_pass()
    # WTK prop-fix pass round 2 (2026-09-26): same robust-save hardening as
    # the other two ensure_map_and_import() paths above.
    world = unreal.EditorLevelLibrary.get_editor_world()
    saved_ok = unreal.EditorLevelLibrary.save_current_level()
    saved_ok2 = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("REIMPORT_PATH_USED=first_import saved(save_current_level=%s, save_map=%s)" % (saved_ok, saved_ok2))
    return "first_import", (saved_ok or saved_ok2), scene


def main():
    results = []
    actor_lines = []

    if not os.path.isfile(DATASMITH_FILE):
        log("ERROR: Datasmith file not found: %s" % DATASMITH_FILE)
        return

    reimport_path_used, saved_ok, _scene = ensure_map_and_import()
    log("import complete via path=%s save_current_level -> %s" % (reimport_path_used, saved_ok))

    if reimport_path_used.startswith("delete_and_reimport_ABORTED"):
        # WtkReimp3_20260927 fix: don't run the guard/measurement checks
        # against a level that ensure_map_and_import() deliberately left in
        # a torn-down-but-not-reimported state (actors already destroyed,
        # content-folder delete unsafe/incomplete, import_scene() never
        # called) -- that would either crash further downstream or write a
        # WTK_Import_Check.txt that looks like a normal FAIL but is actually
        # "no import was attempted this run at all", which is a materially
        # different, more urgent situation for whoever reads the report.
        log("ABORTED before import_scene(): writing a minimal report and stopping "
            "without running guard/measurement checks against a torn-down level.")
        try:
            with open(RESULTS_PATH, "w") as f:
                f.write("WTK Import Check — generated by import_wtk.py\n")
                f.write("Datasmith source: %s\n" % DATASMITH_FILE)
                f.write("Imported to: %s\n" % IMPORT_DEST)
                f.write("Reimport path used: %s\n" % reimport_path_used)
                f.write("\nFINAL status: ABORTED (see Saved/Logs for the ensure_map_and_import() "
                        "abort reason -- content-folder delete left stale assets behind, or an "
                        "exception was raised during the delete-previous-actors/content step; "
                        "the level's previous-import actors were destroyed but NO reimport was "
                        "attempted, so the level is currently in a torn-down, non-representative "
                        "state until the next successful run.)\n")
        except Exception as e:
            log("Could not write aborted-run report: %s" % e)
        return

    # --- Gather actors in the current level ---
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
    log("Total actors in level: %d" % len(all_actors))

    casework_bounds = None  # (min, max) unreal.Vector -- base cabinets only
    counter_top_z = None
    floor_top_z = None
    ceiling_bottom_z = None
    ceiling_found = False
    wall_env_min = None  # wall bounding envelope (outer)
    wall_env_max = None
    wall_thickness_cm = 15.24

    # Re-import hardening 2026-09-27, Task 3: track WHICH actor(s) fed each
    # measurement, logged into WTK_Import_Check.txt so a future corrupted
    # import is immediately traceable rather than requiring another
    # inspect_hardware.py-style investigation.
    floor_actors_used = []
    counter_actors_used = []
    ceiling_actors_used = []
    wall_actors_used = []

    actor_type_counts = {}

    for actor in all_actors:
        label = actor.get_actor_label()
        cls = actor.get_class().get_name()
        actor_type_counts[cls] = actor_type_counts.get(cls, 0) + 1

        origin, extent = actor.get_actor_bounds(only_colliding_components=False)
        bmin = origin - extent
        bmax = origin + extent

        actor_lines.append(
            "%s | class=%s | bounds_min=(%.3f,%.3f,%.3f) bounds_max=(%.3f,%.3f,%.3f)"
            % (label, cls, bmin.x, bmin.y, bmin.z, bmax.x, bmax.y, bmax.z)
        )

        if is_base_cabinet_label(label):
            if casework_bounds is None:
                casework_bounds = [bmin, bmax]
            else:
                casework_bounds[0] = unreal.Vector(
                    min(casework_bounds[0].x, bmin.x),
                    min(casework_bounds[0].y, bmin.y),
                    min(casework_bounds[0].z, bmin.z),
                )
                casework_bounds[1] = unreal.Vector(
                    max(casework_bounds[1].x, bmax.x),
                    max(casework_bounds[1].y, bmax.y),
                    max(casework_bounds[1].z, bmax.z),
                )

        # Revit's Datasmith export nests real geometry under empty parent
        # "container" actors that share the same label substring (e.g. the
        # Actor "Level_1_4__Head_Ceiling" has zero-size bounds and contains
        # a child StaticMeshActor "Ceilings_Basic_Ceiling_Generic" with the
        # real mesh bounds). Skip degenerate/zero-extent actors here so they
        # don't pollute the floor/ceiling/wall min/max aggregates below --
        # otherwise e.g. the empty ceiling container's bmin.z=0.0 wins the
        # min() over the real ceiling mesh's bmin.z=243.84.
        is_degenerate_bounds = (extent.x == 0.0 and extent.y == 0.0 and extent.z == 0.0)

        # Re-import hardening 2026-09-27, Task 3: any actor outside the
        # room's real XY footprint is ignored for ALL four measurements
        # below (the stray exploded-B30 parts from the corrupted reimport
        # mostly sit at the Datasmith assembly origin (0,0,0), well outside
        # the room -- see is_in_room_footprint's docstring).
        in_footprint = is_in_room_footprint(bmin, bmax)

        # Hardened selectors (Task 3): exact category-prefix matches instead
        # of loose substrings, per is_floor_label/is_hardened_ceiling_label/
        # is_wall_label's own docstrings above.
        if is_floor_label(label) and not is_degenerate_bounds and in_footprint:
            floor_top_z = bmax.z if floor_top_z is None else max(floor_top_z, bmax.z)
            floor_actors_used.append(label)

        if is_hardened_counter_label(label) and not is_degenerate_bounds and in_footprint:
            counter_top_z = bmax.z if counter_top_z is None else max(counter_top_z, bmax.z)
            counter_actors_used.append(label)

        if is_hardened_ceiling_label(label) and not is_degenerate_bounds and in_footprint:
            ceiling_found = True
            ceiling_bottom_z = bmin.z if ceiling_bottom_z is None else min(ceiling_bottom_z, bmin.z)
            ceiling_actors_used.append(label)

        if is_wall_label(label) and not is_degenerate_bounds and in_footprint:
            wall_actors_used.append(label)
            if wall_env_min is None:
                wall_env_min, wall_env_max = bmin, bmax
            else:
                wall_env_min = unreal.Vector(min(wall_env_min.x, bmin.x), min(wall_env_min.y, bmin.y), min(wall_env_min.z, bmin.z))
                wall_env_max = unreal.Vector(max(wall_env_max.x, bmax.x), max(wall_env_max.y, bmax.y), max(wall_env_max.z, bmax.z))

    # Re-import hardening 2026-09-27, Task 2: the import guard. Flag, don't
    # delete (per the task spec). Fails the import check (below) unless
    # every unexpected actor is covered by an explicit allow-list.
    unexpected_actors, guard_passed = run_import_guard(all_actors)

    with open(ACTORS_LOG, "w") as f:
        f.write("\n".join(actor_lines))
        f.write("\n\n--- Actor type counts ---\n")
        for k, v in sorted(actor_type_counts.items()):
            f.write("%s: %d\n" % (k, v))

    # --- Materials + static mesh count ---
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    mat_assets = asset_reg.get_assets_by_path(IMPORT_DEST, recursive=True)
    material_names = []
    static_mesh_count = 0
    for a in mat_assets:
        cls_name = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else str(a.asset_class)
        if "Material" in cls_name:
            material_names.append(str(a.asset_name))
        if "StaticMesh" in cls_name:
            static_mesh_count += 1

    with open(ACTORS_LOG, "a") as f:
        f.write("\n--- Imported materials (%d) ---\n" % len(material_names))
        for m in sorted(set(material_names)):
            f.write(m + "\n")
        f.write("\n--- Static mesh asset count: %d ---\n" % static_mesh_count)

    # --- Checks ---
    def fmt_check(name, expected, actual):
        if actual is None:
            return "%s: FAIL (no data found, expected %.2f cm)" % (name, expected)
        diff = abs(actual - expected)
        status = "PASS" if diff <= TOL_CM else "FAIL"
        return "%s: %s (expected %.2f cm, got %.2f cm, diff %.2f cm)" % (name, status, expected, actual, diff)

    run_length = None
    if casework_bounds is not None:
        dx = casework_bounds[1].x - casework_bounds[0].x
        dy = casework_bounds[1].y - casework_bounds[0].y
        run_length = max(abs(dx), abs(dy))

    counter_height_above_floor = None
    if counter_top_z is not None and floor_top_z is not None:
        counter_height_above_floor = counter_top_z - floor_top_z

    ceiling_height_above_floor = None
    if ceiling_found and ceiling_bottom_z is not None and floor_top_z is not None:
        ceiling_height_above_floor = ceiling_bottom_z - floor_top_z

    # Room interior = wall bounding envelope minus 2x wall thickness on each axis
    # (thickness subtracted once per side, i.e. 2x thickness total per dimension).
    room_dim_a = room_dim_b = None
    if wall_env_min is not None and wall_env_max is not None:
        room_dim_a = (wall_env_max.x - wall_env_min.x) - (2.0 * wall_thickness_cm)
        room_dim_b = (wall_env_max.y - wall_env_min.y) - (2.0 * wall_thickness_cm)

    lines = []
    lines.append("WTK Import Check — generated by import_wtk.py")
    lines.append("Datasmith source: %s" % DATASMITH_FILE)
    lines.append("Imported to: %s" % IMPORT_DEST)
    lines.append("Reimport path used: %s" % reimport_path_used)
    lines.append("Map saved: %s (save_current_level=%s)" % (MAP_PATH, saved_ok))
    lines.append("")
    lines.append(fmt_check("(a) Base cabinet run length (DB18/SB36/B30/DB24/B12, excl. FX-)", 304.8, run_length))
    lines.append(fmt_check("(b) Countertop (FX-01) top Z above floor", 91.44, counter_height_above_floor))
    lines.append("    Floor actor(s) used: %s" % (floor_actors_used or "NONE"))
    lines.append("    Counter actor(s) used: %s" % (counter_actors_used or "NONE"))
    if ceiling_found:
        lines.append(fmt_check("(c) Ceiling bottom Z above floor", 243.84, ceiling_height_above_floor))
    else:
        lines.append("(c) Ceiling bottom Z above floor: MISSING (no actor with label starting 'Ceilings_' found in-footprint)")
    lines.append("    Ceiling actor(s) used: %s" % (ceiling_actors_used or "NONE"))
    if room_dim_a is not None:
        lines.append(
            "(d) Room interior dims (wall envelope - 2x%.2fcm thickness): %.2f cm x %.2f cm (expect ~365.76 x 426.72 cm)"
            % (wall_thickness_cm, room_dim_a, room_dim_b)
        )
    else:
        lines.append("(d) Room interior dims: FAIL (no wall bounds found)")
    lines.append("    Wall actor(s) used (%d): %s" % (len(wall_actors_used), wall_actors_used or "NONE"))
    lines.append("")
    lines.append("Total actors: %d" % len(all_actors))
    lines.append("Static mesh assets: %d" % static_mesh_count)
    lines.append("Distinct materials imported: %d" % len(set(material_names)))
    for m in sorted(set(material_names)):
        lines.append("  - %s" % m)

    # Re-import hardening 2026-09-27, Task 2: import guard result. Any
    # UNEXPECTED_ACTOR not covered by an explicit allow-list fails the whole
    # import check regardless of how (a)-(d) came out, per the task spec.
    lines.append("")
    lines.append("--- Import guard (unexpected actors) ---")
    if unexpected_actors:
        lines.append("UNEXPECTED_ACTOR_COUNT: %d" % len(unexpected_actors))
        for lbl in unexpected_actors:
            lines.append("  UNEXPECTED_ACTOR: %s" % lbl)
    else:
        lines.append("UNEXPECTED_ACTOR_COUNT: 0")
    lines.append("Import guard: %s" % ("PASSED" if guard_passed else "FAILED"))

    checks_passed = (
        run_length is not None and abs(run_length - 304.8) <= TOL_CM
        and counter_height_above_floor is not None and abs(counter_height_above_floor - 91.44) <= TOL_CM
        and ceiling_found and ceiling_height_above_floor is not None and abs(ceiling_height_above_floor - 243.84) <= TOL_CM
        and room_dim_a is not None
    )
    final_status = "PASS" if (checks_passed and guard_passed) else "FAIL"
    lines.append("")
    if final_status == "FAIL" and unexpected_actors:
        lines.append("FINAL status: FAIL (unexpected actors: %s)" % unexpected_actors)
    else:
        lines.append("FINAL status: %s" % final_status)

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        f.write("\n".join(lines))

    for l in lines:
        log(l)

    log("WTK_IMPORT_DONE")


main()

# Fallback path: if launched via -ExecutePythonScript on full UnrealEditor.exe,
# quit the editor when done so the process terminates cleanly.
try:
    import sys
    if "-run=pythonscript" not in " ".join(sys.argv):
        unreal.SystemLibrary.quit_editor()
except Exception:
    pass
