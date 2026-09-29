"""
One-time window backplate texture import, split out from
setup_lighting_wtk.py's _import_backplate_texture() for the exact same
reason import_hdri_only.py exists: AssetImportTask-based import touches
ContentBrowser/Slate UI code and crashes under -run=pythonscript's headless
commandlet mode ("Assertion failed: CurrentApplication.IsValid()",
SlateApplication.h) -- confirmed live this pass (2026-09-28 realism pass,
WtkRealism_20260928): the JPG import itself completed successfully (the
Interchange log line "Interchange import completed ...WTK_ExteriorBackplate.jpg"
appears before the crash), but the immediately-following ContentBrowser sync
call the AssetTools import path triggers is what actually asserts -- so the
crash happens AFTER the texture asset is already written to disk, matching
this project's own established import_hdri_only.py precedent exactly. Run
this once via the full editor (not UnrealEditor-Cmd.exe, and not
-run=pythonscript -- this is the one operation in this codebase's own
documented pattern that requires the full editor binary):

  UnrealEditor.exe <proj>.uproject -ExecutePythonScript=<this file>

Idempotent (does_asset_exist() short-circuits a re-run) -- once the texture
exists at /Game/WTK/HDRI/T_WindowBackplate, setup_lighting_wtk.py's own
_import_backplate_texture() (called from setup_window_backplate()) just
loads the existing asset, which is safe under -run=pythonscript.
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_lighting_wtk as sl

_LOG = []


def log(msg):
    line = "[WTK_ImportBackplate] %s" % msg
    print(line)
    _LOG.append(line)


tex = sl.import_hdri_texture if False else None  # (unused; keeps import lint quiet)
tex = sl._import_backplate_texture()
log("Result: %s" % tex)
try:
    os.makedirs(r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkRealism_20260928", exist_ok=True)
    with open(r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkRealism_20260928\import_backplate_run.txt", "w") as f:
        f.write("\n".join(_LOG))
except Exception:
    pass

# Same as import_hdri_only.py: quit cleanly when run via the full editor
# (-ExecutePythonScript), not when run via -run=pythonscript.
try:
    if "-run=pythonscript" not in " ".join(sys.argv):
        unreal.SystemLibrary.quit_editor()
except Exception:
    pass
