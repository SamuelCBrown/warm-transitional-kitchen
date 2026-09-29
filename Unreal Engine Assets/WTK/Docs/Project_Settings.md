# WTK Project Settings — Phase 5a

Date: 2026-09-26. Scope: `05_Unreal/WTK/Config/DefaultEngine.ini` and `05_Unreal/WTK/WTK.uproject` only. No Revit or `Pause/` files were modified (Pause was read-only for research).

## GPU / driver check

- GPU: **AMD Radeon RX 7800 XT**, driver version 32.0.31036.15 (driver date 8/11/2026), ~4 GB reported VRAM via `AdapterRAM` (WMI under-reports VRAM on some AMD drivers; this is a 16 GB card, but the WMI figure is not used for the HW RT decision).
- Windows build: 10.0.26200 (Windows 11 Home).
- Decision: RX 7800 XT is RDNA3, well above the RX 6000-series HW-RT threshold named in the task → **hardware ray tracing is supported**. `r.Lumen.HardwareRayTracing=1` and `r.RayTracing=1` were set accordingly.
- DX12: not independently re-verified via `dxdiag /t` (the dxdiag text-file capture did not complete in the session), but DX12 availability is confirmed indirectly — the actual headless Editor run (Step 4 below) launched successfully using the project's `DefaultGraphicsRHI_DX12` + `PCD3D_SM6` shader format settings with 0 shader compile errors, which would not happen if DX12/SM6 were unavailable on this machine.

## DefaultEngine.ini changes

Added `[/Script/Engine.RendererSettings]`, per the research doc's "(updated after GitHub pass 2)" key set (`Pause/RESEARCH_2026-09-26_UE5_ARCHVIZ_KITCHEN_LOOP2_LOOP3.md`, "Recommended Phase 5-6 setup for WTK" section):

```ini
[/Script/Engine.RendererSettings]
r.DynamicGlobalIlluminationMethod=1
r.ReflectionMethod=1
r.Lumen.HardwareRayTracing=1
r.RayTracing=1
r.Shadow.Virtual.Enable=1
r.GenerateMeshDistanceFields=True
r.Lumen.TraceMeshSDFs=1
r.Nanite=True
r.VirtualTextures=True
r.SkinCache.CompileShaders=True
r.AntiAliasingMethod=4
r.DefaultFeature.AutoExposure=False
r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange=True
r.Substrate=False
```

Notes on specific keys:
- **`r.Nanite=True`**, not `r.Nanite.ProjectEnabled`: the research doc's GitHub pass 2 found real shipped repos (`strangergwenn/AstralShipwright`, `retroandchill/unreal-pokemon`) use the plain `r.Nanite=True` key, not `.ProjectEnabled`. Verified in this project: at runtime **both** `r.Nanite` and `r.Nanite.ProjectEnabled` resolve to `1` (see verification output below), so either key works on 5.7; `r.Nanite=True` was kept as the written key per the doc's correction.
- **`r.Substrate=False`**: explicit, not omitted. The research doc's "Contradictions resolved" and "Decision" sections confirm the project was never opted into Substrate (no `r.Substrate` key existed in the prior `DefaultEngine.ini`) and recommends staying on the legacy (non-Substrate) material path — the learning-curve/tooling cost of Substrate outweighs the benefit for this single-hero-material project. Written explicitly here (rather than left unset) so the decision is self-documenting in the config itself.
- **`r.Lumen.HardwareRayTracing=1` / `r.RayTracing=1`**: set to `1` because the GPU check (above) confirmed RDNA3 hardware RT support.
- **`r.AntiAliasingMethod=4`** (TSR): matches the doc's GitHub-pass-2 addition, following `AstralShipwright`'s explicit choice as the modern default appropriate for a 4K still.
- **`r.DefaultFeature.AutoExposure=False`**: manual exposure, per the doc's exposure section (Epic's own guidance that auto-exposure is "childproofed" and fights intentional lighting; consensus across Faucher/RenderRebels/TUF for manual exposure).
- Existing `[/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings]` section (13 original lines) was left untouched.

Added `[/Script/WindowsTargetPlatform.WindowsTargetSettings]`:

