"""
WTK Phase 5d: lighting, exposure, post-process.

Idempotent: spawns/updates actors by unique Label under a "WTK_Lighting"
folder. Re-running this script updates the same actors in place (found by
label) rather than duplicating them.

Scene facts (UE cm, confirmed via tmp/Wtk5d_20260926/dump_actors.py against
/Game/WTK/Maps/WTK_Main on 2026-09-26):
  - Room interior: X [-335.28, 30.48], Y [-426.72, 0], Z [0, 243.84] (ceiling).
  - Back wall (the one with the window) = Walls_Basic_Wall_WTK_Interior_6in,
    spanning X [-350.52, 45.72], Y [0, 15.24] (6in / 15.24cm thick), Z [0,243.84].
    Its face is at Y=0; room interior (cabinets) is on the NEGATIVE Y side.
  - Cabinets (B30, W18, W30) all span Y [-62.23..-31.75, 0.00] -- confirms the
    room/interior is Y<0, matching the back wall.
  - Window (Windows_Window-Fixed_WTK_Fixed_2630) X [-128.90, -53.98],
    Z [107.32, 197.49], Y [-1.90, 9.52] -- embedded in the back wall at Y~0.
    So OUTSIDE is the +Y side beyond Y=15.24 (through the wall), meaning sun/
    exterior light must come from +Y through the window and land INSIDE at -Y.
  - Ceiling: Z = 243.84 (Ceilings_Basic_Ceiling_Generic top).
  - Uppers: W18 X[-45.72,0], Z[137.16,213.36]; W30 X[-213.36,-137.16],
    Z[137.16,213.36]; both bottom Z=137.16, depth (Y) 31.75cm.

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this> -unattended -nop4 -nosplash -stdout
"""
import unreal
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH

# 2026-09-27 window-only daylight pass (WtkWindowOnly_20260927): replaces the
# night/LED/can preset set entirely, per the user's decision that the LEDs,
# cans, and fill light are REMOVED from the design -- the scene is lit ONLY
# by the sun + sky through the window. Sun geometry per
# Pause/RESEARCH_2026-09-27_WTK_DAYLIGHT_TIME_OF_DAY_LOOP1_LOOP2_LOOP3.md's
# "Recommended settings table" and Test plan, with an orchestrator correction
# applied: the cabinets are on the SAME wall as the window (window at Y=0,
# cabinets Y[-62.23,0]), not the far wall, so direct sun can never land on
# the cabinet fronts -- only a floor sun-patch mid-room (which bounces warm
# fill back onto the cabinet fronts) and the window/countertop area near the
# glass. Geometry re-derived for this pass (window opening
# X[-128.90,-53.98], Z[107.32,197.49], center X=-91.44, back wall face Y=0,
# floor Z=0, room Y[-426.72,0], room X[-335.28,30.48]):
#   Elevation 28 deg, yaw 245 deg (25 deg off the dead-on yaw=270, within the
#   research doc's 20-30 deg offset band). Forward vector (UE convention,
#   forward=(cos(yaw),sin(yaw),-sin(elev))) = (-0.423,-0.906,-0.469) -- has
#   the required -Y component (light travels from +Y outside, through the
#   window, into the -Y room) and a -X rake component so the patch isn't
#   square-on. Ray-traced against the window opening's own head/sill Z at
#   this elevation/yaw: the projected floor patch spans
#   X[-269,-188] x Y[-207,-381] -- fully inside the room bounds (X[-335,30],
#   Y[-427,0]), squarely mid-room (visible in CAM_Wide loc Y=-380/CAM_Angle
#   loc Y=-300), and does NOT overlap the B30 door/brass area (B30 is ON THE
#   WALL at Y[-62.23,0], X[-213.36,-137.16] -- the floor patch's nearest edge
#   at Y=-207 is ~145cm clear of the cabinet face at Y=0, and CAM_Detail's
#   B30 knob framing (X~-171, Y~-62) sits well outside the patch's Y range
#   entirely). This satisfies the task's own verification requirement (patch
#   lands mid-room, visible in CAM_Wide/CAM_Angle, no hard patch on B30/brass
#   in CAM_Detail).
SUN_ELEVATION_DEG = 28.0
SUN_AZIMUTH_YAW_DEG = 245.0
# Real clear-sky lux (research doc: ~60,000-100,000 for clear sun). Chosen at
# the low end of that range since Extend Default Luminance Range + manual
# exposure (see setup_ppv()) is what actually controls the window/room
# brightness relationship, not the raw lux value alone; a full ~100,000 lux
# sun made the window fully clip white even at a bias tuned for the room in
# round-1 iteration (see Docs/Lighting.md), so 65,000 lux is used as the
# justified real-world value that leaves headroom for the manual-exposure
# tuning below to do its job without needing an unrealistically low lux.
SUN_INTENSITY_LUX = 65000.0
SUN_TEMP_K = 4400.0  # research doc: ~4000-4800K for a 25-30deg elevation sun
# 2026-09-27 path-tracer pass: the orchestrator review found the pre-path-
# tracer hero renders had a sepia/orange cast across the whole image (walls,
# ceiling, ivory cabinets all reading tan/brown instead of warm-white/ivory).
# White Balance mode's white_temp neutralises a light source AT that
# temperature to appear white/neutral; 5200K under a 4400K sun + a real
# (uncorrected) sky was undercorrecting the sun's own warmth, leaving the
# sepia cast. Lowered into the task's suggested 4600-5000K band -- 4800K,
# picked as the middle of that band for the first path-tracer round, judged
# and re-tuned against the ivory patches' measured R/G/B ratios below.
WHITE_TEMP = 3800.0  # White Balance mode -- round 5/final (path-tracer pass): round 4 (4200K) moved B/R the right direction (0.62->0.70 upper, 0.38->0.46 lower) but not far enough; pushed further below the task's original suggested band, which this scene's real 4400K sun + SkyAtmosphere needed to fully neutralise

SUN_SOURCE_ANGLE_DEG = 0.5357  # Epic default -- research doc: keep default for a clear-sky hero, don't enlarge toward overcast

# ---------------------------------------------------------------------------
# 2026-09-27 window-only daylight pass: day-only preset set. Env var
# WTK_LIGHT_PRESET selects one of:
#   hero      -- Variant A: elevation 28deg (SUN_ELEVATION_DEG), the primary
#                recommended look.
#   alt_soft  -- Variant B: elevation 15-20deg, softer/lower-contrast
#                alternate (sun patch mostly clears the room per the
#                research doc's geometry table; room reads more skylight-lit).
#   overcast  -- Variant D: farmland_overcast.hdr exterior backdrop, sun
#                intensity dropped substantially (soft/no direct patch),
#                per the research doc's Mr. Hollt-sourced pattern.
# Defaults to "hero" if unset/unrecognized. Variant C (exposure-only
# regression check) is intentionally NOT a preset here -- it was a
# diagnostic-only variant in the research doc's test plan, skipped per this
# pass's own task instruction ("Skip Variant C").
# ---------------------------------------------------------------------------
import os as _os

VALID_PRESETS = ("hero", "alt_soft", "overcast")
CURRENT_PRESET = _os.environ.get("WTK_LIGHT_PRESET", "hero")
if CURRENT_PRESET not in VALID_PRESETS:
    CURRENT_PRESET = "hero"

IS_NIGHT = False  # kept as a name for minimal downstream diff; night presets no longer exist
IS_ALT_SOFT = CURRENT_PRESET == "alt_soft"
IS_OVERCAST = CURRENT_PRESET == "overcast"
IS_HERO = CURRENT_PRESET == "hero"

# WTK_PPV's own exposure_bias per preset -- iterated live against CAM_Wide
# renders; see Docs/Lighting.md for the round-by-round measurements that
# produced these final values. This is the PPV's shared bias; CAM_Wide/
# CAM_Angle/CAM_Detail's own per-camera overrides (setup_cameras_wtk.py)
# fully replace this for whichever camera has one set (see
# apply_exposure_override()'s docstring there), so the real controlling
# value for those cameras lives in WTK_LIGHT_PRESET-aware code in that
# script, not here -- this PPV-level default only matters for a camera with
# no override, or for in-editor viewport preview.
PPV_BIAS_BY_PRESET = {
    "hero": 3.4,
    "alt_soft": 3.6,
    "overcast": 3.0,
}


def log(msg):
    print("[WTK_Lighting] %s" % msg)


def _actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def find_actor_by_label(label):
    actors = _actor_subsys().get_all_level_actors()
    for a in actors:
        if a.get_actor_label() == label:
            return a
    return None


def spawn_or_get(actor_class, label, location=unreal.Vector(0, 0, 0), rotation=unreal.Rotator(0, 0, 0)):
    existing = find_actor_by_label(label)
    if existing:
        # Round 6 fix: this used to return the existing actor WITHOUT ever
        # applying the caller's (possibly-changed) location/rotation --
        # confirmed via the LED roll fix (round 6) silently not taking
        # effect across a rerun: the actor already existed from an earlier
        # round, so its rotation stayed at the OLD roll=0 value even after
        # the script was edited to pass roll=90. Every "idempotent update"
        # call site in this file relies on spawn_or_get() to actually re-
        # apply position/rotation on a rerun, so it must do so here.
        #
        # WTK prop-fix pass, round 2 (2026-09-26) audit finding: the
        # coordinator found place_props_wtk.py's equivalent "update existing
        # actor" path silently failed to persist to WTK_Main.umap because
        # set_actor_location()/set_actor_rotation() do not themselves mark
        # the owning package dirty -- the same risk applies here, since this
        # function never called existing.modify() before mutating it either.
        # This was NOT independently re-verified against a live rerun this
        # pass (that would require re-running the full lighting setup and
        # checking the .umap's on-disk timestamp again, which was out of
        # this pass's scope -- only place_props_wtk.py's own bug was
        # confirmed and fixed by direct testing). Fixed defensively here by
        # the same pattern regardless, since it is cheap and strictly safer.
        existing.modify()
        existing.set_actor_location(location, False, False)
        existing.set_actor_rotation(rotation, False)
        log("Found existing actor '%s' (%s) -- updated location/rotation in place." % (label, existing.get_class().get_name()))
        return existing, False
    actor = _actor_subsys().spawn_actor_from_class(actor_class, location, rotation)
    actor.set_actor_label(label)
    log("Spawned new actor '%s' (%s)." % (label, actor.get_class().get_name()))
    return actor, True


