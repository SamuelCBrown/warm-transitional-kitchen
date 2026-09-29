"""
One-time HDRI texture import, split out from setup_lighting_wtk.py's
import_hdri_texture() because AssetImportTask-based import touches
ContentBrowser/Slate UI code and crashes under -run=pythonscript's headless
commandlet mode ("Assertion failed: CurrentApplication.IsValid()") -- the
same constraint already documented for prop/texture import elsewhere in this
project (place_props_wtk.py's own docstring, Docs/Materials.md's
"Environment notes"). Run this once via the full editor:

  UnrealEditor.exe <proj>.uproject -ExecutePythonScript=<this file>

Idempotent (does_asset_exist() short-circuits a re-run) -- once the texture
exists at /Game/WTK/HDRI/T_Farmland_Overcast, setup_lighting_wtk.py's own
import_hdri_texture() (called from setup_sky_dome(), day presets only) just
loads the existing asset, which is safe under -run=pythonscript.
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_lighting_wtk as sl

_LOG = []


def log(msg):
    line = "[WTK_ImportHDRI] %s" % msg
    print(line)
    _LOG.append(line)


tex = sl.import_hdri_texture()
log("Result: %s" % tex)
try:
    with open(r"C:\Users\Sam\Documents\Chess\tmp\WtkRelight2_20260927\import_hdri_run.txt", "w") as f:
        f.write("\n".join(_LOG))
except Exception:
    pass

# 2026-09-27 finding: unreal.SystemLibrary.quit_editor() crashed here with a
# "ModeManagerInteractiveToolsContext ... Object is not packaged" fatal error
# following an "EditorModeToolsSingleton.IsValid()" ensure failure -- the
# import completed successfully before this (confirmed via
# tmp/WtkRelight2_20260927/import_hdri_run.txt), so the crash is in editor
# shutdown, not the import itself, but it still produced a non-zero exit
# code and a scary-looking crash log. Using a hard process exit instead
# avoids running the engine's own (apparently unstable in this headless-ish
# full-editor context) shutdown path.
log("Import step complete -- exiting process directly (see this file's own comment for why "
    "quit_editor() is avoided here).")
try:
    with open(r"C:\Users\Sam\Documents\Chess\tmp\WtkRelight2_20260927\import_hdri_run.txt", "w") as f:
        f.write("\n".join(_LOG))
except Exception:
    pass
os._exit(0)
