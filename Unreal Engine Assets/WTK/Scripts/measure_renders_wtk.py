"""
WTK relight pass (2026-09-27): objective pixel measurement of the test
renders via PIL. Standalone, run with the system Python (not Unreal's
embedded interpreter) -- this does not touch the editor/level at all.

Usage:
  python measure_renders_wtk.py [preset_suffix] [round_label]

  preset_suffix: one of day_soft/day_sun/night_led/night_led_cans, or ""/
  omitted to read the legacy bare "WTK_Test_CAM_Wide_0000.png" filenames
  (no suffix) -- matches render_tests_wtk.py's own PRESET_SUFFIX/job_name
  convention (WTK_LIGHT_PRESET env pass-through), so this script's filename
  reads always match whatever render_tests_wtk.py actually wrote for a given
  preset run.

Reads 06_Renders/tests/WTK_Test_CAM_{Wide,Angle,Detail}[_<preset>]_0000.png
and reports, for CAM_Wide:
  - ivory cabinet door face: mean RGB (day target ~140-175 per the
    2026-09-27 day/night preset task, superseding the earlier 200-225 "studio
    bright" target)
  - ceiling centre: mean RGB (day target ~95-140, and must read darker than
    the window wall / back-wall area -- see back_wall_area below)
  - corner / side wall patch: mean RGB (must read darker than the back-wall
    centre patch -- distance-from-window falloff check)
  - back wall centre patch (near the window, for the corner/side-wall
    falloff comparison and the "wall right around the window reads darker
    than the view" backlit check)
  - window glass: mean RGB + % of ITS OWN pixels clipped (>=250 all
    channels) -- day target <40% clipped, i.e. NOT fully blown, sky/
    landscape recognisable through the glass now that the HDRI sky
    dome/ground plane give it something real to show
  - B30 oak (still sampled on CAM_Detail, same boxes as before): mean RGB,
    "still a readable warm brown" check
  - counter-under-W30-LED patch (CAM_Angle, night presets): % clipped in
    that patch (night target <5%), for the LED-wash-not-blown check
  - whole-image clipped-pixel pct (>=250 all channels), as before, plus the
    window-only clip pct called out separately above.
"""
import sys
import os

try:
    from PIL import Image
except ImportError:
    print("PIL/Pillow not installed in this Python. Install with: pip install pillow")
    sys.exit(1)

RENDER_DIR = r"C:\Users\Sam\Documents\Chess\06_Renders\tests"
# 2026-09-27 window-only daylight pass: night presets removed; day-only
# preset set (hero/alt_soft/overcast), per setup_lighting_wtk.py's own
# VALID_PRESETS.
VALID_PRESETS = ("hero", "alt_soft", "overcast")