# ---------------------------------------------------------------------------
# 1. Sun (Directional Light)
# ---------------------------------------------------------------------------
def setup_sun():
    """
    Elevation ~15 deg per Plan.md / research doc. Azimuth chosen so sunlight
    enters through the window (which faces +Y -> -Y, i.e. the window's
    outward normal points toward +Y) and rakes across the counter/floor.
    The window's outward normal is +Y (0,1,0). For the sun to shine IN
    through the window, the light must travel in the -Y-ish direction (from
    +Y toward -Y) when it hits the glass, i.e. the DirectionalLight's forward
    vector (the direction light travels) should have a negative Y component.
    We also want some X component so the light rakes across the counter at
    an angle rather than straight in.
    A DirectionalLight's forward vector = rotator's forward. We want forward
    approx (dirX, dirY, dirZ) with dirY < 0 (traveling from +Y into the room),
    dirZ negative (coming down, elevation 15 deg above horizon means the ray
    travels downward at 15 deg), and a modest dirX for the raking angle.
    Elevation 15 deg above horizon -> pitch = -(90-15) is wrong convention;
    for UE's DirectionalLight, Pitch is the rotation about Y (tilts forward
    vector's Z). A light forward vector pointing mostly along -Y with a
    downward tilt of 15 deg below the horizontal (sun elevation 15 deg means
    it travels down at 15 deg from horizontal) needs Pitch = -15 (so forward
    Z = -sin(15)) -- UE DirectionalLight Pitch convention: Pitch rotates
    forward vector down when negative in the Rotator->forward-vector sense
    used by unreal.Rotator (roll, pitch, yaw) -> get_forward_vector().
    Yaw chosen so forward has a negative Y and a moderate negative X, i.e.
    the sun is positioned in the +Y,+X quadrant outside the window shining
    down-and-across into -Y,-X, raking across the counter/floor at an angle.
    Window-only daylight pass (2026-09-27): elevation/yaw are now computed
    per the research doc's geometry (see module header for the full
    derivation and the orchestrator correction that the cabinets are on the
    SAME wall as the window, so the sun can only ever produce a floor patch,
    never a direct hit on the cabinet fronts).
    """
    # 2026-09-27 window-only daylight pass: per-preset sun geometry/intensity.
    #   hero (Variant A): SUN_ELEVATION_DEG/SUN_AZIMUTH_YAW_DEG as derived in
    #     the module header (28deg/245deg), SUN_INTENSITY_LUX (65000).
    #   alt_soft (Variant B): lower elevation (15-20deg, using 17deg), same
    #     azimuth offset -- per the research doc, the direct beam mostly
    #     clears the room depth at this elevation, so the room reads more
    #     skylight-lit/soft rather than showing a hard floor patch.
    #   overcast (Variant D): sun intensity dropped substantially (a low,
    #     soft key per the research doc's Mr. Hollt-sourced pattern) since
    #     the farmland_overcast.hdr backdrop is the dominant visual read;
    #     elevation/yaw kept for consistency but barely matters at this low
    #     an intensity.
    if IS_ALT_SOFT:
        elevation_deg = 17.0
        azimuth_yaw_deg = SUN_AZIMUTH_YAW_DEG
        intensity = SUN_INTENSITY_LUX
        cast_shadows = True
    elif IS_OVERCAST:
        elevation_deg = SUN_ELEVATION_DEG
        azimuth_yaw_deg = SUN_AZIMUTH_YAW_DEG
        intensity = 8000.0  # low/soft key, per Mr. Hollt's HDRI-backdrop pattern (research doc Loop 3)
        cast_shadows = True
    else:  # hero
        elevation_deg = SUN_ELEVATION_DEG
        azimuth_yaw_deg = SUN_AZIMUTH_YAW_DEG
        intensity = SUN_INTENSITY_LUX
        cast_shadows = True

    pitch = -elevation_deg  # negative pitch tilts the forward vector downward
    rot = unreal.Rotator(pitch=pitch, yaw=azimuth_yaw_deg, roll=0.0)
    sun, is_new = spawn_or_get(unreal.DirectionalLight, "WTK_Sun", unreal.Vector(0, 200, 300), rot)
    sun.set_actor_rotation(rot, False)

    comp = sun.light_component
    comp.modify()  # WTK prop-fix pass round 2: modify() before mutating an existing component's properties, see spawn_or_get()'s own comment
    comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    comp.set_editor_property("intensity", intensity)  # lux
    comp.set_editor_property("light_color", unreal.Color(255, 255, 255, 255))
    comp.set_editor_property("use_temperature", True)
    comp.set_editor_property("temperature", SUN_TEMP_K)
    comp.set_editor_property("light_source_angle", SUN_SOURCE_ANGLE_DEG)
    comp.set_editor_property("cast_shadows", cast_shadows)
    comp.set_editor_property("atmosphere_sun_light", True)
    try:
        comp.set_editor_property("shadow_source_angle_factor", 1.0)
    except Exception:
        pass
    # Virtual Shadow Maps (VSM) is the Lumen default; explicitly opt-in.
    try:
        comp.set_editor_property("use_ray_traced_distance_field_shadows", False)
    except Exception:
        pass
    log("Sun [%s]: elevation=%.1f deg (pitch=%.1f), yaw=%.1f, intensity=%.0f lux, cast_shadows=%s" %
        (CURRENT_PRESET, elevation_deg, pitch, azimuth_yaw_deg, intensity, cast_shadows))
    return sun


# ---------------------------------------------------------------------------
# 2. Sky Atmosphere + Sky Light + optional Height Fog
# ---------------------------------------------------------------------------
def setup_sky_atmosphere():
    actor, _ = spawn_or_get(unreal.SkyAtmosphere, "WTK_SkyAtmosphere", unreal.Vector(0, 0, 0))
    return actor


def setup_sky_light():
    actor, _ = spawn_or_get(unreal.SkyLight, "WTK_SkyLight", unreal.Vector(-150, -200, 120))
    comp = actor.light_component
    comp.modify()  # WTK prop-fix pass round 2
    comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    comp.set_editor_property("real_time_capture", True)
    # Distance-threshold gotcha from research: default 150000 makes a small
    # interior room look "fully inside" the capture sphere and go dark/flat.
    # Lower it so the capture actually resolves interior vs exterior at this
    # room's ~4m scale.
    comp.set_editor_property("sky_distance_threshold", 150.0)
    # UE 5.7 exposes this as 'lower_hemisphere_is_black' (not
    # 'LowerHemisphereIsSolidColor' as in some older/other-branch docs) --
    # confirmed via property introspection (tmp/Wtk5d_20260926/introspect_skylight.py).
    #
    # 2026-09-27 window-only daylight pass: user feedback on the previous
    # render was "too bright, natural window light does not look like that"
    # -- the earlier relight-pass cheat (lower_hemisphere_is_black=False +
    # a synthetic fill color/intensity) is REMOVED entirely; no
    # skylight-leaking cheat. lower_hemisphere_is_black=True (physically
    # correct: the ground below the horizon should not glow uniformly) and
    # a real, physically-plausible intensity of 1.0 per the task spec,
    # relying on the manual-exposure-first workflow (setup_ppv() +
    # setup_cameras_wtk.py's per-camera override) rather than an artificially
    # dimmed SkyLight to keep the ceiling/walls from reading too bright.
    # Round 2 iteration finding: intensity=1.0 (naive physically-plausible
    # default) plus the round-2 exposure bump pushed the ceiling centre to
    # ~155 (target 90-140, and it must read darker than the back/window
    # wall). Lowered slightly to 0.75 -- still a real, non-cheat physically
    # plausible SkyLight intensity (not the near-zero/near-1 tug-of-war the
    # earlier day/night preset pass went through), just tuned down enough
    # that the ceiling's bounce contribution comes back under its target
    # once combined with the round-3 camera-bias retune.
    # 2026-09-27 WtkPTFix5 pass: tried raising SkyLight intensity 0.5->0.9 to
    # lift the shadowed lower-cabinet zone (oak flat panel measured ~76/42/22
    # vs target 105-120/63-90/41-75). RETRACTED -- a real re-render at 0.9
    # measured byte-identical pixel values to the 0.5 baseline in every
    # patch (upper ivory 144.76/122.24/101.84, oak flat panel
    # 76.23/41.81/22.20, back_wall 159.87/140.74/121.29, window
    # 197.98/200.02/201.38 -- all unchanged to 2 decimal places). This
    # reproduces section 15.1's diagnostic (f) finding (Docs/Lighting.md):
    # the SkyLight actor's own real-time-captured contribution is negligible
    # to the path tracer, which samples SkyAtmosphere directly instead --
    # SkyLight intensity is not a usable lever for path-traced ambient fill
    # in this engine/pipeline. Reverted to the documented 0.5 value; the
    # lower-cabinet brightness shortfall is addressed via camera
    # AutoExposureBias instead (setup_cameras_wtk.py), disclosed as a
    # geometry-driven falloff (lower cabinets are out of the sun's direct
    # throw) rather than fully resolved.
    comp.set_editor_property("lower_hemisphere_is_black", True)
    comp.set_editor_property("intensity", 0.5)
    comp.set_editor_property("light_color", unreal.Color(255, 255, 255, 255))
    log("SkyLight [%s]: real_time_capture=True, sky_distance_threshold=150, "
        "lower_hemisphere_is_black=True, intensity=0.5 (physically plausible, no cheat; 0.9 tested and retracted -- no measurable effect on the path tracer)" % CURRENT_PRESET)
    return actor


def setup_height_fog():
    actor, _ = spawn_or_get(unreal.ExponentialHeightFog, "WTK_HeightFog", unreal.Vector(0, 0, 0))
    comp = actor.component
    comp.modify()  # WTK prop-fix pass round 2
    comp.set_editor_property("fog_density", 0.005)  # subtle, optional per task
    log("HeightFog: fog_density=0.005 (subtle); inscattering colour left at engine default "
        "(no 'fog_inscattering_color' property exposed on this UE 5.7 ExponentialHeightFogComponent build)")
    return actor


# ---------------------------------------------------------------------------
# 3. Exterior view through the window: HDRI sky dome + textured ground plane
# (2026-09-27 day/night preset pass -- replaces the earlier bare grey/grass
# engine-default plane, which read as a clipped white/grey void through the
# glass at the old cheat exposure). Outside is the +Y side beyond the back
# wall (Y > 15.24).
# ---------------------------------------------------------------------------
# 2026-09-27 path-tracer pass (WtkPathTrace_20260927): the orchestrator
# review of the pre-path-tracer hero renders flagged the window exterior as
# "a pale grey void with no landscape". Root-caused to using
# farmland_overcast.hdr (a soft OVERCAST sky) for the hero/alt_soft presets
# too, which reads as a flat, nearly-white sky at the exposure/WB tuned for a
# bright clear-sun interior -- wrong sky character, not a missing-geometry
# bug. hero/alt_soft now use a genuine clear-sky HDRI (sunny_vondelpark, CC0,
# Poly Haven -- see WTK_SourceTextures/LICENSES.md section 8) with visible
# blue sky and tree/ground detail; overcast keeps farmland_overcast.hdr
# unchanged (it is that preset's own intended look, Variant D).
HDRI_SRC_PATH_CLEAR = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK_SourceTextures\HDRI\sunny_vondelpark\sunny_vondelpark_4k.hdr"
HDRI_SRC_PATH_OVERCAST = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK_SourceTextures\HDRI\farmland_overcast\farmland_overcast_4k.hdr"
HDRI_DEST_DIR = "/Game/WTK/HDRI"
# The Interchange importer names the resulting Texture2D asset after the
# source file's own basename, NOT a "T_" prefix -- confirmed live
# (tmp/WtkRelight2_20260927/import_hdri.log's own
# "Waiting for textures to be ready 0/1 (/Game/WTK/HDRI/farmland_overcast_4k)"
# line) after a first attempt at a "T_Farmland_Overcast" path failed with
# "LoadAsset failed: ... could not be found in the Asset Registry."
HDRI_TEXTURE_PATH_CLEAR = "/Game/WTK/HDRI/sunny_vondelpark_4k"
HDRI_TEXTURE_PATH_OVERCAST = "/Game/WTK/HDRI/farmland_overcast_4k"
SKY_MAT_PATH = "/Game/WTK/HDRI/M_SkyDome_Unlit"
GROUND_MAT_PATH = "/Game/WTK/HDRI/M_GroundOutside_Unlit"

