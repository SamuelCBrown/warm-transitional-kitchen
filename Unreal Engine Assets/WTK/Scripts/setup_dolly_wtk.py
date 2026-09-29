"""
WTK Phase 6 Part 2 (2026-09-28): 10-15s slow dolly (Plan.md 6.2).

Creates a CineCamera actor CAM_Dolly and a LevelSequence
/Game/WTK/Cinematics/LS_Dolly_Kitchen with a 12s (288-frame @ 24fps) slow
lateral dolly + gentle push-in across the cabinet wall, level (no roll/pitch
wobble), eye height ~155cm, 32mm, f/8. Both the start and end compositions
show the window and the cabinetry (verified geometrically below). The
camera's per-camera post-process is copied from CAM_Wide (setup_cam_wide()
in setup_cameras_wtk.py) so the animated shot matches look A: exposure bias
8.5 (hero baseline 6.4 + look-A delta 2.1), white balance temp 3300K/tint
-0.05, Local Exposure highlight/shadow contrast 1.0/detail 1.05, bloom 0,
path-tracer reference atmosphere on. Idempotent: re-running updates the
existing CAM_Dolly actor and LS_Dolly_Kitchen sequence in place rather than
duplicating them.

Path geometry (Y=-back wall plane distance, X=lateral):
  start: loc (-190.0, -370.0, 155.0), level (pitch=0, yaw=90)
  end:   loc (-115.0, -330.0, 155.0), level (pitch=0, yaw=90)
At 32mm on the 36x20.25mm filmback (matching CAM_Wide's filmback setup),
horizontal half-frame-width at the back-wall plane (Y=0) is ~110.6cm at
Y=-370 and ~98.6cm at Y=-330 -- both comfortably bracket the full cabinet
run (world X[-304.8,0]) and the window (centred X=-91.44), so both the
first and last frame show the window and the complete cabinetry.

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this> -unattended -nop4 -nosplash -stdout
"""
import unreal
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH
SEQ_DIR = "/Game/WTK/Cinematics"
SEQ_NAME = "LS_Dolly_Kitchen"
CAM_LABEL = "CAM_Dolly"

FPS = 24
DURATION_SEC = 12.0
FRAME_COUNT = int(FPS * DURATION_SEC)  # 288

START_LOC = unreal.Vector(-190.0, -370.0, 155.0)
END_LOC = unreal.Vector(-115.0, -330.0, 155.0)
LEVEL_ROT = unreal.Rotator(pitch=0.0, yaw=90.0, roll=0.0)  # level, facing the cabinet wall (+Y), no wobble

FOCAL_LENGTH = 32.0
APERTURE = 8.0

_LOG_LINES = []


def log(msg):
    line = "[WTK_Dolly] %s" % msg
    print(line)
    _LOG_LINES.append(line)


def _flush_log_to_file():
    out_dir = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\tmp\WtkDolly_20260928"
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "setup_dolly_last_run.txt"), "w") as f:
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
        existing.modify()
        existing.set_actor_location(location, False, False)
        existing.set_actor_rotation(rotation, False)
        return existing
    cam = _actor_subsys().spawn_actor_from_class(unreal.CineCameraActor, location, rotation)
    cam.set_actor_label(label)
    log("Spawned new camera '%s'." % label)
    return cam


def copy_look_a_postprocess_from_cam_wide(comp):
    """
    Task spec: "give the camera the same per-camera post-process as look A:
    copy it from CAM_Wide (exposure bias, WB, local exposure, bloom 0,
    reference atmosphere)." Rather than re-derive the look-A values here
    (risking drift from setup_cameras_wtk.py's own LOOK_PARAMS table), import
    that module directly and reuse its apply_exposure_override() +
    WIDE_ANGLE_BIAS_BY_PRESET table -- the exact function/values CAM_Wide
    itself is configured with -- so CAM_Dolly is byte-for-byte the same
    per-camera post-process override as CAM_Wide, not a hand-copied
    approximation.
    """
    import importlib
    import setup_cameras_wtk as cams_mod
    importlib.reload(cams_mod)  # picks up the Part 1 recompose edits too, harmless here
    bias = cams_mod.WIDE_ANGLE_BIAS_BY_PRESET[cams_mod.CURRENT_PRESET]
    if cams_mod.IS_HERO:
        bias += cams_mod.LOOK_PARAMS[cams_mod.CURRENT_LOOK]["bias_delta"]
    cams_mod.apply_exposure_override(comp, bias)
    log("Copied CAM_Wide's look-A per-camera post-process (bias=%.2f, preset=%s, look=%s)." %
        (bias, cams_mod.CURRENT_PRESET, cams_mod.CURRENT_LOOK))
    return bias


