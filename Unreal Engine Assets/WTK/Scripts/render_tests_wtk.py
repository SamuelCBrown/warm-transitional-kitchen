"""
WTK Phase 5d: build MRQ test-render jobs (one per test camera/sequence),
save a manifest, and print the headless render command to run afterward.

This script itself only BUILDS the queue + config and saves the manifest;
it does not invoke the actual headless render (that is a second, separate
UnrealEditor-Cmd.exe process per the research doc's confirmed pattern,
mirroring EpicGames/tk-unreal's publish_movie.py). Call render_headless.ps1-
equivalent commands separately (see Docs/Pipeline.md for the exact command).

Run with:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this> -unattended -nop4 -nosplash -stdout
"""
import unreal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wtk_paths import ACTIVE_MAP_PATH as MAP_PATH
SEQ_DIR = "/Game/WTK/Cinematics"

# Phase 6 (2026-09-28): configurable resolution/output so the 4K quality
# test and finals can reuse this same script without touching the hard-coded
# 1920x1080 test-render path. WTK_RES="WxH" (default "1920x1080");
# WTK_OUTPUT_DIR (default 06_Renders\tests, unchanged from before -- so a
# bare re-run with no env vars set is byte-for-byte the same job/behavior as
# before this pass, preserving the test-render path).
_res_env = os.environ.get("WTK_RES", "1920x1080")
try:
    _res_w, _res_h = [int(v) for v in _res_env.lower().split("x")]
except Exception:
    print("[WTK_Render] WARNING: could not parse WTK_RES=%r, falling back to 1920x1080" % _res_env)
    _res_w, _res_h = 1920, 1080
RES_W, RES_H = _res_w, _res_h

OUTPUT_DIR = os.environ.get("WTK_OUTPUT_DIR", r"C:\Users\Sam\Documents\Chess\06_Renders\tests")
MANIFEST_DIR = "WTK_Renders"  # relative to Saved/MovieRenderPipeline/
MANIFEST_NAME = "WTK_Test_Manifest"

# Phase 6: stable final naming scheme. WTK_FINAL_NAMES=1 switches the
# per-job file_name_format from "WTK_Test_<cam>[...]" to the fixed
# "WTK_Final_CAM_<cam>" the finals task requires, independent of preset/
# look/render-mode tags (those still exist in job_name for the manifest/log,
# just not in the output filename) so the final deliverable names never
# change even if a future preset/look pass changes tagging. Idempotent: same
# name every run, MRQ overwrites in place.
FINAL_NAMES = os.environ.get("WTK_FINAL_NAMES", "0") == "1"

# Phase 6: also write a 16-bit EXR master alongside the 8-bit PNG, when
# requested. Checked against the MRQ Python API below (MoviePipelineImage
# SequenceOutput_EXR); if unavailable in this UE 5.7 build, PNG-only and a
# clear log line, per the task's own fallback instruction.
WRITE_EXR = os.environ.get("WTK_WRITE_EXR", "0") == "1"

_ALL_CAMERAS = ["CAM_Wide", "CAM_Angle", "CAM_Detail"]
# 2026-09-27 day/night preset pass: WTK_RENDER_CAMS lets an iteration round
# build a queue with just CAM_Wide (per the task's own "rendering only
# CAM_Wide while iterating" instruction), e.g.
# WTK_RENDER_CAMS=CAM_Wide. Comma-separated; defaults to all 3.
_cams_env = os.environ.get("WTK_RENDER_CAMS", "")
CAMERAS = [c.strip() for c in _cams_env.split(",") if c.strip()] if _cams_env else _ALL_CAMERAS

# 2026-09-27 day/night preset pass: WTK_LIGHT_PRESET must ALSO be read here
# (not just by setup_lighting_wtk.py/setup_cameras_wtk.py) so each preset's
# renders land in differently-named output files
# (WTK_Test_CAM_Wide_day_soft_0000.png etc) instead of overwriting each
# other -- per the task's explicit "render output names must not overwrite
# each other" requirement. Empty string (WTK_LIGHT_PRESET unset) keeps the
# old bare "WTK_Test_CAM_Wide_0000.png" naming for backward compatibility
# with any existing tooling/renders that expect that exact name.
PRESET_SUFFIX = os.environ.get("WTK_LIGHT_PRESET", "")
if PRESET_SUFFIX not in ("hero", "alt_soft", "overcast"):
    PRESET_SUFFIX = ""

