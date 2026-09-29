"""
WTK Phase 5c-2 Task 1: set UV mode (UseWorldAligned=False) on ALL Material
Instances, and correct UVTiling to a physically-accurate value now that the
UV check confirmed UV set 0 is a real-unit-scale projection in FEET (not
degenerate, not a 0-1 atlas) on every sampled mesh (B30, FX-05 shelf, wall,
floor, FX-01 counter, DB18/SB36 painted cabinets, FX-04 backsplash -- see
tmp/Wtk5c2_20260926/uv_check_extended.txt and uv_check_b30.txt).

UVTiling formula: UVTiling = 1 / tile_size_in_feet, since UV set 0's units
are feet (confirmed: B30's 30in width spans 2.5 UV units = exactly 30in/12 =
2.5ft; FX-01's countertop run spans UV extent 10.1667 against physical
309.88cm = 10.1667ft, an exact match).

Tile sizes (task spec):
  Oak (white_oak_veneer)      ~50cm  = 1.6404 ft -> UVTiling = 0.6096
    (2026-09-27 WtkPTFix pass: raised to 90cm -> UVTiling = 0.3387 on
    MI_Oak_Rift_Stained/MI_Oak_Shelf ONLY -- see TILE_SIZE_CM below and
    Docs/Lighting.md's new path-tracer-glass/oak-seam section. Root cause of
    the CAM_Detail horizontal seam across both B30 doors and the centre
    stiles: the old 50cm tile repeat boundary landed mid-door on every
    door-height mesh, at a height matching the observed seam almost exactly.
    90cm covers a full door height (B30 doors are >=76cm tall) with margin,
    in one tile, no visible repeat boundary on any door face.)
  Paint/Wall (white_plaster_02) 1.5m = 4.9213 ft -> UVTiling = 0.2032
  Stone (Marble020)           ~1.2m  = 3.9370 ft -> UVTiling = 0.2540
    (Marble020's physical tile size is NOT published in LICENSES.md /
    ambientCG's catalogue -- confirmed by inspection of
    05_Unreal/WTK_SourceTextures/LICENSES.md section 3, "ambientCG does not
    publish explicit real-world dimensions for this texture" -- so the
    task's own fallback value of ~1.2m is used, matching the existing
    TextureSize_cm=120 already set on MI_Stone_HonedCream.)
    (2026-09-28 realism pass: raised to 2.6m -- see TILE_SIZE_CM below.
    ROOT-CAUSE NOTE, found this pass: this script runs AFTER
    build_wtk_material_instances.py in the mandated re-run order and
    unconditionally forces UseWorldAligned=False (line ~98) plus computes
    UVTiling from the mesh's own UV set (feet-based), which OVERRIDES
    build_wtk_material_instances.py's UseWorldAligned=True/TextureSize_cm=260
    for MI_Stone_HonedCream -- a TextureSize_cm-only edit in that other
    script has ZERO effect on the actually-rendered tile scale once this
    script re-runs, since TextureSize_cm is only consulted when
    UseWorldAligned=True, and this script always sets it False. The real,
    load-bearing lever for the counter/backsplash's veining scale is THIS
    file's TILE_SIZE_CM table -- verified by a live before/after CAM_Wide
    re-render (see Docs/Lighting.md Section 20) after fixing it here.)
  Floor (WoodFloor051)        180cm  = 5.9055 ft -> UVTiling = 0.1694
  Metals (brass/steel)        ~30cm  = 0.9843 ft -> UVTiling = 1.0160

This also sets UseWorldAligned=False everywhere (world-aligned was a
placeholder in the master that has no real triplanar sample chain -- see
Materials.md "Open item" -- so leaving it True was inert/misleading; UV mode
is the now-confirmed-correct path for every checked mesh).

Run headless:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
"""
import unreal
import os

MEL = unreal.MaterialEditingLibrary
MI_DIR = "/Game/WTK/Materials"
OUT_PATH = r"C:\Users\Sam\Documents\Chess\tmp\Wtk5c2_20260926\set_uv_mode_tiling.txt"

FT_TO_CM = 30.48