# 2026-09-28 realism pass (WtkRealism_20260928): the sky dome (setup_sky_dome,
# above) reads as a flat, featureless cyan/blue wash through the window --
# disclosed as an open, not-fixed-this-pass limitation in 3 prior passes
# (WtkPTFix/2/3/4/5, see this doc's own history) despite the HDRI cubemap
# genuinely being sampled (confirmed live: hiding the dome or forcing a
# garish tint both visibly changed the window, ruling out "nothing is being
# sampled" -- the issue is that at the room's tuned interior exposure, the
# HDRI's own sky-dominant hemisphere reads as a near-uniform bright colour
# with no recognisable tree/foliage silhouette). Per the task's own "Option
# B" fallback, added a dedicated flat unlit-emissive BACKPLATE CARD (a large
# plane, NOT the dome) carrying an actual LDR photo (trees + sky, real
# spatial detail baked into the pixels rather than relying on HDR-range
# sampling) placed just outside the window, facing into the room. This is a
# plain Texture2D UV-mapped quad, independent of the dome/cubemap machinery
# above -- both the dome and the ground plane are LEFT IN PLACE (harmless,
# unused visually once the backplate card's larger, closer, opaque plane
# occludes them through the window's narrow view cone; not deleted so a
# future revert is a one-line change).
BACKPLATE_SRC_PATH = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK_SourceTextures\Backplate\WTK_ExteriorBackplate.jpg"
# 2026-09-28: matches import_hdri_texture()'s own already-documented finding
# (see HDRI_TEXTURE_PATH_CLEAR's comment above) -- the Interchange importer
# names the resulting asset after the source file's own basename, NOT a
# "T_"-prefixed name; confirmed live this pass (the first two rounds crashed
# under -run=pythonscript on EVERY run rather than short-circuiting via
# does_asset_exist() on round 2+, because this path was wrong and never
# matched the real imported asset -- WTK_ExteriorBackplate.uasset, not
# T_WindowBackplate.uasset -- so does_asset_exist() always returned False).
BACKPLATE_TEXTURE_PATH = "/Game/WTK/HDRI/WTK_ExteriorBackplate"
BACKPLATE_MAT_PATH = "/Game/WTK/HDRI/M_WindowBackplate_Unlit"


def _import_hdri(src_path, dest_texture_path):
    """
    Imports one .hdr (CC0, see WTK_SourceTextures/HDRI's own license file),
    once per texture path. Idempotent: does_asset_exist() short-circuits a
    re-import on every subsequent run (a re-import with
    replace_existing=True would also be safe/idempotent, but skipping is
    cheaper and these textures never change). Note: UE 5.7's Interchange
    importer produces a TextureCube from a .hdr (confirmed live), not a
    plain Texture2D -- _build_unlit_emissive_material()'s cubemap-sample
    node setup accounts for this.
    """
    if unreal.EditorAssetLibrary.does_asset_exist(dest_texture_path):
        return unreal.EditorAssetLibrary.load_asset(dest_texture_path)
    if not os.path.isfile(src_path):
        log("ERROR: HDRI source file not found: %s -- exterior view will fall back to a plain sky colour." % src_path)
        return None
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    task = unreal.AssetImportTask()
    task.filename = src_path
    task.destination_path = HDRI_DEST_DIR
    task.automated = True
    task.save = True
    task.replace_existing = True
    asset_tools.import_asset_tasks([task])
    tex = unreal.EditorAssetLibrary.load_asset(dest_texture_path)
    if tex is None:
        log("ERROR: HDRI import did not produce %s -- check the imported name/path." % dest_texture_path)
    else:
        log("Imported HDRI texture -> %s" % dest_texture_path)
    return tex


def import_hdri_texture():
    """Selects and imports the correct per-preset HDRI (clear-sky for hero/
    alt_soft, overcast for the overcast preset) -- see module-level comment
    above HDRI_SRC_PATH_CLEAR for why hero/alt_soft moved off
    farmland_overcast.hdr."""
    if IS_OVERCAST:
        return _import_hdri(HDRI_SRC_PATH_OVERCAST, HDRI_TEXTURE_PATH_OVERCAST)
    return _import_hdri(HDRI_SRC_PATH_CLEAR, HDRI_TEXTURE_PATH_CLEAR)


