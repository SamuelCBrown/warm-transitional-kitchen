"""
WTK close-range inspection helper (2026-09-27, Phase 5.1 last item).

Temporarily re-poses CAM_Detail for inspection close-ups, so the existing
LS_Test_CAM_Detail sequence + render_tests_wtk.py can render them, then
restores the camera exactly. Pose is chosen via env var WTK_INSPECT_POSE:
  A        countertop exposed left (-X) end + front edge corner
  B        sink cutout front edge
  C        crown molding end return on the W18 upper (+X end)
  restore  put CAM_Detail back from the saved JSON, then delete the JSON
The original camera state is saved once to STATE_PATH before the first pose.
Report: tmp/WtkP5Close_20260927/inspect_<pose>.txt
"""
import json
import math
import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH

OUT_DIR = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkP5Close_20260927"
STATE_PATH = os.path.join(OUT_DIR, "cam_detail_original.json")

# CAM_Detail's approved exposure is bias 2.8 at f/3.2; stopping down to f/8
# costs log2((8/3.2)^2) = 2.64 EV, so the bias is raised by the same amount.
INSPECT_APERTURE = 8.0
INSPECT_BIAS = 2.8 + 2 * math.log2(8.0 / 3.2)
INSPECT_FOCAL = 50.0


def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def _find(label):
    for a in _actors():
        if a.get_actor_label() == label:
            return a
    return None


def _bounds_of(substr, lines):
    hits = [a for a in _actors() if substr in a.get_actor_label()
            and not a.get_actor_label().startswith("WTK_")
            and isinstance(a, unreal.StaticMeshActor)]
    if not hits:
        raise RuntimeError("no StaticMeshActor with '%s' in its label" % substr)
    o, e = hits[0].get_actor_bounds(only_colliding_components=False)
    bmin, bmax = o - e, o + e
    lines.append("%s -> %s bounds min=(%.2f,%.2f,%.2f) max=(%.2f,%.2f,%.2f)"
                 % (substr, hits[0].get_actor_label(), bmin.x, bmin.y, bmin.z, bmax.x, bmax.y, bmax.z))
    return bmin, bmax


def _look_at(loc, target):
    d = target - loc
    yaw = math.degrees(math.atan2(d.y, d.x))
    pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
    return unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw)


def _cam_state(cam):
    comp = cam.camera_component
    loc = cam.get_actor_location()
    rot = cam.get_actor_rotation()
    pps = comp.get_editor_property("post_process_settings")
    return {
        "loc": [loc.x, loc.y, loc.z],
        "rot": [rot.pitch, rot.yaw, rot.roll],
        "focal": comp.get_editor_property("current_focal_length"),
        "aperture": comp.get_editor_property("current_aperture"),
        "focus": comp.get_editor_property("focus_settings").get_editor_property("manual_focus_distance"),
        "bias": pps.get_editor_property("auto_exposure_bias"),
    }


def _apply(cam, loc, rot, focal, aperture, focus, bias):
    cam.modify()
    comp = cam.camera_component
    comp.modify()
    cam.set_actor_location(loc, False, False)
    cam.set_actor_rotation(rot, False)
    comp.set_editor_property("current_focal_length", focal)
    comp.set_editor_property("current_aperture", aperture)
    fs = comp.get_editor_property("focus_settings")
    fs.set_editor_property("manual_focus_distance", focus)
    comp.set_editor_property("focus_settings", fs)
    pps = comp.get_editor_property("post_process_settings")
    pps.set_editor_property("auto_exposure_bias", bias)
    pps.set_editor_property("override_auto_exposure_bias", True)
    comp.set_editor_property("post_process_settings", pps)


def main():
    pose = os.environ.get("WTK_INSPECT_POSE", "").strip()
    lines = ["pose=%s" % pose]
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    cam = _find("CAM_Detail")
    if cam is None:
        raise RuntimeError("CAM_Detail not found")

    if pose == "restore":
        if not os.path.exists(STATE_PATH):
            lines.append("nothing to restore (no saved state)")
        else:
            s = json.load(open(STATE_PATH))
            _apply(cam, unreal.Vector(*s["loc"]), unreal.Rotator(pitch=s["rot"][0], yaw=s["rot"][1], roll=s["rot"][2]),
                   s["focal"], s["aperture"], s["focus"], s["bias"])
            lines.append("restored: %s" % json.dumps(s))
            os.remove(STATE_PATH)
    else:
        if not os.path.exists(STATE_PATH):
            json.dump(_cam_state(cam), open(STATE_PATH, "w"))
            lines.append("saved original CAM_Detail state")
        if pose == "A":
            bmin, bmax = _bounds_of("FX-01", lines)
            target = unreal.Vector(bmin.x + 4.0, bmin.y + 2.0, bmax.z - 1.5)
            loc = target + unreal.Vector(-30.0, -40.0, 22.0)
        elif pose == "B":
            bmin, bmax = _bounds_of("FX-01", lines)
            target = unreal.Vector(-110.0, -55.0, bmax.z - 0.5)
            loc = target + unreal.Vector(25.0, -45.0, 18.0)
        elif pose == "C":
            bmin, bmax = _bounds_of("W18", lines)
            target = unreal.Vector(bmax.x - 2.0, bmin.y + 2.0, bmax.z - 4.0)
            loc = target + unreal.Vector(35.0, -45.0, -30.0)
        else:
            raise RuntimeError("WTK_INSPECT_POSE must be A, B, C or restore")
        rot = _look_at(loc, target)
        focus = (target - loc).length()
        # The sink sits in the sun patch, so pose B needs a lower bias.
        bias = float(os.environ.get("WTK_INSPECT_BIAS", INSPECT_BIAS))
        _apply(cam, loc, rot, INSPECT_FOCAL, INSPECT_APERTURE, focus, bias)
        lines.append("target=(%.2f,%.2f,%.2f) loc=(%.2f,%.2f,%.2f) rot=(p%.1f,y%.1f) focus=%.1f bias=%.2f"
                     % (target.x, target.y, target.z, loc.x, loc.y, loc.z, rot.pitch, rot.yaw, focus, bias))

    world = unreal.EditorLevelLibrary.get_editor_world()
    ok = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)
    lines.append("save_map -> %s" % ok)
    with open(os.path.join(OUT_DIR, "inspect_%s.txt" % (pose or "none")), "w") as f:
        f.write("\n".join(lines))


main()