# MI name -> tile size in cm (feet computed below).
TILE_SIZE_CM = {
    # 2026-09-27 WtkPTFix pass: 50.0 -> 90.0 (see module docstring's Oak
    # entry above for the seam root-cause/fix reasoning).
    "MI_Oak_Rift_Stained": 90.0,
    "MI_Oak_Shelf": 90.0,
    "MI_Paint_WarmIvory": 150.0,
    # WtkThree_20260928 (Issue 3): lowered 150.0 -> 60.0cm. ROOT-CAUSE NOTE,
    # same class of bug as MI_Stone_HonedCream's own documented finding
    # above: this script runs AFTER build_wtk_material_instances.py in the
    # mandated re-run order and unconditionally sets UseWorldAligned=False +
    # computes UVTiling from this table for every MI in
    # UV_CAPABLE_MASTERS_MIS (MI_Wall_WarmOffWhite included) -- silently
    # overriding build_wtk_material_instances.py's own
    # UseWorldAligned=True/TextureSize_cm=60.0 set on that MI for the Issue-3
    # orange-peel-scale fix. A TextureSize_cm-only edit in that other script
    # has ZERO effect on the actually-rendered normal-map tile scale once
    # this script re-runs -- THIS table is the real, load-bearing lever.
    # 60cm (vs the previous 150cm) makes the SAME plaster normal/roughness
    # maps repeat at a much finer physical scale -- smaller, more numerous
    # bumps per unit wall area, closer to a real mm-scale orange-peel texture
    # than the old 150cm tile (which stretched the same bump map over a much
    # larger area, reading almost imperceptibly smooth at normal viewing
    # distance).
    "MI_Wall_WarmOffWhite": 60.0,
    "MI_Stone_HonedCream": 260.0,  # 2026-09-28 realism pass: 120->260cm, slab-scale flowing veins vs tiny repetitive speckle (see module docstring)
    "MI_Brass_Satin": 30.0,
    "MI_Brass_Knob_Radial": 5.0,  # knob-scale override retained (task's own MI note); not the generic 30cm metal default
    "MI_Steel_Brushed": 30.0,
    "MI_Floor_Oak": 180.0,
    # No texture / flat-tint MIs: UVTiling is inert (no UV-sampled texture to scale), leave at 1.0.
    "MI_Ceiling_FlatWhite": None,
    "MI_WindowFrame_White": None,
    "MI_Glass_Clear": None,   # different master (M_WTK_Glass), no UV/tiling params
    "MI_LED_3000K": None,     # different master (M_WTK_Emissive), no UV/tiling params
}

# MIs whose parent master has the UseWorldAligned/UVTiling params (Opaque/ClearCoat).
UV_CAPABLE_MASTERS_MIS = [
    "MI_Oak_Rift_Stained", "MI_Oak_Shelf", "MI_Paint_WarmIvory", "MI_Wall_WarmOffWhite",
    "MI_Ceiling_FlatWhite", "MI_Stone_HonedCream", "MI_Brass_Satin", "MI_Brass_Knob_Radial",
    "MI_Steel_Brushed", "MI_Floor_Oak", "MI_WindowFrame_White",
]


def log(lines, msg):
    print(msg)
    lines.append(msg)


def main():
    lines = []
    log(lines, "=== WTK5c-2 Task 1: set UV mode + tiling start ===")

    for mi_name in UV_CAPABLE_MASTERS_MIS:
        path = "%s/%s" % (MI_DIR, mi_name)
        mi = unreal.EditorAssetLibrary.load_asset(path)
        if mi is None:
            log(lines, "ERROR: could not load %s" % path)
            continue

        # UseWorldAligned=False everywhere (UV mode is the confirmed-correct path).
        MEL.set_material_instance_static_switch_parameter_value(mi, "UseWorldAligned", False)

        tile_cm = TILE_SIZE_CM.get(mi_name)
        if tile_cm is not None:
            tile_ft = tile_cm / FT_TO_CM
            uv_tiling = 1.0 / tile_ft
            MEL.set_material_instance_scalar_parameter_value(mi, "UVTiling", uv_tiling)
            log(lines, "%s: UseWorldAligned=False, tile=%.2fcm (%.4fft), UVTiling=%.4f"
                % (mi_name, tile_cm, tile_ft, uv_tiling))
        else:
            log(lines, "%s: UseWorldAligned=False, UVTiling left at default (no texture to scale)" % mi_name)

        unreal.EditorAssetLibrary.save_loaded_asset(mi, only_if_is_dirty=False)

    # Oak grain rotation: verified via uv_orientation_check.py that U runs
    # vertically on B30's unwrap (avg |dU|/|dZ|=0.105 vs |dV|/|dZ|=0.033,
    # ~3.2x stronger U-Z correlation, tmp/Wtk5c2_20260926/uv_orientation_check.txt).
    # Standard wood-grain textures (T_Oak_Color) run their grain along V.
    # Since U (not V) is vertical here, a 90-deg rotation is required to swap
    # U/V so the grain reads vertically in world space -- confirming (not
    # just placeholder-assuming) the existing UVRotation_deg=90 on
    # MI_Oak_Rift_Stained is correct.
    oak_stiles = unreal.EditorAssetLibrary.load_asset("%s/MI_Oak_Rift_Stained" % MI_DIR)
    if oak_stiles is not None:
        MEL.set_material_instance_scalar_parameter_value(oak_stiles, "UVRotation_deg", 90.0)
        unreal.EditorAssetLibrary.save_loaded_asset(oak_stiles, only_if_is_dirty=False)
        log(lines, "MI_Oak_Rift_Stained: UVRotation_deg=90 CONFIRMED (U is vertical on unwrap; grain runs V in source tex)")

    # Shelf: grain along the shelf's long axis (horizontal), rotation 0 kept
    # as-is per the existing MI (not independently re-verified against FX-05's
    # own UV-to-position correlation in this pass -- see report / Materials.md
    # for the flagged follow-up if a stronger guarantee is wanted).
    oak_shelf = unreal.EditorAssetLibrary.load_asset("%s/MI_Oak_Shelf" % MI_DIR)
    if oak_shelf is not None:
        MEL.set_material_instance_scalar_parameter_value(oak_shelf, "UVRotation_deg", 0.0)
        unreal.EditorAssetLibrary.save_loaded_asset(oak_shelf, only_if_is_dirty=False)
        log(lines, "MI_Oak_Shelf: UVRotation_deg=0 kept (grain along length, per original recipe; not independently re-verified this pass)")

    log(lines, "WTK5C2_SET_UV_MODE_TILING_DONE")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))


main()
