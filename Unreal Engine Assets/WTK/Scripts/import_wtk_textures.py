"""
WTK Phase 5c step 1: import source textures into /Game/WTK/Textures/<Material>/.

Run headless:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput

Idempotent: re-running re-imports over the same destination paths (AssetTools
import task with replace_existing=True), so it is safe to run again after a
source texture change.

Source: 05_Unreal/WTK_SourceTextures/ (see LICENSES.md for provenance).
Colour maps -> sRGB on, compression TC_Default.
Roughness/Metalness/AO/Displacement -> sRGB off, compression TC_Masks (Masks/Grayscale).
Normal maps -> compression TC_Normalmap, sRGB off, flip green OFF (source already DirectX).
HDRI -> imported as a TextureCube (HDR) reflection-capture-style source, dest /Game/WTK/Textures/HDRI/.
"""
import unreal
import os

SRC_ROOT = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK_SourceTextures"
DEST_ROOT = "/Game/WTK/Textures"
LOG_PATH = r"C:\Users\Sam\Documents\Chess\tmp\Wtk5c_20260926\texture_import_log.txt"

# (material folder name under DEST_ROOT, source file relative to SRC_ROOT, kind)
# kind in {"color", "mask", "normal", "hdri"}
TEXTURES = [
    # Oak (primary: white_oak_veneer 4K)
    ("Oak", "Oak/white_oak_veneer/white_oak_veneer_diff_4k.jpg", "color", "T_Oak_Color"),
    ("Oak", "Oak/white_oak_veneer/white_oak_veneer_rough_4k.jpg", "mask", "T_Oak_Roughness"),
    ("Oak", "Oak/white_oak_veneer/white_oak_veneer_nor_dx_4k.jpg", "normal", "T_Oak_Normal"),
    # Oak backup (oak_veneer_05, kept alongside for a quick swap if needed)
    ("Oak", "Oak/oak_veneer_05/oak_veneer_05_diff_2k.jpg", "color", "T_Oak_Backup_Color"),
    ("Oak", "Oak/oak_veneer_05/oak_veneer_05_rough_2k.jpg", "mask", "T_Oak_Backup_Roughness"),
    ("Oak", "Oak/oak_veneer_05/oak_veneer_05_nor_dx_2k.jpg", "normal", "T_Oak_Backup_Normal"),
    # Paint / Wall plaster (white_plaster_02 -- reused for Paint and Wall slots)
    ("Paint_WallPlaster", "Paint_WallPlaster/white_plaster_02/white_plaster_02_diff_2k.jpg", "color", "T_Plaster_Color"),
    ("Paint_WallPlaster", "Paint_WallPlaster/white_plaster_02/white_plaster_02_rough_2k.jpg", "mask", "T_Plaster_Roughness"),
    ("Paint_WallPlaster", "Paint_WallPlaster/white_plaster_02/white_plaster_02_nor_dx_2k.jpg", "normal", "T_Plaster_Normal"),
    # Stone (Marble020)
    ("Stone", "Stone/Marble020/Marble020_2K-JPG_Color.jpg", "color", "T_Stone_Color"),
    ("Stone", "Stone/Marble020/Marble020_2K-JPG_Roughness.jpg", "mask", "T_Stone_Roughness"),
    ("Stone", "Stone/Marble020/Marble020_2K-JPG_NormalDX.jpg", "normal", "T_Stone_Normal"),
    ("Stone", "Stone/Marble020/Marble020_2K-JPG_Displacement.jpg", "mask", "T_Stone_Displacement"),
    # Metal_Brushed (Metal009 linear + Metal051A radial)
    ("Metal_Brushed", "Metal_Brushed/Metal009/Metal009_2K-JPG_Color.jpg", "color", "T_Metal009_Color"),
    ("Metal_Brushed", "Metal_Brushed/Metal009/Metal009_2K-JPG_Roughness.jpg", "mask", "T_Metal009_Roughness"),
    ("Metal_Brushed", "Metal_Brushed/Metal009/Metal009_2K-JPG_Metalness.jpg", "mask", "T_Metal009_Metalness"),
    ("Metal_Brushed", "Metal_Brushed/Metal009/Metal009_2K-JPG_NormalDX.jpg", "normal", "T_Metal009_Normal"),
    ("Metal_Brushed", "Metal_Brushed/Metal051A/Metal051A_2K-JPG_Color.jpg", "color", "T_Metal051A_Color"),
    ("Metal_Brushed", "Metal_Brushed/Metal051A/Metal051A_2K-JPG_Roughness.jpg", "mask", "T_Metal051A_Roughness"),
    ("Metal_Brushed", "Metal_Brushed/Metal051A/Metal051A_2K-JPG_Metalness.jpg", "mask", "T_Metal051A_Metalness"),
    ("Metal_Brushed", "Metal_Brushed/Metal051A/Metal051A_2K-JPG_NormalDX.jpg", "normal", "T_Metal051A_Normal"),
    # Floor (WoodFloor051)
    ("Floor", "Floor/WoodFloor051/WoodFloor051_2K-JPG_Color.jpg", "color", "T_Floor_Color"),
    ("Floor", "Floor/WoodFloor051/WoodFloor051_2K-JPG_Roughness.jpg", "mask", "T_Floor_Roughness"),
    ("Floor", "Floor/WoodFloor051/WoodFloor051_2K-JPG_NormalDX.jpg", "normal", "T_Floor_Normal"),
    ("Floor", "Floor/WoodFloor051/WoodFloor051_2K-JPG_AmbientOcclusion.jpg", "mask", "T_Floor_AO"),
]