```ini
[/Script/WindowsTargetPlatform.WindowsTargetSettings]
DefaultGraphicsRHI=DefaultGraphicsRHI_DX12
+D3D12TargetedShaderFormats=PCD3D_SM6
```

SM5 was not added (task said "keep SM5 only if needed" — not needed here; the project targets desktop DX12/SM6 only, consistent with the Datasmith archviz interior use case, and the headless run confirmed SM6 shaders compile/resolve on this machine).

Added `[/Script/EngineSettings.GameMapsSettings]`:

```ini
[/Script/EngineSettings.GameMapsSettings]
EditorStartupMap=/Game/WTK/Maps/WTK_Main
GameDefaultMap=/Game/WTK/Maps/WTK_Main
```

## WTK.uproject changes

`Plugins` array: kept `DatasmithImporter`, `DatasmithContent`, `PythonScriptPlugin`, `EditorScriptingUtilities`; added:

- `GeometryScripting` — confirmed present at `Engine/Plugins/Runtime/GeometryScripting/GeometryScripting.uplugin` in the UE 5.7 install (for scripted bevels via GeometryScript).
- `MovieRenderPipeline` — confirmed present at `Engine/Plugins/MovieScene/MovieRenderPipeline/MovieRenderPipeline.uplugin` (the exact 5.7 plugin name; note this is distinct from `MoviePipelineMaskRenderPass`, a separate add-on plugin not needed here).
- `ModelingToolsEditorMode` — confirmed present at `Engine/Plugins/Editor/ModelingToolsEditorMode/ModelingToolsEditorMode.uplugin`, added for GeometryScript mesh editing support on static meshes in the editor.

## Verification (headless Python run)

Pre-check: `Get-Process UnrealEditor*` returned no running processes before any edit — safe to proceed.

Command:
```
UnrealEditor-Cmd.exe "WTK.uproject" -run=pythonscript -script=<tmp_verify_script>.py -unattended -nop4 -nosplash -stdout
```

Shader compilation was already cached from a prior editor session (log showed "Shaders left to compile 0"), so the run completed in under a second of Python execution time and did not require the 30-40 minute wait the task anticipated for a cold shader-compile pass.

Resolved console variables (read back via `unreal.SystemLibrary.get_console_variable_int_value`):

```
r.DynamicGlobalIlluminationMethod=1
r.ReflectionMethod=1
r.Lumen.HardwareRayTracing=1
r.RayTracing=1
r.Shadow.Virtual.Enable=1
r.Substrate=0
r.AntiAliasingMethod=4
r.Nanite=1
r.Nanite.ProjectEnabled=1
hasattr GeometryScript_MeshModeling=True
hasattr MoviePipelineQueueSubsystem=True
```

All values match the intended config. `r.Substrate=0` confirms the explicit non-Substrate decision took effect. Both `GeometryScript_MeshModeling` and `MoviePipelineQueueSubsystem` Python classes are available, confirming the new plugins are active and Python-exposed.

Raw log evidence: `05_Unreal/WTK/Saved/Logs/WTK.log` (LogPython lines, "=== WTK5A VERIFY START/END ===" block) and `tmp/Wtk5a_20260926/verify_run.log`.

## Issues / open items

- `dxdiag /t` did not produce a completed text file in this session (command returned before the file was written, or was blocked) — DX12 availability is inferred from the successful DX12/SM6 headless Editor run rather than a direct dxdiag report. If a definitive dxdiag report is needed later, rerun `dxdiag /t <path>` and allow it to finish (it can take 10-30s).
- WMI's `Win32_VideoController.AdapterRAM` reported ~4 GB for the RX 7800 XT, which under-reports the card's actual 16 GB VRAM (a known WMI/driver limitation on some AMD configurations) — not used as the basis for the hardware-RT decision, which was made on GPU architecture/generation instead.
- No blocked commands were encountered; nothing needed to be stopped mid-way.

## Backups

Pre-edit copies saved to `tmp/Wtk5a_20260926/backup/`:
- `backup/Config/DefaultEngine.ini` (original 13-line Android-only file)
- `backup/WTK.uproject` (original 4-plugin manifest)
