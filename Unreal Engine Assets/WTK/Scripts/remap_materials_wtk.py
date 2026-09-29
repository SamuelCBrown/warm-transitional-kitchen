"""
WTK Phase 5c step 5: remap Datasmith-imported source materials to the WTK
Material Instances, by actor-label regex + source-material-name rule table.
Idempotent: safe to run after every import_wtk.py reimport.

Run headless (standalone):
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput

Also called from the end of import_wtk.py (after save_imported_assets(), before
save_current_level()) so every reimport re-applies the mapping automatically.
"""
import unreal
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH
MI_DIR = "/Game/WTK/Materials"
LOG_PATH = r"C:\Users\Sam\Documents\Chess\tmp\Wtk5c_20260926\remap_results.txt"

# Rule table: list of (actor_label_regex, source_material_name, mi_path).
# actor_label_regex may be None to match any actor (source-material name is
# then the only discriminator). Evaluated top-to-bottom; first match wins.
RULES = [
    # Oak: two different MI targets depending on which part of the run.
    (r"Casework.*B30", "Oak_StainedWarmBrown", "%s/MI_Oak_Rift_Stained" % MI_DIR),
    (r"FX-05", "Oak_StainedWarmBrown", "%s/MI_Oak_Shelf" % MI_DIR),
    # Fallback for Oak_StainedWarmBrown elsewhere (default to the stained MI).
    (None, "Oak_StainedWarmBrown", "%s/MI_Oak_Rift_Stained" % MI_DIR),

    (None, "Paint_WarmIvory", "%s/MI_Paint_WarmIvory" % MI_DIR),
    (None, "Stone_HonedCream", "%s/MI_Stone_HonedCream" % MI_DIR),

    # Metal_SatinBrass: knob/pull-specific radial MI if the label says "Knob",
    # else the linear satin brass MI.
    (r"Knob", "Metal_SatinBrass", "%s/MI_Brass_Knob_Radial" % MI_DIR),
    (None, "Metal_SatinBrass", "%s/MI_Brass_Satin" % MI_DIR),

    (None, "Steel_Brushed", "%s/MI_Steel_Brushed" % MI_DIR),
    (None, "Wall_WarmOffWhite", "%s/MI_Wall_WarmOffWhite" % MI_DIR),
    (None, "Glass_Clear", "%s/MI_Glass_Clear" % MI_DIR),
    (None, "Light_LED3000K", "%s/MI_LED_3000K" % MI_DIR),
    (None, "Default_Floor", "%s/MI_Floor_Oak" % MI_DIR),
    (None, "RNT_Material", "%s/MI_Ceiling_FlatWhite" % MI_DIR),

    # Window family: two source material names both map to the same MI.
    (None, "Clad_-_White", "%s/MI_WindowFrame_White" % MI_DIR),
    (None, "Wood_-_Stained", "%s/MI_WindowFrame_White" % MI_DIR),
]


def log(lines, msg):
    print(msg)
    lines.append(msg)


# Reverse index: MI asset base name -> set of MI paths that already ARE that
# name (so a slot already carrying e.g. "MI_Oak_Rift_Stained" -- because a
# prior remap pass ran and a later reimport's delete_and_reimport step
# reused/recreated actors whose StaticMeshComponent default/override
# materials still point at the previously-assigned MI, rather than reverting
# to the raw Datasmith source material name -- is recognized as "already
# correctly assigned" instead of falling through to UNMAPPED. Confirmed
# empirically in Phase 5c-2: after rebuilding the masters/MIs and rerunning
# import_wtk.py, all 52 slots showed up already carrying MI names (e.g.
# "MI_Stone_HonedCream") rather than Datasmith source names (e.g.
# "Stone_HonedCream"), because the Datasmith reimport path is not a full
# from-scratch texture/material reassignment -- it's a delete+recreate of
# actors against the SAME (already-saved) StaticMesh assets/material slots.
ALL_MI_PATHS = set(mi_path for _, _, mi_path in RULES)
ALL_MI_BASENAMES = set(p.rsplit("/", 1)[-1] for p in ALL_MI_PATHS)


def find_mi_target(actor_label, source_mat_name, lines):
    # Already-correct case: the slot's current material IS one of our MIs.
    if source_mat_name in ALL_MI_BASENAMES:
        return "%s/%s" % (MI_DIR, source_mat_name)
    for label_re, src_name, mi_path in RULES:
        if src_name != source_mat_name:
            continue
        if label_re is not None and not re.search(label_re, actor_label or ""):
            continue
        return mi_path
    return None


