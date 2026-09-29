"""
2026-09-27 day/night preset pass: single driver that runs
setup_lighting_wtk.main() then setup_cameras_wtk.main() in ONE process, so
both scripts see the same WTK_LIGHT_PRESET env var and both write to the
same already-loaded level before a single final save -- avoids relying on
each standalone script's own load_map()/save chain being consistent across
two separate process launches for what is really one atomic "apply this
preset" operation.

Run with:
  set WTK_LIGHT_PRESET=day_soft   (or day_sun / night_led / night_led_cans)
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -stdout
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_LOG_LINES = []


def log(msg):
    line = "[WTK_ApplyPreset] %s" % msg
    print(line)
    _LOG_LINES.append(line)


def flush():
    try:
        with open(r"C:\Users\Sam\Documents\Chess\tmp\WtkRelight2_20260927\apply_preset_run.txt", "a") as f:
            f.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass


def main():
    preset = os.environ.get("WTK_LIGHT_PRESET", "day_sun")
    log("=== Applying preset: %s ===" % preset)

    import setup_lighting_wtk
    setup_lighting_wtk.main()
    log("setup_lighting_wtk.main() done.")

    import setup_cameras_wtk
    setup_cameras_wtk.main()
    log("setup_cameras_wtk.main() done.")

    log("=== Preset %s applied and saved. ===" % preset)
    flush()


if __name__ == "__main__":
    main()