PATCHES = {
    "CAM_Wide": {
        "ivory_cabinet_door": (390, 500, 560, 600),  # left upper cabinet door face, lower/lit portion clear of the crown shadow band -- verified against an actual render
        # 2026-09-27 window-only daylight pass recalibration: the old box
        # (700,10,1200,90) sat directly above/around the window opening,
        # where the ceiling is expected to read brightest (adjacent to the
        # window's own direct spill) -- confirmed visually against the hero
        # round-3 render, this box was measuring the brightest ceiling band,
        # not a representative "ceiling centre" reading, which is why it
        # measured brighter than back_wall_near_window even though the far
        # corners of the ceiling clearly read darker in the same image.
        # Moved right, still on the true ceiling plane but past the window's
        # direct-spill zone, closer to the room's centre depth.
        "ceiling_centre": (1300, 10, 1700, 90),

        # 2026-09-27 day/night preset pass, new patches (task requirement:
        # "add these patches to measure_renders_wtk.py"). Coordinates are
        # approximate framing-based estimates for CAM_Wide's known
        # composition (window/back wall centred, side walls at the frame
        # edges, corners at the top edges) -- verify/adjust against an
        # actual render the first time this is used; flagged here rather
        # than silently assumed exact.
        "corner_side_wall": (20, 10, 220, 90),  # top-left corner -- a corner/side-wall area, verified against an actual render
        "back_wall_near_window": (850, 200, 1050, 340),  # back wall area flanking the window, for the falloff/backlit comparison
        "window_glass": (630, 390, 880, 730),  # the window opening itself, verified against an actual render
        # 2026-09-27 window-only daylight pass: floor sun-patch check (task
        # spec: "the floor sun patch present and not fully clipped over most
        # of its area"). Approximate framing estimate for CAM_Wide's known
        # composition (floor visible at the bottom of frame, patch expected
        # mid-room per the module-level ray-traced geometry) -- verify/adjust
        # against an actual render the first time this is used.
        "floor_sun_patch": (580, 780, 980, 870),  # calibrated against round-1 hero render's visible counter/sink sun patch
        # 2026-09-27 path-tracer pass: lower-cabinet ivory door patch (task
        # spec: "ADD a lower-cabinet ivory patch, e.g. the DB18/SB36 door
        # face in CAM_Wide"). CAM_Wide's lower run is ivory-painted at the
        # far right side of frame per the hero render (the sink base/B30-
        # adjacent lowers read dark-stained oak, not ivory -- the rightmost
        # lower cabinet bank, matching a DB18/SB36 position, is the painted
        # ivory one). Box picked on the flat door-panel area of that
        # rightmost lower run, clear of shadow/knob -- verify/adjust against
        # an actual render the first time this is used.
        "ivory_lower_cabinet_door": (1300, 900, 1600, 980),  # recalibrated round 1 (path-tracer pass): the rightmost lower cabinet bank's flat drawer front, confirmed ivory-painted (not the dark oak B30) against the actual render
        # A smooth, evenly-lit flat wall patch away from the window/corner/
        # sun-patch, used for the path-tracer noise check (task spec: stddev
        # of luminance in a flat wall patch < 6). The upper-left wall area
        # beside the left upper cabinet, mid-height, reads as flat/evenly lit
        # in the hero render with no strong gradient or shadow edge crossing
        # it.
        "noise_check_wall_patch": (1750, 150, 1900, 300),  # recalibrated round 1 (path-tracer pass): right side wall, confirmed visually flat/no gradient in the actual render (the original left-wall box crossed a real lighting gradient, which inflated stddev even when noise-free)
    },
    "CAM_Angle": {
        # 2026-09-27 night preset pass: counter area directly under the W30
        # LED strip (W30 spans X[-213.36,-137.16] at the back wall -- CAM_Angle
        # is aimed at that corner per setup_cam_angle()'s own target
        # (-175,-10,120)), used for the night LED-wash-not-clipped check.
        # Approximate framing estimate, same caveat as the CAM_Wide patches
        # above -- verify against an actual night render.
        "counter_under_w30_led": (700, 650, 1100, 850),
    },
    "CAM_Detail": {
        "b30_door_centre": (760, 400, 1160, 680),  # centre region of a 1920x1080 detail close-up
        "b30_door_flat_panel": (100, 500, 700, 950),  # lower-left door panel, away from knob specular/frame edge
    },
}

# 2026-09-27 window-only daylight pass targets (task spec's own acceptance
# criteria for CAM_Wide, via PIL):
#   - window pixels >=250 in all channels < 40%
#   - ivory upper door face mean ~140-175
#   - ceiling centre ~90-140 and darker than the back wall near the window
#   - side-wall corners darker than the back-wall centre
#   - B30 oak a readable warm brown
#   - floor sun patch present and not fully clipped over most of its area
TARGETS = {
    "ivory_cabinet_door": {"mean_range": (150, 185), "note": "path-tracer pass: upper ivory door, R>G>B (warm), NOT tan/brown"},
    "ivory_lower_cabinet_door": {"mean_range": (120, 165), "b_over_r_min": 0.80, "note": "path-tracer pass: lower ivory door, R>G>B, B/R>=0.80 (not orange)"},
    "ceiling_centre": {"mean_range": (90, 140), "note": "day: darker than the back/window wall"},
    "window_glass": {"clip_pct_max": 40.0, "note": "day: <40%% of window pixels fully clipped; sky/landscape recognisable"},
    "floor_sun_patch": {"clip_pct_max": 60.0, "note": "day: floor sun patch present, NOT fully clipped over most of its area (i.e. not >60% clipped)"},
    "b30_door_centre": {"r_range": (110, 150), "g_range": (75, 105), "b_range": (45, 75), "note": "still a readable warm brown"},
    "b30_door_flat_panel": {"r_range": (110, 150), "g_range": (80, 110), "b_range": (55, 85), "note": "path-tracer pass: CAM_Detail oak flat panel, warm honey/mid-brown, R>G>B"},
    "counter_under_w30_led": {"clip_pct_max": 5.0, "note": "legacy LED-wash check (LEDs removed 2026-09-27; kept only for historical comparison against pre-removal renders)"},
    "noise_check_wall_patch": {"luminance_stddev_max": 6.0, "note": "path-tracer pass: Lumen-noise/mottling check on a flat, evenly-lit wall patch"},
}