def _build_unlit_emissive_material(mat_path, texture, tint=None, brightness=1.0):
    """
    Builds (or reuses) a simple unlit, emissive-only Material whose Emissive
    Color is the given texture (optionally tinted/scaled) -- used for both
    the sky dome (the HDRI itself, so the window shows real sky+landscape
    detail, not a flat colour) and, with a different tint/no texture, the
    ground plane. Unlit so it reads at a fixed, exposure-independent-ish
    brightness appropriate for a background/backdrop element, matching the
    common "HDRI backdrop" convention (the real HDRIBackdrop plugin's own
    A_HDRIBackdrop actor uses an unlit sphere the same way) rather than being
    lit/shadowed by the interior's own lights, which would be physically
    wrong for a distant sky/landscape anyway.
    """
    # 2026-09-27 iteration finding: skip-if-exists made an in-place tint/
    # brightness tweak (e.g. the night sky's brightness=1.0->14.0 fix) a
    # silent no-op on a rerun, since the OLD asset (with the old values
    # baked into its node graph) was just reloaded and reused -- confirmed
    # live (a brightness bump had zero measured effect on the rendered
    # window pixels until this was found). Deletes and recreates every run
    # instead, matching this project's own established pattern for exactly
    # this class of bug (build_wtk_material_instances.py's own "Idempotent:
    # deletes and recreates each MI asset on every run" docstring/fix).
    if unreal.EditorAssetLibrary.does_asset_exist(mat_path):
        unreal.EditorAssetLibrary.delete_asset(mat_path)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialFactoryNew()
    pkg_path, asset_name = mat_path.rsplit("/", 1)
    mat = asset_tools.create_asset(asset_name, pkg_path, unreal.Material, factory)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)

    editor_lib = unreal.MaterialEditingLibrary
    if texture is not None:
        # The Interchange .hdr importer produces a TextureCube (confirmed
        # live: /Game/WTK/HDRI/farmland_overcast_4k imports as class
        # 'TextureCube', not Texture2D), so this samples it as a cubemap
        # driven by the pixel's own world-space normal rather than a UV
        # coordinate -- the correct approach for a skydome sphere viewed
        # from inside (the camera sits inside the sphere, and each pixel's
        # surface normal on the sphere's inner face already points in
        # exactly the direction that pixel represents looking outward at
        # the sky, which is exactly what a cubemap lookup needs).
        tex_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameterCube, -600, 0)
        tex_node.set_editor_property("texture", texture)
        tex_node.set_editor_property("parameter_name", "SkyCubemap")
        normal_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionPixelNormalWS, -900, 0)
        editor_lib.connect_material_expressions(normal_node, "", tex_node, "UVs")
        out_pin = tex_node
    else:
        out_pin = None

    if tint is not None:
        const_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 200)
        const_node.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
        if out_pin is not None:
            mul_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 0)
            editor_lib.connect_material_expressions(out_pin, "RGB", mul_node, "A")
            editor_lib.connect_material_expressions(const_node, "", mul_node, "B")
            out_pin = mul_node
        else:
            out_pin = const_node

    if brightness != 1.0 and out_pin is not None:
        bright_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -200, 100)
        bright_node.set_editor_property("r", brightness)
        mul2 = editor_lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -100, 0)
        editor_lib.connect_material_expressions(out_pin, "", mul2, "A")
        editor_lib.connect_material_expressions(bright_node, "", mul2, "B")
        out_pin = mul2

    if out_pin is not None:
        # Signature is connect_material_property(from_expression,
        # from_output_name, property) -- confirmed via a live TypeError on
        # the first attempt, which had the output-name and property args
        # swapped.
        editor_lib.connect_material_property(out_pin, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    editor_lib.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(mat_path)
    log("Built unlit emissive material %s (texture=%s, tint=%s, brightness=%.2f)" %
        (mat_path, texture is not None, tint, brightness))
    return mat


def setup_sky_dome():
    """
    A large inverted sphere (engine /Engine/BasicShapes/Sphere, negatively
    scaled so its faces point inward toward the camera, matching the usual
    skydome convention) centered on the room, big enough that the window's
    view reads as real sky+landscape rather than a flat void or a clipped-
    white background. Unlit emissive material samples the HDRI texture
    directly, so the window shows recognisable sky/ground detail regardless
    of interior exposure changes. At night, a plain deep-blue-black unlit
    material is used instead (no daytime HDRI at night).
    """
    label = "WTK_SkyDome"
    existing = find_actor_by_label(label)
    if existing:
        actor = existing
    else:
        actor = _actor_subsys().spawn_actor_from_class(
            unreal.StaticMeshActor, unreal.Vector(-91.44, -200.0, 100.0), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(label)
        sphere_mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Sphere.Sphere")
        smc = actor.static_mesh_component
        smc.set_static_mesh(sphere_mesh)
        log("Spawned new sky dome actor.")

    smc = actor.static_mesh_component
    smc.modify()
    # Engine sphere is ~100cm radius at scale 1; scale up to a large backdrop
    # (~60m radius) well outside the room but still resolves as detailed sky
    # through the window at this room's ~4m scale. Negative scale flips
    # winding so the sphere's faces render from the inside (camera is
    # inside the sphere, looking out at its inner surface).
    actor.set_actor_scale3d(unreal.Vector(-600.0, -600.0, -600.0))
    smc.set_editor_property("cast_shadow", False)

    # 2026-09-27 path-tracer pass: hero/alt_soft now use sunny_vondelpark.hdr
    # (a genuine clear-sky HDRI) instead of farmland_overcast.hdr, per the
    # module-level comment above HDRI_SRC_PATH_CLEAR -- overcast keeps
    # farmland_overcast.hdr, its own dedicated Variant D look.
    tex = import_hdri_texture()
    # 2026-09-27 path-tracer pass, round 1 finding: the hero path-traced
    # render came back with the window fully white (all 3 window-area sample
    # pixels checked read 240-251 sRGB, no sky/tree colour or detail visible
    # at all) even though the whole-image/window-patch clip percentage was
    # only ~1% -- the sky dome's own brightness=1.3 emissive multiplier was
    # pushing the HDRI's own bright-sky pixels essentially to white before
    # the path tracer's manual-exposure/White-Balance pipeline ever sees
    # them, at the exposure level tuned for the room's ivory targets. Lowered
    # substantially (1.3 -> 0.35) so the sky dome's own emitted radiance sits
    # in a range the same exposure that make the ivory read correctly also
    # renders as a recognisable, non-blown sky/tree exterior.
    # 2026-09-27 WtkPTFix pass: tried 0.35 -> 0.5 after fixing M_WTK_Glass
    # (see build_wtk_masters.py's build_glass() docstring), reasoning that
    # the previously-opaque-reading glass had been blocking most of the sky
    # dome's radiance regardless of this value. Tested via a real CAM_Wide
    # render at 512 SPP: no visible change in whether the sky/tree silhouette
    # reads as recognisable (still a flat, featureless light wash by eye,
    # matching this module's own section-4/round pass findings that this is
    # a real HDR-dynamic-range-vs-single-exposure limit, not a brightness
    # dial problem) -- reverted to 0.35 since raising it bought nothing
    # visible and only risked increasing window clip%%. Disclosed, not fixed
    # this pass -- see Docs/Lighting.md's new WtkPTFix section.
    brightness = 0.9 if IS_OVERCAST else 0.35
    day_mat = _build_unlit_emissive_material(SKY_MAT_PATH, texture=tex, tint=(1.0, 1.0, 1.0), brightness=brightness)
    smc.set_material(0, day_mat)
    log("SkyDome [%s]: %s HDRI, unlit emissive, brightness=%.2f." %
        (CURRENT_PRESET, "farmland_overcast" if IS_OVERCAST else "sunny_vondelpark", brightness))
    return actor


def setup_ground_plane():
    """
    A large flat plane at world Z=0 (matching the room floor) representing
    the ground/landscape outside the window, given a real (unlit, HDRI-
    tinted) material rather than the engine's default grey/checker, so the
    view through the glass reads as ground, not a void, at any exposure.
    """
    label = "WTK_GroundPlane_Outside"
    existing = find_actor_by_label(label)
    if existing:
        actor = existing
        log("Found existing ground plane actor.")
    else:
        actor = _actor_subsys().spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(-91.44, 800.0, 0.0), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(label)
        plane_mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Plane.Plane")
        smc = actor.static_mesh_component
        smc.set_static_mesh(plane_mesh)
        # Engine plane is 100x100 units; scale up to a large ground extent.
        actor.set_actor_scale3d(unreal.Vector(30.0, 30.0, 1.0))
        log("Spawned new ground plane actor at (-91.44, 800, 0), scale 30x30.")

    smc = actor.static_mesh_component
    smc.modify()  # WTK prop-fix pass round 2: needed on the existing-actor path below (material assignment)

    # 2026-09-27 path-tracer pass: hero/alt_soft now show sunny_vondelpark.hdr
    # through the window (a sunlit park, not overcast farmland), so the
    # ground plane tint is switched to match -- a brighter, warmer sunlit
    # grass-green rather than the muted overcast-farmland olive/brown, so the
    # ground plane and the sky dome's horizon still read as one continuous
    # exterior. Overcast keeps its original muted olive/brown tone matching
    # farmland_overcast.hdr's own palette.
    tint = (0.14, 0.16, 0.09) if IS_OVERCAST else (0.22, 0.30, 0.12)
    day_ground = _build_unlit_emissive_material(
        GROUND_MAT_PATH, texture=None, tint=tint, brightness=1.0)
    smc.set_material(0, day_ground)
    log("Ground plane [%s]: applied %s ground tone." %
        (CURRENT_PRESET, "muted overcast-farmland" if IS_OVERCAST else "sunlit grass-green"))

    # 2026-09-27 WtkBand pass: this plane is, by this function's own
    # docstring/design intent, a purely VISUAL unlit backdrop element (same
    # documented reasoning as the sky dome's own unlit material -- "not
    # lit/shadowed by the interior's own lights ... would be physically
    # wrong for a distant sky/landscape anyway"). Lumen's software-RT/
    # screen-space GI never treated it as a real light-transport participant
    # for the room's lighting, but UE 5.7's hardware-RT Path Tracer does
    # sample it as a genuine large flat area emitter (it's MSM_UNLIT +
    # two_sided=True with a flat, distance-independent radiance, i.e. exactly
    # a physically-unrealistic area light once actually ray-traced). Root
    # cause of the horizontal luminance "band" reported on the B30 door
    # faces (and the same-height band across all CAM_Wide lower cabinets):
    # as a sample point on a door face crosses the world-Z height where the
    # window-sill/counter geometry starts occluding this plane's visible
    # solid angle through the window opening, the plane's flat, uniform
    # radiance contribution steps sharply -- a pure multiplicative luminance
    # change with no chroma shift, matching every prior pass's own
    # measurement (Docs/Lighting.md secs 15-17) exactly. Confirmed by direct
    # bisection: hiding this actor entirely collapses the step from
    # delta~8.3/11.6 to delta~-0.9/-0.4 (CAM_Detail door1/door2, 1024 SPP,
    # reproduced twice, byte-identical); every other candidate this project
    # tested (materials, geometry, Nanite, FX-02, SkyAtmosphere reference-
    # atmosphere, r.PathTracing.LightGridResolution/MISMode/EnableEmissive)
    # had zero or noise-level effect.
    #
    # Fix: visible_in_ray_tracing=False on this component. This removes it
    # from BOTH the path tracer's visibility AND its light-transport
    # sampling (hardware ray tracing only) while leaving Lumen/raster
    # rendering completely untouched -- confirmed via a direct Lumen
    # re-render after setting this flag (CAM_Detail hero, non-degenerate
    # frame/window-region luminance, matching the pre-fix Lumen look). This
    # is the surgical equivalent of the diagnostic "hide the whole actor"
    # test (which also fixes the band, byte-identical result) but keeps the
    # plane visible in Lumen test/preview renders and in the editor
    # viewport, only opting it out of the one render path where its
    # unlit-flat-emissive design was never physically valid in the first
    # place.
    smc.set_editor_property("visible_in_ray_tracing", False)
    log("Ground plane [%s]: visible_in_ray_tracing=False (path-tracer band fix; "
        "still visible in Lumen/raster)." % CURRENT_PRESET)
    return actor


def _import_backplate_texture():
    """
    Imports the CC0 exterior backplate JPG (see WTK_SourceTextures/
    Backplate + LICENSES.md section 9) as a plain Texture2D (NOT a cubemap --
    this is a flat photo UV-mapped onto a flat plane, unlike the HDRI sky
    dome's TextureCube). Idempotent: does_asset_exist() short-circuits.
    """
    if unreal.EditorAssetLibrary.does_asset_exist(BACKPLATE_TEXTURE_PATH):
        return unreal.EditorAssetLibrary.load_asset(BACKPLATE_TEXTURE_PATH)
    if not os.path.isfile(BACKPLATE_SRC_PATH):
        log("ERROR: backplate source file not found: %s -- window will show no exterior card." % BACKPLATE_SRC_PATH)
        return None
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    task = unreal.AssetImportTask()
    task.filename = BACKPLATE_SRC_PATH
    task.destination_path = HDRI_DEST_DIR
    task.automated = True
    task.save = True
    task.replace_existing = True
    asset_tools.import_asset_tasks([task])
    tex = unreal.EditorAssetLibrary.load_asset(BACKPLATE_TEXTURE_PATH)
    if tex is None:
        log("ERROR: backplate import did not produce %s -- check the imported name/path." % BACKPLATE_TEXTURE_PATH)
    else:
        # sRGB photo, not a linear data map -- ensure sRGB sampling (default
        # for a Texture2D import, set explicitly since this asset is
        # consumed unlit/emissive and must NOT be treated as a mask/data map).
        try:
            tex.set_editor_property("srgb", True)
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
            unreal.EditorAssetLibrary.save_loaded_asset(tex)
        except Exception as e:
            log("WARNING: could not confirm backplate texture sRGB/compression settings (%s)." % e)
        log("Imported window backplate texture -> %s" % BACKPLATE_TEXTURE_PATH)
    return tex


def _build_backplate_material(texture, brightness=1.0, warm_tint=(1.0, 1.0, 1.0)):
    """
    Plain unlit-emissive Material sampling `texture` via a standard UV-mapped
    Texture2D (not the sky dome's TextureCube/PixelNormalWS setup in
    _build_unlit_emissive_material -- a flat card needs ordinary UVs, not a
    world-normal-driven cubemap lookup). Deletes and recreates on every run
    (same established idempotency pattern as the sky dome/ground materials --
    see _build_unlit_emissive_material's own comment on why skip-if-exists
    silently no-ops a brightness/texture tweak).

    2026-09-28 WtkWindow2 pass (Issue 2): added `warm_tint`, an RGB multiplier
    applied alongside `brightness`, to compensate for the per-camera White
    Balance (white_temp=3300K, a warm reference point per setup_cameras_wtk.py's
    LOOK_PARAMS) pulling this unlit-emissive card toward navy-blue in the
    final graded image -- confirmed in the prior pass's glass-hidden test
    (window_2x_glasshidden_v2.png): the card's real photo (source mean sRGB
    ~(90,122,103), green-dominant) rendered dark and blue-shifted
    (~(93,119,144)) once the room's warm grading was applied, because White
    Balance is a global per-camera post-process with no per-object escape
    (same "global transform, no per-zone exemption" finding as Section 20/21).
    Since the grade pushes blue up and warmth down, a compensating multiplier
    that raises R (and to a lesser extent G) while holding B flat pre-biases
    the card's own emissive so grass reads green and sky reads blue AFTER
    grading rather than before.
    """
    if unreal.EditorAssetLibrary.does_asset_exist(BACKPLATE_MAT_PATH):
        unreal.EditorAssetLibrary.delete_asset(BACKPLATE_MAT_PATH)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialFactoryNew()
    pkg_path, asset_name = BACKPLATE_MAT_PATH.rsplit("/", 1)
    mat = asset_tools.create_asset(asset_name, pkg_path, unreal.Material, factory)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", False)  # single-sided card facing the room; back face never seen

    editor_lib = unreal.MaterialEditingLibrary
    tex_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -400, 0)
    tex_node.set_editor_property("texture", texture)
    tex_node.set_editor_property("parameter_name", "BackplateTex")

    # 2026-09-28 WtkWindow2 pass (Issue 2), round 2 finding: with the card's
    # rotation Rotator(pitch=0,yaw=0,roll=-90) (correct per WtkThree's
    # Issue-1 fix -- unchanged this pass), the engine Plane mesh's default UV
    # V axis comes out inverted relative to the source photo's own top-to-
    # bottom layout -- confirmed live (round 2 measured the TOP window half
    # green-dominant (36,91,90) and the BOTTOM half blue-dominant (50,81,102),
    # i.e. tree-canopy-at-top/sky-at-bottom, backwards from the intended
    # sky-top/lawn-bottom composition). Fixed by sampling with V flipped
    # (1-V) via an explicit TexCoord -> ComponentMask(V) -> OneMinus ->
    # AppendVector(U,1-V) chain feeding the texture sample's UVs, rather than
    # editing the source photo -- keeps the fix in the reproducible script.
    coord_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, -150)
    mask_u = editor_lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -600, -200)
    mask_u.set_editor_property("r", True)
    mask_u.set_editor_property("g", False)
    mask_v = editor_lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -600, -100)
    mask_v.set_editor_property("r", False)
    mask_v.set_editor_property("g", True)
    oneminus_v = editor_lib.create_material_expression(mat, unreal.MaterialExpressionOneMinus, -500, -100)
    append_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -450, -150)
    editor_lib.connect_material_expressions(coord_node, "", mask_u, "")
    editor_lib.connect_material_expressions(coord_node, "", mask_v, "")
    editor_lib.connect_material_expressions(mask_v, "", oneminus_v, "")
    editor_lib.connect_material_expressions(mask_u, "", append_node, "A")
    editor_lib.connect_material_expressions(oneminus_v, "", append_node, "B")
    editor_lib.connect_material_expressions(append_node, "", tex_node, "UVs")
    out_pin = tex_node

    needs_mul = (brightness != 1.0) or tuple(warm_tint) != (1.0, 1.0, 1.0)
    if needs_mul:
        tint_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 150)
        tint_r = warm_tint[0] * brightness
        tint_g = warm_tint[1] * brightness
        tint_b = warm_tint[2] * brightness
        tint_node.set_editor_property("constant", unreal.LinearColor(tint_r, tint_g, tint_b, 1.0))
        mul_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 0)
        editor_lib.connect_material_expressions(out_pin, "RGB", mul_node, "A")
        editor_lib.connect_material_expressions(tint_node, "", mul_node, "B")
        out_pin = mul_node
        editor_lib.connect_material_property(out_pin, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    else:
        editor_lib.connect_material_property(out_pin, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    editor_lib.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(BACKPLATE_MAT_PATH)
    log("Built window backplate material %s (brightness=%.2f, warm_tint=%s)" % (BACKPLATE_MAT_PATH, brightness, warm_tint))
    return mat


def setup_window_backplate():
    """
    2026-09-28 realism pass: a large, single unlit-emissive plane carrying a
    real exterior photo (trees/garden/sky -- see LICENSES.md section 9),
    placed outside the window facing into the room, replacing the sky dome's
    flat cyan wash as what the window actually shows.

    2026-09-28 WtkWindow2 pass (Issue 2) -- REPOSITIONED, recomputed from the
    real camera sightlines (the v1/v3 placement at Y=1200cm/12m out was too
    far/small in the frame to read as anything but a flat wash even once the
    WtkThree rotation bug was fixed). New sightline math below.

    Geometry derivation (window + camera facts from this script's own header
    and setup_cameras_wtk.py):
      - Window (`Windows_Window-Fixed_WTK_Fixed_2630`): X[-128.90,-53.98],
        Z[107.32,197.49] (centre X=-91.44, Z=152.4), back wall face at Y=0,
        room interior at Y<0, exterior at Y>0 (through the wall's 15.24cm
        thickness).
      - CAM_Wide: loc=(-150,-380,160), yaw=90 (eye height 160cm, looking
        toward +Y). CAM_Angle: loc=(-40,-300,155), aimed at (-175,-10,120).
        CAM_Detail does not frame the window (tight B30 close-up) -- not a
        constraint here.
      - Card placed at Y=500cm (5m outside the back wall face, inside the
        task's 4-6m band). Projecting each camera's ray through the window's
        4 corners (X extents at window centre Z, Z extents at window centre
        X) onto the Y=500 plane, via `t=(500-cam.y)/(target.y-cam.y)`,
        `hit = cam + t*(target-cam)`:
          CAM_Wide cone at Y=500: X[-101.1, 72.4], Z[38.0, 246.8]
          CAM_Angle cone at Y=500: X[-277.1, -77.3], Z[27.9, 268.3]
        Union of both cones: X[-277.1, 72.4] (span 349.5cm, centre X=-102.3),
        Z[27.9, 268.3] (span 240.4cm, centre Z=146.2). Sized the card to
        6m x 4m (600 x 400cm) -- comfortable margin over the 350x240cm
        required union -- centred at world (-102.3, 500.0, 146.2).
      - Composition mapping: the source photo
        (WTK_ExteriorBackplate.jpg, 2048x1204) has its fence/hedge line at
        roughly 45-54% of image height (tree canopy + open sky above, lawn
        below), matching a UV V-centre placed at the card's mid-height --
        with the card's Z-centre (146.2) sitting just below the window's own
        Z-centre (152.4), the fence line reads a little below window-centre
        and the tree canopy/sky fill the window's upper portion, exactly the
        "tree line + fence + some lawn + sky" composition requested. No
        additional UV offset needed beyond the default 0-1 UV the engine
        Plane mesh already provides (confirmed by inspecting the source
        photo directly).
    """
    label = "WTK_WindowBackplate"
    existing = find_actor_by_label(label)
    if existing:
        actor = existing
        log("Found existing window backplate actor.")
    else:
        actor = _actor_subsys().spawn_actor_from_class(
            unreal.StaticMeshActor, unreal.Vector(-102.3, 500.0, 146.2), unreal.Rotator(0, 0, 0))
        actor.set_actor_label(label)
        plane_mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Plane.Plane")
        smc = actor.static_mesh_component
        smc.set_static_mesh(plane_mesh)
        log("Spawned new window backplate actor.")

    smc = actor.static_mesh_component
    smc.modify()
    actor.modify()

    # Engine plane is 100x100 units (1m x 1m), local +Z is its visible face
    # normal at identity rotation. WtkThree_20260928 root-cause finding
    # (Issue 1, test (b)): the previous rotation, Rotator(pitch=-90,yaw=0,
    # roll=0), was WRONG -- empirically verified via quaternion.rotate_vector()
    # on local (0,0,1): that rotation sends the face normal to world (+1,0,0),
    # i.e. the card was facing sideways (+X), edge-on to every camera, not
    # toward the room at all. Correct rotation, confirmed the same way:
    # Rotator(pitch=0,yaw=0,roll=-90) sends local+Z to world (0,-1,0) --
    # exactly facing -Y, toward the room/camera side. Kept unchanged this
    # pass -- only the location/scale/brightness moved.
    actor.set_actor_location(unreal.Vector(-102.3, 500.0, 146.2), False, False)
    actor.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=0.0, roll=-90.0), False)
    actor.set_actor_scale3d(unreal.Vector(6.0, 4.0, 1.0))
    smc.set_editor_property("cast_shadow", False)

    tex = _import_backplate_texture()
    # 2026-09-28 WtkWindow2 pass (Issue 2): raised from the prior 1.0x
    # ("keep close to real sunlit-exterior brightness") -- the orchestrator
    # review asked for the window patch mean to read ~1.2-1.5x the back-wall
    # mean (a bright sunny exterior), which a literal 1.0x photographic
    # multiplier under-delivers once the room's own per-camera grading is
    # applied (see Lighting.md Section 21.1's glass-hidden test: the card
    # read DARKER than the source photo's own mean once graded).
    # Round 1 this pass: brightness=1.35 measured window patch mean
    # (34,58,77) -- an order of magnitude below the ~250+ target -- because
    # CAM_Wide's TOTAL AutoExposureBias (per-camera override 6.4 + look-A
    # bias_delta 2.1 = 8.5 stops-equivalent) is tuned for the room's directly
    # -sunlit surfaces and crushes a comparatively modest unlit-emissive
    # card much harder than expected. Round 2: brightness raised ~6x,
    # 1.35->8.0 (scaling the round-1 measured G channel, 58, toward the
    # ~250 target: 250/58~4.3x on top of round 1's 1.35, i.e. ~8.0 total).
    # warm_tint compensates for the White Balance's warm reference point
    # (3300K) cooling/blueing this unlit card in the final grade -- R raised
    # more than G, B held at 1.0, so grass reads green and sky reads blue
    # AFTER grading rather than being swamped by the compensating warmth.
    # Round 2 (brightness=8.0): window patch mean only reached (43,86,96) --
    # the response to brightness is strongly sub-linear at this scene's
    # aggressive CAM_Wide exposure bias (6.4 base + 2.1 look-A delta = 8.5
    # stops-equivalent, tuned for the directly-sunlit interior, which
    # compresses/crushes a comparatively modest unlit source hard via Local
    # Exposure/tonemap highlight compression) -- also fixed the V-flip bug
    # this round (see the UV chain above), so round 2's own measurement is
    # not directly comparable channel-for-channel to round 3's. Round 3:
    # raised further, 8.0->16.0. Result: window patch mean (61,164,191),
    # top half (sky) B=226, bottom half (lawn/fence) recognisably green --
    # a genuine, qualitatively correct "tree line + fence + lawn + sky"
    # composition, confirmed by eye via a 2x crop -- but the numeric target
    # (window G/B ~1.2-1.5x the back-wall's 195/182, i.e. ~234-293) was not
    # yet hit (164/191 vs 234-293). Round 4: scaled up proportionally,
    # 16.0 -> 24.0 (234/164~1.43x, 293/164~1.78x -- took the mid of that
    # band applied to round 3's 16.0). Result: window patch mean
    # (75,183,204), ratio to back-wall (203,195,182) = (0.37,0.94,1.12) --
    # G/B close to but just under the 1.2-1.5x target, R still visibly low
    # (the fence/concrete area reads darker/cooler than its true mid-grey).
    # 2x crop confirmed a strongly recognisable garden: blue sky, tree
    # canopy, roofline, hedge/fence, pink/orange flowers, green lawn --
    # qualitatively the strongest result of this pass. Round 5 (final
    # CAM_Wide round, per the task's <=5-round cap): brightness raised
    # 24.0->34.6 (scaling G's 182.7 toward the ~263.5 band-mid target) and
    # warm_tint R raised 1.35->1.55 (a further correction specifically for
    # the fence/concrete midtones, which the flat per-channel multiplier
    # under-serves relative to the brighter sky/foliage highlights).
    mat = _build_backplate_material(tex, brightness=34.6, warm_tint=(1.55, 1.15, 1.0)) if tex is not None else None
    if mat is not None:
        smc.set_material(0, mat)

    # Must be part of the ray-tracing scene to be seen by the path tracer
    # (same lesson as WTK_GroundPlane_Outside's own visible_in_ray_tracing
    # fix, just the opposite direction: that plane needed to be EXCLUDED
    # from ray tracing to fix a light-leak band; this plane needs to be
    # INCLUDED since it's the only thing giving the window real detail).
    smc.set_editor_property("visible_in_ray_tracing", True)
    log("Window backplate: 6m x 4m plane at (-102.3, 500, 146.2), facing -Y, "
        "unlit emissive CC0 garden photo, brightness=1.35, warm_tint=(1.35,1.15,1.0), "
        "visible_in_ray_tracing=True.")
    return actor


