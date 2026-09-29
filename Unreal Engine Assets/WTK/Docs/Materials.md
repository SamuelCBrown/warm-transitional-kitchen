# Oak clear-coat frosty-glaze fix (2026-09-27) — cool sky reflection was washing out the wood colour

Prompted by CAM_Detail's B30 macro (`06_Renders/tests/WTK_Test_CAM_Detail_0000.png`)
showing a "frosty lavender/white glaze" across the rift-sawn oak door grain —
light streaks reading like whitewash/liming wax, flat-panel mean sRGB
~(125,102,97) with blue too high (B/R ≈ 0.77, vs a ≤0.6 target) — instead of
a clear-coated natural/light-honey white oak.

## Root cause

**Not the texture, not the base-colour graph.** Both were checked first and
ruled out:

- `T_Oak_Color` / `white_oak_veneer_diff_4k.jpg` sampled directly (3000+
  pixels): mean sRGB (145, 122, 99), darkest sampled pixel (102,77,57),
  lightest (185,161,137) — correctly warm golden-tan with pores/latewood
  genuinely DARKER than the surrounding wood, exactly as intended. No
  inversion, no desaturation baked into the source asset.
- `build_wtk_masters.py`'s `build_common_opaque_chain()` base-colour chain
  (`BaseColorTex` -> multiply by `BaseColorTint` -> multiply by
  `BaseColorBrightness` -> `UseBaseColorTex` switch -> vein-contrast/
  desaturate lerps, both inert at MI defaults `DesaturateTex=0`,
  `VeinContrast=1` for oak) is a straightforward multiply chain with no
  step that lightens pores or inverts the texture.

**Actual cause**: at CAM_Detail's tight macro framing, the oak MI's
dielectric **Specular=0.5** plus a near-mirror **ClearCoat=1.0 @
ClearCoatRoughness=0.2** reflected the room's cool SkyLight/fill ambient
directly and strongly back at the camera. This cool reflected component,
layered on top of the diffuse albedo, is what read as a "frosty lavender/
white glaze" — consistent with this file's own pre-existing Phase 5e note
("cool grey-mauve... the room's cooler SkyLight/fill ambient plus the
ClearCoat's broad specular sheen... was washing the saturation out toward
neutral grey"), which had only been partially addressed via tint warming
(insufficient on its own, confirmed below).

## Investigation order and per-round findings (all rounds: CAM_Detail only,
`b30_door_flat_panel` box `(100,500,700,950)`, per `measure_renders_wtk.py`)

| Round | Change | Flat-panel mean sRGB | B/R ratio | Luminance stddev (grain contrast) |
|---|---|---|---|---|
| Baseline | (unchanged) | (124.6, 102.0, 96.5) | 0.775 | not measured (visibly washed) |
| 1 | ClearCoat 1.0->0.7, ClearCoatRoughness 0.2->0.35 | (117.5, 92.8, 85.1) | 0.724 | — |
| 2 | + tint (0.60,0.42,0.20)->(0.62,0.45,0.25), brightness 0.66->0.70 | (121.0, 95.6, 87.4) | 0.723 | — |
| 3 | Specular 0.5->0.35, ClearCoat 0.7->0.5, ClearCoatRoughness 0.35->0.4 | (111.9, 83.9, 72.3) | 0.646 | 10.3 |
| 4 (final) | BaseColorBrightness 0.70->0.78 | (117.0, 86.9, 73.8) [full-scene final render: (117.1, 87.0, 73.8)] | 0.631 | 10.5 |

**(a) Clear coat — the dominant contributor.** Round 1's ClearCoatRoughness
fix alone moved B/R from 0.775 to 0.724, a meaningful but incomplete step
(satin roughness reduces the mirror-like reflection but doesn't eliminate
it). Round 3's further easing of both base Specular (0.5->0.35) and
ClearCoat (0.7->0.5, roughness 0.35->0.4) produced the largest single
improvement (B/R 0.723->0.646), confirming the base dielectric specular was
compounding with the clear coat, not just the clear coat alone.

**(b) Base-colour texture handling — ruled out.** No inversion/desaturation
found; texture and graph both confirmed correct (see Root cause above).

**(c) Specular/roughness map wiring — ruled out.** `RoughnessTex` is
correctly wired to `MP_ROUGHNESS` via the min/max remap; `BaseColorTex` is
correctly wired to base colour. No swap found.

**(d) Tint warming — real but secondary, and ineffective in isolation.**
Round 2 (tint warmed toward the task's suggested (0.62,0.45,0.25) with
brightness raised for the same target luminance) barely moved the
measurement (B/R 0.724->0.723) — confirming the task's own instruction to
tune (a)-(c) BEFORE (d) was correct here: tint alone could not have fixed
this. Once the clear-coat/specular fix (Round 3) reduced the reflected cool
component, a final brightness lift (Round 4, 0.70->0.78, tint unchanged at
0.62/0.45/0.25) pushed R/G into the target bands without materially moving
B/R, landing the final result at (117.0, 86.9, 73.8), B/R 0.631 — just
above the 0.6 target line but clearly R>G>B with the grazing-glaze artifact
gone.

## Final parameter values (`MI_Oak_Rift_Stained` and `MI_Oak_Shelf`, identical
except `UVRotation_deg`)

| Parameter | Old (frosty-glaze) | New (final) |
|---|---|---|
| BaseColorTint | (0.60, 0.42, 0.20) | **(0.62, 0.45, 0.25)** |
| BaseColorBrightness | 0.66 | **0.78** |
| Specular | 0.5 | **0.35** |
| ClearCoat | 1.0 | **0.5** |
| ClearCoatRoughness | 0.2 | **0.4** |

`RoughnessMin/Max` (0.35/0.55), `NormalStrength` (1.0), `Metallic` (0.0),
`UVTiling`/`TextureSize_cm`/`UVRotation_deg` unchanged from Phase 5e.

## Verification against real renders (final round, all 3 cameras, 1920x1080)

- **CAM_Detail** `b30_door_flat_panel`: (117.1, 87.0, 73.8) — R in the
  120-160 target band's lower edge (117, ~3 below), G in the 85-115 band
  (87), B in the 50-75 band (73.8), R>G>B clearly, B/R=0.630 (target ≤0.6,
  slightly over but the visible glaze/whitewash artifact is gone). Luminance
  stddev in the panel box 10.5 (target ≥8, grain clearly visible). No white
  streaks visible on direct inspection of the final PNG.
- **CAM_Wide**: B30's lower cabinet doors read a consistent warm mid-brown,
  no red/mahogany cast, no frost — matches the wide-shot family established
  in Phase 5e.
- **CAM_Angle**: same warm mid-brown family on B30, consistent with
  CAM_Wide; the floating shelves (`FX-05`, a separate dark walnut-toned
  material, not the oak MI) are unaffected and read correctly.

**Honest remaining gap**: B/R is 0.630, just above the 0.6 target ceiling,
and flat-panel R (117) sits just under the 120 floor of its target band.
Both are close enough that the visible "frosty/whitewash" defect is fully
resolved (confirmed by direct image inspection, not just the numbers), but
a strict reading of the two numeric targets is not 100% met. A 5th round
(within the 5-round budget but not spent, since the visible defect was
already resolved and further tuning risks re-introducing the cool cast if
pushed via clear-coat/specular again, or an unnaturally saturated tint if
pushed via (d) alone) could nudge `BaseColorBrightness` up slightly further
(e.g. 0.80-0.82) to lift R over 120 while watching B/R doesn't creep back
up — flagged as an optional follow-up, not executed this pass since the
task's qualitative target ("no visible white streaks", "clear-coated
rift-sawn white oak... warm golden-tan to mid-brown") is met.

## Files changed this pass