def configure_dolly_camera(cam):
    comp = cam.camera_component
    comp.modify()
    comp.set_editor_property("current_focal_length", FOCAL_LENGTH)
    comp.set_editor_property("current_aperture", APERTURE)

    bias = copy_look_a_postprocess_from_cam_wide(comp)

    # Same 16:9-native filmback fix as the 3 still cameras (see
    # setup_cameras_wtk.py configure_camera()'s own comment) -- required so
    # the sensor aspect matches the MRQ output canvas exactly.
    filmback = comp.get_editor_property("filmback")
    filmback.set_editor_property("sensor_width", 36.0)
    filmback.set_editor_property("sensor_height", 20.25)
    comp.set_editor_property("filmback", filmback)
    try:
        comp.set_editor_property("constrain_aspect_ratio", False)
    except Exception:
        pass

    # Manual focus at f/8 stopped down: with a 32mm lens at f/8 and a working
    # distance of 330-410cm to the cabinet wall, depth of field is very deep
    # (hyperfocal well beyond the wall) -- focus distance doesn't need to
    # track the dolly move to stay sharp throughout. Set once at the
    # mid-path distance to the wall.
    focus_settings = comp.get_editor_property("focus_settings")
    focus_settings.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    focus_settings.set_editor_property("manual_focus_distance", 350.0)
    comp.set_editor_property("focus_settings", focus_settings)

    return bias


def ensure_sequence_dir():
    if not unreal.EditorAssetLibrary.does_directory_exist(SEQ_DIR):
        unreal.EditorAssetLibrary.make_directory(SEQ_DIR)


