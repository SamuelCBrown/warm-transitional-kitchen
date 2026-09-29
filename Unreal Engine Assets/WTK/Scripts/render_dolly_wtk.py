"""
WTK Phase 6 Part 2 (2026-09-28): build an MRQ job for the LS_Dolly_Kitchen
sequence (path tracer), mirroring render_tests_wtk.py's job-building pattern
but for a multi-frame animated sequence instead of the 1-frame still
sequences.

Env vars:
  WTK_DOLLY_START_FRAME / WTK_DOLLY_END_FRAME: render only this frame range
    (default: the full sequence, 0..288) -- used for the 5-frame speed test
    and the 24-frame flicker check before committing to the full render.
  WTK_PT_SPP: path tracer samples per pixel (default 256, this pass's
    starting point per the task's "target <=90min total, e.g. 256 SPP"
    guidance).
  WTK_RES: output resolution (default 1920x1080, the review deliverable
    resolution per the task spec).
  WTK_OUTPUT_DIR: output directory (default 06_Renders/animation/frames).
  WTK_OUTPUT_SUBDIR: optional subfolder under WTK_OUTPUT_DIR (used to keep
    the speed-test/flicker-check frames separate from the full-sequence
    output without overwriting).

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this> -unattended -nop4 -nosplash -stdout
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH

SEQ_PATH = "/Game/WTK/Cinematics/LS_Dolly_Kitchen"

_res_env = os.environ.get("WTK_RES", "1920x1080")
try:
    RES_W, RES_H = [int(v) for v in _res_env.lower().split("x")]
except Exception:
    print("[WTK_DollyRender] WARNING: could not parse WTK_RES=%r, falling back to 1920x1080" % _res_env)
    RES_W, RES_H = 1920, 1080

BASE_OUTPUT_DIR = os.environ.get("WTK_OUTPUT_DIR", r"C:\Users\Sam\Documents\Chess\06_Renders\animation\frames")
SUBDIR = os.environ.get("WTK_OUTPUT_SUBDIR", "")
OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, SUBDIR) if SUBDIR else BASE_OUTPUT_DIR

PT_SPP = int(os.environ.get("WTK_PT_SPP", "256"))
PT_MAX_BOUNCES = int(os.environ.get("WTK_PT_MAX_BOUNCES", "8"))

START_FRAME = os.environ.get("WTK_DOLLY_START_FRAME")
END_FRAME = os.environ.get("WTK_DOLLY_END_FRAME")


def log(msg):
    print("[WTK_DollyRender] %s" % msg)


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    seq_asset = unreal.EditorAssetLibrary.load_asset(SEQ_PATH)
    if seq_asset is None:
        log("ERROR: sequence not found: %s -- run setup_dolly_wtk.py first." % SEQ_PATH)
        return

    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    queue = subsystem.get_queue()

    existing_jobs = list(queue.get_jobs())
    for j in existing_jobs:
        if str(j.job_name).startswith("WTK_Dolly"):
            queue.delete_job(j)

    job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.job_name = "WTK_Dolly_Kitchen"
    job.map = unreal.SoftObjectPath(MAP_PATH)
    job.sequence = unreal.SoftObjectPath(SEQ_PATH)

    config = job.get_configuration()

    out_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out_setting.output_directory = unreal.DirectoryPath(OUTPUT_DIR)
    out_setting.file_name_format = "WTK_Dolly_{frame_number}"
    out_setting.output_resolution = unreal.IntPoint(RES_W, RES_H)
    out_setting.use_custom_frame_rate = True
    out_setting.output_frame_rate = unreal.FrameRate(24, 1)

    # Optional frame-range override (5-frame speed test / 24-frame flicker
    # check) -- MoviePipelineOutputSetting exposes use_custom_playback_range
    # + custom_start_frame/custom_end_frame for exactly this purpose.
    if START_FRAME is not None and END_FRAME is not None:
        out_setting.use_custom_playback_range = True
        out_setting.custom_start_frame = int(START_FRAME)
        out_setting.custom_end_frame = int(END_FRAME)
        log("Custom playback range: [%s,%s]" % (START_FRAME, END_FRAME))

    try:
        existing_lumen_pass = config.find_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        if existing_lumen_pass is not None and not isinstance(existing_lumen_pass, unreal.MoviePipelineDeferredPass_PathTracer):
            config.remove_setting(existing_lumen_pass)
    except Exception:
        pass
    config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPass_PathTracer)

    config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)

    aa_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa_setting.spatial_sample_count = PT_SPP
    aa_setting.temporal_sample_count = 1
    aa_setting.render_warm_up_count = 0
    aa_setting.override_anti_aliasing = True

    camera_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineCameraSetting)
    try:
        camera_setting.shutter_angle = 180.0
    except Exception as e:
        log("WARNING: could not set shutter_angle: %s" % e)

    config.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)

    console_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    try:
        console_setting.add_or_update_console_variable("r.ScreenPercentage", 100.0)
        console_setting.add_or_update_console_variable("r.TSR.Enable", 0.0)
        console_setting.add_or_update_console_variable("r.PathTracing.MaxBounces", float(PT_MAX_BOUNCES))
        console_setting.add_or_update_console_variable(
            "r.PathTracing.Denoiser", float(os.environ.get("WTK_PT_DENOISER", "1")))
        console_setting.add_or_update_console_variable("r.PathTracing.SamplesPerPixel", float(PT_SPP))
    except Exception as e:
        log("WARNING: could not set console variables on job: %s" % e)

    log("Built job '%s' -> sequence %s, output %s, %dx%d, PathTracer SPP=%d, MaxBounces=%d" %
        (job.job_name, SEQ_PATH, OUTPUT_DIR, RES_W, RES_H, PT_SPP, PT_MAX_BOUNCES))

    manifest_result = unreal.MoviePipelineEditorLibrary.save_queue_to_manifest_file(queue)
    if isinstance(manifest_result, tuple):
        manifest_package_path, manifest_package_name = manifest_result
        manifest_path = "%s%s" % (manifest_package_path, manifest_package_name)
    else:
        manifest_path = manifest_result
    log("Saved manifest: %s" % manifest_path)


if __name__ == "__main__":
    main()