# 2026-09-27 look-variant pass: WTK_LOOK (A/B/C, matching setup_cameras_wtk.py's
# own WTK_LOOK env var) is folded into the job_name/output filename so the 3
# look variants never overwrite each other or the plain hero output. Only
# meaningful when PRESET_SUFFIX == "hero" (setup_cameras_wtk.py only applies
# look deltas for the hero preset); left in the filename regardless (harmless,
# makes provenance explicit) so a stray alt_soft/overcast run with WTK_LOOK
# set is still traceable rather than silently mislabeled.
LOOK_TAG = os.environ.get("WTK_LOOK", "")
if LOOK_TAG not in ("A", "B", "C"):
    LOOK_TAG = ""

# 2026-09-27 path-tracer pass (WtkPathTrace_20260927): final-still rendering
# switches from the real-time Lumen deferred pass to the UE 5.7 hardware-RT
# Path Tracer via MRQ's MoviePipelineDeferredPass_PathTracer, per the task's
# explicit instruction. WTK_RENDER_MODE selects which MRQ render-pass class
# (and matching sample-count settings) a job uses; default is "pathtracer"
# (the new final-still mode) so a bare re-run of this script without the env
# var picks up the task's intended default rather than silently staying on
# the old Lumen path. "lumen" is kept as an explicit opt-out/fallback for
# quick iteration or a GPU that can't path-trace.
RENDER_MODE = os.environ.get("WTK_RENDER_MODE", "pathtracer")
if RENDER_MODE not in ("pathtracer", "lumen"):
    RENDER_MODE = "pathtracer"

# Path Tracer sample count: the task specifies SPP ~512-2048 via the
# Anti-Aliasing spatial sample count (the path tracer repurposes that same
# spatial_sample_count field as its SPP knob) with temporal samples fixed at
# 1 (temporal accumulation is meaningless for the path tracer's own internal
# per-pixel accumulation loop; MRQ's temporal-sample mechanism is a Lumen/
# TAA-era concept). WTK_PT_SPP lets an iteration round use a lower SPP
# (faster feedback loop) before committing to the final hero SPP; defaults to
# 1024 (mid-point of the 512-2048 target band) for a first full-quality pass.
PT_SPP = int(os.environ.get("WTK_PT_SPP", "1024"))
# Path Tracer max bounces: task spec "interiors need many bounces", >=8.
PT_MAX_BOUNCES = int(os.environ.get("WTK_PT_MAX_BOUNCES", "8"))


def log(msg):
    print("[WTK_Render] %s" % msg)