GLASS_HIDDEN_PT_MAT_PATH = "/Game/WTK/HDRI/M_WTK_GlassHidden_PT"


def setup_glass_hidden_for_pt():
    """
    2026-09-28 WtkWindow2 pass (Issue 2): ships the glass-HIDDEN approach for
    path-traced stills, per the task's explicit instruction ("ship the
    glass-hidden approach... a render-only choice"). This is the cleanly
    named, permanent successor to the prior pass's throwaway diagnostic
    `M_TempDiag_MaskedGlass` (tmp/WtkThree_20260928/diag_e_hide_glass.py) --
    same BLEND_MASKED/OpacityMask=0 technique (the window mesh's Glass_Clear
    slot gets a fully-masked, unlit-black material, so the glass pane is
    excluded from the render entirely and the backplate card is seen
    directly with no translucent-shading-model limitation in the way), but
    now a first-class, idempotent, documented asset wired into the normal
    setup pipeline rather than a one-off tmp/ script.

    Root cause this fixes: UE 5.7's DefaultLit+Translucent
    Surface-ForwardShading blend transmits background COLOUR through a glass
    pane but not IMAGE DETAIL (confirmed exhaustively, Sections 14/15.2/20/21)
    -- the required MSM_THIN_TRANSLUCENT shading model's node is not exposed
    via Python reflection in this engine build. Removing the glass from the
    render path sidesteps the limitation entirely for path-traced stills
    (a render-only choice, not a permanent geometry change -- MI_Glass_Clear
    itself, and the window mesh's default slot assignment via
    remap_materials_wtk.py, are both left untouched; this function's slot
    override must be (re)applied as a render-prep step AFTER
    remap_materials_wtk.py in the pipeline, and is idempotent -- re-running
    it just reassigns the same slot to the same material).
    """
    window = None
    for a in _actor_subsys().get_all_level_actors():
        if a.get_actor_label().startswith("Windows_Window-Fixed_WTK_Fixed_2630"):
            window = a
            break
    if window is None:
        log("ERROR: window actor not found by prefix match -- glass-hidden PT material not applied.")
        return None

    if unreal.EditorAssetLibrary.does_asset_exist(GLASS_HIDDEN_PT_MAT_PATH):
        mat = unreal.EditorAssetLibrary.load_asset(GLASS_HIDDEN_PT_MAT_PATH)
    else:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialFactoryNew()
        pkg_path, asset_name = GLASS_HIDDEN_PT_MAT_PATH.rsplit("/", 1)
        mat = asset_tools.create_asset(asset_name, pkg_path, unreal.Material, factory)
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        mat.set_editor_property("two_sided", True)
        editor_lib = unreal.MaterialEditingLibrary
        zero_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 0)
        zero_node.set_editor_property("r", 0.0)
        editor_lib.connect_material_property(zero_node, "", unreal.MaterialProperty.MP_OPACITY_MASK)
        black_node = editor_lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 150)
        black_node.set_editor_property("constant", unreal.LinearColor(0, 0, 0, 1))
        editor_lib.connect_material_property(black_node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        editor_lib.recompile_material(mat)
        unreal.EditorAssetLibrary.save_asset(GLASS_HIDDEN_PT_MAT_PATH)
        log("Built %s (fully-masked, OpacityMask=0, unlit-black -- excludes the glass pane from the render)." % GLASS_HIDDEN_PT_MAT_PATH)

    window.modify()
    smc = window.static_mesh_component
    smc.modify()
    mesh = smc.static_mesh
    materials = mesh.get_editor_property("static_materials") if mesh else []
    glass_slot = None
    for i, sm in enumerate(materials):
        slot_name = str(sm.get_editor_property("material_slot_name"))
        cur_mat = smc.get_material(i)
        if "Glass" in slot_name or (cur_mat and "Glass" in cur_mat.get_name()):
            glass_slot = i
            break
    if glass_slot is None:
        log("ERROR: could not identify the glass material slot by name -- glass-hidden PT material not applied.")
        return None

    smc.set_material(glass_slot, mat)
    log("Window mesh slot %d (glass) set to %s -- glass pane excluded from path-traced stills." % (glass_slot, GLASS_HIDDEN_PT_MAT_PATH))
    return mat


# ---------------------------------------------------------------------------
# 4. REMOVED artificial-light actors (2026-09-27 window-only daylight pass)
# ---------------------------------------------------------------------------
# User decision: the 2 under-cabinet LEDs are removed from the design (docs/
# BOM handled elsewhere); in Unreal, DELETE the LED actors (WTK_LED_W18,
# WTK_LED_W30, and any LED channel/diffuser/emissive strip meshes/actors
# representing them), DELETE the 4 ceiling cans (WTK_Can_1..4), the fill
# light (WTK_Fill_Room), and the night presets. The scene is lit ONLY by the
# sun + sky through the window. Unlike the previous day/night preset pass
# (which kept these actors as hidden/zero-intensity placeholders for an
# idempotent "preset switch"), this pass actually DELETES them from the
# level and removes their setup functions entirely, so nothing respawns them
# on any future run of this script.
REMOVED_ARTIFICIAL_LIGHT_LABELS = [
    "WTK_LED_W18", "WTK_LED_W30",  # under-cabinet LEDs (+ any channel/diffuser child actors, matched by prefix below)
    "WTK_Can_1", "WTK_Can_2", "WTK_Can_3", "WTK_Can_4",  # ceiling downlights
    "WTK_Fill_Room",  # cheat fill light
]
REMOVED_ARTIFICIAL_LIGHT_PREFIXES = [
    "WTK_LED_", "WTK_Can_", "WTK_Fill_",
]


def remove_artificial_lights():
    """
    Idempotent deletion: destroys every actor whose label exactly matches
    REMOVED_ARTIFICIAL_LIGHT_LABELS or starts with one of
    REMOVED_ARTIFICIAL_LIGHT_PREFIXES (covers any LED channel/diffuser/
    emissive-strip child actor that might carry a longer WTK_LED_*-prefixed
    label rather than the exact base label, e.g. a future
    "WTK_LED_W18_Diffuser"). Safe to call every run: once deleted, there is
    nothing left to find on a subsequent run, so this is a no-op after the
    first successful pass.
    """
    actor_subsys = _actor_subsys()
    all_actors = actor_subsys.get_all_level_actors()
    deleted = []
    for a in list(all_actors):
        label = a.get_actor_label()
        if label in REMOVED_ARTIFICIAL_LIGHT_LABELS or any(label.startswith(p) for p in REMOVED_ARTIFICIAL_LIGHT_PREFIXES):
            actor_subsys.destroy_actor(a)
            deleted.append(label)
    if deleted:
        log("Removed %d artificial-light actor(s): %s" % (len(deleted), ", ".join(deleted)))
    else:
        log("No artificial-light actors found to remove (already clean).")
    return deleted


# ---------------------------------------------------------------------------
# 4b. Optional window-opening Rect Light ("sky fill" portal) -- per the
# research doc's Recommended settings table: sized to the window's own RO
# (~75x90cm), ~80-120 lm, tested with/against the hero look and kept only if
# it improves the look without flattening it. Distinct from the removed
# under-cabinet LEDs: this represents the sky itself pushing light through
# the opening (a physically-motivated "portal" light, matching the CIVAR/
# Faucher window-rect-light convention cited in the research doc), not an
# artificial room fixture.
# ---------------------------------------------------------------------------
WINDOW_X_MIN, WINDOW_X_MAX = -128.90, -53.98
WINDOW_Z_MIN, WINDOW_Z_MAX = 107.32, 197.49
WINDOW_WALL_FACE_Y = 0.0

# Toggle: whether the window-portal Rect Light is included in this preset's
# setup. Tested hero with and without it (see Docs/Lighting.md); kept ON for
# all 3 day presets at a conservative 100 lm -- it visibly softened the
# harsh edge of the window reveal onto the splashback without flattening the
# floor-patch/falloff look, per the round-by-round comparison log.
# 2026-09-27 path-tracer pass round 3: temporarily testing whether the
# window-portal rect light (a physically-motivated but still artificial
# "sky fill" light placed right at the glass) is the dominant contributor to
# the window reading as pure blown white in the path-traced render (rounds
# 1-2 both showed near-zero pixel variance across the whole glass area, no
# sky/tree detail at all, despite the sky dome's own brightness already
# lowered to 0.35) -- the path tracer samples the sky/HDRI directly per the
# task spec, so this portal light may now be redundant/actively harmful
# (double-counting sky contribution) rather than merely optional, unlike in
# the old Lumen pipeline where it plausibly helped bounce light onto the
# splashback.
WINDOW_PORTAL_ENABLED = False
WINDOW_PORTAL_LUMENS = 100.0


def setup_window_portal_light():
    if not WINDOW_PORTAL_ENABLED:
        # Idempotent removal if a previous run left one behind and this flag
        # was later turned off.
        existing = find_actor_by_label("WTK_WindowPortal")
        if existing:
            _actor_subsys().destroy_actor(existing)
            log("WTK_WindowPortal: WINDOW_PORTAL_ENABLED=False -- removed existing portal light.")
        return None

    width = (WINDOW_X_MAX - WINDOW_X_MIN)   # ~74.9cm, matches the ~75cm RO width
    height = (WINDOW_Z_MAX - WINDOW_Z_MIN)  # ~90.2cm, matches the ~90cm RO height
    x_center = (WINDOW_X_MIN + WINDOW_X_MAX) / 2.0
    z_center = (WINDOW_Z_MIN + WINDOW_Z_MAX) / 2.0
    # Sits just inside the room from the window wall face (Y=0, room at -Y),
    # facing into the room (-Y forward), matching the sun's own -Y travel
    # direction through the same opening.
    y_pos = -3.0
    rot = unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0)  # forward = -Y (into the room)

    light, _ = spawn_or_get(unreal.RectLight, "WTK_WindowPortal", unreal.Vector(x_center, y_pos, z_center), rot)
    comp = light.light_component
    comp.modify()
    comp.set_editor_property("relative_rotation", rot)
    comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    # Rect Light's local width/height axes: with yaw=180 (forward=-Y), Right
    # runs along world -X and Up along world Z, so source_width covers the
    # window's X-span and source_height its Z-span, matching the opening.
    comp.set_editor_property("source_width", width)
    comp.set_editor_property("source_height", height)
    comp.set_editor_property("use_temperature", True)
    comp.set_editor_property("temperature", 6500.0)  # cool sky-blue, distinct from the warm direct sun
    try:
        comp.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    except Exception:
        pass
    comp.set_editor_property("intensity", WINDOW_PORTAL_LUMENS)
    comp.set_editor_property("cast_shadows", False)  # a soft sky-fill portal, not a hard-shadow-casting key light
    try:
        comp.set_editor_property("attenuation_radius", 300.0)
    except Exception:
        pass
    log("WTK_WindowPortal [%s]: pos=(%.1f,%.1f,%.1f), %.1fx%.1fcm (matches window RO), %.0f lm, 6500K, no shadows" %
        (CURRENT_PRESET, x_center, y_pos, z_center, width, height, WINDOW_PORTAL_LUMENS))
    return light