def mean_rgb(img, box):
    crop = img.crop(box).convert("RGB")
    pixels = list(crop.getdata())
    n = len(pixels)
    r = sum(p[0] for p in pixels) / n
    g = sum(p[1] for p in pixels) / n
    b = sum(p[2] for p in pixels) / n
    return r, g, b


def luminance_stddev(img, box):
    """
    2026-09-27 path-tracer pass: objective noise/mottling check (task spec:
    "the stddev of luminance in a flat wall patch ... < 6"). Rec.709
    luminance per pixel, then population stddev across the patch. A high
    value on a patch that's visually flat/evenly-lit indicates path-tracer
    fireflies/blotchy undersampling noise rather than real surface detail.
    """
    crop = img.crop(box).convert("RGB")
    pixels = list(crop.getdata())
    n = len(pixels)
    if n == 0:
        return 0.0
    lum = [0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in pixels]
    mean = sum(lum) / n
    variance = sum((l - mean) ** 2 for l in lum) / n
    return variance ** 0.5


def clip_pct(img, threshold=250, box=None):
    region = img.crop(box) if box else img
    rgb = region.convert("RGB")
    pixels = list(rgb.getdata())
    n = len(pixels)
    clipped = sum(1 for (r, g, b) in pixels if r >= threshold and g >= threshold and b >= threshold)
    return 100.0 * clipped / n if n else 0.0


def filename_for(cam, preset_suffix, mode_tag="", look_tag=""):
    if preset_suffix:
        return "WTK_Test_%s_%s%s%s_0000.png" % (cam, preset_suffix, mode_tag, look_tag)
    return "WTK_Test_%s%s%s_0000.png" % (cam, mode_tag, look_tag)


def main():
    args = sys.argv[1:]
    preset_suffix = args[0] if args and args[0] in VALID_PRESETS else ""
    remaining = args[1:] if (args and args[0] in VALID_PRESETS) else args
    # 2026-09-27 path-tracer pass: optional "pt"/"lumen" mode token (any
    # position in the remaining args) selects the _pt-suffixed path-tracer
    # output filenames render_tests_wtk.py now writes when
    # WTK_RENDER_MODE=pathtracer; omit/pass "lumen" for the old Lumen
    # filenames (no _pt tag).
    mode_tag = "_pt" if "pt" in remaining else ""
    # 2026-09-27 look-variant pass: optional "lookA"/"lookB"/"lookC" token
    # (any position in remaining args) selects the _lookX-suffixed filenames
    # render_tests_wtk.py writes when WTK_LOOK is set, matching that script's
    # own "_look%s" % LOOK_TAG job_name/output-filename convention.
    look_tag = ""
    for _a in remaining:
        if _a in ("lookA", "lookB", "lookC"):
            look_tag = "_look" + _a[-1]
            break
    remaining = [a for a in remaining if a not in ("pt", "lumen", "lookA", "lookB", "lookC")]
    label = remaining[0] if remaining else (preset_suffix or "unlabeled")
    print("=== WTK render measurement (preset=%s, mode=%s, look=%s, label=%s) ===" %
          (preset_suffix or "(none/legacy)", "pathtracer" if mode_tag else "lumen", look_tag or "(none)", label))
    for cam, patches in PATCHES.items():
        fname = filename_for(cam, preset_suffix, mode_tag, look_tag)
        path = os.path.join(RENDER_DIR, fname)
        if not os.path.exists(path):
            print("%s: MISSING (%s)" % (cam, path))
            continue
        img = Image.open(path)
        print("%s (%dx%d) [%s]:" % (cam, img.width, img.height, fname))
        for name, box in patches.items():
            r, g, b = mean_rgb(img, box)
            line = "  %s box=%s mean_sRGB=(%.1f, %.1f, %.1f)" % (name, box, r, g, b)
            if name in ("window_glass", "counter_under_w30_led", "floor_sun_patch"):
                pct = clip_pct(img, box=box)
                line += " clipped_pct_in_patch=%.2f%%" % pct
            if name in ("ivory_cabinet_door", "ivory_lower_cabinet_door") and r > 0:
                line += " B/R=%.3f" % (b / r)
            if name == "noise_check_wall_patch":
                sd = luminance_stddev(img, box)
                line += " luminance_stddev=%.2f" % sd
            print(line)
        pct = clip_pct(img)
        print("  whole-image clipped-pixel pct (>=250 all channels): %.2f%%" % pct)
    print("=== end ===")


if __name__ == "__main__":
    main()