def build_job(subsystem, queue, cam_name):
    seq_path = "%s/LS_Test_%s" % (SEQ_DIR, cam_name)
    seq_asset = unreal.EditorAssetLibrary.load_asset(seq_path)
    if seq_asset is None:
        log("ERROR: sequence not found: %s -- run setup_cameras_wtk.py first." % seq_path)
        return None

    job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    # job_name includes the preset suffix (when set) so the {job_name} token
    # in file_name_format below produces a distinct filename per preset,
    # e.g. WTK_Test_CAM_Wide_day_soft_0000.png -- see the module-level
    # PRESET_SUFFIX comment for why this is read here too.
    # job_name also carries the render-mode tag (pt/lumen) when path tracing
    # is active, so path-traced and Lumen outputs never overwrite each other
    # -- mirrors the existing PRESET_SUFFIX disambiguation mechanism/reasoning
    # above (same {job_name} file_name_format token).
    mode_tag = "_pt" if RENDER_MODE == "pathtracer" else ""
    look_tag = "_look%s" % LOOK_TAG if LOOK_TAG else ""
    if PRESET_SUFFIX:
        job.job_name = "WTK_Test_%s_%s%s%s" % (cam_name, PRESET_SUFFIX, mode_tag, look_tag)
    else:
        job.job_name = "WTK_Test_%s%s%s" % (cam_name, mode_tag, look_tag)
    job.map = unreal.SoftObjectPath(MAP_PATH)
    job.sequence = unreal.SoftObjectPath(seq_path)

    config = job.get_configuration()

    out_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out_setting.output_directory = unreal.DirectoryPath(OUTPUT_DIR)
    # {sequence_name} resolved empty/identical across all 3 jobs in the first
    # test run, causing every job's PNG to overwrite the same filename (only
    # 1 of 3 PNGs survived). Use {job_name} instead, which is unique per job
    # (job.job_name = "WTK_Test_<cam>[_<preset>][_pt]" set above) -- confirmed
    # fixes this, and now also disambiguates across presets and render modes.
    # Phase 6: when WTK_FINAL_NAMES=1, use the fixed deliverable naming
    # scheme instead (WTK_Final_CAM_<cam>_<frame>), independent of job_name's
    # preset/look/mode tags, per the finals task's stable-naming requirement.
    if FINAL_NAMES:
        # cam_name is already "CAM_Wide"/"CAM_Angle"/"CAM_Detail" (includes
        # the "CAM_" prefix) -- strip a leading "CAM_" before re-prefixing
        # with "WTK_Final_CAM_" so the result is "WTK_Final_CAM_Wide", not
        # the doubled "WTK_Final_CAM_CAM_Wide".
        short_cam = cam_name[4:] if cam_name.startswith("CAM_") else cam_name
        out_setting.file_name_format = "WTK_Final_CAM_%s_{frame_number}" % short_cam
    else:
        out_setting.file_name_format = "{job_name}_{frame_number}"
    out_setting.output_resolution = unreal.IntPoint(RES_W, RES_H)
    out_setting.use_custom_frame_rate = True
    out_setting.output_frame_rate = unreal.FrameRate(24, 1)

    if RENDER_MODE == "pathtracer":
        # 2026-09-27 path-tracer pass: MoviePipelineDeferredPass_PathTracer is
        # the MRQ render-pass class for the UE 5.7 hardware-RT path tracer
        # (distinct from MoviePipelineDeferredPassBase, which is the
        # Lumen/rasterized deferred pass used previously). Only one deferred-
        # family pass should be present on a job at a time; if a prior Lumen
        # run left a MoviePipelineDeferredPassBase setting on this job's
        # config (jobs are cleared/rebuilt each run in main(), so this is
        # mostly defensive), remove it before adding the path tracer pass.
        try:
            existing_lumen_pass = config.find_setting_by_class(unreal.MoviePipelineDeferredPassBase)
            if existing_lumen_pass is not None and not isinstance(existing_lumen_pass, unreal.MoviePipelineDeferredPass_PathTracer):
                config.remove_setting(existing_lumen_pass)
        except Exception:
            pass
        config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPass_PathTracer)
    else:
        config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)

    png_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)

    # Phase 6: optional 16-bit EXR master alongside the 8-bit PNG. MRQ
    # supports adding multiple MoviePipelineOutputBase-derived settings to
    # the same job configuration simultaneously (each renders its own copy
    # of every frame), so this is additive, not a replacement for the PNG.
    exr_written = False
    if WRITE_EXR:
        try:
            exr_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_EXR)
            # Class exists and was added to the job config -- confirms this
            # UE 5.7 build's MRQ Python API does support a second (EXR)
            # output setting alongside the PNG setting above, satisfying the
            # task's "if the MRQ Python API supports adding a second output
            # setting" check. This output setting has no exposed
            # bit-depth/compression Python properties in this build (direct
            # set_editor_property calls for "compression"/"output_directory"
            # both raised on inspection, so left unset rather than silently
            # writing a bogus value) -- it uses the class's own C++ defaults,
            # which for MoviePipelineImageSequenceOutput_EXR is 16-bit float
            # per channel. This is the DISPLAY-REFERRED, post-tonemap/post-
            # OCIO frame buffer that MRQ's deferred/path-tracer pass hands to
            # every output setting (the same source the PNG setting reads),
            # not a separate scene-linear HDR pass -- so it is faithful to
            # the approved look-A grade, per the task's stated preference.
            exr_written = True
            log("EXR master output enabled via MoviePipelineImageSequenceOutput_EXR "
                "(class defaults: 16-bit float, display-referred/post-tonemap, same source buffer as the PNG).")
        except Exception as e:
            log("WARNING: MoviePipelineImageSequenceOutput_EXR unavailable in this engine build (%s) -- "
                "PNG-only output; EXR master NOT written." % e)

    aa_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    if RENDER_MODE == "pathtracer":
        # Task spec: the path tracer repurposes the Anti-Aliasing spatial
        # sample count as its SPP (samples per pixel), ~512-2048; temporal
        # samples fixed at 1 (no TAA-style temporal accumulation -- the path
        # tracer accumulates internally per spatial sample instead).
        aa_setting.spatial_sample_count = PT_SPP
        aa_setting.temporal_sample_count = 1
        aa_setting.render_warm_up_count = 0
    else:
        aa_setting.spatial_sample_count = 1
        aa_setting.temporal_sample_count = 8
        aa_setting.render_warm_up_count = 32
    aa_setting.override_anti_aliasing = True

    # 2026-09-27 path-tracer pass: confirmed via engine source
    # (MovieRenderPipelineRenderPasses/Public/MoviePipelineDeferredPasses.h)
    # that UE 5.7 has NO separate MoviePipelinePathTracerSetting Python/UCLASS
    # -- UMoviePipelineDeferredPass_PathTracer (added above) carries no extra
    # bounce/SPP properties of its own; it inherits the shared AA setting's
    # spatial_sample_count as its SPP (set above) and the path tracer's
    # bounce depth/denoiser are engine-global console variables, not a
    # per-job UObject setting. Set via MoviePipelineConsoleVariableSetting
    # below (r.PathTracing.MaxBounces / r.PathTracing.Denoiser) rather than a
    # nonexistent setting class.
    # Fix for "Too many temporal samples for the given shutter angle/tick
    # rate combination... Shutter Angle: 0.000000" (logged every round):
    # MRQ's camera settings default shutter angle to 0 in this project,
    # which is incompatible with temporal_sample_count=8 (needs a nonzero
    # shutter angle to divide the frame into sub-frame ticks for temporal
    # accumulation). Set a standard 180-degree shutter explicitly.
    camera_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineCameraSetting)
    try:
        camera_setting.shutter_angle = 180.0
    except Exception as e:
        log("WARNING: could not set shutter_angle: %s" % e)

    config.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)

    # Round 3 fix: every test render (rounds 1-3, all 3 cameras, regardless
    # of camera/material/exposure changes) showed real scene content only in
    # the LEFT HALF of the 1920x1080 canvas (exactly x<960), with the right
    # half solid white (255,255,255) confirmed via direct pixel inspection --
    # not a display/preview artifact. This matches a known TSR/screen-
    # percentage upscale-target mismatch (the frame renders at a reduced
    # internal resolution and the upscale to the full output canvas doesn't
    # fill correctly in this MRQ/-game configuration). Force screen
    # percentage to 100 via console variables on the job to rule this out.
    console_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    # 2026-09-27 path-tracer pass fix: confirmed via engine source
    # (MovieRenderPipelineSettings/Public/MoviePipelineConsoleVariableSetting.h)
    # that this UE 5.7 build has NO plain "console_variables" dict/map
    # property (the underlying CVars array is ScriptNoExport) -- the actual
    # Python-exposed API is the AddOrUpdateConsoleVariable(Name, Value)
    # UFUNCTION. The prior `console_setting.console_variables = {...}` line
    # was silently failing every run (caught by its own try/except, logged as
    # a WARNING) since before this pass; fixed here for both the pre-existing
    # r.ScreenPercentage/r.TSR.Enable cvars and the new path-tracer ones.
    try:
        console_setting.add_or_update_console_variable("r.ScreenPercentage", 100.0)
        console_setting.add_or_update_console_variable("r.TSR.Enable", 0.0)
        if RENDER_MODE == "pathtracer":
            # The portable, always-available way to drive max bounces + the
            # built-in denoiser is via these r.PathTracing.* console
            # variables (UE 5.7 has no separate MoviePipelinePathTracerSetting
            # class -- confirmed above). r.PathTracing.MaxBounces sets the
            # path tracer's max bounce depth (task spec >=8 for interiors).
            # r.PathTracing.Denoiser=1 enables UE 5.7's built-in path-tracing
            # denoiser -- this is the classic Intel Open Image Denoise (OIDN)
            # integration baked into the path tracer module itself (the
            # OpenImageDenoise plugin enabled in WTK.uproject supplies the
            # underlying OIDN library this cvar's denoiser pass links
            # against; confirmed loaded live via the engine log's own
            # "LogOpenImageDenoise: OIDN shutting down" line on every run),
            # distinct from the newer NNEDenoiser plugin (not enabled here --
            # OIDN is the documented/default path-tracer denoiser and was
            # chosen over NNEDenoiser to keep to one well-established
            # denoiser rather than adding a second, separately-configured
            # ML-inference plugin for the same job).
            console_setting.add_or_update_console_variable("r.PathTracing.MaxBounces", float(PT_MAX_BOUNCES))
            # Diagnostics: WTK_EXTRA_CVARS="r.Foo=1;r.Bar=0" adds MRQ console variables.
            for _pair in os.environ.get("WTK_EXTRA_CVARS", "").split(";"):
                if "=" in _pair:
                    _k, _v = _pair.split("=", 1)
                    console_setting.add_or_update_console_variable(_k.strip(), float(_v))
            # WTK_PT_DENOISER=0 renders the raw path-traced image (diagnostics).
            console_setting.add_or_update_console_variable(
                "r.PathTracing.Denoiser", float(os.environ.get("WTK_PT_DENOISER", "1")))
            console_setting.add_or_update_console_variable("r.PathTracing.SamplesPerPixel", float(PT_SPP))
    except Exception as e:
        log("WARNING: could not set console variables on job: %s" % e)

    if RENDER_MODE == "pathtracer":
        log("Built job '%s' -> sequence %s, output %s, %dx%d, PathTracer SPP=%d, MaxBounces=%d, Denoiser=OIDN(on), EXR=%s" %
            (job.job_name, seq_path, OUTPUT_DIR, RES_W, RES_H, PT_SPP, PT_MAX_BOUNCES, exr_written))
    else:
        log("Built job '%s' -> sequence %s, output %s, %dx%d, Lumen AA spatial=1/temporal=8, warmup=32, EXR=%s" %
            (job.job_name, seq_path, OUTPUT_DIR, RES_W, RES_H, exr_written))
    return job


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    queue = subsystem.get_queue()

    # Idempotent: clear any previously-built WTK_Test_* jobs before rebuilding,
    # so re-running this script doesn't accumulate duplicate jobs.
    existing_jobs = list(queue.get_jobs())
    for j in existing_jobs:
        if str(j.job_name).startswith("WTK_Test_"):
            queue.delete_job(j)
    log("Cleared %d prior WTK_Test_* job(s) before rebuild." % len([j for j in existing_jobs if str(j.job_name).startswith("WTK_Test_")]))

    built = []
    for cam_name in CAMERAS:
        job = build_job(subsystem, queue, cam_name)
        if job:
            built.append(job)

    if not built:
        log("ERROR: no jobs were built -- aborting manifest save.")
        return

    # This UE 5.7 build's save_queue_to_manifest_file() takes only the queue
    # (no name arg) and returns a tuple (package_path, package_name) rather
    # than a single path string.
    manifest_result = unreal.MoviePipelineEditorLibrary.save_queue_to_manifest_file(queue)
    if isinstance(manifest_result, tuple):
        manifest_package_path, manifest_package_name = manifest_result
        manifest_path = "%s%s" % (manifest_package_path, manifest_package_name)
    else:
        manifest_path = manifest_result
    log("Saved manifest: %s" % manifest_path)
    log("Relative-to-Saved manifest dir token (per research doc pattern): %s" % MANIFEST_DIR)
    log("Built %d job(s): %s" % (len(built), ", ".join(j.job_name for j in built)))

    # Print the exact headless command for convenience (also documented in
    # Docs/Pipeline.md).
    uproject = r"C:\Users\Sam\Documents\Chess\05_Unreal\WTK\WTK.uproject"
    editor_cmd = r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
    # -ResX/-ResY placed BEFORE the map URL argument: confirmed this is what
    # actually makes systemresolution.resx/resy report the requested
    # resolution in the log (placing them after the map URL left the window
    # at the project's default 1280x720 despite the flags being present on
    # the command line). Phase 6: RES_W/RES_H (from WTK_RES) instead of the
    # old hardcoded 1920x1080, so a WTK_RES=3840x2160 run launches the
    # window at the matching size.
    cmd = ('"%s" "%s" -ResX=%d -ResY=%d MoviePipelineEntryMap?game=/Script/MovieRenderPipelineCore.MoviePipelineGameMode '
           '-game -windowed -NoLoadingScreen -log -Unattended '
           '-MoviePipelineConfig="%s"') % (editor_cmd, uproject, RES_W, RES_H, manifest_path)
    log("Headless render command:")
    log(cmd)


if __name__ == "__main__":
    main()
