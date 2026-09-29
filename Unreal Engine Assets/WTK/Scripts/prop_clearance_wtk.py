"""
WTK prop clearance pass (2026-09-27).

Measures the combined world bounds (actor + attached children) of the
counter/shelf props and nudges them so that:
  - counter props (cutting board, bowl) keep >= MIN_BACKSPLASH_GAP_CM from
    the backsplash face (Y = -1.90, room interior is -Y), and their base sits
    on the counter top (Z 91.44) within +/-0.05 cm;
  - the plant's base sits on the upper shelf top (Z 191.77) within +/-0.05 cm.
Idempotent: a prop that already satisfies the constraints is not moved.

Called from place_props_wtk.py before its save (main(load_level=False)), or
standalone via the -run=pythonscript commandlet (loads the map and saves).
Report: tmp/WtkP5Close_20260927/prop_clearance.txt
"""
import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH

REPORT_PATH = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkP5Close_20260927\prop_clearance.txt"

BACKSPLASH_FACE_Y = -1.90
COUNTER_TOP_Z = 91.44
SHELF_UPPER_TOP_Z = 191.77
MIN_BACKSPLASH_GAP_CM = 1.0   # target gap (spec: >= 0.5 cm)
Z_TOL_CM = 0.05

PROPS = {
    "WTK_Prop_CuttingBoard": {"rest_z": COUNTER_TOP_Z, "backsplash": True},
    "WTK_Prop_Bowl": {"rest_z": COUNTER_TOP_Z, "backsplash": True},
    "WTK_Prop_Plant": {"rest_z": SHELF_UPPER_TOP_Z, "backsplash": False},
}


def _find(label):
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


def _bounds(actor):
    o, e = actor.get_actor_bounds(only_colliding_components=False)
    bmin, bmax = o - e, o + e
    for child in actor.get_attached_actors():
        co, ce = child.get_actor_bounds(only_colliding_components=False)
        cmin, cmax = co - ce, co + ce
        bmin = unreal.Vector(min(bmin.x, cmin.x), min(bmin.y, cmin.y), min(bmin.z, cmin.z))
        bmax = unreal.Vector(max(bmax.x, cmax.x), max(bmax.y, cmax.y), max(bmax.z, cmax.z))
    return bmin, bmax


def main(load_level=True):
    lines = []
    if load_level:
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)

    moved = False
    for label, rule in PROPS.items():
        actor = _find(label)
        if actor is None:
            lines.append("%s: NOT FOUND" % label)
            continue
        bmin, bmax = _bounds(actor)
        lines.append("%s before: min=(%.2f,%.2f,%.2f) max=(%.2f,%.2f,%.2f)"
                     % (label, bmin.x, bmin.y, bmin.z, bmax.x, bmax.y, bmax.z))
        dy = 0.0
        if rule["backsplash"]:
            gap = BACKSPLASH_FACE_Y - bmax.y
            if gap < MIN_BACKSPLASH_GAP_CM - 1e-3:
                dy = -(MIN_BACKSPLASH_GAP_CM - gap)
        dz = 0.0
        if abs(bmin.z - rule["rest_z"]) > Z_TOL_CM:
            dz = rule["rest_z"] - bmin.z
        if dy or dz:
            actor.modify()
            loc = actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(loc.x, loc.y + dy, loc.z + dz), False, False)
            moved = True
            bmin, bmax = _bounds(actor)
            lines.append("  moved dy=%.2f dz=%.2f" % (dy, dz))
        gap_txt = ("backsplash gap=%.2f cm" % (BACKSPLASH_FACE_Y - bmax.y)) if rule["backsplash"] else "shelf prop"
        lines.append("%s after: min=(%.2f,%.2f,%.2f) max=(%.2f,%.2f,%.2f); base-rest_z=%.3f cm; %s"
                     % (label, bmin.x, bmin.y, bmin.z, bmax.x, bmax.y, bmax.z,
                        bmin.z - rule["rest_z"], gap_txt))

    if load_level and moved:
        world = unreal.EditorLevelLibrary.get_editor_world()
        ok = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)
        lines.append("save_map -> %s" % ok)
    lines.append("moved_any=%s" % moved)
    lines.append("PROP_CLEARANCE_DONE")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))
    return moved


if __name__ == "__main__":
    main()