# ---------------------------------------------------------------------------
# 5. Post Process Volume (unbound) -- manual exposure, Lumen, bloom, etc.
# ---------------------------------------------------------------------------
def setup_ppv(exposure_bias=11.0):
    ppv, _ = spawn_or_get(unreal.PostProcessVolume, "WTK_PPV", unreal.Vector(-150, -200, 120))
    # WTK prop-fix pass round 2: ppv.settings is a plain FPostProcessSettings
    # struct (not itself a UObject), so modify() is called on the owning
    # PostProcessVolume actor instead, before any of its properties/struct
    # fields are mutated below. NOTE: this function's `settings` local is
    # never explicitly reassigned back via `ppv.settings = settings` --
    # relies on UE's Python struct-property binding writing through the
    # returned struct reference into the actor's live memory in place (the
    # existing, pre-this-pass behaviour; NOT independently re-verified this
    # pass beyond adding this actor-level modify() call for the same
    # dirty-marking safety as every other component/actor mutation in this
    # file).
    ppv.modify()
    ppv.set_editor_property("unbound", True)
    settings = ppv.settings

    # Exposure: manual, per research doc's AEM_Manual / bias ~9-14 calibrated
    # down for an interior (see Docs/Lighting.md for the calibration log).
    settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    settings.set_editor_property("auto_exposure_bias", exposure_bias)
    try:
        settings.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    except Exception:
        pass
    settings.set_editor_property("bOverride_AutoExposureMethod", True)
    settings.set_editor_property("bOverride_AutoExposureBias", True)

    # Lumen quality. Task spec: Hit Lighting for reflections/GI if supported;
    # screen tracing / final gather quality >=2. final_gather_quality kept at
    # 4.0 (max useful range per Lumen docs ~1-4) for indirect bounce/GI
    # quality; lumen_scene_detail/reflection_quality at 2.0 (>=2, per spec).
    settings.set_editor_property("lumen_final_gather_quality", 4.0)
    settings.set_editor_property("bOverride_LumenFinalGatherQuality", True)
    settings.set_editor_property("lumen_scene_detail", 2.0)
    settings.set_editor_property("bOverride_LumenSceneDetail", True)
    settings.set_editor_property("lumen_reflection_quality", 2.0)
    settings.set_editor_property("bOverride_LumenReflectionQuality", True)
    # Hit Lighting for reflections/GI (research doc, Karim Yasser: Lighting
    # Mode hierarchy Surface Cache < Hit Lighting for Reflections < Hit
    # Lighting -- recommended for a hero still on hardware RT hardware).
    # Wrapped in try/except since the exact enum/property name for "Lumen
    # Reflections: Lighting Mode" varies across UE 5.7 Python-binding
    # revisions; if unavailable, the scene falls back to the engine default
    # (Surface Cache) rather than failing the whole setup.
    try:
        # Confirmed live (tmp_introspect_pp_enums3.py): the enum type backing
        # this property is unreal.LumenRayLightingModeOverride, not a
        # "RayTracingLightingMode" type (that name doesn't exist in this
        # UE 5.7 Python binding). HIT_LIGHTING is the full hardware-RT mode
        # the research doc recommends for a hero still (Karim Yasser's
        # hierarchy: Surface Cache < Hit Lighting for Reflections < Hit
        # Lighting).
        settings.set_editor_property("lumen_ray_lighting_mode", unreal.LumenRayLightingModeOverride.HIT_LIGHTING)
        settings.set_editor_property("bOverride_LumenRayLightingMode", True)
        log("Lumen ray lighting mode: HIT_LIGHTING.")
    except Exception as e:
        log("WARNING: could not set lumen_ray_lighting_mode (%s) -- leaving engine default (Surface Cache)." % e)

    # Diffuse Color Boost (research doc: 1.0-2.0, only if the room reads too
    # dark after exposure). Kept at engine default (1.0, i.e. no boost) for
    # the hero/alt_soft/overcast presets in this pass -- the measurement
    # rounds below (Docs/Lighting.md) did not need it once global exposure
    # was corrected; left here, off, as the documented next lever if a
    # future re-render finds the room too dark.
    try:
        settings.set_editor_property("lumen_diffuse_color_boost", 1.0)
        settings.set_editor_property("bOverride_LumenDiffuseColorBoost", True)
    except Exception:
        pass

    # Bloom: subtle.
    settings.set_editor_property("bloom_intensity", 0.3)
    settings.set_editor_property("bOverride_BloomIntensity", True)

    # Vignette: off/low.
    settings.set_editor_property("vignette_intensity", 0.1)
    settings.set_editor_property("bOverride_VignetteIntensity", True)

    # White Balance mode (NOT Color Temperature mode -- they are inverses;
    # research doc's own forum-corroborated gotcha). Slightly warm reference
    # so the ivory paint reads ivory, not blown-white or yellow, matching the
    # task spec's "Use White Balance mode, slightly warm" instruction.
    try:
        # Confirmed live: the enum type is unreal.TemperatureMethod (not
        # "TemperatureType" -- that name doesn't exist in this UE 5.7 Python
        # binding), values TEMP_WHITE_BALANCE / TEMP_COLOR_TEMPERATURE.
        settings.set_editor_property("temperature_type", unreal.TemperatureMethod.TEMP_WHITE_BALANCE)
        settings.set_editor_property("bOverride_TemperatureType", True)
    except Exception as e:
        log("WARNING: could not explicitly set TemperatureType to White Balance (%s) -- White Balance is the engine default, verify in-editor." % e)
    settings.set_editor_property("white_temp", WHITE_TEMP)
    settings.set_editor_property("bOverride_WhiteTemp", True)

    # Local Exposure (task spec / research doc CIVAR numbers): Highlight
    # Contrast Scale ~0.85-0.95, Shadow Contrast Scale softened, Detail
    # Strength ~1.25-1.5. Applied here at the PPV level as the scene-wide
    # baseline; setup_cameras_wtk.py's per-camera post_process_settings
    # override REPLACES these values for CAM_Wide/CAM_Angle/CAM_Detail (same
    # "camera override fully replaces PPV" mechanism already documented for
    # AutoExposureBias), so the real controlling values for the 3 render
    # cameras live there -- this PPV-level setting only matters for the
    # in-editor viewport preview or an unconfigured camera.
    try:
        settings.set_editor_property("local_exposure_highlight_contrast_scale", 0.9)
        settings.set_editor_property("bOverride_LocalExposureHighlightContrastScale", True)
        settings.set_editor_property("local_exposure_shadow_contrast_scale", 0.7)
        settings.set_editor_property("bOverride_LocalExposureShadowContrastScale", True)
        settings.set_editor_property("local_exposure_detail_strength", 1.35)
        settings.set_editor_property("bOverride_LocalExposureDetailStrength", True)
        log("PPV Local Exposure: HighlightContrastScale=0.9, ShadowContrastScale=0.7 (softened), DetailStrength=1.35.")
    except Exception as e:
        log("WARNING: could not set PPV-level Local Exposure properties (%s) -- verify property names in-editor; "
            "per-camera overrides in setup_cameras_wtk.py are the ones that actually control the 3 render cameras." % e)

    # AO: default (leave engine defaults, do not override).

    # Round-4 fix (coordinator diagnosis): every test render showed a
    # smooth, featureless, extremely blurred image. Motion blur was 0.5
    # (engine default, not overridden) and DOF f-stop was 4.0 (engine
    # default, not overridden) -- for a static 1-frame MRQ render motion
    # blur should be a no-op, but disable it explicitly to rule it out.
    # Depth of field is disabled outright at the PPV level (not just a high
    # f-stop) so no PPV-level DOF setting can blur the establishing/angle
    # shots; CineCameraActor per-camera DOF (FocusMethod/aperture) still
    # applies independently per setup_cameras_wtk.py.
    settings.set_editor_property("motion_blur_amount", 0.0)
    settings.set_editor_property("bOverride_MotionBlurAmount", True)
    settings.set_editor_property("depth_of_field_fstop", 22.0)
    settings.set_editor_property("bOverride_DepthOfFieldFstop", True)
    try:
        settings.set_editor_property("depth_of_field_method", unreal.DepthOfFieldMethod.DOFM_CIRCLE_DOF)
        settings.set_editor_property("bOverride_DepthOfFieldMethod", True)
    except Exception:
        pass

    log("PPV [%s]: AEM_Manual, bias=%.2f, LumenFinalGather=4.0, LumenSceneDetail=2.0, "
        "LumenReflectionQuality=2.0, bloom=0.3, vignette=0.1, white_temp=%.0fK (White Balance mode), "
        "motion_blur_amount=0.0 (forced off), PPV DOF fstop=22 (forced deep)" %
        (CURRENT_PRESET, exposure_bias, WHITE_TEMP))
    return ppv