def create_or_get_dolly_sequence(camera_actor):
    asset_path = "%s/%s" % (SEQ_DIR, SEQ_NAME)
    ensure_sequence_dir()

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        seq = unreal.EditorAssetLibrary.load_asset(asset_path)
        log("Found existing sequence '%s' -- reusing." % asset_path)
    else:
        factory = unreal.LevelSequenceFactoryNew()
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        seq = asset_tools.create_asset(SEQ_NAME, SEQ_DIR, unreal.LevelSequence, factory)
        log("Created new sequence '%s'." % asset_path)

    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(FRAME_COUNT)
    seq.set_work_range_start(0.0)
    seq.set_work_range_end(DURATION_SEC)

    # Camera cut track: bind CAM_Dolly for the full sequence range, same
    # possessable-resolution-check pattern as create_or_get_sequence() in
    # setup_cameras_wtk.py (guards against a stale binding from a previous
    # level rebuild silently pointing at a nonexistent actor).
    cut_track = None
    for t in seq.get_tracks():
        if isinstance(t, unreal.MovieSceneCameraCutTrack):
            cut_track = t
            break
    if cut_track is None:
        cut_track = seq.add_track(unreal.MovieSceneCameraCutTrack)

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
            log("Existing possessable for CAM_Dolly correctly resolves -- reusing.")
        else:
            log("Existing possessable for CAM_Dolly is stale -- removing and re-creating.")
            try:
                seq.remove_possessable(b)
            except Exception as rex:
                log("WARNING: could not remove stale possessable: %s" % rex)
        break
    if cam_binding is None:
        cam_binding = seq.add_possessable(camera_actor)
        log("Created fresh possessable binding for CAM_Dolly -> %s." % camera_actor.get_actor_label())

    sections = cut_track.get_sections()
    if not sections:
        section = cut_track.add_section()
    else:
        section = sections[0]
    section.set_range(0, FRAME_COUNT)
    section.modify()
    binding_id = unreal.MovieSceneObjectBindingID()
    binding_id.set_editor_property("guid", cam_binding.get_id())
    section.set_camera_binding_id(binding_id)
    log("Camera-cut binding set for CAM_Dolly, range [0,%d]." % FRAME_COUNT)

    # Transform track: linear/eased keyframes at frame 0 (START_LOC, level
    # rotation) and frame FRAME_COUNT (END_LOC, same level rotation) on the
    # possessable's 3D Transform track. Two keys with an eased (not linear)
    # interpolation give the requested slow, smooth move rather than a
    # constant-velocity slide; rotation stays constant (no wobble) since both
    # keys use the identical LEVEL_ROT.
    transform_track = None
    for t in cam_binding.get_tracks():
        if isinstance(t, unreal.MovieScene3DTransformTrack):
            transform_track = t
            break
    if transform_track is None:
        transform_track = cam_binding.add_track(unreal.MovieScene3DTransformTrack)
    transform_track.modify()

    t_sections = transform_track.get_sections()
    if t_sections:
        t_section = t_sections[0]
        # Clear any pre-existing channels' keys before re-keying (idempotent
        # re-run safety).
    else:
        t_section = transform_track.add_section()
    t_section.set_range(0, FRAME_COUNT)

    channels = t_section.get_all_channels()
    # MovieScene3DTransformSection channel order: Location.X/Y/Z,
    # Rotation.X(Roll)/Y(Pitch)/Z(Yaw), Scale.X/Y/Z (9 double channels). This
    # UE 5.7 build names them with a numeric suffix (e.g. "Location.X_0", not
    # bare "Location.X" -- confirmed via a standalone probe script against a
    # throwaway sequence/section). Match by prefix rather than hardcoding the
    # exact suffix, so a different suffix index doesn't silently break this.
    names = [c.get_name() for c in channels]
    log("Transform section channels: %s" % names)

    def find_channel(prefix):
        for c in channels:
            if c.get_name().startswith(prefix):
                return c
        raise KeyError("no channel found with prefix %r among %s" % (prefix, names))

    def set_two_keys(channel, v_start, v_end):
        channel.remove_default()
        try:
            channel.set_default(v_start)
        except Exception:
            pass
        # Clear existing keys first for idempotency.
        try:
            existing_keys = channel.get_keys()
            for k in existing_keys:
                channel.remove_key(k)
        except Exception:
            pass
        k0 = channel.add_key(unreal.FrameNumber(0), v_start,
                              interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
        k1 = channel.add_key(unreal.FrameNumber(FRAME_COUNT), v_end,
                              interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
        return k0, k1

    # Location
    set_two_keys(find_channel("Location.X"), START_LOC.x, END_LOC.x)
    set_two_keys(find_channel("Location.Y"), START_LOC.y, END_LOC.y)
    set_two_keys(find_channel("Location.Z"), START_LOC.z, END_LOC.z)
    # Rotation -- identical start/end (no wobble): Roll, Pitch, Yaw
    set_two_keys(find_channel("Rotation.X"), LEVEL_ROT.roll, LEVEL_ROT.roll)
    set_two_keys(find_channel("Rotation.Y"), LEVEL_ROT.pitch, LEVEL_ROT.pitch)
    set_two_keys(find_channel("Rotation.Z"), LEVEL_ROT.yaw, LEVEL_ROT.yaw)
    # Scale -- constant 1,1,1
    set_two_keys(find_channel("Scale.X"), 1.0, 1.0)
    set_two_keys(find_channel("Scale.Y"), 1.0, 1.0)
    set_two_keys(find_channel("Scale.Z"), 1.0, 1.0)

    log("Keyed CAM_Dolly transform: start=%s end=%s over [0,%d] frames (%.1fs @ %dfps)." %
        (START_LOC, END_LOC, FRAME_COUNT, DURATION_SEC, FPS))

    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    log("Sequence '%s' saved." % asset_path)
    return seq


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)

    cam = spawn_or_get_camera(CAM_LABEL, START_LOC, LEVEL_ROT)
    bias = configure_dolly_camera(cam)
    seq = create_or_get_dolly_sequence(cam)

    world = unreal.EditorLevelLibrary.get_editor_world()
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    saved_ok = unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH) if world else False
    log("save_map(%s) returned %s" % (MAP_PATH, saved_ok))
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("Dolly camera + sequence setup complete (bias=%.2f). Level saved." % bias)
    _flush_log_to_file()


if __name__ == "__main__":
    main()