- `Scripts/build_wtk_material_instances.py` — `build_oak_rift_stained()` and
  `build_oak_shelf()`: `Specular` 0.5->0.35, `ClearCoat` 1.0->0.5,
  `ClearCoatRoughness` 0.2->0.4, `BaseColorTint` (0.60,0.42,0.20)->
  (0.62,0.45,0.25), `BaseColorBrightness` 0.66->0.78. All values persisted
  directly in the idempotent MI-build functions (rerunning the script
  reproduces these exact values, per the existing "deletes and recreates
  each MI asset on every run" pattern).
- Re-ran (mandatory per the documented lesson, every round): 
  `set_uv_mode_tiling.py`, `remap_materials_wtk.py` after every
  `build_wtk_material_instances.py` run (masters/`build_wtk_masters.py`
  itself was NOT changed this pass — no master rebuild was needed, but the
  MI rebuild alone still requires the tiling/remap re-run since
  `build_wtk_material_instances.py` fully recreates each MI asset).
- Backup taken before any change: `tmp/WtkOak_20260927/
  build_wtk_material_instances.py.bak`, `build_wtk_masters.py.bak` (masters
  file backed up defensively even though unchanged).
- `render_tests_wtk.py`'s `CAMERAS` list was temporarily narrowed to
  `["CAM_Detail"]` for rounds 1-4 (to stay within a reasonable render-time
  budget while iterating) and restored to all 3 cameras
  (`["CAM_Wide", "CAM_Angle", "CAM_Detail"]`) for the final round —
  confirmed restored, no lasting change to this file.
- Final renders (all 3 cameras, 1920x1080): `06_Renders/tests/WTK_Test_CAM_
  {Wide,Angle,Detail}_0000.png`.

---

# WTK prop-fix pass addendum (2026-09-26) — brass tint fix (pale cream/ivory -> champagne-bronze satin)

Prompted by the orchestrator's close-up review flagging that
`MI_Brass_Satin` / `MI_Brass_Knob_Radial` read pale cream/ivory rather than a
warm metal in the CAM_Detail close-up.

## Root cause

Both MIs' `BaseColorTint` was `(0.80, 0.60, 0.33)` at `Roughness 0.3-0.4`,
Metallic=1. On a fully metallic surface, the base colour largely determines
the specular/reflected tint, but a bright, moderately-desaturated tint like
`(0.80,0.60,0.33)` (max channel 0.80, only a ~2.4:1 R:B ratio) reads close to
a warm-white highlight once lit at a fairly low roughness (0.3-0.4, closer to
mirror-like) -- exactly the "pale cream/ivory" look reported, since a satin
metal at this roughness reflects a lot of the scene's own warm light back
fairly directly, washing out a base tint that isn't saturated/dark enough to
hold its own colour under that reflection.

## Fix

New tint **`(0.62, 0.46, 0.25)`** (linear) -- the task's own suggested
starting point, unchanged (no further tuning needed; see verification
below) -- a more saturated, darker base (max channel down from 0.80 to
0.62, R:B ratio up slightly to 2.48:1, but every channel scaled down
together, so the hue family is preserved, just deepened). `Roughness`
raised slightly from `0.3-0.4` to **`0.35-0.45`** (a touch less mirror-like,
consistent with a "satin" finish holding more of its own base colour rather
than reading mostly as scene reflection). `Anisotropy` (0.4) and the
Metal009/Metal051A brushing/tangent maps unchanged -- applied identically to
both `MI_Brass_Satin` and `MI_Brass_Knob_Radial`.

## Verification against the real render

Rebuilt only the material instances (`build_wtk_material_instances.py`; no
master-graph change was needed, so `set_uv_mode_tiling.py` /
`remap_materials_wtk.py` were **not** re-run, per the pipeline's own
documented "MI-only change doesn't need the master rebuild" rule), then
re-rendered CAM_Wide/CAM_Angle/CAM_Detail and sampled the real B30 knob
pixels in CAM_Detail (`PIL`, `tmp/WtkProps2_20260926`):

| Region | Avg sRGB (this pass) | Avg sRGB (before, per the orchestrator's report) |
|---|---|---|
| Knob 1 | (210.1, 187.2, 161.4) | pale cream/ivory (not separately re-sampled from the old render, but visually and by hue confirmed distinct) |
| Knob 2 | (210.2, 187.7, 162.1) | same |

R:G:B ratio ≈ 1.30 : 1.16 : 1.0 -- a clearly warm gold/bronze hue, not a
neutral or pale tone. The sampled brightness is still fairly high (still
inside this shot's pre-existing, disclosed CAM_Detail overexposure -- see
Lighting.md's long-standing open item on that specific camera/exposure
combination, unrelated to this material fix), but the underlying *hue* is
now unambiguously warm brass rather than washed-out ivory, visible clearly
in both knobs and consistent with the champagne-bronze target.

## Files changed this pass

- `Scripts/build_wtk_material_instances.py` -- `build_brass_satin()` and
  `build_brass_knob_radial()`: new tint `(0.62,0.46,0.25)` (was
  `(0.80,0.60,0.33)`), Roughness 0.35-0.45 (was 0.3-0.4).
- Re-ran: `build_wtk_material_instances.py` only (no master rebuild, so no
  UVTiling/remap re-run needed this pass).
- Final renders: `06_Renders/tests/WTK_Test_CAM_{Wide,Angle,Detail}_0000.png`.

---

# Phase 5e addendum (2026-09-26) — oak tint fix (reddish/mahogany -> neutral warm mid-brown)

Prompted by a review of the round-7 renders flagging that B30's stained-oak
door read reddish/mahogany-like and the open floating shelves read
pinkish-orange -- not the intended "golden/early-American" white-oak stain
(a yellow-olive-brown undertone, not red).

## Root cause

`MI_Oak_Rift_Stained` / `MI_Oak_Shelf`'s `BaseColorTint` was
`(0.2423, 0.1144, 0.0543)` -- derived directly from the sRGB hex `#866044` by
converting hex-to-linear and treating the raw oak texture as if it were a
flat near-white average (i.e. the tint essentially *was* the intended final
colour, before `BaseColorBrightness=1.8` re-scaled it up to hit a target
luminance). That tint's **R:G ratio is 2.19** -- a strongly red-leaning
brown. Multiplied against the real, non-flat `T_Oak_Color` texture (which
itself carries the oak's own warm-yellow grain colour) and then lifted 1.8x
in brightness, the compounded result skewed noticeably redder than intended
in the full-scene render, reading as mahogany rather than a neutral
golden-brown oak stain.

## Fix

New tint `(0.55, 0.42, 0.26)` (linear), per the task's own suggested
starting point, at `BaseColorBrightness=0.57`. **R:G ratio 1.31** -- down
from 2.19, a genuinely more olive/neutral brown, with every channel scaled
down together (no channel selectively re-reddened). Brightness solved
against the same texture-luminance proxy the original recipe used (see
`build_wtk_material_instances.py`'s `build_oak_rift_stained()` docstring for
the full arithmetic): target luminance 0.25 (mid of the 0.2-0.3 range) ->
`BaseColorBrightness = 0.25 / (k * new_tint_luminance) = 0.57`, where `k` is
the same empirical texture/graph scale factor implied by the old recipe's
own documented result (0.25 luminance from tint_lum 0.1381 x brightness
1.8). Effective tint*brightness = `(0.314, 0.239, 0.148)`.

Applied identically to both `MI_Oak_Rift_Stained` and `MI_Oak_Shelf` (only
`UVRotation_deg` differs between them, unchanged from Phase 5c/5d). ClearCoat
(grain still visible under a satin lacquer, `ClearCoat=1.0`) and all
roughness/normal parameters unchanged.

## Verification against real renders

After rebuilding masters + material instances and re-running
`set_uv_mode_tiling.py` + `remap_materials_wtk.py` (per the pipeline's own
mandatory-after-rebuild lesson), re-rendered all 3 test cameras and sampled
real pixels (`PIL`-based sampling, sRGB->linear conversion by the standard
transfer function):

| Camera | B30 door region avg sRGB | linear luminance | Notes |
|---|---|---|---|
| CAM_Wide | (113.0, 77.1, 50.9) | 0.091 | warm brown, no red cast; below the 0.2-0.3 target because this framing/lighting angle under-lights B30 (a lighting/framing effect, not a material defect -- see Lighting.md's long-documented "B30 receives little direct light" finding) |
| CAM_Angle | (103.0, 66.7, 40.8) | ~0.08 (comparable ratio to CAM_Wide) | same warm-brown family, consistent with CAM_Wide, no red cast |
| CAM_Detail | (170.3, 123.6, 87.2) | 0.236 | **squarely in the 0.2-0.3 target range** at this shot's own per-camera exposure (see Lighting.md's Phase 5e section) |

The colour family (hue/ratio) is now consistently warm olive-brown across
all three cameras -- the remaining luminance gap on CAM_Wide/CAM_Angle is a
disclosed, pre-existing lighting-angle effect on this specific mesh/framing
(consistent with Lighting.md Section 7's long-standing "B30 receives
essentially no direct light from either the sun or the LEDs" finding), not
a regression or a new material problem.

## Files changed this pass

- `Scripts/build_wtk_material_instances.py` -- `build_oak_rift_stained()`
  and `build_oak_shelf()`: new tint `(0.55,0.42,0.26)` /
  `BaseColorBrightness=0.57` (was `(0.2423,0.1144,0.0543)` / `1.8`).
- Re-ran (mandatory per the documented lesson): `set_uv_mode_tiling.py`,
  `remap_materials_wtk.py`.

---

# WTK Material System — Phase 5c

Date: 2026-09-26. Scope: `05_Unreal/WTK/Content/WTK/Textures/`, `.../Materials/`, and the
Python scripts under `05_Unreal/WTK/Scripts/`. No Revit or `Pause/` files were modified
(Pause research docs were read-only inputs). No git.

Backup taken before any level/content change: `tmp/Wtk5c_20260926/backup_Content_WTK/`
mirrors `05_Unreal/WTK/Content/WTK/` as it stood before this task.

---

# Phase 5d addendum (2026-09-26) — master-material bugs found rendering test shots

Found and fixed while investigating why every WTK Material Instance fell
back to Unreal's default checkerboard material in `-game`/MRQ renders (never
visible in the editor preview), and later why stone/oak read near-black.
Full detail in `Docs/Lighting.md` Sections 6 and 9; summarized here since the
fixes are in `Scripts/build_wtk_masters.py`, this doc's own file, not just
the lighting doc.

1. **`add_texture_param()`** created `TextureSampleParameter2D` nodes with
   `texture=None` when no default was given (true for `BaseColorTex` on
   `MI_Ceiling_FlatWhite`/`MI_WindowFrame_White`, `RoughnessTex`, `NormalTex`,
   `TangentTex` on most MIs). Fatal PCD3D_SM6 shader compile error in
   `-game`/cooked contexts only ("Param2D> Found NULL, requires Texture2D").
   Fixed: default to the engine's `WhiteSquareTexture` (Color-type samplers)
   or `FlatNormal` (Normal-type samplers, via a new `is_normal` parameter)
   when no real texture is supplied.
2. **`add_switch()`** used `MaterialExpressionStaticSwitchParameter`, which
   has its own required `A`/`B` branch inputs (per its own engine header) —
   never wired anywhere in this codebase, since every call site only
   consumes it as a plain boolean feeding a separate
   `MaterialExpressionStaticSwitch`'s Value pin. Fatal "Missing A/B input"
   SM6 compile error on every WTK MI. Fixed by switching to
   `MaterialExpressionStaticBoolParameter` (no branch inputs of its own),
   in both `add_switch()` and `build_world_aligned_switch()`.
3. A secondary bug surfaced only after fixing (1): `flatten_lerp`'s inputs
   were a `Constant4Vector` (A) and a texture-sample float3 output (B) —
   `LinearInterpolate` requires matching vector widths. Fixed by switching
   to `Constant3Vector`.
4. **UVTiling regression**: rebuilding the masters (to apply fixes 1-3)
   necessarily rebuilds every Material Instance from scratch via
   `build_wtk_material_instances.py`, which does **not** itself set
   `UVTiling` — that's set by the separate, one-time
   `Scripts/set_uv_mode_tiling.py` (per its own docstring). This silently
   reverted every textured MI's tiling back to the master's `1.0` default,
   which is what actually caused stone/oak to look wrong (not a graph
   defect) — confirmed via `tmp/Wtk5d_20260926/check_stone_uv_params.py` and
   `check_oak_uv_params.py`. **Fix**: re-ran `set_uv_mode_tiling.py` after
   the masters/MI rebuild, restoring the documented tiling table's values
   (Stone 0.254, Oak 0.6096, Floor 0.1693, Paint/Wall 0.2032). **Lesson for
   any future masters rebuild**: `set_uv_mode_tiling.py` must be re-run
   after `build_wtk_material_instances.py` every time the masters change,
   not treated as truly one-time.

All fixes verified: `grep -c "Failed to compile Material" Saved/Logs/WTK.log`
went from 693-720+ (every render before these fixes) to **0** after.

---

# Phase 5d-7 addendum (2026-09-26) — look-development round: stone root cause, oak consistency check, colour-cast fix

Scope this pass: `Content/WTK/Materials/`, `Content/WTK/Textures/` (read-only),
`Scripts/build_wtk_masters.py`, `Scripts/build_wtk_material_instances.py`,
`Scripts/setup_lighting_wtk.py`, and `06_Renders/tests/`. No Revit/`Pause/`
files touched, no git. Backup: `tmp/Wtk5d7_20260926/backup/Content_WTK/`
(mirrors `Content/WTK/` before this pass). No `UnrealEditor` process was
running before any change (`Get-Process UnrealEditor*` returned nothing,
checked before starting).

## Task A: stone root cause -- CONFIRMED NOT a broken graph; recipe + lighting were the real causes

**Diagnostic performed exactly as specified**: dumped `MI_Stone_HonedCream`'s
live parameters first (`tmp/Wtk5d7_20260926/dump_mi_params.py` /
`dump_mi_params.txt`) -- confirmed `UseBaseColorTex=True`, `BaseColorTex`
correctly assigned to `T_Stone_Color`, `UVTiling=0.254` (the documented
correct value, i.e. the round-6 UVTiling regression was NOT still present),
`UseWorldAligned=False`. Then set a **neutral pass-through** (tint (1,1,1),
brightness 1, desaturate 0, vein contrast 1) and rendered CAM_Wide
(`tmp/Wtk5d7_20260926/stone_neutral_test.py`): **the counter rendered as a
correctly light warm cream/tan surface with visible marble veining, NOT dark
brown** -- this single result proves the base-colour chain (texture sampler,
sRGB import setting, UV coordinates feeding the sampler, the
desaturate/vein-contrast nodes) was never broken. A by-hand trace of the
chain's real numbers (raw `T_Stone_Color` sampled at 3000 random pixels:
average sRGB (177.8,162.5,149.2) -> linear (0.444,0.364,0.301), luminance
0.376) through the *old* recipe's own tint/brightness/desaturate/vein-contrast
values also predicted ~0.34 luminance on paper, not near-black -- consistent
with the neutral-pass-through finding.

**Root cause of the "dark brown counter" look, in order of contribution**:
1. **The recipe's own tint was too dark**: `BaseColorTint=(0.62,0.57,0.48)` at
   `BaseColorBrightness=1.0` pulled the already-moderate 0.376-luminance raw
   texture down to ~0.22 luminance before anything else happened -- this
   alone is well below the 0.55-0.6 target.
2. **`VeinContrast` fed a `MaterialExpressionPower` node's Exponent directly**
   (`Power(desaturated_colour, VeinContrast)`). This is the wrong operator
   for "reduce vein contrast" even though, numerically, `Power(x,k<1)` for
   `x` in (0,1) is a mild *brightener* not a darkener -- it reshapes the
   whole tonal curve nonlinearly (crushing shadow/highlight relationships)
   rather than simply pulling vein outliers toward the surface's own mean
   colour. **Fixed** in `build_wtk_masters.py`'s `build_common_opaque_chain()`:
   replaced the `Power` node with a `MaterialExpressionLinearInterpolate`
   from the desaturated colour (A) toward that colour's own luminance/mean
   (via a second `Desaturation` node feeding B) by `(1 - VeinContrast)`
   (via a `MaterialExpressionOneMinus`) -- so `VeinContrast=1.0` still means
   "full veining, no change" and `VeinContrast<1.0` softens veining by
   blending toward flat, with **zero darkening curve** involved.
3. **The scene's amber-cast, underlit lighting** (Task C's own subject)
   compounded on top of an already-dark material result, reading the final
   pixel as a near-uniform dark smear rather than a legible honed stone --
   this matches Lighting.md's Phase 5d round-6 finding that "even with
   veining now visible and UVTiling correct, the counter/backsplash still
   reads warm-brown... dominated by the sun's own warm colour."

**Fix applied**: (a) the graph fix above (LERP-toward-mean, no power law);
(b) a lighter, warmer tint (1.0, 0.94, 0.82) at `BaseColorBrightness=1.55`,
computed against the real sampled texture average to land at linear
luminance 0.553 with every channel <0.8 (0.688, 0.530, 0.383) -- see the
updated `build_stone_honedcream()` docstring in
`build_wtk_material_instances.py` for the exact arithmetic; (c)
`DesaturateTex` kept in range at 0.5 and `VeinContrast` at 0.6 (gentle
reduction, now via the LERP not a power curve); (d) the Task C colour-cast
fix (below), which was the single biggest visual improvement to how the
stone actually reads in the full scene.

**`UseWorldAligned` note (unchanged from Phase 5c-2)**: still confirmed inert
by construction on `MI_Stone_HonedCream` (and every MI) -- the switch is
exposed but never wired to anything downstream in the master graph (see
Materials.md's existing "Open item"). This was **not** the cause of the dark
stone; flagged again here only for completeness since Task A's own
diagnostic checklist asked to check "the UseBaseColorTex switch."

## Task B: oak consistency -- MI_Oak_Shelf and MI_Oak_Rift_Stained were ALREADY parametrically identical

Dumped both MIs' live parameters (same diagnostic script): `BaseColorTint`,
`BaseColorBrightness`, `RoughnessMin/Max`, `NormalStrength`, `ClearCoat`,
`ClearCoatRoughness`, `Metallic`, `Specular` are **all identical** between
`MI_Oak_Shelf` and `MI_Oak_Rift_Stained` (both `(0.2423, 0.1144, 0.0543)`
tint, brightness 1.8, ClearCoat 1.0) -- the only difference is
`UVRotation_deg` (0 vs 90, intentional per the grain-direction spec). **Both
were already on the same `M_WTK_ClearCoat` master** -- there is no
Opaque-vs-ClearCoat split between them as the coordinator's review
hypothesized. No material-parameter change was needed or made for Task B;
the grey-shelf-vs-chocolate-door discrepancy described in the review is a
**lighting/shading artifact** (the open shelf catches more ambient sky/wall
bounce at a grazing angle and reads cooler/lighter, while the enclosed B30
door sits mostly in the LED/fill shadow and reads warmer/darker), not a
material bug -- consistent with this pass's CAM_Angle render, where the
visible shelf corner and the B30 door read as variations of the same
mid-warm-brown stain, not two different materials.

**Not fully resolved**: `06_Renders/tests/WTK_Test_CAM_Detail_0000.png`'s
tight B30 close-up still reads notably lighter (avg sampled sRGB
~240,209,188 on the door region) than the 0.2-0.3 luminance target --
this is an **exposure/framing issue specific to that one shot**, not a
material-parameter issue (see Lighting.md's Round 7 log: lowering
`WTK_Fill_Room` from 2000 to 900 lm barely moved this shot's average
brightness, proving the fill light was not the dominant contributor;
lowering global `AutoExposureBias` to 3.0 helped that shot somewhat but
reintroduced the amber cast on the other two cameras, so it was not kept).
Flagged as an open follow-up requiring a per-shot exposure treatment (or a
narrower/more targeted fill beam) rather than a global PPV or material
change.

## Task C: colour cast -- root cause and fix

**Root cause** (per the coordinator's own diagnosis, confirmed by this
pass's renders): the 15-degree sun elevation makes `SkyAtmosphere` produce
golden-hour-like light, which the real-time `SkyLight` captures into every
bounce/fill in the room; the PPV's `WhiteTemp=5500K` was not aggressive
enough to compensate, so walls read tan and ivory cabinets read beige.

**Tried both options**: (i) `WhiteTemp=4700K` at the existing 15-degree sun
(kept -- see below); (ii) sun elevation raised to 25-30 degrees with
`WhiteTemp=6000-6500K` was considered but not separately re-rendered as its
own full round, since option (i) alone (combined with the Task A stone fix)
already produced the target look -- walls read warm off-white, ivory
cabinets read ivory not beige/tan -- without giving up the 15-degree raking
sun highlight across the counter that Lighting.md's Section 5 specifically
praised ("the raking sunlight is genuinely visible ... this is the effect
the task asked for"). Raising the sun elevation would have changed that
established, working effect, so it was not pursued once (i) alone worked.

**Final values**: `SUN_ELEVATION_DEG=15.0`, `SUN_TEMP_K=5200.0` (unchanged),
**`WHITE_TEMP=4700.0`** (down from 5500K), both now named module-level
constants at the top of `setup_lighting_wtk.py` for easy A/B re-tuning.

**Exposure re-check after the colour-cast fix (per the task's own
instruction)**: the corrected, warmer-reading walls/cabinets/stone are
substantially brighter overall than the old amber-cast bake at the same
`AutoExposureBias=4.0` (expected -- a less-saturated warm cast reads lighter
per the same underlying luminance). Tried lowering to 3.0 to address
CAM_Detail's overexposed close-up, but that reintroduced the amber/tan cast
on CAM_Wide/CAM_Angle's walls (bias and white-balance interact: darkening
exposure makes warm tones read MORE saturated). **Kept `AutoExposureBias=4.0`**
as the better overall balance across all 3 cameras -- see Task B's note
above for CAM_Detail's disclosed remaining shortfall. `WTK_Fill_Room`
lowered from 2000 to 900 lm lumens as a secondary, minor adjustment (did not
meaningfully change CAM_Detail but is a legitimate small improvement to the
wider shots' shadow depth).

## Files changed this pass

- `Scripts/build_wtk_masters.py` -- `build_common_opaque_chain()`: replaced
  the vein-contrast `Power` node with a `LinearInterpolate`-toward-mean
  chain (no darkening curve).
- `Scripts/build_wtk_material_instances.py` -- `build_stone_honedcream()`:
  new tint/brightness/desaturate/vein-contrast values, documented inline
  with the exact linear-colour arithmetic.
- `Scripts/setup_lighting_wtk.py` -- `SUN_ELEVATION_DEG`/`SUN_TEMP_K`/
  `WHITE_TEMP` module constants added; `WhiteTemp` lowered to 4700K;
  `WTK_Fill_Room` lowered to 900 lm; `AutoExposureBias` re-confirmed at 4.0
  after trying and rejecting 3.0.
- Re-ran (idempotent, mandatory per the Phase 5d UVTiling-regression lesson):
  `Scripts/set_uv_mode_tiling.py` after the masters/MI rebuild (confirmed
  `MI_Stone_HonedCream` UVTiling=0.254, all other MIs unchanged from their
  documented table) and `Scripts/remap_materials_wtk.py` (52/52 WTK slots
  still correctly assigned; the only "unmapped" slot is
  `WTK_GroundPlane_Outside`'s engine-default material, out of scope).
- Backup: `tmp/Wtk5d7_20260926/backup/Content_WTK/`.
- Diagnostics: `tmp/Wtk5d7_20260926/dump_mi_params.py`/`.txt`,
  `stone_neutral_test.py`.
- Final renders: `06_Renders/tests/WTK_Test_CAM_{Wide,Angle,Detail}_0000.png`.

---

# Phase 5c-2 addendum (2026-09-26)

Backup taken before any change this pass: `tmp/Wtk5c2_20260926/backup_Content_WTK/`
mirrors `05_Unreal/WTK/Content/WTK/` as it stood before Phase 5c-2 (100 files). No
UnrealEditor instance was open (`Get-Process UnrealEditor*` returned nothing) before any
edit. Four tasks: (1) UV mode + physically-correct tiling everywhere, (2) wire ClearCoat/
ClearCoatRoughness into the shading model via MaterialAttributes, (3) enable Nanite,
(4) edge bevels for the realism "tell". See `Docs/Pipeline.md` for the ordered post-import
steps this pass added.

## Task 1 — UV mode everywhere: extended check + tiling

Extended the Phase 5c UV check (B30, FX-05) to 4 more meshes: a wall, the floor, the
FX-01 counter, a painted cabinet (DB18 and SB36 both checked), and the FX-04
backsplash. Script: `05_Unreal/WTK/Scripts/uv_check_extended.py`. Findings
(`tmp/Wtk5c2_20260926/uv_check_extended.txt`):

| Mesh | Physical size (cm) | UV set 0 extent (U x V) | Notes |
|---|---|---|---|
| Wall (`..._6in`) | 396.24 x 15.24 x 243.84 | 27.5 x 8.25 | not degenerate; multi-island unwrap |
| Wall (`..._6in_2`) | 15.24 x 441.96 x 243.84 | 29.5 x 8.25 | same pattern |
| Floor (`Floor_Generic_-_12_`) | 365.76 x 426.72 x 30.48 | 28.0 x 28.0 | |
| FX-01 counter | 309.88 x 63.50 x 3.81 | 10.1667 x 10.1667 | **exact feet match**: 309.88cm/30.48=10.1667ft |
| DB18 (painted cabinet) | 45.72 x 62.23 x 87.63 | 4.0833 x 4.5417 | |
| SB36 (painted cabinet) | 91.44 x 62.23 x 87.63 | 5.0417 x 4.5417 | |
| FX-04 backsplash | 304.80 x 1.90 x 45.72 | 3.0 x 3.0 | |

**Confirmed**: UV set 0 is a real-unit-scale (feet) projection on every mesh checked, not
a 0-1 packed atlas and not degenerate — consistent with the Phase 5c finding on B30/FX-05
(B30's 30in width = 2.5 UV units = exactly 30in/12in-per-ft = 2.5ft; FX-05's 35.5in length
≈ 2.96 UV units ≈ 35.5in/12 = 2.958ft). The overall per-mesh UV bounding box is NOT a
single clean ratio against any one physical axis for multi-part/multi-island meshes
(confirmed via a units cross-check: only FX-01, a single simple slab with presumably one
UV island, shows an exact 1.0 ft/UV ratio on its long axis) — this is expected for a
per-face/per-part real-world unwrap where multiple box-like Datasmith solids are packed
side-by-side in UV space, not a single continuous planar mapping. It does NOT indicate a
degenerate or unusable UV set; each individual face/island is still feet-scaled.
**Decision confirmed**: continue using UV mode (not world-aligned) everywhere.

### UVTiling table (`UVTiling = 1 / tile_size_in_feet`, applied via `set_uv_mode_tiling.py`)

| Material | Tile size | Tile (ft) | UVTiling | MI(s) |
|---|---|---|---|---|
| Oak (white_oak_veneer) | 50 cm | 1.6404 | **0.6096** | MI_Oak_Rift_Stained, MI_Oak_Shelf |
| Paint/Wall (white_plaster_02) | 1.5 m | 4.9213 | **0.2032** | MI_Paint_WarmIvory, MI_Wall_WarmOffWhite |
| Stone (Marble020) | ~1.2 m (not published by ambientCG — task's own fallback used; see note below) | 3.9370 | **0.2540** | MI_Stone_HonedCream |
| Floor (WoodFloor051) | 180 cm | 5.9055 | **0.1693** | MI_Floor_Oak |
| Metals (brass/steel, general) | 30 cm | 0.9843 | **1.0160** | MI_Brass_Satin, MI_Steel_Brushed |
| Brass knob (radial, knob-scale override) | 5 cm | 0.1640 | **6.0960** | MI_Brass_Knob_Radial |

**Marble020 tile-size note**: checked `05_Unreal/WTK_SourceTextures/LICENSES.md` section 3
per the task's instruction ("check the asset's listed size in LICENSES.md") — it states
explicitly: *"Physical size: ambientCG does not publish explicit real-world dimensions for
this texture... treat as a standard ~1-2 m seamless tile and verify scale against the
brief's guidance"*. So the task's own ~1.2m fallback value is what's used (matches the
pre-existing `TextureSize_cm=120` already set on `MI_Stone_HonedCream` in Phase 5c).

`UseWorldAligned` is now `False` on every MI (`MI_Ceiling_FlatWhite`, `MI_Glass_Clear`
[different master, N/A], `MI_LED_3000K` [different master, N/A], and `MI_WindowFrame_White`
have no texture to scale, so `UVTiling` is left at its master default of 1.0 for them —
`UseWorldAligned=False` is still set for consistency/documentation).

### Oak grain rotation — verified, not just placeholder

Script: `05_Unreal/WTK/Scripts/uv_orientation_check.py`. Sampled all 240 triangles of
`Casework_WTK_B30_B30`, correlating `|dU|` and `|dV|` against `|dZ|` (world/local vertical)
across every triangle edge with real vertical extent (320 qualifying edges). Result:
`avg |dU|/|dZ| = 0.1050` vs `avg |dV|/|dZ| = 0.0328` — **U correlates with vertical motion
~3.2x more strongly than V**, i.e. **U runs vertically on this mesh's unwrap**. Since the
source oak texture (`T_Oak_Color`) has its grain running along its native V axis (standard
convention for a wood-grain texture), and U (not V) is vertical here, a 90-degree rotation
is required to swap U/V so the grain reads vertically in world space. This **confirms**
(rather than merely assumes, as the Phase 5c placeholder did) that `MI_Oak_Rift_Stained`'s
existing `UVRotation_deg=90` is correct. `MI_Oak_Shelf`'s `UVRotation_deg=0` (grain along
shelf length) was left as-is and not independently re-verified this pass via the same
per-triangle correlation method (flagged as an open follow-up if a stronger guarantee is
wanted — the method in `uv_orientation_check.py` could be pointed at FX-05 the same way).

### World-aligned switch — made harmless, documented

See the "RESOLVED (Phase 5c-2 Task 1)" note inserted above the M_WTK_Opaque parameter
table: the `UseWorldAligned` switch is structurally disconnected from the graph (never
consumed by anything downstream), confirmed by inspection of `build_wtk_masters.py`'s
`build_common_opaque_chain()` — so it is already harmless by construction. Every MI now
also has it explicitly set to `False` for clarity/consistency with the confirmed-correct
UV-mode path.

## Task 2 — Clear Coat: RESOLVED

See the "RESOLVED (Phase 5c-2 Task 2)" section inserted above the old Known Limitation
(kept below it for context/diagnostic history). Summary: `M_WTK_ClearCoat` now uses
`use_material_attributes=True` + a `MaterialExpressionMakeMaterialAttributes` node wired
to every existing chain by pin name (including `"ClearCoat"`/`"ClearCoatRoughness"`, which
ARE reachable on this node type, unlike on `SetMaterialAttributes` or the raw `UMaterial`
properties), connected to `MP_MATERIAL_ATTRIBUTES`. Verified: `use_material_attributes`
reads back `True`, `shading_model` reads back `MSM_CLEAR_COAT`, the material recompiles
without error, expression count grew from ~45 to 55, and `MI_Oak_Rift_Stained.ClearCoat`
still reads `1.0` after the masters/MI rebuild. No headless API was found to directly
confirm the compiled shader's ClearCoat pin is populated (the strongest available
signal short of an in-editor visual check).

## Task 3 — Nanite

`import_wtk.py`'s new `run_nanite_pass()` enables Nanite (`nanite_settings.enabled=True`,
set via the StaticMesh's `nanite_settings` property directly — `get_editor_subsystem
(unreal.StaticMeshEditorSubsystem)` returned `None` in headless commandlet mode in this
UE 5.7 build, confirmed via introspection) on every StaticMesh under `/Game/WTK/Datasmith`
except: (a) meshes whose name contains "Glass" or "Window" (translucent/glass, where
Nanite doesn't apply/help), and (b) meshes under a 12-triangle threshold (tiny meshes,
counted via the same GeometryScript copy-to-DynamicMesh + `get_num_triangle_i_ds` path
already used elsewhere in this codebase, since `StaticMesh.get_number_of_triangles()`
does not exist in this Python binding). **Result on the full WTK_Main import: 39 meshes
enabled, 2 skipped (glass/window), 0 already-enabled on a fresh reimport; a rerun shows
0 newly enabled / 39 already-enabled (idempotent).**

## Task 4 — Edge bevels

`import_wtk.py`'s new `run_bevel_pass()` applies a 0.159cm (1/16in) bevel to hard edges on
casework (`Casework_WTK_*`), the counter (`FX-01`), the shelf (`FX-05`), and the
backsplash (`FX-04`), skipping glass. Method (validated on B30 alone first, per the task's
own instruction, before batching):

1. `GeometryScript_AssetUtils.copy_mesh_from_static_mesh()` → DynamicMesh.
2. `GeometryScript_MeshSelection.select_mesh_sharp_edges(min_angle_deg=30.0)` — hard-edge
   selection by angle threshold.
3. `GeometryScript_MeshSelection.select_mesh_boundary_edges()` — **necessary because the
   Datasmith meshes are composed of many separate box-like solids/islands per mesh** (each
   logical part — stile, rail, panel, knob, etc — is its own disconnected solid); a
   boundary-edge selection catches every such part's own hard edges in addition to the
   sharp-angle selection. Combined via
   `GeometryScript_MeshSelection.combine_mesh_selections(..., ADD)` — B30 alone had 518
   combined edges selected (240 triangles → many boundary edges from its 138 UV
   islands/parts, per the Phase 5c UV check).
4. `GeometryScript_MeshModeling.apply_mesh_bevel_edge_selection()` with
   `GeometryScriptMeshBevelSelectionOptions.bevel_distance = 0.159`. **API note**: the
   correct struct type is `GeometryScriptMeshBevelSelectionOptions`, NOT
   `GeometryScriptMeshBevelOptions` (a same-shaped but different struct that
   `apply_mesh_bevel_edge_selection` rejects with a `NativizeStructInstance` TypeError) —
   confirmed via trial-and-error in `bevel_test_b30.py`.
5. `GeometryScript_Normals.compute_split_normals()` with a 60-degree opening-angle
   threshold (hard edges stay hard, the new small bevel faces read smooth across
   themselves and blend into their neighbors per the angle test).
6. `GeometryScript_AssetUtils.copy_mesh_to_static_mesh()` back to the asset at LOD0.
   **API note**: the write side needs a `GeometryScriptMeshWriteLOD` struct (NOT the
   `GeometryScriptMeshReadLOD` used for the read side) — same same-shaped-but-different-type
   TypeError pattern as step 4, confirmed via trial-and-error.
7. Idempotency marker: `EditorAssetLibrary.set_metadata_tag(mesh, "WTK_Beveled_v1", "1")`,
   set only after validating the bevel actually grew the triangle count and left material
   slots unchanged; checked before beveling on every run.

**B30 single-mesh validation** (`bevel_test_b30.py`, `tmp/Wtk5c2_20260926/bevel_test_b30.txt`):
- Triangle count: 240 → 745 (**3.10x**, a moderate increase, not runaway).
- Bounds delta: **exactly 0.00000 cm** on all six min/max XYZ components (tolerance was
  ±0.01cm) — the bevel does not change the mesh's overall bounding box, as expected for a
  small inward-facing chamfer.
- Material slots: `['Paint_WarmIvory', 'Oak_StainedWarmBrown', 'Metal_SatinBrass']`
  unchanged before/after.
- No degenerate-triangle check API was found directly exposed in this UE 5.7 GeometryScript
  Python binding (no `count_degenerate_triangles`-equivalent) — the triangle-count-grew +
  bounds-unchanged + material-slots-unchanged checks are the practical validation used
  instead, per the task's own list of things to check.

**Batch result** (full pipeline, 10 target meshes): all succeeded, 0 failed. Per-mesh
before/after triangle counts and ratios are in `Docs/Pipeline.md`'s Verification section.
Reimporting against unchanged Datasmith source geometry correctly reports
`already_done=10, beveled=0` on a rerun (idempotent).

---


## Environment notes

- All headless runs used `UnrealEditor-Cmd.exe -run=pythonscript` **except** the texture
  import step, which requires the full `UnrealEditor.exe -ExecutePythonScript` path.
  `unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(...)` touches
  ContentBrowser/Slate UI code and crashes under `-run=pythonscript`'s headless commandlet
  mode with `Assertion failed: CurrentApplication.IsValid()` (SlateApplication.h:321) —
  confirmed empirically on the first `import_asset_tasks` call. All other steps (master
  materials, material instances, UV check, remap) ran fine under the lighter, faster
  `-run=pythonscript` commandlet path, since `MaterialEditingLibrary`/`GeometryScript_*`
  do not touch Slate.
- Several UE 5.7 Python API names differ from what's typically documented/assumed;
  discovered by introspection during this task and noted inline in the scripts:
  - No `unreal.MaterialExpressionCustomRotator` — UV rotation was hand-built from
    Sine/Cosine + the 2D rotation matrix (`build_wtk_masters.py:build_uv_and_tiling_chain`).
  - No `unreal.MaterialExpressionFlattenNormal` — its effect was reproduced by hand
    (lerp sampled normal toward flat (0.5,0.5,1.0) by Strength, then Normalize).
  - `MaterialInstanceConstantFactoryNew` has no Python-settable `initial_parent`; the
    parent is set post-creation via `MaterialEditingLibrary.set_material_instance_parent`.
  - `GeometryScript_AssetUtils` / `GeometryScript_MeshQueries` (not
    `GeometryScriptLibrary_StaticMeshFunctions`/`MeshQueryFunctions`) are the actual
    Python-exposed class names in this build; several of their functions return tuples
    (mesh + outcome, or value + outcome) rather than taking an outcome as an out-param.

## RESOLVED (Phase 5c-2 Task 2) — ClearCoat / ClearCoatRoughness now wired via MaterialAttributes

**Update, Phase 5c-2**: the Known Limitation below (kept for its diagnostic detail) is
resolved. `M_WTK_ClearCoat` now has `use_material_attributes=True` and a
`MaterialExpressionMakeMaterialAttributes` node that every existing chain (BaseColor,
Metallic, Specular, Roughness, Anisotropy, Normal, Tangent, ClearCoat, ClearCoatRoughness)
connects into by pin name, itself connected to the material's `MP_MATERIAL_ATTRIBUTES`
output. **The breakthrough**: `unreal.MaterialExpressionMakeMaterialAttributes` exposes
static, string-addressable input pins including `"ClearCoat"` and `"ClearCoatRoughness"`
(confirmed via `MaterialEditingLibrary.get_material_expression_input_names()` on a
freshly-created node — see `tmp/Wtk5c2_20260926/introspect_matattr.py`'s output, which
lists `ClearCoat`/`ClearCoatRoughness` among 27 named pins). This differs from
`MaterialExpressionSetMaterialAttributes`, whose per-shading-model sub-pins are
dynamically generated at edit time and not reachable by name string (the path tried and
abandoned in Phase 5c). `MaterialEditingLibrary.connect_material_expressions()` accepts
these pin names on a `MakeMaterialAttributes` node without error.

Implementation: `build_wtk_masters.py`'s `build_common_opaque_chain()` now returns every
terminal expression (base colour, roughness, normal, metallic, specular, anisotropy,
tangent, and — when `is_clearcoat` — the ClearCoat/ClearCoatRoughness scalar parameter
expressions) instead of connecting them straight to `MaterialProperty` outputs when
building the ClearCoat variant; `build_clearcoat()` then builds the
`MakeMaterialAttributes` node and wires all of them in by name. `build_opaque()` is
unchanged (still connects directly to `MaterialProperty` outputs — no
`use_material_attributes` needed there, since M_WTK_Opaque has no ClearCoat pins to
reach).

**Verification performed** (headless, no way to render/screenshot in this environment):
`use_material_attributes` reads back `True`; `shading_model` reads back
`MSM_CLEAR_COAT`; `MEL.recompile_material()` completes without raising (a real shader
compile error, e.g. a dangling/invalid MaterialAttributes pin, raises here); the graph's
expression count grew from ~45 to 55 after adding the MakeMaterialAttributes node and its
9 connections; `MI_Oak_Rift_Stained`'s `ClearCoat` parameter still reads back `1.0` after
the masters rebuild. There is no headless Python API in this UE 5.7 build to directly
introspect "is the ClearCoat shading input pin populated in the compiled shader" (no
`get_material_default_bool`/equivalent was found) — an in-editor visual check (open
`M_WTK_ClearCoat`, confirm the ClearCoat/ClearCoatRoughness pins on the Clear Coat
shading-model output node are fed from the MakeMaterialAttributes node, not
disconnected) is the recommended final confirmation once the editor is opened
interactively.

## Prior limitation (kept for context) — direct ClearCoat pin write attempt, Phase 5c

`UMaterial`'s `ClearCoat` and `ClearCoatRoughness` `FExpressionInput` members (the legacy
Clear Coat shading model's dedicated pins, historically CustomData0/CustomData1) are marked
**protected** in this engine build's Python reflection:

```
get_editor_property('clearcoat') -> "Property 'ClearCoat' ... is protected and cannot be read"
set_editor_property('clearcoat', <expr>) -> "Property 'ClearCoat' ... is protected and cannot be set"
```

`MaterialEditingLibrary`'s `MaterialProperty` enum (used by `connect_material_property`) only
exposes: `MP_AMBIENT_OCCLUSION, MP_ANISOTROPY, MP_BASE_COLOR, MP_EMISSIVE_COLOR,
MP_FRONT_MATERIAL, MP_MATERIAL_ATTRIBUTES, MP_METALLIC, MP_NORMAL, MP_OPACITY,
MP_OPACITY_MASK, MP_REFRACTION, MP_ROUGHNESS, MP_SPECULAR, MP_SUBSURFACE_COLOR, MP_TANGENT,
MP_WORLD_POSITION_OFFSET` — no ClearCoat entries. `MaterialEditingLibrary` also has no
dedicated `connect_material_expressions(..., mat, "ClearCoat")` path (pin-name string
match against the Material object fails silently), and
`MaterialExpressionSetMaterialAttributes`'s dynamically-generated ClearCoat sub-pin isn't
reachable by string either (`get_material_expression_input_names` only returns the node's
static `MaterialAttributes` input, not the per-shading-model sub-pins the UI generates).

**Result**: `M_WTK_ClearCoat` has `ClearCoat` and `ClearCoatRoughness` ScalarParameters
created, positioned, and documented (values below), but **not wired** to the shading
model's actual ClearCoat inputs by this script.

**Required manual step** (one-time, ~10 seconds, in-editor): open `M_WTK_ClearCoat` in the
Material Editor, and drag-connect the existing `ClearCoat` and `ClearCoatRoughness`
ScalarParameter nodes (in the `07_ClearCoat` parameter group, already positioned at
x=-1000, y=900/960) into the material's `ClearCoat` / `Clear Coat Roughness` input pins
(visible once the Clear Coat shading model is selected, which it already is). Save and
recompile. This is required before `MI_Oak_Rift_Stained` / `MI_Oak_Shelf`'s ClearCoat=1.0
values will visibly affect the render — until then those MI parameter values are stored
correctly but inert.

## 1. Texture import summary

25 textures + 1 HDRI imported to `/Game/WTK/Textures/`, all succeeded (0 failures).

| Material folder | Textures imported | Colour(sRGB on) | Mask(sRGB off,TC_Masks) | Normal(TC_Normalmap) |
|---|---|---|---|---|
| Oak | T_Oak_Color, T_Oak_Roughness, T_Oak_Normal, T_Oak_Backup_Color, T_Oak_Backup_Roughness, T_Oak_Backup_Normal | 2 | 2 | 2 |
| Paint_WallPlaster | T_Plaster_Color, T_Plaster_Roughness, T_Plaster_Normal | 1 | 1 | 1 |
| Stone | T_Stone_Color, T_Stone_Roughness, T_Stone_Normal, T_Stone_Displacement | 1 | 2 | 1 |
| Metal_Brushed | T_Metal009_Color/Roughness/Metalness/Normal, T_Metal051A_Color/Roughness/Metalness/Normal | 2 | 4 | 2 |
| Floor | T_Floor_Color, T_Floor_Roughness, T_Floor_Normal, T_Floor_AO | 1 | 2 | 1 |
| HDRI | T_HDRI_FarmlandOvercast | — imported as **TextureCube** (confirmed by class check) | | |

All normal maps left `flip_green_channel = False` (source is already DirectX convention per
`WTK_SourceTextures/LICENSES.md`). All mask/grayscale textures (Roughness, Metalness, AO,
Displacement) set `srgb=False`, `compression_settings=TC_MASKS`. Colour maps left
`srgb=True`, `compression_settings=TC_DEFAULT`.

Path: `05_Unreal/WTK/Scripts/import_wtk_textures.py`. Log:
`tmp/Wtk5c_20260926/texture_import_log.txt`.

## 2. Master materials

All four built via `MaterialEditingLibrary`, in `/Game/WTK/Materials/Masters/`. Script:
`05_Unreal/WTK/Scripts/build_wtk_masters.py`.

### M_WTK_Opaque (DefaultLit)

Parameter groups: `01_Textures`, `02_Color`, `03_UVs`, `04_Physical`, `05_Anisotropy`,
`06_Stone`.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| BaseColorTex | Texture2D | none | |
| UseBaseColorTex | StaticSwitch | true | true = textured, false = flat BaseColorTint |
| BaseColorTint | Vector | (1,1,1) | multiplies BaseColorTex, or used directly if switch is false |
| BaseColorBrightness | Scalar | 1.0 | multiplies the tinted result |
| DesaturateTex | Scalar | 0.0 | 0=full colour, 1=fully desaturated (stone) |
| VeinContrast | Scalar | 1.0 | Power exponent applied after desaturate (stone vein contrast) |
| RoughnessTex | Texture2D | none | |
| RoughnessMin / RoughnessMax | Scalar | 0.3 / 0.7 | Lerp remap of RoughnessTex.R |
| NormalTex | Texture2D(Normal) | none | |
| NormalStrength | Scalar | 1.0 | hand-built FlattenNormal-equivalent (lerp toward flat + normalize) |
| Metallic | Scalar | 0.0 | |
| Specular | Scalar | 0.5 | |
| Anisotropy | Scalar | 0.0 | connected to MP_ANISOTROPY |
| UseTangentTex | StaticSwitch | false | true = TangentTex drives MP_TANGENT, false = VertexNormalWS |
| TangentTex | Texture2D(Normal) | none | direction map for brushed-metal anisotropy |
| UseWorldAligned | StaticSwitch | false | placeholder for a future triplanar function swap-in (see below) |
| TextureSize_cm | Scalar | 100.0 | tile size in cm; consumed once world-aligned/triplanar is wired |
| UVTiling | Scalar | 1.0 | multiplies the (rotated, centred) mesh UV |
| UVRotation_deg | Scalar | 0.0 | hand-built 2D rotation (see Environment notes) |
| UVOffset | Vector | (0,0) | added after tiling |

**Open item (Phase 5c) / RESOLVED (Phase 5c-2 Task 1)**: `UseWorldAligned` and
`TextureSize_cm` are exposed as the task specifies, but the master graph currently always
samples via the UV chain (TexCoord0-based), not a true WorldAlignedTexture/triplanar
sample. A full triplanar implementation requires per-texture-sample world-position-based
UVs (3 samples + blend per texture, multiplied across every texture parameter in the
graph) — flagged as a follow-up rather than implemented, since Phase 5c-2's extended UV
check (see "5c-2 Task 1" section below) confirmed the mesh UVs are usable (real-unit/feet
scale, not degenerate) on every mesh sampled: B30, FX-05 shelf, a wall, the floor, the
FX-01 counter, two painted cabinets (DB18/SB36), and the FX-04 backsplash.

**As of Phase 5c-2, `UseWorldAligned` is set to `False` on every Material Instance.**
The `UseWorldAligned` `MaterialExpressionStaticSwitchParameter` node in the master graph
(`build_world_aligned_switch()` in `build_wtk_masters.py`) is created and exposed as a
parameter, but is **never connected to anything downstream** — confirmed by inspection of
`build_common_opaque_chain()`: the `ws` (switch) and `texture_size` expressions returned by
`build_world_aligned_switch()` are stored in the function's return dict but no
`MaterialExpressionStaticSwitch` consumes `ws`'s output anywhere in the graph, so the
material always samples via the UV chain (`TexCoord0` → rotate → tile → offset)
regardless of the switch's value. This makes the switch structurally harmless already
(toggling it changes nothing about the compiled shader) — it is left in place, still
exposed on every MI, as the task specifies ("leave the switch but make it harmless"), for
a future pass that wants to implement the real triplanar sample chain without changing
the public parameter interface. **Do not rely on `UseWorldAligned=True` doing anything
in this engine build's current graph** — it is inert by construction, not just by MI
default value.

### M_WTK_ClearCoat (Clear Coat shading model)

Same inputs as M_WTK_Opaque, plus:

| Parameter | Type | Default | Notes |
|---|---|---|---|
| ClearCoat | Scalar | 0.0 | **not wired to the shading pin — see Known Limitation above** |
| ClearCoatRoughness | Scalar | 0.2 | **not wired to the shading pin — see Known Limitation above** |

### M_WTK_Glass (Translucent)

| Parameter | Type | Default |
|---|---|---|
| BaseColorTint | Vector | (0.9, 0.95, 0.95) |
| Opacity | Scalar | 0.12 |
| Roughness | Scalar | 0.02 |
| Specular | Scalar | 0.5 |
| Metallic | Scalar | 0.0 |
| IOR | Scalar | 1.5 (connected to MP_REFRACTION) |

Blend Mode = Translucent. Attempted `translucency_lighting_mode =
TLM_SURFACE_TRANSLUCENCY_VOLUME`; if that property set failed silently in this engine build,
the material is left at the engine default lighting mode (Surface ForwardShading) — verify
in-editor. Lumen front-layer translucency reflections
(`r.Lumen.Translucency.FrontLayer.Enable`) is a **project setting**, not a material
property; not set in this pass since it requires a `DefaultEngine.ini` edit, which is out
of this task's write scope beyond what Phase 5a already did. Flagged as an open item for
whoever does the lighting/render pass.

### M_WTK_Emissive (DefaultLit + emissive)

| Parameter | Type | Default |
|---|---|---|
| BaseColorTint | Vector | (0.05,0.05,0.05) |
| Roughness | Scalar | 0.6 |
| EmissiveColor3000K | Vector | (1.0, 0.588, 0.281) — approximate 3000K blackbody warm white |
| EmissiveStrength | Scalar | 5.0 — deliberately low; the real light comes from Rect Lights per the lighting research doc |

## 3. Material instances

All in `/Game/WTK/Materials/`, built via `build_wtk_material_instances.py`. Colour values
below are **linear** (0-1), matching UE5's VectorParameter convention; sRGB/hex sources are
converted via the standard transfer function (documented per-value below).

| MI | Parent | Key values | Citation |
|---|---|---|---|
| MI_Oak_Rift_Stained | ClearCoat | BaseColorTex=T_Oak_Color; Tint=(0.2423,0.1144,0.0543) [sRGB #866044 -> linear]; Brightness=1.8 (lifts luminance from 0.138 to ~0.25, target 0.2-0.3); Roughness 0.35-0.55; ClearCoat 1.0, ClearCoatRoughness 0.2; TextureSize_cm=50; UVRotation_deg=90 (grain vertical, placeholder pending visual check) | WOOD_CABINET_MATERIALS research doc, "Recommended material recipes / Oak_StainedWarmBrown" |
| MI_Oak_Shelf | ClearCoat | Same as above but UVRotation_deg=0 (grain along shelf length) | same |
| MI_Paint_WarmIvory | Opaque | UseBaseColorTex=False; Tint=(0.70,0.66,0.58) (luminance ≈0.664, all channels <0.8); Roughness 0.35-0.45 (RoughnessTex=T_Plaster_Roughness); NormalStrength 0.15; UseWorldAligned=True, TextureSize_cm=80 | Benjamin Moore Precious Ivory LRV 70.38 correction; ARCHVIZ_KITCHEN doc's <0.8 Path Tracer note |
| MI_Wall_WarmOffWhite | Opaque | Tint=(0.74,0.70,0.63) (luminance ≈0.70); Roughness 0.8-0.9; NormalStrength 0.08; UseWorldAligned=True, TextureSize_cm=100 | UE5_Reference_Notes.md master-material plan |
| MI_Ceiling_FlatWhite | Opaque | Tint=(0.76,0.75,0.71) (luminance ≈0.75, neutral-warm); Roughness 0.9; no normal | task spec |
| MI_Stone_HonedCream | Opaque | BaseColorTex=T_Stone_Color; Tint=(1.0,0.94,0.82) light warm-cream multiply; BaseColorBrightness=1.55; DesaturateTex=0.5; VeinContrast=0.6 (reduced via LERP-toward-mean, NOT a power law -- Phase 5d-7 fix, see Section "Phase 5d-7" below); Roughness 0.45-0.5; UseWorldAligned=False (inert switch, see Open item), UVTiling=0.254, TextureSize_cm=120 | Marble020 desaturated per task spec; honed-quartz 35-40% reflectance finding; Phase 5d-7 root-cause fix for the "dark brown counter" bug |
| MI_Brass_Satin | Opaque | Metallic=1; Tint=(0.62,0.46,0.25) champagne-bronze (WTK prop-fix pass, was (0.80,0.60,0.33) -- read pale cream/ivory in close-up, see this doc's prop-fix pass addendum); Roughness 0.35-0.45 (was 0.3-0.4), Metal009; Anisotropy 0.4; TangentTex=T_Metal009_Normal | WOOD_CABINET research doc's Metal_SatinBrass recipe; WTK prop-fix pass tint/roughness correction |
| MI_Brass_Knob_Radial | Opaque | Same as MI_Brass_Satin but Metal051A (radial brushing); TextureSize_cm=5 (knob scale) | same, "Substance Painter Anisotropic Radial" analogue |
| MI_Steel_Brushed | Opaque | Metallic=1; Tint=(0.56,0.57,0.58); Roughness 0.25-0.35 (Metal009); Anisotropy 0.5 | task spec |
| MI_Glass_Clear | Glass | Master defaults (Opacity 0.12, Roughness 0.02, IOR 1.5) | — |
| MI_LED_3000K | Emissive | Master defaults (EmissiveStrength 5.0, low — real light from Rect Lights) | task spec + Lumen-emissive-GI note in WTK_UE5_Reference_Notes.md |
| MI_Floor_Oak | Opaque | BaseColorTex=T_Floor_Color; Tint=(1.0,0.95,0.85) warm; Roughness 0.45-0.6; UseWorldAligned=True, TextureSize_cm=15.24 (6in target board width — see note below) | task spec |
| MI_WindowFrame_White | Opaque | Tint=(0.78,0.78,0.76); Roughness 0.5; no texture | task spec |

**MI_Floor_Oak tile-size note**: `LICENSES.md` records WoodFloor051's asset tile as
180x180cm with no published plank count, so an exact "boards per 180cm tile" computation
was not possible from metadata. `TextureSize_cm` was set directly to the 6in (15.24cm)
target board width on the assumption that the master's (currently UV-chain-based, not yet
triplanar) tiling maps `TextureSize_cm` to one repeat unit. **This must be visually
confirmed once the level is open** — if the source texture's native plank width isn't
15.24cm-per-UV-tile, this value needs adjusting after a visual check against the floor
mesh. Flagged, not silently assumed correct.

Full values and rationale for every MI: `05_Unreal/WTK/Scripts/build_wtk_material_instances.py`
(each `build_*` function has a docstring with the exact linear-colour derivation).

## 4. UV check — B30 casework and FX-05 shelf

Script: `05_Unreal/WTK/Scripts/uv_check_b30.py`. Findings (from
`tmp/Wtk5c_20260926/uv_check_b30.txt`):

**Casework_WTK_B30_B30** (240 triangles, 1 StaticMeshComponent):
- **UV set 0**: bounding box U[-2.0417, 2.5000], V[-2.5000, 2.0417] — **not normalized to
  0-1**. This is a real-unit-scale UV projection (consistent with a Revit/Datasmith export
  that carries real-world-scale UVs rather than a packed 0-1 texture atlas), with 138 UV
  islands across the mesh.
- **UV set 1**: bounding box U[0, 1], V[0.025, 0.975] — a standard packed 0-1 lightmap UV
  (as expected — Datasmith/Revit exports typically generate a second UV channel for
  lightmapping).
- **Material slots** (3): `Paint_WarmIvory`, `Oak_StainedWarmBrown`, `Metal_SatinBrass`.
  Only 3 slots exist for the whole B30 actor — **confirms the research doc's prediction**:
  the stiles, rails, and panel (all Oak_StainedWarmBrown-tagged) share a single material
  slot; the mesh/material-slot structure does **not** separate rails from stiles/panel.

**Furniture_FX-05** (24 triangles, the floating shelf):
- **UV set 0**: bounding box U[-1.4792, 1.4792], V[-1.4792, 1.4792] — same
  non-normalized/real-unit-scale pattern as B30.
- **UV set 1**: bounding box U[0,1], V[0.359, 0.641] — packed lightmap UV.
- **Material slots** (1): `Oak_StainedWarmBrown` only.

### UV vs world-aligned decision

**Decision: use the mesh's own UV set 0 (UV mode), not world-aligned, for both B30 and the
FX-05 shelf.** Rationale:
- UV set 0's bounding box is centered near the origin with a magnitude in the 1.5-2.5
  range — plausible for a real-unit UV projection at this part's scale (B30 is roughly
  2.25-10 in / 5.7-25 cm across its parts; a UV range of ~4-5 units total is consistent
  with a per-face real-world unwrap at roughly meter-scale, not a degenerate/garbage UV).
  It is **not** a 0-1 packed atlas UV (that's UV set 1, reserved for lightmapping) and it is
  **not** degenerate (zero-area or NaN) — 138 UV islands on B30, one per logical face/part,
  is a sane, non-collapsed unwrap.
- Both master materials' UV chain (rotate -> tile -> offset) operates on whichever UV set is
  fed to `TextureCoordinate(coordinate_index=0)`, i.e. UV set 0 — the real-unit set. This
  means `UVTiling`/`UVRotation_deg`/`UVOffset` can be tuned directly against real UV-space
  units without first solving a world-aligned/triplanar sample chain (which is not yet built
  in the master — see the M_WTK_Opaque "Open item" above).
- The task's own fallback condition ("if the Revit UVs are unusable, use world-aligned")
  does not apply here: the UVs are not unusable, just not confirmed to be in an exact
  physical-cm scale — visual verification against the actual grain scale (grain tile ≈50cm
  per the recipe) is still needed once the level is open in the editor, per the pre-mortem
  in the research doc ("A/B test against the LRV-anchored... under the same lighting").
- `MI_Oak_Rift_Stained` and `MI_Oak_Shelf` are therefore both set with `UseWorldAligned=False`
  and rely on `UVTiling`/`UVRotation_deg` against UV set 0. `UVRotation_deg=90` for
  `MI_Oak_Rift_Stained` (grain vertical on stiles/panel) and `UVRotation_deg=0` for
  `MI_Oak_Shelf` (grain along shelf length) are **placeholder values pending a visual check**
  in the editor — the UV check script confirms the UVs are sane and gives their bounding
  box, but does not (and cannot, headlessly, without a render) confirm which UV axis
  currently reads as "along the grain" for this specific unwrap. **Open follow-up**: open
  the level, apply `MI_Oak_Rift_Stained` to B30, and tune `UVRotation_deg` by eye against the
  real grain direction.

### Follow-up noted per the task: rails cannot be separated from stiles/panel

Confirmed by the material-slot check above: B30's single `Oak_StainedWarmBrown` slot covers
stiles, rails, and panel together (no separate rail slot exists in the current mesh).
**Proposed follow-up** (not implemented in this pass — would require a Revit/Datasmith
family or material-slot change, out of this task's Unreal-only scope): split the rails into
their own Revit material slot (or, as a render-only workaround, prepare a normal/roughness
mask keyed to mesh position/UV-V-range if the rails occupy a consistent UV band) so the
grain rotation could differ between stiles/panel (vertical) and rails (horizontal) within
a single actor, per `build_a102_details.ps1:98`'s grain-direction spec. Currently
`MI_Oak_Rift_Stained`'s single `UVRotation_deg` value applies uniformly to the whole slot.

## 5. Material remap script and results

Script: `05_Unreal/WTK/Scripts/remap_materials_wtk.py`. Rule table matches
(actor-label regex, source-material-name) -> MI path, evaluated top-to-bottom, first match
wins; regex-qualified rules (B30 oak, FX-05 shelf oak, Knob brass) are listed before their
regex-less fallback so the more specific rule wins.

**Run against `/Game/WTK/Maps/WTK_Main` on 2026-09-26:**

- **Slots inspected: 52**
- **Assigned: 52**
- **Unmapped: 0** (matches the task's "expect 0")

Every source material name present in the level (`Paint_WarmIvory`, `Oak_StainedWarmBrown`,
`Stone_HonedCream`, `Metal_SatinBrass`, `Steel_Brushed`, `Wall_WarmOffWhite`, `Glass_Clear`,
`Light_LED3000K`, `Default_Floor`, `RNT_Material`, `Clad_-_White`, `Wood_-_Stained`) was
successfully mapped. Full 52-line per-slot assignment log:
`tmp/Wtk5c_20260926/remap_results.txt`.

Notable per-actor results:
- `Casework_WTK_B30_B30`: slot 0 -> MI_Paint_WarmIvory, slot 1 -> MI_Oak_Rift_Stained, slot 2
  -> MI_Brass_Satin.
- `Furniture_FX-05`: slot 0 -> MI_Oak_Shelf (grain-along-length variant), confirming the
  FX-05-specific rule fired correctly ahead of the generic Oak_StainedWarmBrown fallback.
- `Generic_Models_Hardware0_Knob` / `Hardware1_Knob`: both -> MI_Brass_Knob_Radial (the
  "Knob" label regex fired ahead of the generic Metal_SatinBrass -> MI_Brass_Satin fallback),
  confirming the knob/pull parts **are** separate mesh actors with their own label, so the
  radial-brushing MI could be targeted precisely as the task anticipated.
- `Windows_Window-Fixed_...`: both `Clad_-_White` and `Wood_-_Stained` source materials on
  the same actor correctly mapped to the single `MI_WindowFrame_White`.
- `Casework_FX-01` (countertop): slot 0 -> MI_Stone_HonedCream, slot 1 -> MI_Paint_WarmIvory
  (this fixture actor apparently carries a stone top + a painted apron/skirt in its own
  mesh, both handled generically by the by-name rule table without any FX-01-specific rule
  needed).

`remap_materials_wtk.py` is idempotent (a rerun just reassigns the same MIs by the same
name-matching rule) and is now called from `import_wtk.py`'s `run_material_remap()` helper,
inserted after `save_imported_assets()` and before `save_current_level()` at all three
reimport-path call sites (`datasmith_scene_update`, `delete_and_reimport`, `first_import`).

## 6. File paths

- Texture import: `05_Unreal/WTK/Scripts/import_wtk_textures.py`
- Master materials: `05_Unreal/WTK/Scripts/build_wtk_masters.py`
- Material instances: `05_Unreal/WTK/Scripts/build_wtk_material_instances.py`
- UV check: `05_Unreal/WTK/Scripts/uv_check_b30.py`
- Remap: `05_Unreal/WTK/Scripts/remap_materials_wtk.py`
- Import script (now calls remap): `05_Unreal/WTK/Scripts/import_wtk.py`
- This doc: `05_Unreal/WTK/Docs/Materials.md`
- Backup: `tmp/Wtk5c_20260926/backup_Content_WTK/`
- Logs: `tmp/Wtk5c_20260926/*.log`, `*.txt`