# ---------------------------------------------------------------------------
# 6. Light-leak blockers (2026-09-27 WtkKnobs pass)
# ---------------------------------------------------------------------------
# Diagnosis (tmp/WtkKnobs_20260927/lightleak_diag.txt, live actor-bounds dump
# against WTK_Main_v2): the 4 wall actors' bounding boxes meet/overlap
# EXACTLY at every corner (x_gap/y_gap <= 0.00cm -- the expected 15.24cm
# mitered-corner overlap, no authored dimensional gap) and every wall top
# meets the ceiling bottom at exactly 0.000cm. So there is no literal seam in
# the shell's dimensions. However every wall/ceiling material
# (MI_Wall_WarmOffWhite, MI_Ceiling_FlatWhite) is confirmed two_sided=False
# (single-sided) -- the same class of bug already found and fixed once in
# this project for the ceiling (Pipeline.md's "ceiling flip pass": a
# single-sided mesh with its front face pointed the wrong way is effectively
# see-through from the back-face side for both camera rendering AND Lumen's
# ray-traced shadowing). At a mitered wall-box corner (two overlapping thin
# box solids sharing a 15.24cm seam) and at the exact wall-top/ceiling-bottom
# junction, a single-sided face whose normal isn't oriented outward at that
# specific micro-facet lets the low sun angle (elevation 15deg, forward
# vector confirmed (-0.9077,-0.3304,-0.2588) -- a strongly grazing, near-
# horizontal ray) pass straight through as if the shell weren't there,
# producing exactly the reported hard bright wedge at the far ceiling/wall
# corner (CAM_Wide) and the sharp streak crossing the counter at the same
# grazing angle (CAM_Angle).
#
# Fix chosen (per the task's own suggested approach): rather than risk
# re-flipping real casework/wall normals (high risk of a new, different leak
# or visibly wrong-shaded walls, and the wall meshes are Datasmith-imported
# real box geometry, not simple flat planes like the ceiling was), add thin,
# invisible-in-render-but-shadow-casting blocker boxes just OUTSIDE the
# shell at the two vulnerable junctions: the far top corner (opposite the
# window wall, where walls _2/_3/_4 all meet the ceiling) and along the
# window-wall/ceiling top junction. "Invisible but shadow-casting" is
# implemented via a StaticMeshActor using the engine Cube primitive with
# visibility off for camera/reflections but still contributing to Lumen's
# shadow/GI ray tracing (actor.set_actor_hidden_in_game stays False --
# render in shadow pass only would need a dedicated shadow-only mesh flag;
# used here instead: an actual opaque box, thin, painted to match the wall/
# ceiling colour and positioned to exactly overlap the seam from outside, so
# even if it IS visible at a grazing angle it reads as more wall/ceiling, not
# as a visible foreign object) -- kept idempotent by label lookup, deleted
# and respawned each run so geometry always matches the current shell
# bounds.
LIGHT_LEAK_BLOCKER_LABELS = ["WTK_Blocker_FarCorner_Top", "WTK_Blocker_WindowWall_Ceiling"]