def main():
    lines = []
    log(lines, "=== WTK5c material remap start ===")

    # 2026-09-27 fix (WTK_Main_v2 clean-room rebuild): when run in-process
    # from import_wtk.py's first_import path, the freshly created level
    # (new_level() + import_scene(), with the newly imported actors only in
    # memory) has NOT been saved to disk yet at the point this function is
    # called. does_asset_exist(MAP_PATH) can still return False for a level
    # that only exists in memory, and even when it returns True (e.g. a
    # brand-new empty package created by new_level() before any content was
    # added), an unconditional load_level(MAP_PATH) here would reload from
    # disk and silently wipe the in-memory, not-yet-saved import actors --
    # exactly the bug that produced "Total actors: 0" on the first-ever
    # import into a new map. Guard: only reload from disk if the currently
    # loaded editor world isn't already MAP_PATH.
    current_world = unreal.EditorLevelLibrary.get_editor_world()
    current_world_path = current_world.get_path_name().split(".")[0] if current_world else ""
    already_on_map = current_world_path == MAP_PATH

    if not already_on_map:
        if not unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
            log(lines, "ERROR: map %s does not exist -- run import_wtk.py first." % MAP_PATH)
            return
        unreal.EditorLevelLibrary.load_level(MAP_PATH)
    else:
        log(lines, "Already on %s in-memory (skipping load_level to avoid discarding "
                   "unsaved just-imported actors)." % MAP_PATH)

    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()

    # Cache loaded MI assets so repeated lookups don't re-hit the asset registry.
    mi_cache = {}

    def load_mi(path):
        if path not in mi_cache:
            mi_cache[path] = unreal.EditorAssetLibrary.load_asset(path)
        return mi_cache[path]

    assigned = 0
    unmapped = []
    inspected_slots = 0

    for actor in all_actors:
        label = actor.get_actor_label()
        smcs = actor.get_components_by_class(unreal.StaticMeshComponent)
        for comp in smcs:
            sm = comp.static_mesh
            if sm is None:
                continue
            num_slots = sm.get_num_sections(0) if hasattr(sm, "get_num_sections") else None
            # Use the StaticMeshComponent's material slots (override-material
            # count), which matches the mesh's material-slot count.
            try:
                num_materials = comp.get_num_materials()
            except Exception:
                num_materials = 0

            inspected_slots += num_materials

            for slot_index in range(num_materials):
                current_mat = comp.get_material(slot_index)
                if current_mat is None:
                    continue
                current_name = current_mat.get_name()

                mi_path = find_mi_target(label, current_name, lines)
                if mi_path is None:
                    unmapped.append("%s | slot %d | material=%s" % (label, slot_index, current_name))
                    continue

                mi_asset = load_mi(mi_path)
                if mi_asset is None:
                    log(lines, "ERROR: MI asset not found: %s (needed for %s | slot %d | %s)" % (mi_path, label, slot_index, current_name))
                    unmapped.append("%s | slot %d | material=%s (MI MISSING: %s)" % (label, slot_index, current_name, mi_path))
                    continue

                # WTK prop-fix pass round 2 (2026-09-26) audit finding: the
                # coordinator found place_props_wtk.py's actor/component
                # mutations silently failed to persist because modify() was
                # never called first -- comp.set_material() here has the
                # same risk (never confirmed to call Modify()/mark the
                # package dirty internally in this UE 5.7 Python binding).
                # Not independently re-verified against a live rerun this
                # pass (remap wasn't re-run -- no master-material rebuild
                # happened this pass, per Pipeline.md's own "MI-only change
                # doesn't need the master rebuild" rule) -- fixed defensively.
                comp.modify()
                comp.set_material(slot_index, mi_asset)
                assigned += 1
                log(lines, "ASSIGNED  %-45s slot %d  %-24s -> %s" % (label, slot_index, current_name, mi_path))

    log(lines, "")
    log(lines, "--- Summary ---")
    log(lines, "Slots inspected: %d" % inspected_slots)
    log(lines, "Assigned: %d" % assigned)
    log(lines, "Unmapped: %d" % len(unmapped))
    for u in unmapped:
        log(lines, "  UNMAPPED: %s" % u)

    # WTK prop-fix pass round 2 (2026-09-26): robust save, matching the fix
    # applied to place_props_wtk.py -- save_current_level() alone was found
    # to silently no-op there when the mutated actors/components were never
    # explicitly modify()'d first. The comp.modify() fix above addresses the
    # root cause for this script's own mutations; save_map() is added here
    # as the same second, independent line of defence. NOT independently
    # re-verified by a live before/after .umap-timestamp check this pass
    # (remap wasn't rerun this pass).
    world = unreal.EditorLevelLibrary.get_editor_world()
    saved_ok = unreal.EditorLevelLibrary.save_current_level()
    saved_ok2 = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log(lines, "Level save after remap -> save_current_level=%s, save_map=%s" % (saved_ok, saved_ok2))
    log(lines, "WTK5C_REMAP_DONE")

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