# HDRI handled separately (TextureCube import path differs from Texture2D).
HDRI_SRC = "HDRI/farmland_overcast/farmland_overcast_4k.hdr"
HDRI_DEST = "/Game/WTK/Textures/HDRI"
HDRI_NAME = "T_HDRI_FarmlandOvercast"


def log(lines, msg):
    print(msg)
    lines.append(msg)


def build_import_task(src_abs, dest_path, asset_name, kind):
    task = unreal.AssetImportTask()
    task.filename = src_abs
    task.destination_path = dest_path
    task.destination_name = asset_name
    task.automated = True
    task.save = True
    task.replace_existing = True
    task.replace_existing_settings = True

    options = unreal.TextureFactory()
    task.options = None  # texture import settings are applied post-import below
    return task


def apply_texture_settings(texture, kind):
    if texture is None:
        return
    if kind == "color":
        texture.srgb = True
        texture.compression_settings = unreal.TextureCompressionSettings.TC_DEFAULT
    elif kind == "mask":
        texture.srgb = False
        texture.compression_settings = unreal.TextureCompressionSettings.TC_MASKS
    elif kind == "normal":
        texture.srgb = False
        texture.compression_settings = unreal.TextureCompressionSettings.TC_NORMALMAP
        # Source maps are already DirectX (green channel down) per LICENSES.md;
        # do not flip green -- bFlipGreenChannel stays False (default).
        try:
            texture.set_editor_property("flip_green_channel", False)
        except Exception:
            pass
    unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)


def import_one(src_rel, dest_folder, asset_name, kind, lines):
    src_abs = os.path.join(SRC_ROOT, src_rel)
    if not os.path.isfile(src_abs):
        log(lines, "MISSING SOURCE: %s" % src_abs)
        return None
    dest_path = "%s/%s" % (DEST_ROOT, dest_folder)
    task = build_import_task(src_abs, dest_path, asset_name, kind)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.imported_object_paths)
    if not imported:
        log(lines, "IMPORT FAILED: %s -> %s/%s" % (src_rel, dest_path, asset_name))
        return None
    asset_path = imported[0]
    texture = unreal.EditorAssetLibrary.load_asset(asset_path)
    apply_texture_settings(texture, kind)
    log(lines, "OK  %-8s  %-50s -> %s" % (kind, src_rel, asset_path))
    return asset_path


def import_hdri(lines):
    src_abs = os.path.join(SRC_ROOT, HDRI_SRC)
    if not os.path.isfile(src_abs):
        log(lines, "MISSING SOURCE (HDRI): %s" % src_abs)
        return None
    task = unreal.AssetImportTask()
    task.filename = src_abs
    task.destination_path = HDRI_DEST
    task.destination_name = HDRI_NAME
    task.automated = True
    task.save = True
    task.replace_existing = True
    task.replace_existing_settings = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.imported_object_paths)
    if not imported:
        log(lines, "HDRI IMPORT FAILED: %s" % HDRI_SRC)
        return None
    asset_path = imported[0]
    tex = unreal.EditorAssetLibrary.load_asset(asset_path)
    cls_name = tex.get_class().get_name() if tex else "None"
    log(lines, "OK  hdri      %-50s -> %s (class=%s)" % (HDRI_SRC, asset_path, cls_name))
    if cls_name != "TextureCube":
        log(
            lines,
            "NOTE: %s imported as %s, not TextureCube. UE's default .hdr importer "
            "produces a Texture2D long/lat panorama by default; a TextureCube requires "
            "either 'Create long/lat cubemap' via the reflection-capture pipeline or "
            "conversion through an HDRIBackdrop / SkyLight cubemap workflow. Left as-is "
            "for now (not consumed by any material in this step; the task says 'for "
            "later use'). Flagged in Materials.md." % cls_name,
        )
    unreal.EditorAssetLibrary.save_loaded_asset(tex, only_if_is_dirty=False)
    return asset_path


def main():
    lines = []
    log(lines, "=== WTK5c texture import start ===")
    ok, fail = 0, 0
    for dest_folder, src_rel, kind, asset_name in TEXTURES:
        result = import_one(src_rel, dest_folder, asset_name, kind, lines)
        if result:
            ok += 1
        else:
            fail += 1
    hdri_result = import_hdri(lines)
    log(lines, "=== Texture import summary: %d ok, %d failed (textures only) ===" % (ok, fail))
    log(lines, "HDRI: %s" % ("ok" if hdri_result else "FAILED"))
    log(lines, "WTK5C_TEXTURES_DONE")

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        f.write("\n".join(lines))


main()

# Fallback path: if launched via -ExecutePythonScript on full UnrealEditor.exe
# (required because AssetTools.import_asset_tasks touches ContentBrowser/Slate
# UI code that asserts under -run=pythonscript's headless commandlet mode --
# confirmed empirically: "Assertion failed: CurrentApplication.IsValid()" in
# SlateApplication.h, raised from AssetTools.dll -> ContentBrowser.dll on the
# first import_asset_tasks call), quit the editor when done so the process
# terminates cleanly instead of leaving an idle editor window open.
try:
    import sys
    if "-run=pythonscript" not in " ".join(sys.argv):
        unreal.SystemLibrary.quit_editor()
except Exception:
    pass