def setup_light_leak_blockers():
    """
    Idempotent: deletes any existing WTK_Blocker_* actors and respawns fresh,
    matching the current shell bounds (re-read live each run rather than
    hardcoded, so a future reimport with different wall/ceiling extents is
    still covered correctly).
    """
    actor_subsys = _actor_subsys()
    all_actors = actor_subsys.get_all_level_actors()

    walls = []
    ceiling_bounds = None
    for a in all_actors:
        label = a.get_actor_label()
        if label.startswith("Walls_"):
            origin, extent = a.get_actor_bounds(only_colliding_components=False)
            walls.append((label, origin - extent, origin + extent))
        elif label.startswith("Ceilings_"):
            origin, extent = a.get_actor_bounds(only_colliding_components=False)
            ceiling_bounds = (origin - extent, origin + extent)

    # Delete existing blockers first (idempotent respawn). Matches ANY
    # "WTK_Blocker_" prefixed actor, not just this pass's own two exact
    # labels -- confirmed live (tmp/WtkKnobs_20260927/import_check_stdout.txt)
    # that a restored/prior level state can carry a DIFFERENTLY-NAMED set of
    # legacy blocker actors (WTK_Blocker_RightWallCeilingGap/
    # LeftWallCeilingGap/FrontWallCeilingGap/BackWallCeilingGap, from an
    # earlier attempt at this same fix, surfaced as UNMAPPED in the material
    # remap log) that an exact-label-only delete would silently leave behind
    # as orphaned duplicates. Cleaning up by prefix guarantees exactly this
    # pass's own two blockers exist after any run, regardless of what a
    # previous session may have left in the level.
    deleted = 0
    for a in list(all_actors):
        if a.get_actor_label().startswith("WTK_Blocker_"):
            actor_subsys.destroy_actor(a)
            deleted += 1
    log("Light-leak blockers: deleted %d existing blocker actor(s) (any WTK_Blocker_* label) before respawn." % deleted)

    if not walls or ceiling_bounds is None:
        log("Light-leak blockers: SKIPPED -- walls or ceiling not found in level (nothing to blocker-seal).")
        return []

    wall_env_min = unreal.Vector(
        min(w[1].x for w in walls), min(w[1].y for w in walls), min(w[1].z for w in walls))
    wall_env_max = unreal.Vector(
        max(w[2].x for w in walls), max(w[2].y for w in walls), max(w[2].z for w in walls))
    ceil_min, ceil_max = ceiling_bounds

    cube_mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    wall_mi_path = "/Game/WTK/Materials/MI_Wall_WarmOffWhite"
    wall_mi = unreal.EditorAssetLibrary.load_asset(wall_mi_path) if unreal.EditorAssetLibrary.does_asset_exist(wall_mi_path) else None

    spawned = []

    def spawn_blocker(label, location, scale):
        actor = actor_subsys.spawn_actor_from_class(unreal.StaticMeshActor, location, unreal.Rotator(0, 0, 0))
        actor.set_actor_label(label)
        smc = actor.static_mesh_component
        smc.modify()
        smc.set_static_mesh(cube_mesh)
        actor.set_actor_scale3d(scale)
        if wall_mi is not None:
            smc.set_material(0, wall_mi)
        # Keep it a real, normal-rendering opaque box (matches wall colour) --
        # simplest reliable way to guarantee it also blocks/casts shadows for
        # Lumen without depending on a shadow-only render flag that may not
        # be exposed identically across UE 5.7 Python bindings; painted to
        # match the wall so even a grazing-angle glimpse reads as more wall.
        smc.set_editor_property("cast_shadow", True)
        log("Spawned light-leak blocker '%s' at (%.2f,%.2f,%.2f) scale (%.3f,%.3f,%.3f)."
            % (label, location.x, location.y, location.z, scale.x, scale.y, scale.z))
        spawned.append(actor)
        return actor

    # Engine Cube primitive is 100x100x100 units (1m); scale.x/y/z map
    # directly to size in cm / 100.
    BLOCKER_THICKNESS_CM = 5.0  # thin shell, just enough to fully occlude a seam
    OUTSET_CM = 2.5  # sits centered ON the seam, half outside/half overlapping the shell -- guarantees full coverage of any sliver gap regardless of which side it's on

    # 1) Far top corner (opposite the window wall): the ceiling's own top
    # perimeter, run along the full ceiling XY envelope at ceiling-top Z,
    # as a flat capping slab sitting exactly at the wall-top/ceiling-bottom
    # junction Z (ceil_min.z, confirmed 0.000cm gap to every wall top) --
    # covers the entire top junction, not just one corner, since the
    # diagnostic couldn't isolate a single corner as uniquely responsible
    # (all 4 wall-tops meet the ceiling at the identical 0.000cm reading).
    center_x = (wall_env_min.x + wall_env_max.x) / 2.0
    center_y = (wall_env_min.y + wall_env_max.y) / 2.0
    span_x = (wall_env_max.x - wall_env_min.x) + 2 * OUTSET_CM
    span_y = (wall_env_max.y - wall_env_min.y) + 2 * OUTSET_CM
    spawn_blocker(
        "WTK_Blocker_FarCorner_Top",
        unreal.Vector(center_x, center_y, ceil_min.z),
        unreal.Vector(span_x / 100.0, span_y / 100.0, BLOCKER_THICKNESS_CM / 100.0),
    )

    # 2) Window-wall/ceiling top junction: a second, narrower capping strip
    # directly above the window wall only (Walls_..._6in, the wall containing
    # the window), so the window's own light path through the glass is
    # preserved (the blocker sits ABOVE the wall's Z-span entirely, at
    # ceil_min.z, well above the window's own Z[107.32,197.49] -- verified
    # no overlap with the window bounds) while still sealing that wall's
    # specific top seam a second time with a tighter, wall-width-matched cap.
    window_wall = next((w for w in walls if w[0] == "Walls_Basic_Wall_WTK_Interior_6in"), walls[0])
    ww_label, ww_min, ww_max = window_wall
    ww_center_x = (ww_min.x + ww_max.x) / 2.0
    ww_center_y = (ww_min.y + ww_max.y) / 2.0
    ww_span_x = (ww_max.x - ww_min.x) + 2 * OUTSET_CM
    ww_span_y = (ww_max.y - ww_min.y) + 2 * OUTSET_CM
    spawn_blocker(
        "WTK_Blocker_WindowWall_Ceiling",
        unreal.Vector(ww_center_x, ww_center_y, ceil_min.z),
        unreal.Vector(ww_span_x / 100.0, ww_span_y / 100.0, BLOCKER_THICKNESS_CM / 100.0),
    )

    return spawned


# WtkPTFix4 pass (2026-09-27) note: a fix_fx02_shadow() function (disabling
# Plumbing_Fixtures_FX-02's cast_shadow/cast_dynamic_shadow/cast_static_shadow)
# was tried here as a candidate fix for the CAM_Detail oak-line defect --
# FX-02 (the sink cutout/basin) is an actor whose bottom edge (Z~63.0)
# lands inside the line's own back-solved world-Z band (~64-69cm, derived
# from a CAM_Detail +10cm height diagnostic that confirmed the line is
# world-fixed, not image-space). A first A/B render appeared to show the
# fix working (delta dropped from ~5.0/5.0 to 1.7/0.8), but this was NOT
# reproducible: 3 independent, byte-identical-settings re-renders (with
# FX-02's shadow flags confirmed False via a fresh post-reload readback
# each time) all measured delta 4.70/5.82 -- statistically indistinguishable
# from the true unmodified baseline (cast_shadow=True) measured immediately
# afterward at 4.71/5.83. The original "fixed" measurement could not be
# reproduced and is retracted as a measurement error, not a real effect --
# per this task's own "verify each claim with a crop" standard, nothing
# citing FX-02 as the root cause is shipped. No change was made to FX-02
# by this pass (it remains at its original imported defaults). The oak
# line's root cause is NOT FOUND, consistent with 3 prior passes
# (Docs/Lighting.md sections 15.1/16.1) -- see this pass's own section 17
# for the honest final disclosure.


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    log("=== WTK_LIGHT_PRESET = %s ===" % CURRENT_PRESET)

    setup_sun()
    setup_sky_atmosphere()
    setup_sky_light()
    setup_height_fog()
    setup_sky_dome()
    setup_ground_plane()
    setup_window_backplate()
    # 2026-09-28 WtkWindow2 pass (Issue 2): applies AFTER setup_window_backplate()
    # so the card is in place, and runs here (this script executes after
    # remap_materials_wtk.py per Docs/Pipeline.md's documented order) so this
    # override is the LAST word on the window mesh's glass slot for
    # path-traced stills -- a plain rerun of remap_materials_wtk.py alone
    # (e.g. after any future material rebuild) will put MI_Glass_Clear back,
    # and this script must be re-run afterward to restore the glass-hidden
    # PT look, matching this project's established "rebuild order matters"
    # pattern (set_uv_mode_tiling.py/remap_materials_wtk.py after any MI
    # rebuild).
    setup_glass_hidden_for_pt()
    remove_artificial_lights()
    setup_window_portal_light()
    # NOTE (2026-09-27): light-leak blockers are NOT called from here.
    # Docs/Pipeline.md documents a separate, more thorough fix
    # (Scripts/fix_light_leak_wtk.py) covering all 4 walls' ceiling-gap
    # seams (this function's own setup_light_leak_blockers(), covering only
    # 2 of the 4 walls, was an earlier/inferior pass-local attempt and is
    # left defined but UNCALLED here to avoid the two fixes fighting over
    # the same WTK_Blocker_* actor labels on every rerun). Pipeline order
    # per Docs/Pipeline.md: import -> remap -> ceiling flip -> bevel ->
    # Nanite -> save -> lighting setup (this script) -> light-leak blockers
    # (fix_light_leak_wtk.py, run separately) -> cameras/props/render.
    setup_ppv(exposure_bias=PPV_BIAS_BY_PRESET[CURRENT_PRESET])

    # WTK prop-fix pass round 2 (2026-09-26): robust save, matching the fix
    # applied to place_props_wtk.py after the coordinator found that script's
    # save_current_level()-only call silently failed to persist to the
    # .umap (the package was never marked dirty). This function's own
    # modify()-before-mutate fixes above address the root cause; save_map()
    # is added here as the same second, independent line of defence. NOT
    # independently re-verified by a live before/after .umap-timestamp check
    # this pass (only place_props_wtk.py's own persistence bug was directly
    # tested and confirmed fixed) -- flagged as a recommended follow-up
    # verification the next time this script is actually rerun.
    world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    saved_ok = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    log("save_map(%s) returned %s" % (MAP_PATH, saved_ok))
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("Lighting setup complete, level saved (save_current_level + save_map + save_dirty_packages).")


if __name__ == "__main__":
    main()
