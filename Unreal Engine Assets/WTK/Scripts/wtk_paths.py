"""
Shared path constants for the WTK Unreal pipeline scripts.

Single source of truth for which map/import-destination the pipeline
scripts (import_wtk.py, remap_materials_wtk.py, setup_lighting_wtk.py,
setup_cameras_wtk.py, place_props_wtk.py) target. Change ACTIVE_MAP_PATH /
ACTIVE_IMPORT_DEST here to retarget the whole pipeline at once (e.g. from
the deprecated /Game/WTK/Maps/WTK_Main to /Game/WTK/Maps/WTK_Main_v2)
without editing every script individually.

Added 2026-09-27 during the WTK_Main_v2 clean-room rebuild.
"""

# --- Deprecated (kept, not deleted, per the 2026-09-27 rebuild task) ---
LEGACY_MAP_PATH = "/Game/WTK/Maps/WTK_Main"
LEGACY_IMPORT_DEST = "/Game/WTK/Datasmith"

# --- Current production target ---
V2_MAP_PATH = "/Game/WTK/Maps/WTK_Main_v2"
V2_IMPORT_DEST = "/Game/WTK/Datasmith_v2"

# --- Active selection: this is what every pipeline script imports ---
ACTIVE_MAP_PATH = V2_MAP_PATH
ACTIVE_IMPORT_DEST = V2_IMPORT_DEST
