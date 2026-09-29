"""
One-time level edit (2026-09-27 props-removal pass): deletes the 3 prop
actors (WTK_Prop_CuttingBoard, WTK_Prop_Bowl, WTK_Prop_Plant) and every
attached child actor (the plant's multi-mesh _Part1/2/3 children -- see
place_props_wtk.py's spawn_or_update_prop() docstring for why the plant has
children) from the level, then saves.

This is NOT part of the regular pipeline (it is not called from
import_wtk.py or any other script) -- run it once, standalone:

  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -stdout

The imported source assets under /Game/WTK/Props/ and place_props_wtk.py's
own code are left untouched (kept for possible future re-enable via its
PLACE_PROPS flag) -- only the LEVEL ACTORS are removed here.
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH

PROP_LABELS = ["WTK_Prop_CuttingBoard", "WTK_Prop_Bowl", "WTK_Prop_Plant"]


_LOG_LINES = []


def log(msg):
    line = "[WTK_RemoveProps] %s" % msg
    print(line)
    _LOG_LINES.append(line)


def _flush_log():
    try:
        with open(r"C:\Users\Sam\Documents\Chess\tmp\WtkRelight2_20260927\remove_props_run.txt", "w") as f:
            f.write("\n".join(_LOG_LINES))
    except Exception:
        pass


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    actor_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = actor_subsys.get_all_level_actors()

    to_delete = []
    for a in all_actors:
        label = a.get_actor_label()
        if label in PROP_LABELS or any(label.startswith(p + "_Part") for p in PROP_LABELS):
            to_delete.append(a)

    if not to_delete:
        log("No WTK_Prop_* actors found -- nothing to delete (already removed, or level not loaded correctly).")
    else:
        for a in to_delete:
            log("Deleting actor '%s' (%s)" % (a.get_actor_label(), a.get_class().get_name()))
            actor_subsys.destroy_actor(a)
        log("Deleted %d prop actor(s)." % len(to_delete))

    world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    saved_ok = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    log("save_map(%s) returned %s" % (MAP_PATH, saved_ok))
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)

    # Verify: re-scan and confirm none remain.
    remaining = [a.get_actor_label() for a in actor_subsys.get_all_level_actors()
                 if a.get_actor_label() in PROP_LABELS or any(a.get_actor_label().startswith(p + "_Part") for p in PROP_LABELS)]
    if remaining:
        log("WARNING: actors still present after delete+save: %s" % remaining)
    else:
        log("Verified: no WTK_Prop_* actors remain in the level.")
    log("WTK_REMOVE_PROPS_DONE")
    _flush_log()


if __name__ == "__main__":
    main()
