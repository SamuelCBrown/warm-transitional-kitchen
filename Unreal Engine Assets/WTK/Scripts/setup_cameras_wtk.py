"""
WTK Phase 5d: test cameras + Level Sequences for MRQ test renders.

Idempotent: finds/updates CineCameraActors and LevelSequences by name/label.

Scene facts (see setup_lighting_wtk.py header for full derivation):
  - Room interior X [-335.28, 30.48], Y [-426.72, 0], Z [0, 243.84].
  - Back wall (with window) at Y in [0, 15.24]; cabinets/room interior at Y<0.
  - Cabinet wall run: B30 X[-213.36,-137.16], W18/W30 uppers above, all at
    the back wall (Y approx 0..-62.23 depth).
  - Front (opposite) wall: Walls_..._6in_3, Y in [-441.96,-426.72] -- i.e.
    the far wall from the cabinets, at Y~-427 to -442 (room's -Y end).
  - B30 door + brass knob detail: B30 center approx X=-175, Y=-31, Z=44
    (cabinet base, brass pulls near door edges).

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this> -unattended -nop4 -nosplash -stdout
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH
SEQ_DIR = "/Game/WTK/Cinematics"

# 2026-09-27 day/night preset pass: same WTK_LIGHT_PRESET env var
# setup_lighting_wtk.py reads, consumed here so each camera's own exposure
# override (which fully replaces WTK_PPV's shared bias for that camera, see
# apply_exposure_override()'s docstring below) can be tuned per preset.
# Iterated live against CAM_Wide only (per the task's "render only CAM_Wide
# while iterating" instruction) -- see Docs/Lighting.md for the round table.
# Values found here are then applied uniformly to all 3 cameras' calls
# below (CAM_Angle/CAM_Detail keep their own pre-existing per-camera offsets
# relative to CAM_Wide's bias, not a hardcoded absolute).
VALID_PRESETS = ("hero", "alt_soft", "overcast")
CURRENT_PRESET = os.environ.get("WTK_LIGHT_PRESET", "hero")
if CURRENT_PRESET not in VALID_PRESETS:
    CURRENT_PRESET = "hero"
IS_NIGHT = False  # night presets removed 2026-09-27 (window-only daylight pass)
IS_HERO = CURRENT_PRESET == "hero"

# 2026-09-27 look-variant pass (WtkPhoto_20260927): orchestrator feedback on
# the hero renders was "not bright enough, not realistic enough" (peach cast,
# flat local-exposure compression, smooth walls). Rather than pick a single
# fix blind, WTK_LOOK selects one of 3 complete reproducible look variants
# (A/B/C) that each retune bias + White Balance + Local Exposure + grain/
# vignette together, per-camera, replacing the single hero/alt_soft/overcast
# per-camera bias tables above with a per-(preset,look) table. Defaults to
# "A" ("bright & airy") if unset/unrecognized. Only meaningful when
# WTK_LIGHT_PRESET=hero (the other 2 presets are unaffected/unchanged, since
# the task's brief is entirely about the hero look).
VALID_LOOKS = ("A", "B", "C")
CURRENT_LOOK = os.environ.get("WTK_LOOK", "A")
if CURRENT_LOOK not in VALID_LOOKS:
    CURRENT_LOOK = "A"

# Per-look tuning, applied on top of the existing hero per-camera bias tables
# below (WIDE_ANGLE_BIAS_BY_PRESET["hero"] / DETAIL_BIAS_BY_PRESET["hero"] are
# each look's *baseline*; LOOK_BIAS_DELTA shifts from there so alt_soft/
# overcast keep their own separate, unmodified per-preset bias when
# WTK_LIGHT_PRESET != "hero"):
#   A "bright & airy": push bias up further (+0.9 stops-equiv over the
#     existing hero baseline) for a genuinely bright cream-white ivory,
#     neutral-cream WB (5000K), natural (not flat) Local Exposure contrast,
#     no grain, very light vignette.
#   B "warm morning": less bright than A (+0.4), warmer WB (4600K, but not
#     peach -- neutralised further than the pre-existing 3800K sepia-cast
#     value), slightly more contrast than A, a whisper of grain.
#   C "editorial": as bright as A but crisper/cooler-neutral WB (5500K), the
#     most contrast of the 3, a touch of grain and vignette for a print-like
#     finish.

# 2026-09-27 look-variant pass, WB-direction correction (round 2): a live
# measurement of round 1 (white_temp=5000 for look A) came back MORE orange
# (ivory B/R=0.544) than the pre-existing hero baseline (white_temp=3800,
# B/R=0.692) -- the opposite of the intended direction. Root cause: UE's
# White Balance mode's white_temp is "the colour temperature of the light
# source to neutralise" -- RAISING it tells the renderer the light is COOLER
# than it really is and over-corrects by warming the image further; LOWERING
# it (toward/below the sun's own ~4400K) is what pulls a warm cast back
# toward neutral. Re-tuned below (lower white_temp = cooler/more-neutral
# result), verified against a second real re-render before committing to the
# full 3x3 matrix (see Docs/Lighting.md Section 19 for the corrected
# measurement).
# 2026-09-27 look-variant pass, round 2 (orchestrator review of look A):
# 3 issues found in the rendered look-A images, all fixed here via new/
# retuned per-look fields:
#   1) Walls/ceiling read faintly MAUVE/pink (G low vs R and B -- e.g.
#      ceiling (187,168,162), back wall (152,138,134): G sits below both R
#      and B, and UE's White Balance Temp axis alone can't fix a magenta/
#      green cast -- that's what the separate Tint axis is for.
#      Scene.h (Engine/Classes/Engine/Scene.h) confirms WhiteTint is a
#      distinct PostProcessSettings float, range -1..+1, UI label "Tint";
#      by UE convention positive Tint pushes magenta, negative pushes green.
#      Added "white_tint" (negative = greener) to every look, applied below
#      via override_white_tint alongside the existing white_temp override.
#   2) Lower ivory reads orange vs the uppers (B/R 0.662, target >=0.75):
#      round-2a iteration (shadow_contrast 0.85->0.97, white_temp 3100->2950)
#      measured WORSE (B/R 0.642) -- Local Exposure's shadow_contrast_scale
#      is a per-pixel LUMINANCE remap (how contrasty/compressed shadow-region
#      brightness reads), not a colour-balance control, so it has ~zero
#      effect on the B/R colour ratio; the small regression is noise from
#      the white_temp nudge alone. White Balance (temp+tint) is a single
#      GLOBAL transform applied uniformly to the whole frame -- it cannot
#      selectively cool only the shadow-zone lowers without also cooling
#      the already-correct uppers past their own target. Round-2b: kept
#      shadow_contrast near-neutral (helps the *tonal* flatness complaint
#      without hurting colour) and pushed the correction entirely onto
#      white_temp (further down) + white_tint (further negative/green),
#      re-verified against a live re-render each step so the uppers don't
#      overshoot past B/R~0.92 while the lowers climb toward >=0.75.
#      Round-2b/2c finding: white_temp 2950->2600 (+tint -0.10->-0.16) moved
#      upper B/R 0.896->1.005 and lower B/R 0.642->0.751 -- the SAME +0.109
#      delta on both. White Balance is a single global transform, so it
#      shifts every zone's B/R by (about) the same amount regardless of how
#      warm/shadowed that zone is; there is no global temp/tint point that
#      gets the lower run to >=0.75 while keeping the upper run <=0.92 (the
#      lower run needs +0.108 of headroom from the iter1 baseline, the upper
#      run only has +0.024 before it exceeds its own ceiling). Settled on
#      2750/-0.14 (interpolated) as the best achievable compromise given
#      this constraint -- verified below.
#   3) CAM_Detail oak reads dark: detail_bias_delta raised by +0.2-0.3 EV
#      per look (was 0.5/0.2/0.5 -> now 0.75/0.45/0.75); round-2a measured
#      still slightly under target (109.3,68.5,45.7 vs 115-135/75-95/50-70)
#      -- bumped further in round-2b.
# 2026-09-28 realism pass (WtkRealism_20260928): orchestrator/user feedback on
# the shipped look A was "not bright enough" and "does not look realistic
# enough" -- a live baseline re-measurement of the untouched look-A render
# confirmed both: upper ivory (171.6,165.1,149.0) vs a bright-airy-kitchen
# target of ~200-215, back wall (178.2,184.3,178.6) vs ~185-205, and a
# slight green-grey lean on the walls/ceiling (G-R = +6.1 on the back wall,
# +3.1 on the ceiling; G should be <=R for a neutral-warm cream, not
# greenish). Root-cause reasoning for the brightness gap: bias_delta=0.9 was
# tuned in the prior look-variant pass against a DIFFERENT (pre-window-fix,
# pre-backplate) baseline; simply raising bias_delta is the direct lever
# (confirmed each look already reads this off LOOK_PARAMS, no other code
# path double-applies it). Raised bias_delta 0.9->1.45 (~+0.55 stops) after
# a live round-1 re-render (see Lighting.md Section 20) landed the upper
# ivory at 205.3, back wall 191.7, ceiling 187.9 -- all within target and
# ceiling still (barely) darker than the window-adjacent wall as required.
# White balance: white_tint moved -0.14 -> -0.05 (less green push) since the
# round-1 remeasurement showed G now *below* R once brightness rose (a
# brighter image samples less deeply into the tonemapper's saturation curve,
# so the same tint value reads differently) -- round 2 confirmed G approx R
# (+/-3) after this correction; white_temp left at 2750.0 (unchanged --
# B/R was already in the 0.90-0.95 target band at this temp and moving it
# risked re-breaking that ratio while only tint needed correcting for the
# G-vs-R axis).
    # 2026-09-28 realism pass, round 3 (live CAM_Wide re-measurement of
    # round 2): round 2 lowered white_temp 2750->2500 on the assumption
    # (carried over from the PRIOR look-variant pass's round-2 note) that a
    # lower reference temp pulls the render warmer -- MEASURED WRONG this
    # time: ceiling B/R went UP (1.037->1.141, more blue) and G-R went up too
    # (+0.5->+11.3, more green), i.e. lowering white_temp pulled this
    # renderer's actual behaviour COOLER/greener, the opposite direction from
    # the old note. Root-caused: the old note was measured against a
    # different baseline (pre-window-backplate, pre-highlight/shadow-
    # contrast=1.0 change) -- not assumed to still hold; trusting it without
    # re-verifying live was round 2's mistake. Corrected empirically this
    # round: white_temp raised back up, 2500->3300 (net UP from round 0's
    # 2750, opposite of round 1/2's direction), white_tint pulled toward
    # neutral, -0.05->0.0 (round 2's ceiling G-R=+11.3 needs LESS green
    # push, not more). bias_delta kept at 1.9 (round 2's brightness alone,
    # independent of the color-temp bug, was reasonable -- upper ivory hit
    # 173-179 across rounds 1-2 at similar bias; the remaining gap to 200-215
    # is addressed by re-measuring once the color axis is fixed, since B/R
    # overshoot was inflating the wall/ceiling numbers this round in a way
    # that doesn't cleanly separate from the brightness read).
    # Round 4 (live remeasurement of round 3's temp=3300/tint=0.0): B/R
    # landed correctly in-band (ceiling 0.902, wall 0.922, target
    # 0.90-0.95) and brightness improved (upper ivory 192.9, close to
    # 200-215) -- but G-R overshot NEGATIVE (ceiling -14.7, wall -11.4,
    # target +/-3), i.e. now too orange/red on the G axis specifically.
    # Round 5: small negative tint nudge (0.0->-0.05) to lift G back toward
    # R without touching B/R (tint's own axis is G-vs-magenta, distinct from
    # temp's R-B axis, confirmed by round 1's history) + a small further
    # bias bump (1.9->2.1) since upper ivory (192.9) was still ~10-20 short
    # of the 200-215 floor.
LOOK_PARAMS = {
    "A": {
        "bias_delta": 2.1, "detail_bias_delta": 2.3,
        "white_temp": 3300.0, "white_tint": -0.05,
        "highlight_contrast": 1.0, "shadow_contrast": 1.0, "detail_strength": 1.05,
        "vignette": 0.08, "grain": 0.0,
    },
    "B": {
        "bias_delta": 0.5, "detail_bias_delta": 0.95,
        "white_temp": 3050.0, "white_tint": -0.14,
        "highlight_contrast": 0.95, "shadow_contrast": 1.00, "detail_strength": 1.15,
        "vignette": 0.10, "grain": 0.04,
    },
    "C": {
        "bias_delta": 0.9, "detail_bias_delta": 1.25,
        "white_temp": 2800.0, "white_tint": -0.145,
        "highlight_contrast": 1.0, "shadow_contrast": 1.0, "detail_strength": 1.2,
        "vignette": 0.12, "grain": 0.06,
    },
}

# CAM_Wide/CAM_Angle bias (shared, matching their pre-existing "same look"
# convention); CAM_Detail keeps its own separately-tuned close-up bias below.
# 2026-09-27 window-only daylight pass: iterated live against CAM_Wide only
# (per the task's "iterate the exposure in <=5 CAM_Wide rounds for the hero"
# instruction) with the real 65,000 lux sun + SkyLight intensity=1.0 (no
# cheats) -- see Docs/Lighting.md for the round-by-round measurement table
# that produced these final values.
# 2026-09-27 path-tracer pass round 2: hero's round-1 path-traced CAM_Wide
# render measured ivory upper door at 143.9 (target 150-185) at bias=4.8 --
# nudged up slightly to bring it into range.
WIDE_ANGLE_BIAS_BY_PRESET = {
    "hero": 6.4,  # 7.0 -> 6.4 after the ground-plane RT fix (WtkBand) lifted the room ~0.6 EV
    "alt_soft": 5.0,
    "overcast": 5.6,
}
# 2026-09-27 WtkPTFix5 pass: with the reference-atmosphere fix (WtkPTFix4)
# and the glass re-tune (this pass, Part 2) both shipped, hero's CAM_Wide
# measured window=(185.8,187.9,189.4) vs back_wall_near_window=
# (145.4,129.6,112.1) at bias=5.2 -- window/wall luminance ratio ~1.42x,
# already over the task's >=1.4x floor -- but the room itself (upper ivory
# ~129/111/93, lower ivory-adjacent cabinets, oak flat panel ~59/30/15) read
# well under every brightness target, confirming the task's own "dim and
# dusky" complaint. Raised hero bias 5.2->6.2 to bring the room up while
# the window still has headroom (only 0.38% clipped in-pane, well under the
# ~40%-of-window-area allowance) -- see this pass's Docs/Lighting.md section
# for the re-measured table after this change.
# 2026-09-27 path-tracer pass: hero's path-traced CAM_Detail render measured
# the oak flat panel at (86.5, 51.7, 32.2) at bias=3.4 -- well under the
# target (R110-150/G80-110/B55-85), reading dark mahogany instead of warm
# honey/mid-brown per the orchestrator's own complaint. Raised to 4.3 (~+0.9
# stops-equivalent bias) to bring it into range; not counted against the
# CAM_Wide-only 5-round iteration cap (task scoped that cap to CAM_Wide
# specifically), single follow-up correction verified by re-render.
DETAIL_BIAS_BY_PRESET = {
    "hero": 4.3,
    "alt_soft": 3.6,
    "overcast": 4.4,
}


_LOG_LINES = []


def log(msg):
    line = "[WTK_Cameras] %s" % msg
    print(line)
    _LOG_LINES.append(line)


def _flush_log_to_file():
    try:
        with open(r"C:\Users\Sam\Documents\Chess\tmp\Wtk5d_20260926\setup_cameras_last_run.txt", "w") as f:
            f.write("\n".join(_LOG_LINES))
    except Exception:
        pass


def _actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def find_actor_by_label(label):
    for a in _actor_subsys().get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


def spawn_or_get_camera(label, location, rotation):
    existing = find_actor_by_label(label)
    if existing:
        log("Found existing camera '%s' -- updating in place." % label)
        # WTK prop-fix pass round 2 (2026-09-26): the coordinator found
        # place_props_wtk.py's equivalent "update existing actor" path
        # silently failed to persist to WTK_Main.umap because
        # set_actor_location()/set_actor_rotation() do not themselves mark
        # the owning package dirty. The same risk applies here -- this
        # function never called existing.modify() before mutating it
        # either. Fixed defensively (not independently re-verified against
        # a live rerun of this specific script this pass -- only
        # place_props_wtk.py's own bug was directly tested and confirmed
        # fixed by checking the .umap's on-disk timestamp before/after).
        existing.modify()
        existing.set_actor_location(location, False, False)
        existing.set_actor_rotation(rotation, False)
        return existing
    cam = _actor_subsys().spawn_actor_from_class(unreal.CineCameraActor, location, rotation)
    cam.set_actor_label(label)
    log("Spawned new camera '%s'." % label)
    return cam


def apply_exposure_override(comp, auto_exposure_bias):
    """
    Phase 5e Task 2: give each CineCameraComponent its own post-process
    exposure override so CAM_Detail can be exposed differently from
    CAM_Wide/CAM_Angle without touching the shared WTK_PPV (which stays at
    its documented AutoExposureBias for the two wider shots). Method:
    CineCameraComponent.post_process_settings (a PostProcessSettings struct
    property on the camera component itself, blended per-camera at
    post_process_blend_weight=1.0) with override_auto_exposure_bias=True and
    the method kept manual (matching WTK_PPV's AEM_MANUAL) so this override
    only changes the bias, not the exposure method.

    2026-09-27 window-only daylight pass: also carries the per-camera Local
    Exposure override (task spec: "apply Local Exposure ... on each camera's
    post-process override (the camera override replaces the PPV values)")
    and White Balance mode/temperature, since a camera-component
    post_process_settings blended at weight=1.0 fully replaces the PPV's
    corresponding fields for that camera, same mechanism as the exposure
    bias override above -- setup_lighting_wtk.py's PPV-level Local
    Exposure/white balance values would otherwise be silently ignored for
    all 3 render cameras exactly the way the old PPV-only AutoExposureBias
    was before this override existed.
    """
    comp.set_editor_property("post_process_blend_weight", 1.0)
    pps = comp.get_editor_property("post_process_settings")
    pps.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    pps.set_editor_property("override_auto_exposure_method", True)
    pps.set_editor_property("auto_exposure_bias", auto_exposure_bias)
    pps.set_editor_property("override_auto_exposure_bias", True)

    # 2026-09-28: bloom off for the path-traced stills. The PPV's 0.3 bloom
    # haloed the sunlit brass faucet/muntin edges against the bright window
    # view (Lighting.md §23); photographic stills don't need it.
    pps.set_editor_property("bloom_intensity", 0.0)
    pps.set_editor_property("override_bloom_intensity", True)

    look = LOOK_PARAMS[CURRENT_LOOK]

    # White Balance mode. 2026-09-27 look-variant pass: replaces the old
    # single 3800K sepia-fighting value with a per-look neutral-cream target
    # (orchestrator diagnosis: ivory B/R~=0.62 = peach cast; target B/R
    # 0.85-0.92). Each look's white_temp is the WB reference temperature (the
    # temperature that WOULD read neutral) -- raising it, relative to the
    # scene's actual warm ~4400K sun, is what pulls the cast back toward
    # cream/neutral rather than orange/peach.
    try:
        pps.set_editor_property("temperature_type", unreal.TemperatureMethod.TEMP_WHITE_BALANCE)
        pps.set_editor_property("override_temperature_type", True)
    except Exception:
        pass
    try:
        pps.set_editor_property("white_temp", look["white_temp"])
        pps.set_editor_property("override_white_temp", True)
    except Exception:
        pass
    # 2026-09-27 look-variant pass round 2 (orchestrator issue 1): separate
    # Tint axis fix for the mauve/pink cast (WhiteTemp alone can't correct a
    # magenta/green shift -- confirmed via Engine/Classes/Engine/Scene.h,
    # which declares WhiteTint as its own PostProcessSettings float,
    # range -1..+1, UI label "Tint", independent of WhiteTemp). Negative
    # value pushes toward green (UE convention: +Tint=magenta, -Tint=green).
    try:
        pps.set_editor_property("white_tint", look["white_tint"])
        pps.set_editor_property("override_white_tint", True)
    except Exception as e:
        log("WARNING: could not set white_tint override (%s) -- verify property name in-editor." % e)

    # Local Exposure: 2026-09-27 look-variant pass -- orchestrator diagnosis
    # #2: the prior hero values (highlight=0.7, shadow=0.5) over-compress the
    # dynamic range, giving a flat/painterly CG look. Moved into the
    # requested natural-contrast band (highlight ~0.85-1.0, shadow ~0.8-1.0,
    # detail ~1.0-1.2), per-look (see LOOK_PARAMS above).
    try:
        pps.set_editor_property("local_exposure_highlight_contrast_scale", look["highlight_contrast"])
        pps.set_editor_property("override_local_exposure_highlight_contrast_scale", True)
        pps.set_editor_property("local_exposure_shadow_contrast_scale", look["shadow_contrast"])
        pps.set_editor_property("override_local_exposure_shadow_contrast_scale", True)
        pps.set_editor_property("local_exposure_detail_strength", look["detail_strength"])
        pps.set_editor_property("override_local_exposure_detail_strength", True)
    except Exception as e:
        log("WARNING: could not set per-camera Local Exposure overrides (%s) -- verify property names in-editor." % e)

    # Photographic touches (task item 6): restrained vignette + tiny film
    # grain, per look. No bloom haze added (bloom stays at the PPV's existing
    # 0.3); lens distortion left off (never enabled here).
    try:
        pps.set_editor_property("vignette_intensity", look["vignette"])
        pps.set_editor_property("override_vignette_intensity", True)
    except Exception as e:
        log("WARNING: could not set per-camera vignette (%s)." % e)
    try:
        pps.set_editor_property("film_grain_intensity", look["grain"])
        pps.set_editor_property("override_film_grain_intensity", True)
    except Exception as e:
        log("WARNING: could not set per-camera film grain (%s) -- property name may differ in this UE 5.7 build." % e)

    # WtkPTFix4 pass (2026-09-27), Part A fix: path_tracing_include_emissive
    # was already True on both WTK_PPV and every camera (confirmed via
    # tmp/WtkPTFix4_20260927/inspect_pt_ppv_settings.py -- not the blocker,
    # ruling out the task's own leading A1 hypothesis for that specific
    # flag), but path_tracing_enable_reference_atmosphere was found False
    # everywhere and had never been tested by any of the 3 prior passes
    # (WtkPTFix/2/3 only ever touched MI_Glass_Clear's own Opacity/
    # BaseColorTint/Specular and the sky dome's emissive material -- never
    # this PPV/path-tracer-specific flag). Setting it True on each camera's
    # own post_process_settings override (required, since the per-camera
    # override at blend_weight=1.0 fully replaces WTK_PPV's own value the
    # same way AutoExposureBias does -- see this function's own docstring)
    # is the actual root cause fix for the window-exterior-is-black defect:
    # a real re-render showed the window go from a flat, near-uniform dark
    # wash (baseline window_glass mean sRGB (65.7,68.6,69.1), stddev
    # 2.7-5.0, per Docs/Lighting.md section 16.2) to a genuine sky gradient
    # with a visible horizon line (blue upper panes, darker lower panes),
    # window_glass mean sRGB (82.6,96.1,111.2), stddev 37-43 (roughly 10x
    # higher spatial variance, confirming real image detail, not just a
    # flat colour shift) -- see tmp/WtkPTFix4_20260927/window_2x_refatmo_on.png.
    # Room-brightness stability confirmed: ivory_cabinet_door mean changed
    # only -3.0% (91.4,78.4,66.9 -> 90.8,76.1,62.7) and b30_door_flat_panel
    # 0.0%% (74.8,40.6,23.8 unchanged), both comfortably inside the task's
    # <=5%% GI-leak budget, so this flag controls background VISIBILITY to
    # the path-traced camera, not scene GI contribution.
    try:
        pps.set_editor_property("path_tracing_enable_reference_atmosphere", True)
        pps.set_editor_property("override_path_tracing_enable_reference_atmosphere", True)
    except Exception as e:
        log("WARNING: could not set path_tracing_enable_reference_atmosphere (%s) -- "
            "verify this property name against the live engine build." % e)

    comp.set_editor_property("post_process_settings", pps)


def configure_camera(cam, focal_length, aperture, focus_distance_cm, auto_exposure_bias=4.0, filmback_preset="Cinema35mmFullApertureCine"):
    comp = cam.camera_component
    comp.modify()  # WTK prop-fix pass round 2: modify() before mutating an existing camera's component, see spawn_or_get_camera()'s own comment
    comp.set_editor_property("current_focal_length", focal_length)
    comp.set_editor_property("current_aperture", aperture)
    apply_exposure_override(comp, auto_exposure_bias)
    # Round 3 fix: a 36x24mm (3:2, aspect_ratio=1.5) sensor against a 16:9
    # (1.778) MRQ output canvas, combined with constrain_aspect_ratio=True
    # (the CineCameraActor default), produced a badly cropped/blown frame in
    # rounds 1-2 test renders (only the top-left ~half of the 1920x1080
    # canvas showed real content, the rest solid white) -- matches a known
    # CineCamera/MRQ letterbox interaction when the sensor aspect doesn't
    # match the output aspect. Use a 36x20.25mm sensor (exactly 16:9) so the
    # camera's native aspect matches the 1920x1080 output canvas exactly,
    # eliminating any letterbox/pillarbox cropping.
    filmback = comp.get_editor_property("filmback")
    filmback.set_editor_property("sensor_width", 36.0)
    filmback.set_editor_property("sensor_height", 20.25)
    comp.set_editor_property("filmback", filmback)
    # Round 4 debug: test renders showed real content only in the left half
    # of the output canvas regardless of sensor aspect match -- try disabling
    # constrain_aspect_ratio entirely to rule out a pillarbox/crop alignment
    # bug in the CineCamera-to-MRQ-canvas path.
    try:
        comp.set_editor_property("constrain_aspect_ratio", False)
    except Exception:
        pass

    focus_settings = comp.get_editor_property("focus_settings")
    focus_settings.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    focus_settings.set_editor_property("manual_focus_distance", focus_distance_cm)
    comp.set_editor_property("focus_settings", focus_settings)


def setup_cam_wide():
    """
    Standing eye height ~160cm, back near the opposite (far) wall, looking at
    the full cabinet wall. Cabinet wall runs along Y~0 (back wall) with the
    run centered roughly at X=-137 (B30 center). Far wall is at Y~-427/-442.
    Place camera near the far wall (Y=-380, leaving a little room margin),
    centered in X on the cabinet run, eye height Z=160, looking back toward
    +Y at the cabinet wall.
    """
    loc = unreal.Vector(-150.0, -380.0, 160.0)
    # Look from -Y position toward +Y (toward the back wall/cabinets): yaw=90
    # points the camera's forward vector along +Y.
    rot = unreal.Rotator(pitch=0.0, yaw=90.0, roll=0.0)
    cam = spawn_or_get_camera("CAM_Wide", loc, rot)
    # 2026-09-27 relight pass: per-camera post_process_settings fully
    # overrides the shared WTK_PPV's AutoExposureBias for this camera (both
    # blend at weight 1.0), so raising the PPV's bias alone (round 2) had
    # zero visible effect on this camera's render -- confirmed via an
    # unchanged pixel measurement before/after that PPV-only change. Raised
    # here instead, from 4.0 (tuned against the OLD leaked-sun baseline) to
    # 6.0, after round 2's render came back with the ivory cabinet still at
    # mean sRGB ~115 (target 200-225) and ceiling ~187 (target >=180, close).
    bias = WIDE_ANGLE_BIAS_BY_PRESET[CURRENT_PRESET]
    if IS_HERO:
        bias += LOOK_PARAMS[CURRENT_LOOK]["bias_delta"]
    configure_camera(cam, focal_length=26.0, aperture=11.0, focus_distance_cm=350.0, auto_exposure_bias=bias)
    log("CAM_Wide [%s/look=%s]: loc=(-150,-380,160), yaw=90 (facing cabinet wall), 26mm, f/8, full-frame filmback, "
        "per-camera AutoExposureBias=%.2f" % (CURRENT_PRESET, CURRENT_LOOK, bias))
    return cam


def setup_cam_angle():
    """
    3/4 view from the left side, ~35mm. Positioned toward the +X (right/far)
    side of the room, looking back across at an angle toward the cabinet
    wall's left portion (W30/B30 side, more negative X).
    """
    loc = unreal.Vector(-40.0, -300.0, 155.0)
    # Aim toward the W30/B30 corner (~X=-175, Y=-10, Z=120).
    target = unreal.Vector(-175.0, -10.0, 120.0)
    direction = target - loc
    rot = direction.rotator()
    cam = spawn_or_get_camera("CAM_Angle", loc, rot)
    bias = WIDE_ANGLE_BIAS_BY_PRESET[CURRENT_PRESET]
    if IS_HERO:
        bias += LOOK_PARAMS[CURRENT_LOOK]["bias_delta"]
    configure_camera(cam, focal_length=35.0, aperture=11.0, focus_distance_cm=280.0, auto_exposure_bias=bias)
    log("CAM_Angle [%s/look=%s]: loc=(-40,-300,155), aimed at (-175,-10,120), 35mm, f/5.6, "
        "per-camera AutoExposureBias=%.2f (matching CAM_Wide)" % (CURRENT_PRESET, CURRENT_LOOK, bias))
    return cam


def setup_cam_detail():
    """
    Close on the B30 base cabinet's oak door + brass knob + counter edge --
    the portfolio's feature detail shot, per the task spec. Round 5
    temporarily retargeted this to the W30 upper cabinet (B30 was almost
    pure black, avg RGB ~12,12,14, at every exposure tried, since it's far
    from both the sun's raking angle and the under-cabinet LEDs). Round 6
    restores the original B30 framing now that (a) the ceiling fix lets the
    Sky Light bounce real light back into the room instead of radiating
    straight out through an open "roof", and (b) WTK_Fill_Room (a subtle,
    non-shadow-casting soft rect light near the camera side) was added
    specifically to lift the lower cabinets -- both substantially brighten
    B30 without needing to blow out the window/uppers via global exposure.
    B30 spans X[-213.36,-137.16], Y[-62.23,0], Z[0,87.63]; its door/knob
    area is roughly at the door's mid-height, front face (most negative Y).

    Phase 5e Task 2: precisely targets a real knob position instead of a
    guessed stile/knob-height point. B30's hardware is derived from
    03_Revit/WTK_Cabinet_Spec.json's "B30" entry (2 knobs, centre_x
    13.4375in / 16.5625in from the cabinet's local left edge, centre_z
    28.4375in from z_bottom=0) plus its placement (x_min=-84in, x_max=-54in,
    z_bottom=0). Revit inches -> UE cm mapping confirmed exact against the
    already-documented B30 actor bounds (Lighting.md: B30 X[-213.36,-137.16]
    cm == (-84,-54)in * 2.54 cm/in): UE X = Revit X (in) * 2.54, and the same
    2.54 scale applies to Z (UE Z = Revit z_bottom-relative height in cm,
    z_bottom=0 aligning with the room floor Z=0). Knob world positions:
      knob 1 (left door): X = (-84 + 13.4375) * 2.54 = -179.23 cm
      knob 2 (right door): X = (-84 + 16.5625) * 2.54 = -171.29 cm
      both: Z = 28.4375 * 2.54 = 72.23 cm
    Front (door) face is B30's most-negative-Y face, Y = -62.23 (per
    Lighting.md's confirmed cabinet-depth bounds). Framed on knob 2 (the
    inner/right knob, closer to the cabinet's horizontal centre so both
    doors' stile seam and both knobs have a chance of falling in frame at
    this focal length) with the camera pulled back and slightly low so the
    counter's front top edge (Z=91.44 at the counter's front, Y nearer 0)
    clips into the bottom of frame as the requested "sliver of counter edge".
    """
    # Phase 5e render-iteration finding: the first framing (target at knob
    # height Z=72.23, camera pulled back only ~96cm, 65mm) put both knobs
    # too close to frame edge and showed no counter sliver at the bottom at
    # all. Re-aimed slightly lower (Z=68, between knob and door-centre
    # height) and pulled back further (~121cm) at the same 65mm focal length
    # so the frame's bottom edge reaches down far enough to catch the
    # counter's front top edge (Z=91.44) as the requested sliver, while
    # still keeping both B30 knobs and the door stile seam comfortably in
    # frame at this focal length/working distance.
    # 2026-09-28 Phase 6 Part 1 recompose (Plan.md 6.1): the prior framing
    # (knob-height target, dead-on yaw~90, 65mm) was too tight -- it showed
    # only B30's two doors/knobs with no adjacent painted cabinetry or stone
    # edge in frame (RENDER_SETTINGS.md "Composition check" note). Re-aimed
    # slightly right (toward the B30/SB36 seam at world X=-137.16) and raised
    # both the camera and the aim point so the frame's top edge clears the
    # countertop line (Z=91.44) and shows the illuminated stone overhang, and
    # the frame's right edge crosses the B30/SB36 seam into a few inches of
    # SB36's painted ivory door. Camera pulled back to ~121cm working
    # distance at a slightly-above-knob height, aimed down at ~-8deg pitch --
    # a gentle 3/4-ish look (yaw~92.4, not dead-on 90) rather than a
    # straight-on elevation. Verified by projecting the frame onto the front
    # face plane (Y=-62.23): world X range approx [-202.6,-127.4] (covers all
    # of B30 [-213.36,-137.16] plus ~10cm/4in of SB36 past the -137.16 seam)
    # and Z range approx [56.8,99.2] (brackets the counter top at Z=91.44,
    # giving a visible stone edge/overhang near the top of frame while still
    # keeping both B30 knobs -- world X -179.23/-171.29 -- and the door-stile
    # seam comfortably inside the frame).
    # Iteration 2 (preview 1 review): iteration 1 (-165,-62.23,78 / cam
    # -160,-182.23,95, 58mm) showed only a narrow ~12%-of-frame sliver of
    # SB36's painted ivory door at the left edge -- widened further (aim
    # further right toward SB36, camera pulled back a touch more) so the
    # adjacent painted cabinetry reads clearly as its own material, not just
    # an edge pixel.
    target = unreal.Vector(-160.0, -62.23, 79.0)
    loc = unreal.Vector(-155.0, -192.0, 96.0)        # ~131cm back, camera above knob height, tilted down
    direction = target - loc
    rot = direction.rotator()
    cam = spawn_or_get_camera("CAM_Detail", loc, rot)
    focus_dist = (target - loc).length()
    # Phase 5e Task 2: f/3.2 (shallow but not razor-thin at this ~96cm
    # working distance -- keeps both the near knob and the door's grain
    # readably sharp while still separating from the counter/background),
    # per-camera AutoExposureBias tuned specifically for this shot (see
    # apply_exposure_override / Docs/Lighting.md Phase 5e section) so the
    # oak reads the Task 1 target mid-brown without clipping the brass
    # knob's specular highlight.
    # Phase 5e render-iteration finding: the first attempt at this shot used
    # AutoExposureBias=5.5 (reasoning it needed MORE exposure like the other
    # two cameras) and came back badly blown out (door grain avg sRGB
    # ~243,227,212, knob fully clipped at 255) -- this close framing catches
    # far more of the LED/fill-light bounce than the wider shots' view of
    # the same B30 surface (which, at the shared bias=4.0, actually reads
    # UNDER the 0.2-0.3 target at ~0.09 linear luminance -- the two cameras
    # see very different amounts of light on the same material because of
    # framing/angle, not because the material itself changed). Lowered to
    # AutoExposureBias=1.8 for this shot specifically.
    # 2026-09-27 relight pass iteration log: bias=1.8 (old baseline) measured
    # mean sRGB ~96,87,92 (too dark, B>G wrong ratio); bias=3.6 measured
    # ~181,172,177 (badly overexposed, washed pink-grey, still B>G). Target
    # is R~110-150/G~75-105/B~45-75 -- roughly halfway between those two
    # points on brightness, so interpolating: 1.8 + (3.6-1.8)*((130-96)/(181-96))
    # ~= 2.5. Also note B>G persisted at BOTH prior bias values despite the
    # material's own tint being correctly R>G>B on paper -- this is the
    # skylight/fill's cooler color temperature dominating a still-underlit
    # surface, expected to correct itself as exposure lands in-range (a
    # correctly-exposed warm-lit surface should stop reading cool-shifted).
    # 2026-09-27 relight pass round 5 finding: the original centre-crop
    # measurement box included the brass knobs' specular highlights, which
    # biased the sampled mean toward grey/blue (B>G) even once the material
    # tint and exposure were both correct -- a flat-panel-only crop (away
    # from the knob) at this same bias=2.5 measured (109.8, 88.7, 83.8),
    # correctly R>G>B and inside/adjacent to the G/B targets, with only R
    # sitting ~0.2 below the 110 floor. Nudged up slightly to 2.8 to clear it.
    # 2026-09-28 Phase 6 Part 1 recompose: widened focal length 65mm -> 58mm
    # and opened the aperture slightly, f/3.2 -> f/3.6, to hold a touch more
    # depth of field across the wider frame (both knobs, the door-stile seam,
    # the SB36 seam, and the countertop edge all now span a bigger working
    # area than the old tight crop) while staying in the approved 50-65mm /
    # f/3.2-4 band and keeping the near B30 knob the sharp focal point.
    bias = DETAIL_BIAS_BY_PRESET[CURRENT_PRESET]
    if IS_HERO:
        bias += LOOK_PARAMS[CURRENT_LOOK]["detail_bias_delta"]
    configure_camera(cam, focal_length=55.0, aperture=3.6, focus_distance_cm=focus_dist, auto_exposure_bias=bias)
    log("CAM_Detail [%s/look=%s]: loc=(-155.0,-192.0,96.0), aimed at (-160.0,-62.23,79.0) near B30 knob 2, "
        "widened to include SB36 painted door + countertop/stone edge, 55mm, f/3.6, focus_distance=%.1fcm, "
        "per-camera AutoExposureBias=%.2f" % (CURRENT_PRESET, CURRENT_LOOK, focus_dist, bias))
    return cam


def ensure_sequence_dir():
    if not unreal.EditorAssetLibrary.does_directory_exist(SEQ_DIR):
        unreal.EditorAssetLibrary.make_directory(SEQ_DIR)


def create_or_get_sequence(name, camera_actor, frame_count=1):
    """
    Creates /Game/WTK/Cinematics/LS_Test_<name> with a camera cut track
    bound to camera_actor, 1 frame long (or frame_count frames).
    Idempotent: if the sequence asset already exists, reuse it and just
    ensure the camera-cut binding/frame range are correct.
    """
    asset_name = "LS_Test_%s" % name
    asset_path = "%s/%s" % (SEQ_DIR, asset_name)
    ensure_sequence_dir()

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        seq = unreal.EditorAssetLibrary.load_asset(asset_path)
        log("Found existing sequence '%s' -- reusing." % asset_path)
    else:
        factory = unreal.LevelSequenceFactoryNew()
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        seq = asset_tools.create_asset(asset_name, SEQ_DIR, unreal.LevelSequence, factory)
        log("Created new sequence '%s'." % asset_path)

    seq.set_playback_start(0)
    seq.set_playback_end(frame_count)

    # Camera cut track: ensure one exists and has a single section bound to
    # camera_actor spanning the full playback range.
    cut_tracks = seq.find_master_tracks_by_type(unreal.MovieSceneCameraCutTrack) \
        if hasattr(seq, "find_master_tracks_by_type") else seq.get_tracks()
    cut_track = None
    for t in seq.get_tracks():
        if isinstance(t, unreal.MovieSceneCameraCutTrack):
            cut_track = t
            break
    if cut_track is None:
        cut_track = seq.add_track(unreal.MovieSceneCameraCutTrack)

    # Bind the camera actor into the sequence's possessables.
    #
    # 2026-09-27 fix (WTK_Main_v2 clean-room rebuild): the LS_Test_CAM_*
    # sequences are a single shared asset under /Game/WTK/Cinematics/, not
    # per-level -- they were originally created (and possessable-bound)
    # against the CineCameraActor living in the OLD /Game/WTK/Maps/WTK_Main.
    # The old code matched an existing possessable purely by display-name
    # label ("CAM_Wide" == "CAM_Wide") and reused it as-is. A possessable's
    # bound object is resolved at runtime by looking up its stored object
    # reference/Guid against the CURRENTLY LOADED level -- rebuilding the
    # level from scratch spawns a brand-new CineCameraActor with a different
    # underlying object identity, so the label matches but the possessable
    # still silently points at the (now nonexistent, in a different map)
    # OLD actor. This produced a "successful" binding_id readback (the cut
    # section's Guid pointed at a real, resolvable possessable entry) while
    # MRQ's actual render showed "Failed to evaluate camera ... No camera
    # actor found" for every one of the 3 test renders against WTK_Main_v2 --
    # confirmed by inspecting Saved/Logs/WTK.log after the first WTK_Main_v2
    # render pass. Fixed: verify the existing possessable actually resolves
    # to camera_actor in the current world via locate_bound_objects(); if it
    # doesn't (wrong actor, or resolves to nothing), remove the stale
    # possessable and create a fresh one against the current camera_actor.
    bindings = seq.get_bindings()
    cam_binding = None
    for b in bindings:
        if b.get_display_name() != camera_actor.get_actor_label():
            continue
        try:
            world = unreal.EditorLevelLibrary.get_editor_world()
            bound_objects = seq.locate_bound_objects(b, world) if world else []
        except Exception:
            bound_objects = []
        if camera_actor in bound_objects:
            cam_binding = b
            log("Existing possessable for '%s' correctly resolves to the current camera actor -- reusing." % name)
        else:
            log("Existing possessable for '%s' does NOT resolve to the current camera actor "
                "(stale binding from a previous level) -- removing and re-creating." % name)
            try:
                seq.remove_possessable(b)
            except Exception as rex:
                log("WARNING: could not remove stale possessable for %s: %s" % (name, rex))
        break
    if cam_binding is None:
        cam_binding = seq.add_possessable(camera_actor)
        log("Created fresh possessable binding for '%s' -> %s." % (name, camera_actor.get_actor_label()))

    sections = cut_track.get_sections()
    if not sections:
        section = cut_track.add_section()
    else:
        section = sections[0]
    section.set_range(0, frame_count)
    # Round 4 fix (coordinator-prompted investigation): MRQ's own log showed
    # "Expanding Shot 1/1 (Shot: no shot Camera: )" -- an EMPTY camera field
    # -- for every job in every prior round, and all 3 test renders came out
    # byte-identical (same default/fallback camera view showing sky + sun
    # disk, not any of the 3 configured CineCameraActors). Root cause,
    # confirmed via tmp/Wtk5d_20260926/check_binding_id.py and
    # fix_binding_direct.py: passing a bare unreal.Guid directly to either
    # `section.set_editor_property("camera_binding_id", ...)` (round 1-3) or
    # `section.set_camera_binding_id(guid)` (first round-4 attempt) both
    # silently produce a MovieSceneObjectBindingID with an all-zero Guid
    # field ("(Guid=00000000...)") -- neither call errors, they just don't
    # populate the struct correctly from a raw Guid argument. The working
    # pattern: explicitly construct an empty unreal.MovieSceneObjectBindingID(),
    # set its "guid" field via set_editor_property with the binding's real
    # Guid, THEN pass that whole populated struct to
    # section.set_camera_binding_id(). Verified via readback
    # (export_text()) that this actually stores the real, non-zero Guid.
    try:
        # Round 4 fix, second half: the in-memory set_camera_binding_id()
        # call above (built from a properly-populated
        # MovieSceneObjectBindingID struct) reads back correctly WITHIN the
        # same process, but a fresh process loading the saved asset from
        # disk still showed an all-zero Guid -- section.set_camera_binding_id()
        # mutates the section's data but doesn't automatically call
        # Modify()/mark the package dirty, so EditorAssetLibrary.save_asset()
        # (by path) serialized the OLD (zeroed) state. Confirmed fix (via
        # tmp/Wtk5d_20260926/test_dirty_fix.py + a fresh-process readback):
        # call section.modify() BEFORE mutating it, and use
        # EditorAssetLibrary.save_loaded_asset(seq) (the loaded object,
        # not save_asset(path)) afterward.
        section.modify()
        binding_id = unreal.MovieSceneObjectBindingID()
        binding_id.set_editor_property("guid", cam_binding.get_id())
        section.set_camera_binding_id(binding_id)
        readback = section.get_camera_binding_id()
        log("Camera binding id for %s set to %s -> readback %s" % (
            name, cam_binding.get_id().export_text(), readback.export_text()))
    except Exception as e:
        log("WARNING: could not set camera_binding_id on cut section for %s: %s" % (name, e))

    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    log("Sequence '%s' bound to camera '%s', range [0,%d]." % (asset_path, camera_actor.get_actor_label(), frame_count))
    return seq


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)

    cam_wide = setup_cam_wide()
    cam_angle = setup_cam_angle()
    cam_detail = setup_cam_detail()

    create_or_get_sequence("CAM_Wide", cam_wide, frame_count=1)
    create_or_get_sequence("CAM_Angle", cam_angle, frame_count=1)
    create_or_get_sequence("CAM_Detail", cam_detail, frame_count=1)

    # WTK prop-fix pass round 2 (2026-09-26): robust save, matching the fix
    # applied to place_props_wtk.py after the coordinator found that script's
    # save_current_level()-only call silently failed to persist to the
    # .umap. This script's own Level Sequence camera-binding save already
    # uses the correct save_loaded_asset(seq)-on-the-loaded-object pattern
    # (see create_or_get_sequence()'s own comment, fixed back in Phase 5d for
    # a related persistence bug) -- but the LEVEL save at the end of main()
    # here was still the same single save_current_level() call now known to
    # be unreliable. Hardened with the same save_map()+save_dirty_packages()
    # pattern. NOT independently re-verified by a live before/after .umap-
    # timestamp check this pass (only place_props_wtk.py's own bug was
    # directly tested) -- recommended follow-up verification next rerun.
    world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    saved_ok = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    log("save_map(%s) returned %s" % (MAP_PATH, saved_ok))
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("Camera + sequence setup complete, level saved (save_current_level + save_map + save_dirty_packages).")
    _flush_log_to_file()


if __name__ == "__main__":
    main()
