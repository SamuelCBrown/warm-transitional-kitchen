# WtkThree_20260928 pass 2026-09-28 (window backplate rotation root-cause
fix, wall/ceiling colour-cast fix, wall micro-texture fix)

Scope: `05_Unreal/WTK/` and `06_Renders/` only, no git. Full test-by-test
window-backplate diagnosis (a-e), the card-rotation root cause (the card was
facing sideways at +X, not toward the room, since its very first
implementation in the prior pass -- confirmed via
`quaternion.rotate_vector()` on the Plane mesh's local +Z face normal),
confirmation the glass shading-model limitation is real and independent of
the rotation bug (isolated via a masked-glass + magenta-card test), the
wall/ceiling material-level tint fix (G-R improved, ceiling not fully
converged, disclosed), the wall micro-texture fix (RoughnessMin/
NormalStrength/TILE_SIZE_CM, ~1.8x high-frequency-std rise, confirmed subtle
not stucco), the band-check regression guard (0.89, unchanged), and the
honest per-image description are all in `Docs/Lighting.md` Section 21.
Backups: `05_Unreal/WTK/tmp/WtkThree_20260928/{WTK_Main_v2.umap.bak,
backup_scripts,backup_docs}/`. Final renders:
`06_Renders/tests/look_A_v3/{Wide,Angle,Detail}.png`.

---

# WtkRealism_20260928 pass 2026-09-28 (look A realism: brightness, wall
colour, window backplate, plaster texture, countertop scale)

Scope: `05_Unreal/WTK/` and `06_Renders/` only, no git. Full round-by-round
brightness/white-balance iteration table, the window backplate
implementation and its honest not-fully-resolved result, the plaster
texture and countertop tiling root-cause fixes, the SPP decision, band
check, and honest per-image description are all in `Docs/Lighting.md`
Section 20. Backups: `tmp/WtkRealism_20260928/{backup_scripts,backup_content,backup_docs}/`.

Summary:

1. **Brightness/white balance** (5 CAM_Wide rounds, the task's own cap):
   `LOOK_PARAMS["A"]` in `setup_cameras_wtk.py` retuned -- `bias_delta`
   0.9->2.1, `detail_bias_delta` 1.15->2.3, `white_temp` 2750->3300K,
   `white_tint` -0.14->-0.05, Local Exposure highlight/shadow contrast
   relaxed to 1.0/1.0. Result: upper ivory 171.6->194.8 (target 200-215,
   close), ceiling/wall B/R landed in the 0.88-0.90 target band; G-R on
   ceiling/wall did not fully converge to the +/-3 target (disclosed,
   -13.8/-10.2 final) -- White Balance's temp/tint axes move every zone's
   G-R and B/R together, and the wall/ceiling vs window/ivory zones appear
   to need opposite corrections, a possible no-single-global-solution
   constraint (same class of finding as the pre-existing Section 19 note
   for a different axis).
2. **Window backdrop**: added a real CC0 exterior photo backplate card
   (`WTK_WindowBackplate`, Poly Haven `suburban_garden` tonemapped JPG,
   cropped) per the task's own Option B fallback, since the pre-existing
   sky dome route was already exhaustively ruled out in 3+ prior passes.
   Correctly placed/imported/assigned and confirmed live in the level, but
   the window still renders as an essentially flat pale-blue wash -- a live
   test of the most direct remaining lever (glass Opacity 0.10->0.04) showed
   no improvement, confirming this is the same structural DefaultLit+
   Translucent-in-path-tracer limitation (transmits colour, not image
   detail) this project's WtkPTFix5 pass already documented in Lighting.md.
   Reverted glass to a middle point (Opacity=0.08) for legibility. No
   black/void edges confirmed absent (0 near-black window pixels) -- that
   specific requirement is met even though "recognisable trees" is not.
3. **Wall/ceiling plaster texture**: confirmed genuinely invisible via 2x
   crop despite the material already wiring a normal/roughness map;
   `NormalStrength` raised 0.08->0.45 (5.6x) across 2 verified rounds --
   still barely visible at this room's soft, mostly-frontal lighting angle,
   disclosed as a lighting-geometry limitation, not a material wiring bug.
4. **Countertop veining scale**: root-caused the "tiny speckle" complaint to
   `set_uv_mode_tiling.py` unconditionally overriding
   `build_wtk_material_instances.py`'s own `TextureSize_cm`/`UseWorldAligned`
   settings on every mandated post-rebuild re-run -- the real, load-bearing
   fix is `set_uv_mode_tiling.py`'s own `TILE_SIZE_CM` table, raised
   120->260cm for `MI_Stone_HonedCream`. A `TextureSize_cm`-only edit in the
   other script would have been silently ineffective; both files now
   cross-reference this finding.
5. **SPP**: 1024 vs 2048 comparison showed no measurable noise improvement
   (wall patch std dev 3.41 at both) -- kept 1024 for the finals.

Mandatory-lesson compliance: `set_uv_mode_tiling.py` and
`remap_materials_wtk.py` were both re-run after every one of this pass's 3
masters/MI rebuild cycles.

---

# WtkPTFix2 pass 2026-09-27 (re-diagnosis: oak line NOT fixed by the prior
pass's claim; window glass root cause found and partially fixed)

Scope: `05_Unreal/WTK/` and `06_Renders/` only, no git. Full diagnosis
(numeric strip-luminance checks, 2x crops, and every single-variable
diagnostic render actually run) is in `Docs/Lighting.md` Section 15.
Backups: `tmp/WtkPTFix2_20260927/backup_scripts/` and `backup_content/`.
One `UnrealEditor*` process at a time throughout, verified via `tasklist`
before every launch (including after a mid-task interruption, which was
followed by a full audit -- `tmp/WtkPTFix2_20260927/audit_all_diag_state.py`
-- confirming every temporary diagnostic toggle used this pass had been
reverted before the final hero render).

Summary:

1. **Oak line (CAM_Detail): the prior pass's "fixed" claim was false.**
   Re-measured the untouched render first, per this task's own "verify
   before claiming fixed" instruction: |delta|=6.10/7.43 luminance across
   the line (target <3), confirming it is still plainly visible exactly as
   this task described, not "visually gone" as `Lighting.md` Section 14
   claimed. Six single-variable diagnostic re-renders this pass --
   ClearCoat=0, Specular=0, base Roughness forced fully diffuse (1.0),
   direct sun=0, SkyLight=0, Local Exposure neutralised, and SPP doubled to
   2048 -- left the line's magnitude and position completely unchanged
   (never dropping below |delta|~=4.2, never shifting screen position). A
   coarse mesh vertex-position histogram of the live B30 casework mesh
   found no vertex cluster at the line's own derived world height
   (~63-64cm) either. **Root cause NOT found this pass** -- ruled out:
   clear-coat reflection, base-dielectric specular/Fresnel, direct sun/
   shadow, SkyLight ambient, Local Exposure tonemap, denoiser/SPP noise,
   and a raw vertex-position mesh seam. Not ruled out: a vertex-normal-only
   smoothing-group split (GeometryScript Python API limitations prevented
   a clean per-triangle normal check within this pass's time budget) and
   any other geometry crossing the camera's sightline at that height. No
   fix applied; the line remains visible in the final hero render exactly
   as before this pass (final check: |delta|=4.27/5.80).
2. **Window glass: real root cause found, partially fixed, honestly
   disclosed as incomplete.** Diagnosed first, per the task's instructions:
   hiding the fog had no effect; hiding SkyAtmosphere changed the pane's
   colour (proving light reaches it) but not its flatness; forcing the
   backdrop sky dome's emissive to a garish, unmistakable magenta proved
   **the backdrop was never the problem** -- the magenta was completely
   invisible through the glass, meaning the glass itself was blocking
   everything behind it regardless of what's there. Root cause: the
   window's actual assigned material, `MI_Glass_Clear`, still carried its
   own old parameter overrides (near-white tint, Specular=0.5 mirror
   reflectance, IOR=1.5) that silently undid every fix the prior pass made
   to the `M_WTK_Glass` master -- an MI's own explicit overrides always win
   over its parent master's defaults. Fixed `Specular` 0.5->0.0 on both the
   master and the MI (confirmed by testing to be the actual reflection-
   dominates-everything cause, independent of Opacity). Three rounds of MI
   tint/opacity tuning were tested with real renders; none produced visible
   sky/tree/grass detail (every result stayed a flat colour wash, never
   showing image-like variance) -- confirming this is the same disclosed
   `MSM_THIN_TRANSLUCENT`-unavailable-via-Python-API limitation from the
   prior pass, not a fixable parameter-tuning problem. Shipped the least-bad
   compromise (a dim, plausible-looking dark window) rather than either the
   original milky-reflection bug or an even-worse near-black hole (round 1's
   overcorrection, tested and rejected).

Mandatory-lesson compliance: `set_uv_mode_tiling.py` and
`remap_materials_wtk.py` were both re-run after every one of this pass's 4
masters/MI rebuild cycles.

---

# WtkPTFix pass 2026-09-27 (glass, oak seam, SPP check, lower-ivory lift)

Scope: `05_Unreal/WTK/` and `06_Renders/` only, no git. Full root-cause
diagnosis, fixes, SPP/time table, measurements, and honest per-image
descriptions are in `Docs/Lighting.md` Section 14. Backups:
`tmp/WtkPTFix_20260927/`.

Summary:

1. **Window glass** was diagnosed (per the task's own "diagnose first"
   instruction) as `M_WTK_Glass` being `MSM_DEFAULT_LIT` + Translucent with
   a near-white base colour and `TLM_SURFACE_TRANSLUCENCY_VOLUME` lighting
   mode -- DefaultLit translucency shades its own base colour with full
   scene lighting, so a bright base colour read as a lit, opaque-looking
   diffuse panel rather than a see-through pane. `MSM_THIN_TRANSLUCENT` was
   tried first (per the task's suggestion) but reverted after a real test
   render came back near-black: this UE 5.7 build's Python API cannot wire
   the required `ThinTranslucentMaterial` output node
   (`unreal.MaterialExpressionThinTranslucentMaterial` does not exist in
   Python reflection here), so the material silently failed to compile and
   fell back to an opaque default. Shipped fix: `MSM_DEFAULT_LIT` with a
   near-black `BaseColorTint` and `TLM_SURFACE` lighting mode. Result:
   the glass no longer reads as an opaque milky panel (confirmed by a real
   variance increase in direct pixel sampling), but the exterior still does
   not resolve into a clearly recognisable landscape at the room's tuned
   exposure -- a disclosed, still-open HDR-dynamic-range limitation
   (pre-existing per Lighting.md Section 13), not something this pass's
   material fix alone could fully resolve.
2. **Oak seam**: root cause was `Scripts/set_uv_mode_tiling.py`'s
   `TILE_SIZE_CM` table setting the oak MIs' tile size to 50cm, which lands
   a real texture-wrap-point discontinuity mid-door on any door >=76cm
   tall (every B30 door). Raised to 90cm on both `MI_Oak_Rift_Stained` and
   `MI_Oak_Shelf` -- confirmed by a real re-render that the seam is gone,
   continuous grain top to bottom on both doors and the centre stile.
3. **SPP/denoiser**: a controlled 1024-vs-2048-SPP CAM_Wide comparison found
   no visible denoiser smearing at either setting and noise stddev already
   well under target (3.48 at 1024, 3.35 at 2048) -- kept SPP=1024 for the
   finals rather than doubling render cost for an improvement smaller than
   measurement noise. 4K time estimate and the full comparison table are in
   Lighting.md Section 14.3.
4. **Lower ivory**: gentle `local_exposure_shadow_contrast_scale` reduction
   (0.7->0.5, per-camera) lifted the lower cabinets measurably (mean
   86.8->97.6, +12.4%%) without flattening the image or dimming the window,
   but did not fully close the gap to the task's targets -- disclosed as a
   structural under-lighting issue needing a dedicated fix, not further
   Local Exposure tuning.

Mandatory-lesson compliance: after rebuilding `build_wtk_masters.py` and
`build_wtk_material_instances.py` this pass, `set_uv_mode_tiling.py` and
`remap_materials_wtk.py` were both re-run (twice, once per masters/MI
rebuild round) per this doc's own documented lesson.

---

# Window-only daylight pass 2026-09-27 (WtkWindowOnly_20260927)

Scope: `05_Unreal/WTK/` and `06_Renders/` only (per the task's own
constraint — design docs/BOM/Plan.md left untouched, no git). Full detail,
sun-geometry derivation, per-round CAM_Wide measurement table, and the
honest per-image description of all 9 final renders are in
`Docs/Lighting.md` Section 12. Research reference:
`Pause/RESEARCH_2026-09-27_WTK_DAYLIGHT_TIME_OF_DAY_LOOP1_LOOP2_LOOP3.md`.

Summary:

1. **Audit first**: a read-only script (`audit_before_wtk.py`, removed after
   use) dumped every light actor, SkyLight/SkyAtmosphere/fog/PPV settings,
   camera exposure biases, and prop presence to
   `tmp/WtkWindowOnly_20260927/audit_before.txt` before any change. Confirmed
   the level was left on a night preset by the previous (stopped) agent
   (`WTK_Sun` intensity=0, LEDs at 1137/1929 lm, cans at 160 lm) and that
   props were already absent.
2. **Removed** (user decision): `WTK_LED_W18`, `WTK_LED_W30`, `WTK_Can_1..4`,
   `WTK_Fill_Room`, and the old `day_soft`/`day_sun`/`night_led`/
   `night_led_cans` preset set — deleted from the level via a new
   `remove_artificial_lights()` in `setup_lighting_wtk.py`, and no longer
   spawned by any code path (idempotent — safe to rerun, no-op once clean).
   `place_props_wtk.py`'s `PLACE_PROPS=False` confirmed unchanged.
3. **New day-only presets** (`WTK_LIGHT_PRESET=hero|alt_soft|overcast`,
   default `hero`): sun re-geometried (elevation 28°, yaw 245°, 65,000 lux,
   4400K) against the window-on-the-cabinet-wall correction, real SkyLight
   (0.5 intensity, no cheat), Lumen Hit Lighting, PPV + per-camera Local
   Exposure (Highlight Contrast Scale 0.9, Shadow Contrast Scale 0.7, Detail
   Strength 1.35) and White Balance (5200K), and an optional
   window-opening Rect Light portal (`WTK_WindowPortal`, 100 lm, sized to
   the window's ~75×90cm RO).
4. **Exposure iterated 5 rounds** against CAM_Wide only (per the task's own
   cap), then all 3 cameras rendered for all 3 presets (9 images total) via
   the existing 2-process MRQ headless pattern (`render_tests_wtk.py` builds
   the queue, a second `UnrealEditor-Cmd.exe` process renders it) — see the
   "Phase 5d addendum" section below for the exact command, unchanged.
5. **Left on the hero preset** — confirmed via a second audit run
   (`audit_after.txt`): no LED/Can/Fill actors, no props, `WTK_Sun`
   intensity=65000, `WTK_SkyLight` intensity=0.5, `WTK_WindowPortal` present,
   `WTK_PPV` bias=3.4, `CAM_Wide`/`CAM_Angle` bias=4.8, `CAM_Detail`
   bias=3.4.
6. `import_wtk.py` was **not** modified this pass, so its import-check
   script was not re-run (per the task's own conditional).

Backups: `tmp/WtkWindowOnly_20260927/backup_before/` (the `.umap` plus a
copy of every edited script before this pass). No Unreal process was ever
left running between steps (checked via `tasklist` before every launch).

---

# Light-leak fix 2026-09-27 REWRITE — two-sided shell shadows + one roof slab

## Root cause (superseding the "ceiling/wall gap" theory below)

The earlier "4-wall ceiling-inset gap" theory (kept below for history) was
wrong: the side walls are solid geometry, not flat planes, so a dimensional
gap in a solid wall's own thickness was never a coherent explanation for
light passing through the wall material itself. Worse, the 4 visible
`WTK_Blocker_*` boxes it produced showed up as ugly dark bands at the
wall/ceiling junction in `CAM_Wide`, and the leak persisted regardless.

Live inspection this pass (`tmp/WtkRoof_20260927/check_shell_twosided.txt`)
found the actual defect: every shell `StaticMeshComponent` in the level (all
4 `Walls_*`, `Floors_Floor_Generic_-_12_`, `Ceilings_Basic_Ceiling_Generic`)
had `cast_shadow_as_two_sided=False`. The ceiling
(`Ceilings_Basic_Ceiling_Generic`, z=243.84) is a genuinely thin/single-sided
mesh (already documented in Section 9.1 below). `WTK_Sun` has pitch=-15°, so
sunlight arrives from ABOVE and its hardware-RT shadow rays strike the
ceiling from above; on a single-sided mesh with
`cast_shadow_as_two_sided=False`, a shadow ray that hits the mesh's back face
(relative to the ray direction) is not registered as an occluding hit at
all — hardware RT effectively treats the ceiling as transparent to sunlight
arriving from above, letting it pass straight through and travel on to graze
the top of the +X/right wall (matching the `CAM_Wide` wedge geometry) and
reach the counter (`CAM_Angle` streak) — i.e. the sun shines THROUGH the
ceiling, not through any gap.

## Fix

1. **`Scripts/fix_light_leak_wtk.py`** now sets
   `cast_shadow_as_two_sided=True` on every `StaticMeshComponent` belonging
   to an actor labelled `Walls_*`, `Floors_*`, or `Ceilings_*` — this is the
   actual fix, making every shell mesh occlude shadow rays from either side
   regardless of authored front-face winding.
2. **Belt-and-braces**: the old 4 wall-top `WTK_Blocker_*` boxes are
   destroyed and replaced with ONE `WTK_Blocker_Roof` — a single visible,
   shadow-casting `/Engine/BasicShapes/Cube` spanning the whole building
   footprint (all 4 walls' outer extents, confirmed live via
   `tmp/WtkRoof_20260927/footprint.txt`: x:[-350.52,45.72] y:[-441.96,15.24],
   +30cm margin on every side), 20cm thick, with its bottom face at
   `ceiling_z + 1.0cm` (244.84) — entirely above the ceiling plane, so it
   cannot be seen from inside from any camera angle. As before (established
   hardware-RT lesson from the earlier version of this fix): the slab must
   be `visible=True`, `hidden_in_game=False`, `cast_shadow=True`, NOT
   hidden+`cast_hidden_shadow`, since Lumen/hardware RT excludes hidden
   primitives from the ray-tracing scene entirely.

Idempotent: destroys any existing `WTK_Blocker_*`-labelled actor (a widened
match, so a stale run of the OLD 4-wall-blocker version is cleaned up too)
via a snapshot-then-destroy pattern, then spawns exactly one new
`WTK_Blocker_Roof`. `import_wtk.py`'s preserve list already covers the
`WTK_Blocker_` prefix generically (added in the earlier version of this
fix), so `WTK_Blocker_Roof` survives a `delete_and_reimport` pass with no
further change needed.

Run any time after `setup_lighting_wtk.py` (order: import → material remap
→ ceiling flip → bevel → Nanite → save → **lighting setup → light-leak fix
(`fix_light_leak_wtk.py`) → cameras/props/render**).

Verified this pass: `tmp/WtkRoof_20260927/fix_report.txt` — 6 shell
components flipped to `cast_shadow_as_two_sided=True`, 4 old blockers
destroyed, 1 `WTK_Blocker_Roof` spawned (actor count 58→55, net -3 since 4
old blockers were removed and only 1 new one added), `.umap` saved
(`save_current_level=True`, `save_map=True`). See the render section below
for the honest per-image pixel description of the result.

---

# Light-leak fix 2026-09-27 (SUPERSEDED) — ceiling/wall gap blockers (all 4 walls)

**This section's diagnosis and fix have been superseded by the rewrite
above** (single-sided-shell-shadow root cause + one roof slab). Kept for
history only.

## Root cause

`WTK_Test_CAM_Wide_0000.png` showed a hard bright diagonal wedge of light at
the upper right near the ceiling plus a small bright white quad low on the
right wall (~px 1820,920); `WTK_Test_CAM_Angle_0000.png` showed a sharp sun
streak crossing the counter. A read-only diagnostic
(`tmp/WtkLeak_20260927/diag_light_leak.py`) dumped every actor's bounds and
found the ceiling mesh (`Ceilings_Basic_Ceiling_Generic`) is inset to
exactly the INNER face of **all 4 walls** (the 2 side walls plus the front/
window wall and the back wall), each wall 15.24cm thick — not just the 2
side walls as first assumed. Neither wall's own thickness is covered by the
ceiling above it, so a 15.24cm-wide slot runs the full length of the top of
every wall, straight through to outside. `WTK_Sun` (pitch=-15, yaw=-160,
forward vector ≈(-0.908,-0.330,-0.259)) shines directly into the right
wall's slot, producing the CAM_Wide wedge and quad. Full numbers:
`tmp/WtkLeak_20260927/report.txt`.

The CAM_Angle counter streak turned out NOT to be part of this leak: a
sun-ray/window-rectangle intersection check showed window-sourced sunlight
geometrically cannot reach the part of the counter where the streak
appears, and it persisted pixel-for-pixel unchanged across every gap-sealing
revision. A reflection calculation off the countertop's horizontal plane
using the sun's forward vector gives a physically valid, upward-traveling
reflected ray — this streak is assessed as most likely a specular highlight
of the sun on the glossy countertop material, not a leak (not independently
confirmed by disabling the material's specular response; flagged as the
recommended next check for certainty).

## Fix (superseded)

Idempotent step: `Scripts/fix_light_leak_wtk.py` — destroyed any existing
`WTK_Blocker_*` actors and respawned four thin `/Engine/BasicShapes/Cube`
boxes, one per wall. This did not resolve the leak and produced visible dark
bands at the wall/ceiling junction once the boxes were made visible; see the
rewrite section above for the actual fix.

---

# Re-import hardening 2026-09-27

## Context: what the last (corrupted) re-import got wrong

Per the coordinator's report (`tmp/WtkReimp2_20260927/{import_run.log,inspect_hardware.txt,check_b30_tag.log,before.txt}`),
the last re-import had 3 problems, all fixed in `05_Unreal/WTK/Scripts/import_wtk.py`
this pass (code only -- no re-import was run against the fixed Datasmith export,
which is coming separately from the Revit side):

**(a) ~20 exploded-B30 DirectShape actors leaked into the export**, coming in as
`Generic_Models_<PartName>` actors (`Side_Left/Right`, `Bottom`, `Back`,
`Stretcher_Back/Front`, `ToeKick`, `Shelf_1`, `Front0/1_door_{StileL,StileR,
RailTop,RailBottom,Panel}`, `Hardware0/1_Knob` -- 20 actors, confirmed against
`inspect_hardware.txt`). Revit-side, being fixed separately; Unreal-side, this
pass adds an **import guard** (Task 2) that flags every one of them.

**(b) the bevel pass skipped the re-imported casework meshes** because the
plain `WTK_Beveled_v1` metadata tag survived the in-place Datasmith scene
update even though the mesh geometry changed underneath it (B30 came back
with its pre-bevel triangle count, still carrying the old tag from the
PREVIOUS import's already-beveled mesh). Fixed with a fingerprint scheme
(Task 1).

**(c) the import check's floor/counter/ceiling detection got fooled by the
stray actors**, with the counter and ceiling measurements both off by
exactly 25.40cm (10in). Fixed with hardened category-prefix selectors plus a
room-footprint filter (Task 3).

## Task 1 — bevel idempotency: fingerprint replaces the plain tag

`run_bevel_pass()` in `import_wtk.py` previously trusted a single boolean
metadata tag, `WTK_Beveled_v1="1"`, as proof a mesh had already been
beveled. That tag is asset-path-scoped, not geometry-scoped: an in-place
Datasmith scene-update reimport can replace a StaticMesh asset's underlying
geometry (a real Revit edit) while the SAME package/asset keeps whatever
metadata tags it had before, so the tag alone can't distinguish "this exact
mesh was already beveled" from "some mesh that used to live at this asset
path was beveled once."

Fixed by replacing the boolean with two fingerprint strings, computed by the
new `_mesh_fingerprint()` helper (triangle count + rounded (0.01cm) bounding
box + an md5 hash of a stride-7-sampled subset of vertex positions, formatted
as `"tris=<n>|bounds=<x0,y0,z0,x1,y1,z1>|vhash=<hex>"`):

- `WTK_Bevel_Fingerprint_Pre` — the source mesh's fingerprint, computed
  immediately before the bevel geometry is added.
- `WTK_Bevel_Fingerprint_Post` — the same mesh's fingerprint AFTER the bevel,
  computed once the beveled geometry is written back. This is the value the
  NEXT run's idempotency check compares against.

On each run: compute the current mesh's fingerprint (as if it were the
about-to-be-beveled source right now) and compare to the stored
`WTK_Bevel_Fingerprint_Post` tag. Equal → same already-beveled mesh, skip
(`already_done`). Different, or missing (including a mesh that only carries
the legacy `WTK_Beveled_v1` tag with no fingerprint recorded yet — logged
explicitly as "carries legacy tag with no verifiable fingerprint -- treating
as fresh") → treat as fresh: bevel it, then store both fingerprints. The old
`WTK_Beveled_v1` tag is still written alongside (harmless, for any external
tooling that reads it) but is never trusted on read anymore.

**Verified by the dry test below**: the current corrupted level's B30 mesh
(584 triangles this session — geometry has apparently churned again since
`check_b30_tag.log`'s 256-tri snapshot, but the principle is unaffected)
still carries the legacy `WTK_Beveled_v1="1"` tag and no
`WTK_Bevel_Fingerprint_Post` tag at all. The fingerprint check correctly
refuses to trust the legacy tag and classifies the mesh as **FRESH (would
bevel)** — exactly the desired behavior for a mesh whose geometry was
replaced by a reimport.

### Hardware-cylinder exclusion from the bevel edge selection

Small hardware parts (knobs, pulls) are highly-tessellated cylinders; running
the existing sharp-edge + boundary-edge selection over them bevels every
tessellation facet edge, producing visible faceting artifacts rather than a
clean bevel, and isn't visually meaningful on a rounded part anyway. Rather
than excluding by mesh name (not every hardware mesh is reliably named
"Knob"/"Hardware"), `run_bevel_pass()` now ANDs (intersects) the existing
sharp+boundary edge selection against two independent, purely-geometric
filters:

1. **Edge-length filter** (`BEVEL_MIN_EDGE_LENGTH_CM = 1.0`) — via
   `GeometryScript_MeshSelection.select_mesh_edges_by_length()`, keeping only
   edges longer than ~1cm. A cylinder's tessellation chords are short; a box
   part's straight edges survive.
2. **Adjacent-face-area filter** (`BEVEL_MIN_ADJACENT_FACE_AREA_CM2 = 0.5`) —
   via `select_mesh_edges_by_adjacent_face_area()`, keeping only edges with
   at least one adjacent face above ~0.5cm². A cylinder's individual side
   faces are tiny even if one particular chord happens to be long enough to
   survive filter 1 on a larger hardware part.

Both filters are wrapped in `try/except` and skipped gracefully (falling
back to whichever filter IS available, or the un-filtered selection) if
either GeometryScript function isn't present in a given UE 5.7 Python binding
revision — not independently confirmed against a live hardware mesh this
pass (no re-import was run), flagged as a follow-up to verify with real
hardware geometry the next time a full pipeline run happens.

## Task 2 — import guard: unexpected-actor detection

New `is_unexpected_actor_label()` + `run_import_guard()` in `import_wtk.py`,
called from `main()` right after gathering `all_actors`. Flags (does **not**
delete) any actor whose label:

- starts with `Generic_Models_` and does NOT contain `FX-` (the known WTK
  fixtures, FX-01..FX-07, can legitimately appear under the Generic Models
  category alongside Casework/Plumbing/Furniture/Lighting — an FX- match is
  always allowed regardless of category prefix, checked first via
  `EXPECTED_FX_PATTERN = re.compile(r"FX-0[1-7]\b")`), OR
- matches one of the known exploded-B30-part name patterns, regardless of
  category prefix: `Hardware\d+_`, `Front\d+_door_`, `Side_(Left|Right)`,
  `Stretcher_`, `ToeKick`, `Shelf_\d`, `^Generic_Models_(Bottom|Back)$`.

Each match is logged as `UNEXPECTED_ACTOR: <label>`. `run_import_guard()`
accepts an `allowlist_labels` set (empty, `UNEXPECTED_ACTOR_ALLOWLIST`, by
default); an allow-listed label is logged but does not fail the guard.
`main()`'s final report now has a "--- Import guard (unexpected actors) ---"
section listing every flagged label and count, and the `FINAL status` line
is `FAIL` (naming the offending actors) if the guard found any
non-allow-listed unexpected actor, **even if checks (a)-(d) all separately
PASS** — matching the task spec ("fail the import check ... unless an
explicit allow-list covers them").

**Verified by the dry test below**: run against the current corrupted level,
the guard correctly flagged exactly the 20 stray actors named in the task
brief's item (a) and none of the legitimate actors (including
`Generic_Models_FX-06`, which is NOT flagged, correctly, since it matches
`EXPECTED_FX_PATTERN`).

## Task 3 — hardened import-check selectors

Replaced the loose substring matches with exact category-prefix checks,
each as its own named predicate (`is_floor_label`, `is_hardened_counter_
label`, `is_hardened_ceiling_label`, `is_wall_label`):

- **Floor** = label starts with `"Floors_"` (was: `"floor" in label.lower()`
  anywhere in the string — the real label, confirmed in `import_run.log`'s
  `LogStaticMesh: Display: Building static mesh Floors_Floor_Generic_-_12_`
  line, already starts with the exact prefix, so the substring match wasn't
  wrong on the real floor actor, but it also couldn't rule out a coincidental
  stray-actor name match).
- **Counter** = label contains `"FX-01"` (unchanged — this selector wasn't
  independently at fault, but now benefits from the room-footprint filter
  below the same as the others).
- **Ceiling** = label starts with `"Ceilings_"` (was: `"ceiling" in label.
  lower()` anywhere — the real label is `Ceilings_Basic_Ceiling_Generic`).
- **Walls** = label starts with `"Walls_"` (was: `"wall" in label.lower()`
  anywhere).

Additionally, every one of the four measurements now also requires the
actor's XY bounds to overlap the room's real footprint
(`ROOM_FOOTPRINT_X_MIN..MAX = -340.0..35.0`, `ROOM_FOOTPRINT_Y_MIN..MAX =
-430.0..5.0`, via the new `is_in_room_footprint()`) — independent of the
label check, so a stray actor sitting outside the room (most of the 20 stray
Generic_Models_* actors sit at the Datasmith assembly origin (0,0,0), per
`inspect_hardware.txt`'s `loc=<...x:0,y:0,z:0...>` dump, well outside the
footprint) cannot contribute to any measurement even in the hypothetical
case its label happened to also pass one of the four selectors above. The
existing zero-extent (`is_degenerate_bounds`) filter is unchanged and still
applied first.

`main()`'s per-actor loop now also records `floor_actors_used`,
`counter_actors_used`, `ceiling_actors_used`, and `wall_actors_used` (label
lists), each printed into `WTK_Import_Check.txt` right under its
corresponding check line, so a future corrupted import is immediately
traceable to the exact actor(s) that fed each measurement without another
ad hoc inspection script.

## Task 4 — prop-scale tweak, recorded for the next real run (NOT executed)

Per the task's explicit "don't run it now" instruction, `place_props_wtk.py`
was edited but not invoked this pass. Added `compute_uniform_scale_for_
target_length()`: loads the prop's first StaticMesh, reads its native
local-space bounding box (`StaticMesh.get_bounding_box()`, same bounds API
`_combined_local_bounds()` already uses for the `rest_on_z` correction), and
returns a single uniform `unreal.Vector(f, f, f)` scale factor (so the prop
is resized, not stretched/distorted) such that the mesh's long horizontal
axis comes out to a target length in cm.

- `WTK_Prop_CuttingBoard`: `board_scale = compute_uniform_scale_for_target_
  length(board_mesh, target_length_cm=42.0, default_scale=0.55)` — replaces
  the old flat `0.55` magic-number scale so the board's long axis is ~42cm.
- `WTK_Prop_Bowl`: `bowl_scale = compute_uniform_scale_for_target_length(
  bowl_mesh, target_length_cm=22.0, default_scale=0.35)` — replaces the old
  flat `0.35` scale so the bowl's diameter is ~22cm.

Both keep the existing `rest_on_z` correction (a uniform scale doesn't change
which local axis that correction targets, so no change needed there), the
existing `actor.modify()`/`component.modify()` calls before every mutation
(the prop-fix-pass-round-2 persistence fix, already in place and unchanged),
and the existing robust three-call save
(`save_current_level()`+`save_map()`+`save_dirty_packages()`). This function
and its two call sites are live code, ready to run as-is the next time
`place_props_wtk.py` is invoked (via `-ExecutePythonScript`, per its own
docstring) against a real, non-corrupted import — not exercised this pass.

## Task 5 — dry test results (2026-09-27)

Ran `tmp/WtkGuard_20260927/dry_test.py`, a read-only script that loads
`import_wtk.py`'s function/constant definitions (by exec'ing its source with
the trailing `main()` call stripped out, so `ensure_map_and_import()` never
runs and nothing is imported/saved) and exercises only `run_import_guard()`
and `_mesh_fingerprint()` against the CURRENT (corrupted) level's live
state, via a single `UnrealEditor-Cmd.exe -run=pythonscript` process (backup
of `Content/WTK` taken first to `tmp/WtkGuard_20260927/backup_Content_WTK/`;
confirmed no other Unreal process was running before or after via
`tasklist`). Full output: `tmp/WtkGuard_20260927/dryrun.txt`.

**Import guard**: flagged all 20 stray actors, exactly the set named in the
task brief and confirmed against `inspect_hardware.txt` (`Generic_Models_
{Side_Left,Side_Right,Bottom,Back,Stretcher_Back,Stretcher_Front,ToeKick,
Shelf_1,Front0_door_{StileL,StileR,RailTop,RailBottom,Panel},Front1_door_{
StileL,StileR,RailTop,RailBottom,Panel},Hardware0_Knob,Hardware1_Knob}`),
`guard_passed=False`. No legitimate actor (including `Generic_Models_FX-06`)
was flagged.

**Bevel fingerprint**: the current B30 mesh (584 triangles this session —
note the source geometry has apparently changed again since `check_b30_tag.
log`'s 256-tri snapshot; unrelated to and doesn't affect this test) carries
the legacy tag `WTK_Beveled_v1="1"` and no `WTK_Bevel_Fingerprint_Post` tag.
Classification: **FRESH (would bevel)** — the fingerprint check correctly
refuses to trust the unverifiable legacy tag and would re-bevel the mesh on
a real run, which is exactly the target behavior for the reported bug (a
reimported mesh whose geometry changed must not be skipped just because an
old tag survived).

**Nothing was saved**: `WTK_Main.umap`'s on-disk `LastWriteTime` was
`2026-09-26T23:44:13.8185391-07:00` both immediately before launching the
dry-test process and immediately after it exited (confirmed independently
via `Get-Item ... .LastWriteTime` in PowerShell, and via `os.path.getmtime()`
logged inside the dry test itself, both matching to the microsecond) — the
dry test's own script contains no `save_current_level()`, `save_map()`,
`save_dirty_packages()`, `destroy_actor()`, or `set_metadata_tag()` calls
anywhere, by construction. Process exited cleanly (exit code 0) and no
`UnrealEditor` process remained running afterward.

## Files changed/added this pass

- `05_Unreal/WTK/Scripts/import_wtk.py` — `_mesh_fingerprint()`,
  `BEVEL_FP_PRE_TAG`/`BEVEL_FP_POST_TAG` fingerprint scheme replacing the
  plain `WTK_Beveled_v1` trust (Task 1); hardware-cylinder edge-selection
  exclusion via length/area filters (Task 1); `is_unexpected_actor_label()`
  + `run_import_guard()` (Task 2), wired into `main()` with a `FINAL status`
  line; `is_floor_label`/`is_hardened_counter_label`/`is_hardened_ceiling_
  label`/`is_wall_label` + `is_in_room_footprint()` (Task 3), with
  `main()` now logging which actor(s) fed each measurement.
- `05_Unreal/WTK/Scripts/place_props_wtk.py` —
  `compute_uniform_scale_for_target_length()` + the cutting board/bowl scale
  call sites (Task 4, recorded, not executed this pass).
- `tmp/WtkGuard_20260927/dry_test.py` — new, read-only dry-test script
  (Task 5).
- `tmp/WtkGuard_20260927/dryrun.txt`, `editor_run.log` — dry-test output.
- `tmp/WtkGuard_20260927/backup_Content_WTK/` — pre-test backup of
  `05_Unreal/WTK/Content/WTK/`.

---

# WTK prop-fix pass, round 2 (2026-09-26) — level-save persistence bug, audit and fix

## What went wrong

The coordinator found that the round-1 prop-fix pass's re-renders showed the
OLD prop positions (plant still floating, board still at the sink) despite
`place_props_wtk.py`'s own log clearly showing the new transforms being
applied and `place_props()` calling `save_current_level()` at the end.
Direct evidence: `05_Unreal/WTK/Content/WTK/Maps/WTK_Main.umap`'s own on-disk
`LastWriteTime` was `9/26/2026 10:58:46 PM` -- from BEFORE both round-1
placement runs (their logs are timestamped ~23:12 and ~23:14) -- proving
`save_current_level()` silently no-op'd.

## Root cause

`spawn_or_update_prop()`'s "update an existing actor" path called
`actor.set_actor_location()` / `set_actor_rotation()` /
`static_mesh_component.set_static_mesh()` directly, with no
`actor.modify()` / `component.modify()` call first. In this UE 5.7 Python
binding, these setters do not reliably mark the owning package dirty on
their own (this is the same class of bug already independently documented
in `Lighting.md`'s Section 9.4 LED-rotation persistence bug and Section 5b's
camera-binding persistence bug -- both fixed there by an explicit
`.modify()`/`.Modify()` call before the mutation). `save_current_level()`
(and, it turns out, needs to be paired with an explicit `save_map()` call
too) only actually writes packages that are flagged dirty -- an actor whose
properties changed in memory but whose package was never marked dirty is
silently skipped.

## Fix, and live verification

`place_props_wtk.py`: `actor.modify()` / `component.modify()` added
immediately before every property mutation on an existing actor/component
(both the parent StaticMeshActor and the plant's `_Part1/2/3` child actors).
The save call itself was also hardened: `save_current_level()` +
`EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)` +
`save_dirty_packages(True, True)`, all three called, with `save_map`'s own
boolean return logged.

**Live-verified this pass** (the only script actually re-run and checked):
before the fix, `place_props()`'s two round-1 runs left the `.umap`
timestamp unchanged. After the fix, a fresh run advanced the `.umap`'s
`LastWriteTime` from `10:58:46 PM` to `11:22:04 PM`, `save_map()` returned
`True`, and the subsequent re-render (`06_Renders/tests/WTK_Test_CAM_
{Wide,Angle,Detail}_0000.png`, generated at 11:23 PM) visibly shows the
corrected prop positions (see `Docs/Props.md`'s own updated "honest
description" section for exactly what the images show).

## Audit of the other level-editing scripts (per the coordinator's request)

The same "mutate an existing actor/component without calling `.modify()`
first, then save via `save_current_level()` alone" pattern was found, by
code inspection, in:

- **`setup_lighting_wtk.py`**: `spawn_or_get()`'s existing-actor path, and
  every `setup_*` function's `comp.set_editor_property(...)` block (sun,
  sky light, height fog, ground plane material, both LED rect lights, the
  fill light, the PPV). Fixed defensively: `.modify()` added at each site;
  `main()`'s final save hardened with `save_map()` + `save_dirty_packages()`.
- **`setup_cameras_wtk.py`**: `spawn_or_get_camera()`'s existing-actor path,
  and `configure_camera()`'s `comp` (CineCameraComponent) mutations. Fixed
  the same way. (This script's Level Sequence camera-binding save already
  used the correct `save_loaded_asset(seq)`-on-the-loaded-object pattern,
  fixed back in Phase 5d for the camera-binding persistence bug -- that part
  was already correct and is unchanged.)
- **`remap_materials_wtk.py`**: `comp.set_material(slot_index, mi_asset)`
  had the same risk (no `comp.modify()` first). Fixed the same way; its
  final `save_current_level()` call hardened with `save_map()` +
  `save_dirty_packages()`.
- **`import_wtk.py`**: all three `ensure_map_and_import()` return paths
  (`datasmith_scene_update`, `delete_and_reimport`, `first_import`) end with
  a bare `save_current_level()`. Hardened the same way at all three sites.
  (The actor-delete loop in the `delete_and_reimport` fallback path uses
  `destroy_actor()`, a structural change, not a property mutation -- a
  different and lower-risk operation than the ones fixed above; not
  touched.)

**Honest scope of verification**: only `place_props_wtk.py`'s bug was
directly reproduced, fixed, and confirmed via a live before/after `.umap`
timestamp check and a real re-render this pass. The fixes in
`setup_lighting_wtk.py`, `setup_cameras_wtk.py`, `remap_materials_wtk.py`,
and `import_wtk.py` are defensive -- applied because the same at-risk code
pattern was found by inspection, and because the `.umap`'s own on-disk
`LastWriteTime` (10:58:46 PM) lines up with `setup_cameras_wtk.py`'s last
edit (10:58:11 PM, per `Get-ChildItem`'s `LastWriteTime` on the Scripts
folder), meaning that script's own save is the last one known to have
actually reached disk -- but this does NOT by itself confirm or deny
whether every individual property `setup_lighting_wtk.py` and
`setup_cameras_wtk.py` set in earlier rounds (e.g. the Phase 5d-7 white-
balance/fill-light retune, or the Phase 5e per-camera exposure values)
actually persisted through their own respective runs, since none of those
scripts' own save call was independently re-verified by a timestamp check
before this pass. **Recommended follow-up**: the next time
`setup_lighting_wtk.py` or `setup_cameras_wtk.py` is rerun for any reason,
check the `.umap`'s `LastWriteTime` before and after, the same way this
pass did for `place_props_wtk.py`, to close out that open question.

---

# WTK Post-Import Pipeline — Phase 5c-2

Date: 2026-09-26. This documents the ordered steps `import_wtk.py` runs after every
Datasmith import/reimport, and why the order is what it is. No git, no Revit/`Pause/`
files touched. All work is under `05_Unreal/WTK/` and `tmp/Wtk5c2_20260926/`.

## Ordered steps (all three `ensure_map_and_import()` call sites — `datasmith_scene_update`,
`delete_and_reimport`, `first_import` — run this same sequence)

1. **Datasmith import/reimport** (`scene.import_scene(IMPORT_DEST)`), then
   `save_imported_assets()` — writes the imported StaticMesh/Material packages to disk
   (needed before any of the following steps can act on saved assets).
2. **`run_material_remap()`** — reassigns every StaticMeshComponent slot from its raw
   Datasmith source material name (or, on a no-op reimport where the slot already
   carries a WTK Material Instance name, recognizes that as already-correct — see
   Phase 5c-2 fix below) to the matching `/Game/WTK/Materials/MI_*` instance, by an
   actor-label-regex + source-material-name rule table.
3. **`run_ceiling_flip_pass()`** (Phase 5d round 6) — flips normals (via
   `GeometryScript_Normals.flip_normals()`) on every mesh whose name contains
   "Ceiling". `Ceilings_Basic_Ceiling_Generic` is a genuinely zero-thickness,
   single-sided plane whose face normal points up, making it invisible from
   inside the room (open sky was visible above the walls in every render
   until this was found and fixed) — see `Docs/Lighting.md` Section 9.1 for
   the full root-cause writeup.
4. **`run_bevel_pass()`** (Phase 5c-2 Task 4) — applies a small (0.159cm / 1/16in) edge
   bevel to hard edges on casework/counter/shelf/backsplash meshes.
5. **`run_nanite_pass()`** (Phase 5c-2 Task 3) — enables Nanite on eligible StaticMeshes.
6. **`save_current_level()`**.

## Why bevel runs BEFORE Nanite

Nanite builds its cluster/LOD representation from the mesh's geometry at the point the
asset is saved with `nanite_settings.enabled=True`. Since the bevel pass changes the
actual LOD0 triangle data (new small bevel faces added around every hard/boundary edge),
running the bevel first means Nanite's build sees the final, beveled geometry from the
start. Running Nanite first and bevel second would still work correctness-wise (both
steps re-save the asset, and there's no separate "trigger Nanite rebuild" call needed
here since Nanite's data is derived at save time in this pipeline), but bevel-then-Nanite
is the safer, easier-to-reason-about order and avoids any risk of Nanite's build cache
going stale relative to a geometry change made after Nanite was already turned on.

## Why remap runs BEFORE bevel/Nanite

Remap only touches material slot assignments on StaticMeshComponents (Actor/level data);
bevel and Nanite operate on the underlying StaticMesh assets. There's no ordering
dependency between remap and {bevel, Nanite} in principle, but remap was already the
established first post-import step from Phase 5c, and inserting the two new steps after
it (rather than interleaving) keeps each step's log output and failure surface easy to
read top-to-bottom in the console output.

## Idempotency

Every step in the pipeline is safe to rerun:

- **Datasmith reimport**: uses the `DatasmithSceneElement` reimport/update path when
  available, else falls back to delete+recreate of the previous import's actors. If the
  source `.udatasmith` file is unchanged, Datasmith's own diffing means the underlying
  StaticMesh packages are frequently NOT rewritten from scratch on a no-op reimport —
  confirmed empirically in Phase 5c-2 (a bevel-marker metadata tag set on `Casework_WTK_B30_B30`
  in one run was still present on the next `delete_and_reimport` run against the same,
  unchanged `.udatasmith` source).
- **Remap**: pure by-name reassignment; a rerun just reassigns the same MIs (Phase 5c-2
  fix: `find_mi_target()` in `remap_materials_wtk.py` now also recognizes a slot whose
  current material IS already one of the WTK MIs as "correctly assigned" rather than
  falling through to UNMAPPED — needed because a reimport that doesn't rewrite the
  StaticMesh asset also doesn't revert its material slots to the raw Datasmith source
  names).
- **Bevel**: guarded by the `WTK_Beveled_v1` EditorAssetLibrary metadata tag, set on each
  mesh only after a successful bevel (validated: material slots unchanged, triangle count
  actually grew). A mesh already carrying the tag is skipped (`already_done` in the
  pass's return tuple/log line). If the Datasmith source geometry actually changes (a
  real Revit edit, not just a no-op reimport), the mesh's underlying package would be
  rewritten and the tag would not carry over, so the next reimport re-bevels the new
  geometry — correct behavior, not a bug.
- **Nanite**: guarded by checking `nanite_settings.enabled` before setting it; a mesh
  already enabled is skipped (`already_enabled` in the pass's return tuple/log line).
- **Ceiling flip** (Phase 5d round 6): guarded by the `WTK_CeilingFlipped_v1`
  EditorAssetLibrary metadata tag, same pattern as the bevel marker. Validated
  standalone before wiring into the pipeline
  (`tmp/Wtk5d_20260926/test_flip_ceiling.py`): 2 triangles before/after (a
  simple quad, unchanged — `flip_normals` only touches normals/winding, not
  topology), material slots unchanged (`['RNT_Material']`). If the source
  geometry actually changes on a real Revit edit, the tag won't carry over
  and the next reimport correctly re-flips the new geometry.

## Verification (Phase 5c-2, full pipeline rerun, 2026-09-26)

Ran `import_wtk.py` end-to-end (`delete_and_reimport` path) three times in this session
(once before the bevel/Nanite code existed to establish baseline, then twice after
adding Task 3/Task 4). Final run's `WTK_Import_Check.txt`:

```
(a) Base cabinet run length (DB18/SB36/B30/DB24/B12, excl. FX-): PASS (expected 304.80 cm, got 304.80 cm, diff 0.00 cm)
(b) Countertop (FX-01) top Z above floor: PASS (expected 91.44 cm, got 91.44 cm, diff 0.00 cm)
(c) Ceiling bottom Z above floor: PASS (expected 243.84 cm, got 243.84 cm, diff 0.00 cm)
(d) Room interior dims (wall envelope - 2x15.24cm thickness): 365.76 cm x 426.72 cm (expect ~365.76 x 426.72 cm)

Total actors: 48
Static mesh assets: 41
Distinct materials imported: 12
```

Remap: **52/52 slots assigned, 0 unmapped**. Bevel: 10 target meshes beveled on the
fresh-geometry run (`Furniture_FX-05` 24→88 tris [3.67x], `Casework_WTK_W30_W30`
216→641 [2.97x], `Casework_WTK_W18_W18` 144→426 [2.96x], `Casework_WTK_SB36_SB36`
216→655 [3.03x], `Casework_WTK_DB24_DB24` 132→437 [3.31x], `Casework_WTK_DB18_DB18`
156→523 [3.35x], `Casework_WTK_B30_B30` 240→745 [3.10x], `Casework_WTK_B12_B12`
108→349 [3.23x], `Casework_FX-01` 64→128 [2.00x], `Casework_FX-04` 48→117 [2.44x]),
0 failed; a subsequent rerun against unchanged source geometry showed `already_done=10,
beveled=0` (idempotency confirmed). Nanite: 39 meshes enabled, 2 skipped (glass/window
name match), 0 failed; a rerun showed `already_enabled=39, enabled=0`.

**Bounds check on the single-mesh validation run (B30, before batching)**: 240→745
triangles (3.10x), bounds delta exactly `0.00000cm` on all six min/max components
(tolerance was 0.01cm), material slots unchanged
(`['Paint_WarmIvory', 'Oak_StainedWarmBrown', 'Metal_SatinBrass']` before and after).

## Files

- Main pipeline script (all steps wired in): `05_Unreal/WTK/Scripts/import_wtk.py`
  (`run_material_remap()`, `run_bevel_pass()`, `run_nanite_pass()`)
- Standalone single-mesh bevel validation script (kept for reference/re-validation):
  `05_Unreal/WTK/Scripts/bevel_test_b30.py`
- UV mode + tiling setter (Task 1, one-time, not part of the reimport loop since MI
  parameter values persist on the MI asset once set):
  `05_Unreal/WTK/Scripts/set_uv_mode_tiling.py`
- UV extent verification scripts: `05_Unreal/WTK/Scripts/uv_check_extended.py`,
  `05_Unreal/WTK/Scripts/uv_orientation_check.py`
- Master materials (Task 2's ClearCoat wiring lives here):
  `05_Unreal/WTK/Scripts/build_wtk_masters.py`
- Logs: `tmp/Wtk5c2_20260926/*.txt`, `*.log`

---

# Phase 5d addendum (2026-09-26) — MRQ headless test-render command

See `Docs/Lighting.md` for the full lighting/exposure/camera setup this
addendum's render command targets.

Build the MRQ jobs + manifest first (in-editor headless Python):

```
UnrealEditor-Cmd.exe "C:\Users\Sam\Documents\Chess\05_Unreal\WTK\WTK.uproject" ^
  -run=pythonscript -script="C:\Users\Sam\Documents\Chess\05_Unreal\WTK\Scripts\render_tests_wtk.py" ^
  -unattended -nop4 -nosplash -stdout
```

This saves `Saved/MovieRenderPipeline/QueueManifest.utxt` and prints the
render command. Then render headless, as a **second, separate**
`UnrealEditor-Cmd.exe` process (per the research doc's
`EpicGames/tk-unreal`-sourced pattern):

```
"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" ^
  "C:\Users\Sam\Documents\Chess\05_Unreal\WTK\WTK.uproject" ^
  -ResX=1920 -ResY=1080 ^
  MoviePipelineEntryMap?game=/Script/MovieRenderPipelineCore.MoviePipelineGameMode ^
  -game -windowed -NoLoadingScreen -log -Unattended ^
  -MoviePipelineConfig="MovieRenderPipeline/QueueManifest.utxt"
```

Two details that matter and differ from a naive reading of the research doc:

- `-MoviePipelineConfig=` must include the manifest's **`.utxt` extension**
  (a bare path without it is a fatal "Failed to find Pipeline Configuration
  asset to render" error — the extension is what selects the
  `LoadManifestFileFromString()` code path in
  `MovieRenderPipelineCommandLine.cpp`), and the path is relative to the
  project's `Saved/` directory.
- `-ResX=1920 -ResY=1080` must come **before** the map URL argument on the
  command line, not after, or the actual window/backbuffer resolution stays
  at the project's default (1280x720) even though MRQ's own internal render
  target is unaffected (it always correctly targets 1920x1080 per
  `MoviePipelineOutputSetting`, confirmed via the "Total resolution:" log
  line every run).

A window may appear briefly during the render; this is expected. Exit code 0
on success. Typical time for 3 one-frame test shots (32 warm-up frames,
8 temporal samples each) in this session: roughly 4-5 minutes total.

**Update**: the earlier "content only in part of the canvas" issue is
**RESOLVED** — see `Docs/Lighting.md` Section 5b. Root cause was NOT a
resolution/canvas bug at all: the Level Sequences' camera-cut tracks were
never actually binding to the configured CineCameraActors (`camera_binding_id`
was silently left at an all-zero Guid by the original binding code), so MRQ
fell back to a fixed default/no-PlayerStart view identical across every
camera and every round. Fixed in `setup_cameras_wtk.py` by constructing a
`MovieSceneObjectBindingID` explicitly (`set_editor_property("guid", ...)`)
rather than passing a bare Guid, and by calling `section.modify()` +
`EditorAssetLibrary.save_loaded_asset(seq)` (not `save_asset(path)`) so the
binding actually persists to disk. All 3 test cameras now render correctly
framed, distinct shots of the kitchen. Remaining open issues (blown-out
window, underexposed lower cabinets) are exposure/lighting-rig issues, not
render-path issues — see `Docs/Lighting.md` Section 7.

**2026-09-28 update (WtkWindow2 pass, Lighting.md Section 22)**: the window
is no longer blown out or a flat wash — `setup_lighting_wtk.py`'s `main()`
now also calls `setup_glass_hidden_for_pt()` after `setup_window_backplate()`,
which builds/applies a permanent, named `M_WTK_GlassHidden_PT` material
(BLEND_MASKED, OpacityMask=0, unlit-black) to the window mesh's glass slot
for path-traced stills — a render-only choice, since `MI_Glass_Clear` and
its default slot assignment via `remap_materials_wtk.py` are left
untouched. Because this override must be applied AFTER
`remap_materials_wtk.py` (which would otherwise put `MI_Glass_Clear` back
on the slot), the mandated rebuild order is now: `build_wtk_material_
instances.py` -> `set_uv_mode_tiling.py` -> `remap_materials_wtk.py` ->
`setup_lighting_wtk.py` (lighting + backplate + **glass-hidden-for-PT**) ->
`setup_cameras_wtk.py` -> `render_tests_wtk.py` (build MRQ jobs) -> the
headless MRQ render (second process). Re-running `remap_materials_wtk.py`
alone after this point will silently restore the glass and must be
followed by another `setup_lighting_wtk.py` run to re-apply the
glass-hidden material before the next render. Final renders now at
`06_Renders/tests/look_A_v4/{Wide,Angle,Detail}.png`.

**2026-09-28 update (WtkMuntin pass, Lighting.md Section 23)**: the window
muntin's Fresnel-driven overexposure glow (a false neutral-white halo on
the vertical muntin bar in `Angle.png`) is fixed at the material level --
`Scripts/build_wtk_material_instances.py`'s `build_windowframe_white()`
now ships `RoughnessMin`/`RoughnessMax`=1.0 (was 0.5), `Specular`=0.0 (was
0.5), `BaseColorBrightness`=0.6 (was 1.0). No change to the mandated
rebuild order (this is a `build_wtk_material_instances.py`-level MI change,
picked up by the existing order's first step). Final renders now at
`06_Renders/tests/look_A_v5/{Wide,Angle,Detail}.png`. See Lighting.md
Section 23 for the full single-variable diagnostic derivation (bloom,
denoiser, Local Exposure, visible sun disk, Nanite, and a garish-red
material sanity check were all tested and ruled out before finding the
grazing-angle Fresnel + direct-sun mechanism).

---

# Phase 5e addendum (2026-09-26) — finishing round: oak tint, per-camera exposure, props, reimport safety

Scope this pass: `05_Unreal/WTK/Content/WTK/`, `05_Unreal/WTK_SourceTextures/`,
a new `05_Unreal/WTK_SourceProps/`, `06_Renders/tests/`,
`tmp/Wtk5e_20260926/`. No git, no Revit/`Pause/` files touched. Backup taken
before any change: `tmp/Wtk5e_20260926/backup/WTK/` mirrors
`05_Unreal/WTK/Content/WTK/` as it stood before this pass. No `UnrealEditor`
process was running before starting (`tasklist | grep -i unreal` returned
nothing).

## Reimport safety fix (Task 3's own requirement)

**Finding**: `import_wtk.py`'s `ensure_map_and_import()` delete+reimport
fallback path (`REIMPORT_PATH_USED=delete_and_reimport`, used whenever the
`DatasmithSceneElement` reimport/update API path isn't available) used to
call `unreal.EditorLevelLibrary.get_all_level_actors()` and unconditionally
`destroy_actor()` on every single one, on the assumption that the level only
ever contained Datasmith-imported content. That assumption broke as soon as
Phase 5d added hand-authored, non-Datasmith level actors: lighting
(`WTK_Sun`, `WTK_SkyLight`, `WTK_SkyAtmosphere`, `WTK_HeightFog`,
`WTK_GroundPlane_Outside`, `WTK_LED_W18`/`W30`, `WTK_Fill_Room`), the
`WTK_PPV` PostProcessVolume, the 3 test cameras (`CAM_Wide`/`CAM_Angle`/
`CAM_Detail`), and now (Phase 5e) the props (`WTK_Prop_CuttingBoard`/
`WTK_Prop_Plant`/`WTK_Prop_Bowl`) -- none of these come from the Datasmith
source, so a delete_and_reimport run would have silently wiped all of them,
requiring a full re-run of `setup_lighting_wtk.py`, `setup_cameras_wtk.py`,
and `place_props_wtk.py` just to get back to the current look.

**Fix**: `ensure_map_and_import()`'s delete-previous-actors loop now skips
any actor whose label starts with `"WTK_"` or `"CAM_"` -- the two label
prefixes used by every hand-authored WTK actor in this project -- and
destroys only the rest. Confirmed by inspection of the
`WTK_Import_Check.txt` / `actors.txt` actor dump that every genuine
Datasmith-imported actor label (`Casework_WTK_*`, `Walls_Basic_Wall_*`,
`Windows_Window-Fixed_*`, `Ceilings_Basic_Ceiling_Generic`,
`Furniture_FX-*`, `Casework_FX-*`, `Generic_Models_*`, `Site_Location`,
`Survey_Point`, the `DatasmithSceneActor` itself, etc.) starts with neither
prefix, so the filter cannot accidentally spare a real Datasmith actor that
should be deleted and re-created. `run_material_remap()` (which iterates
every actor's `StaticMeshComponent`s and reassigns by *source material name*,
not by actor label) was independently confirmed safe already: a prop's
imported Poly Haven material (e.g. `wooden_cutting_board_mat`) simply won't
match any entry in the WTK remap rule table and falls through as
"unmapped" -- harmless, not destructive -- so no change was needed there.

This is a **process-level fix, not yet independently re-verified against a
live `delete_and_reimport` run** in this pass (that would require running
the full `UnrealEditor-Cmd.exe -run=pythonscript -script=import_wtk.py`
pipeline end-to-end again, which was not exercised this round since no
Revit-side geometry changed) -- flagged as a recommended one-time
confirmation the next time a real Revit reimport is needed.

## Task 1 -- oak tint fix

See `Docs/Materials.md`'s Phase 5e section for the full before/after tint
derivation. Summary: `MI_Oak_Rift_Stained` / `MI_Oak_Shelf` both changed from
`BaseColorTint=(0.2423,0.1144,0.0543)` @ `BaseColorBrightness=1.8` (R:G ratio
2.19, read reddish/mahogany in the full-scene render) to
`BaseColorTint=(0.55,0.42,0.26)` @ `BaseColorBrightness=0.57` (R:G ratio
1.31, a neutral warm olive-brown, same ~0.25 target luminance). Per the
Pipeline's own documented lesson, `set_uv_mode_tiling.py` and
`remap_materials_wtk.py` were both re-run after the masters/MI rebuild to
restore the documented UVTiling table and confirm 52/52 slots still assigned
(tint/brightness changes alone don't touch UVTiling, but the MI is fully
recreated by `build_wtk_material_instances.py` each run, per that script's
own "Idempotent: deletes and recreates each MI asset on every run"
docstring, so the mandatory re-run-after-rebuild lesson still applies).

## Task 2 -- per-camera exposure

`setup_cameras_wtk.py`'s `configure_camera()` now calls a new
`apply_exposure_override()` helper that sets
`CineCameraComponent.post_process_settings` with
`override_auto_exposure_method=True` (kept at `AEM_MANUAL`, matching
`WTK_PPV`), `override_auto_exposure_bias=True` + a per-camera
`auto_exposure_bias`, and `post_process_blend_weight=1.0`. CAM_Wide/CAM_Angle
kept at bias 4.0 (the shared `WTK_PPV` look, confirmed still the best overall
balance for those two shots per Lighting.md's round-7 findings). CAM_Detail
given its own bias of 5.5 and retargeted to a real B30 knob position (see
Docs/Lighting.md's Phase 5e section for the full derivation from
`03_Revit/WTK_Cabinet_Spec.json`'s B30 hardware entry) with a slightly
narrower aperture (f/3.2, was f/2.8) so the oak reads the Task 1 target
mid-brown without clipping the brass knob's highlight -- see
Docs/Lighting.md for the sampled-pixel confirmation.

## Task 3 -- props

3 CC0 Poly Haven props (`wooden_cutting_board`, `potted_plant_04`,
`wooden_bowl_01`) downloaded to `05_Unreal/WTK_SourceProps/<asset>/` (glTF,
2k textures) and logged in `05_Unreal/WTK_SourceProps/LICENSES.md`. Imported
and placed via the new `05_Unreal/WTK/Scripts/place_props_wtk.py` (must run
via `UnrealEditor.exe -ExecutePythonScript=`, not the commandlet, for the
same Slate/ContentBrowser reason texture import does -- see that script's
own docstring). See `Docs/Props.md` for the full placement rationale and
render-time findings.

## Files changed/added this pass

- `Scripts/build_wtk_material_instances.py` -- oak tint/brightness fix
  (Task 1).
- `Scripts/setup_cameras_wtk.py` -- `apply_exposure_override()` added;
  per-camera `auto_exposure_bias` on all 3 cameras; CAM_Detail retargeted to
  a spec-derived knob position with its own bias/aperture (Task 2).
- `Scripts/import_wtk.py` -- delete+reimport fallback path now preserves
  `WTK_*`/`CAM_*` labelled actors (reimport-safety fix, Task 3's own
  requirement).
- `Scripts/place_props_wtk.py` -- new; import + idempotent placement of the
  3 props (Task 3).
- `05_Unreal/WTK_SourceProps/` -- new; 3 asset folders + `LICENSES.md`.
- `Docs/Materials.md`, `Docs/Lighting.md` -- Phase 5e sections added.
- `Docs/Props.md` -- new.
- Backup: `tmp/Wtk5e_20260926/backup/WTK/`.
- Final renders (re-rendered this pass): `06_Renders/tests/WTK_Test_CAM_{Wide,Angle,Detail}_0000.png`.

---

# B30 rail grain pass (2026-09-27)

`Scripts/fix_rail_grain_wtk.py` moves the B30 door-rail triangles (top and
bottom 5.715 cm / 2-1/4 in of each door, centroid test against rectangles
measured from the oak triangles) out of the `Oak_StainedWarmBrown` slot into
a new `MI_Oak_Rift_Rail` slot. That MI copies every parameter from
`MI_Oak_Rift_Stained` on each run, with `UVRotation_deg` + 90, so the rails
read horizontal while stiles and panels stay vertical (cut list P07-P09).

- Result: 200 of 352 oak triangles moved; slots {Paint 305, Oak 152, Rail 200}.
- Idempotent: reuses the existing MI and slot (a second run changes nothing).
  The MI is *not* deleted/recreated, since that would null the mesh's slot
  reference and add a duplicate slot on the next run.
- Wired into `import_wtk.py` as `run_rail_grain_pass()` right after
  `run_knob_smoothing_pass()` at all three import return paths, called with
  `main(load_level=False)` so the in-memory level isn't reloaded from disk.
  A reimport re-bakes the single oak slot, so the pass must run every time.
- Standalone: `UnrealEditor-Cmd.exe WTK.uproject -run=pythonscript -script=Scripts\fix_rail_grain_wtk.py -unattended -nop4 -nosplash -stdout`
  (log: `tmp/WtkRail_20260927/fix_rail_grain_log.txt`).
- Verified in `06_Renders/tests/WTK_Test_CAM_Detail_0000.png` (07:35): the
  top rails show horizontal grain; the stiles and panels are vertical.

# Prop clearance + close-range inspection (2026-09-27)

- `Scripts/prop_clearance_wtk.py`: measures combined prop bounds (actor +
  attached children) and nudges them so counter props keep >= 1.0 cm from the
  backsplash face (Y -1.90) and every base sits on its surface within 0.05 cm.
  It found the yawed 42 cm cutting board 5.5 cm *through* the backsplash
  (max Y +3.64) and moved it dy -6.54. The pass is called from
  `place_props_wtk.py` before its save (`main(load_level=False)`) and can also
  run standalone. Idempotent. Report: `tmp/WtkP5Close_20260927/prop_clearance.txt`.
- `Scripts/inspect_closeups_wtk.py`: inspection helper. Env `WTK_INSPECT_POSE`
  = A (counter end corner) / B (sink cutout) / C (W18 crown return) re-poses
  CAM_Detail at 50 mm f/8 (bias +2.64 EV, or `WTK_INSPECT_BIAS`). Render with
  the existing MRQ manifest and copy the Detail PNG. **Always finish with
  `WTK_INSPECT_POSE=restore`**, which restores CAM_Detail from
  `tmp/WtkP5Close_20260927/cam_detail_original.json` (65 mm, f/3.2, bias 2.8).
  Results: `06_Renders/tests/inspect/`. The restore was verified by
  re-rendering CAM_Detail.

# Path Tracer final-still rendering (2026-09-27, WtkPathTrace_20260927)

See `Docs/Lighting.md` section 13 for the full settings/measurement/render-
time tables. Summary: FINAL-STILL rendering now defaults to the UE 5.7
hardware-RT Path Tracer via MRQ (`r.PathTracing=1` in
`Config/DefaultEngine.ini`, `OpenImageDenoise` plugin enabled in
`WTK.uproject`). `Scripts/render_tests_wtk.py` gained
`WTK_RENDER_MODE=pathtracer|lumen` (default **pathtracer**), plus
`WTK_PT_SPP` (default 1024) and `WTK_PT_MAX_BOUNCES` (default 8). Path-traced
output filenames carry a `_pt` tag so they never collide with the older Lumen
renders of the same camera/preset.

Build-then-render command sequence is otherwise unchanged from the Phase 5d
addendum above (same two-process `-run=pythonscript` build + separate
headless `UnrealEditor-Cmd.exe -MoviePipelineConfig=...` render pattern, same
`-MoviePipelineConfig="MovieRenderPipeline/QueueManifest.utxt"` relative-path
gotcha). A fresh render_tests_wtk.py run picks up `WTK_RENDER_MODE`/
`WTK_LIGHT_PRESET`/`WTK_RENDER_CAMS` from the environment before building the
manifest; the headless render command itself doesn't change based on mode.

Known residual issue (not resolved this pass): the window's exterior view
still does not show a recognisable landscape at the final exposure -- it
reads as a bright, low-variance white pane even with a genuine clear-sky
HDRI (`sunny_vondelpark.hdr`) and a lowered sky-dome emissive brightness.
Diagnosed as the real HDR dynamic range of a 65,000 lux sky through clear
glass exceeding what one manual exposure can compress while also keeping the
interior ivory correctly exposed -- see Lighting.md section 4 for the full
diagnosis and follow-up options.

## WtkPTFix3 pass (2026-09-27) -- both open path-tracer issues re-tested,
neither fixed, both root causes narrowed further (see Lighting.md section 16)

Two issues from the task queue (CAM_Detail's oak luminance line, the
window's flat/detail-less exterior view) were re-investigated with fresh
diagnostic renders. Neither was fixed this pass -- summarized here for quick
reference; full numbers, crops, and the complete test log are in
Lighting.md section 16.

- **Oak line**: the leading hypothesis (path tracer rendering against a
  simplified Nanite fallback mesh) was directly tested by disabling Nanite
  entirely on the B30 mesh and re-rendering -- the line's magnitude was
  unchanged (door 1: 5.03 -> 5.01, door 2: 6.81 -> 6.80), falsifying the
  hypothesis. A follow-up per-triangle normal inspection also cleared the
  vertex-normal/smoothing-group-split hypothesis the previous pass had left
  open. Root cause remains unknown; `import_wtk.py`'s `run_nanite_pass()`
  was inspected but NOT changed (nothing found there is implicated).
- **Window exterior**: confirmed (independently of the previous pass's own
  finding) that the sky-dome/HDRI backdrop does not reach the path-traced
  camera through the window at all, with or without the glass in the way --
  hiding the glass via `MI_Glass_Clear` Opacity=0 revealed solid black, not
  the backdrop. That same test was rejected as a "hide the glass" fix
  regardless, because it raised room-interior brightness 58-73% (the task's
  own stability requirement is ~3%) -- Opacity is not a light-transport-
  neutral way to remove a translucent surface in this engine/shading-model
  combination. Reverted; no fix shipped.

Every diagnostic toggle this pass was reverted and audited
(`tmp/WtkPTFix3_20260927/audit_all_diag_state.py`) before the final hero
render, which ships the same configuration as before this pass.

## WtkPTFix4 pass (2026-09-27) -- window exterior FIXED via a PPV/path-tracer
flag never tried before; oak-line candidate fix retracted as unreproducible

- **Window exterior, ROOT CAUSE FOUND AND FIXED**: every camera's own
  `post_process_settings.path_tracing_enable_reference_atmosphere` was
  `False` (confirmed via `tmp/WtkPTFix4_20260927/inspect_pt_ppv_settings.py`)
  -- a Path-Tracing-specific PPV flag no prior pass (WtkPTFix/2/3) had ever
  inspected or touched; those passes only ever iterated on `MI_Glass_Clear`'s
  own Opacity/BaseColorTint/Specular and the sky dome's emissive material.
  `path_tracing_include_emissive` (the task's own leading A1 hypothesis)
  was already `True` everywhere and was NOT the blocker. Setting
  `path_tracing_enable_reference_atmosphere=True` (+ its override flag) on
  each camera's own post-process override -- persisted in
  `Scripts/setup_cameras_wtk.py`'s `apply_exposure_override()` -- made the
  SkyAtmosphere background visible through the window glass for the first
  time in this project's history: window patch mean sRGB went from a flat
  (65.7,68.6,69.1)/stddev~3 wash to (82.6,96.1,111.2)/stddev 37-43, a real
  sky gradient with a visible horizon line, confirmed by a 2x crop
  (`tmp/WtkPTFix4_20260927/window_2x_FINAL.png`). Room-interior brightness
  changed by only -3.0% to -4.7% across the shared measurement patches,
  comfortably inside the task's <=5% GI-leak budget -- this flag controls
  background camera-visibility in the path tracer, not GI contribution.
- **Oak line: a candidate fix (disabling `Plumbing_Fixtures_FX-02`'s
  cast_shadow) was tried, appeared to work on a single render, and was then
  found NOT reproducible** across 3 independent re-renders with the same
  settings (all measured the original ~4.7-5.8 delta, statistically
  identical to a direct A/B control with FX-02 restored to its true
  defaults). The apparent fix was retracted rather than shipped, per this
  project's own "verify each claim with a crop" standard. Root cause
  remains unknown. A camera-height diagnostic (CAM_Detail +10cm) did newly
  confirm the line is world-space (not a screen-space/tile artifact),
  narrowing the search to a real feature at world Z~64-69cm near B30 not
  yet identified among this project's enumerable actors.

Every diagnostic toggle this pass was reverted and audited
(`tmp/WtkPTFix4_20260927/audit_all_diag_state.py`, recreated fresh since
the WtkPTFix3 audit script this doc referenced was not actually present on
disk) before the final hero render. See `Docs/Lighting.md` section 17 for
the full test-by-test log, measurements, and honest per-image description.

## WtkBand pass (2026-09-27) -- the "oak line" (sections 15-17 above) and
CAM_Wide's own lower-cabinet band ROOT CAUSE FOUND AND FIXED:
`WTK_GroundPlane_Outside`'s ray-tracing visibility

- **Root cause, confirmed by direct, reproduced bisection**:
  `WTK_GroundPlane_Outside` (the large unlit-emissive backdrop plane
  outside the window, `Scripts/setup_lighting_wtk.py`'s
  `setup_ground_plane()`) is visible to the path tracer's hardware ray
  tracing. Hiding it alone drops the CAM_Detail door strip-luminance delta
  from +8.3/+11.6 to **-0.9/-0.4** (reproduced twice, byte-identical) and
  the CAM_Wide lower-cabinet band from +4.2 to **-1.2** -- both comfortably
  under the <3 target. Every other candidate this and 3 prior passes tested
  (materials, mesh geometry/normals, Nanite, FX-02, SkyAtmosphere
  reference-atmosphere, `r.PathTracing.LightGridResolution`/`MISMode`/
  `EnableEmissive`, upper cabinets, countertop/backsplash, the window mesh,
  the knobs) had zero or noise-level effect.
- **Fix**: `setup_ground_plane()` now sets
  `visible_in_ray_tracing=False` on the plane's `StaticMeshComponent`. This
  flag is hardware-ray-tracing-only -- confirmed via a direct Lumen
  re-render showing the plane's real-time/preview visibility is completely
  unaffected. Idempotent (re-applied every `setup_lighting_wtk.py` run).
- **Honest disclosure**: this also removes a real (if physically-
  unrealistic, since the plane is a flat unlit emitter with no falloff) GI
  contribution the plane was making through the window -- whole-frame
  CAM_Wide brightness rose **+12.4%**, ivory upper door **+10.4%**, ceiling
  centre **+7.5%**, exceeding the task's own <=3% "other patches must not
  move" budget on 3 of 4 sampled patches. Three follow-up tests (dimming
  the plane to near-zero brightness, disabling its shadow, making it
  single-sided) each independently confirmed the band and the brightness
  change are caused by DIFFERENT aspects of the same actor: dimming
  restores the brightness (to +/-0.2%) but has ZERO effect on the band, and
  neither shadow nor sidedness affects either. No exposure/SkyLight
  compensation was attempted, per this project's own repeated rejection of
  that class of fix (section "16.2"'s Opacity=0 rejection; the window-only
  pass's "no skylight-leaking cheat" decision) -- left as an open follow-up
  (re-run the exposure calibration ladder against this corrected baseline,
  or find a physically-lit ground-plane treatment that doesn't reproduce
  the visibility-boundary step). See `Docs/Lighting.md` section 18 for the
  full bisection table, mechanism tests, and final measurements.

# Orchestrator follow-up to WtkBand (2026-09-27)

- The WtkBand agent's "final" hero renders (16:23) were byte-identical to the
  control and still showed the band. The fix had been saved to the level
  after them. Verified that WTK_GroundPlane_Outside has
  `visible_in_ray_tracing=False` in WTK_Main_v2 (`tmp/WtkBand_20260927/apply_gp_rt_off.py`),
  then re-rendered: the CAM_Detail band step went from +8.3/+11.6 to -0.9/-0.4 (flat).
- The fix also removed the plane's occlusion of the room in the path tracer, so the
  room brightened ~0.6 EV. The hero CAM_Wide/CAM_Angle bias went 7.0 -> 6.4
  (`setup_cameras_wtk.py`); CAM_Detail stays at 4.3. CAM_Wide now reads: upper ivory
  (179,142,110), lower ivory (140,96,63), window (206,213,220), back wall (182,157,134).
- Diagnostic hooks were added to `render_tests_wtk.py`: `WTK_PT_DENOISER=0` (raw path-traced
  output) and `WTK_EXTRA_CVARS="r.X=1;r.Y=0"`. Neither is set by default.
- Diagnostics that ruled out causes (06_Renders/tests/diag_denoise): the denoiser off,
  NormalStrength 0, FX-02 hidden, r.RayTracing.Nanite.Mode=1. The band was present in all of them.

---

# Look-variant pass round 2 -- WTK_LOOK finish (2026-09-27)

Fixed the 3 orchestrator-flagged issues in look A (mauve ceiling/wall tint,
orange lower-ivory cabinets, dark CAM_Detail oak) and shipped looks B
("warm morning") and C ("editorial") with the same tint fix. Full detail
in Docs/Lighting.md Section 19; summary:

- `Scripts/setup_cameras_wtk.py`'s `apply_exposure_override()` gained a
  `white_tint` post-process override (Engine's `WhiteTint`, distinct from
  `WhiteTemp` -- negative value pushes green, which is the fix for a
  magenta/mauve cast that `white_temp` alone cannot correct).
  `LOOK_PARAMS` retuned per-look (see Lighting.md Section 19.5 table).
- Found and documented a hard constraint: White Balance is a single global
  transform, so it cannot independently fix the orchestrator's "lower ivory
  reads orange" complaint without also over-cooling the (already-correct)
  upper ivory -- final look A is the best achievable compromise, not a full
  fix (Lighting.md Section 19.3).
- `Scripts/measure_renders_wtk.py` extended to recognise `lookA`/`lookB`/
  `lookC` CLI tokens so it can read the `_lookX`-suffixed render filenames
  `render_tests_wtk.py` already produced but this script couldn't measure.
- All 3 looks rendered at all 3 cameras, SPP=1024 (path tracer), and copied
  to `06_Renders/tests/look_{A,B,C}/{Wide,Angle,Detail}.png`. Level left on
  look A.

# Bloom off for stills (2026-09-28, orchestrator; follows Lighting.md §23)

- The WtkMuntin pass's frame-material change (roughness 1.0, specular 0, brightness 0.6)
  removed the neutral Fresnel highlight, but the visible "glow" around the vertical muntin
  and the brass faucet in CAM_Angle was mostly BLOOM (PPV bloom_intensity 0.3) haloing
  those sunlit edges against the bright window view.
- `setup_cameras_wtk.py` `apply_exposure_override()` now sets `bloom_intensity=0.0` with
  its override flag on every camera, so the stills render with no bloom. Re-run
  `setup_cameras_wtk.py` (WTK_LIGHT_PRESET=hero, WTK_LOOK=A) to apply it.
- Result: look_A_v6. The muntin and faucet read crisp, with only a thin sunlit edge. Room
  patches moved ≤1.2% vs v5 (upper ivory 194.9→192.6, back wall 203.1→201.3), and the
  CAM_Detail band stays at |Δ| 1.13.
- The current approved renders are `06_Renders/tests/look_A_v6/{Wide,Angle,Detail}.png`.

---

# WtkReimport_20260928 pass -- re-import of the fresh Datasmith export (FX-07/LED strip removed) into WTK_Main_v2, full look rebuild, v6-vs-v7 verification

Scope: `05_Unreal/WTK/` and `06_Renders/` only, no git. Trigger: a fresh
Revit-side Datasmith re-export (`04_Exchange/WTK_Start-3DView-WTK_Datasmith_
Export.udatasmith`, written 2026-09-28 03:59, 21 ActorMesh) with the
under-cabinet LED strip fixture (FX-07 / `Light_LED3000K` material) removed
from the Revit model. One `UnrealEditor*` process at a time throughout,
confirmed via `tasklist` before every launch; no process left running after
any step.

**Backups** (Step 1, taken before any change):
`05_Unreal/WTK/tmp/WtkReimport_20260928/WTK_Main_v2.umap.bak`,
`05_Unreal/WTK/tmp/WtkReimport_20260928/backup_content/Datasmith_v2/`
(mirrors `Content/WTK/Datasmith_v2/` as it stood before the reimport), and a
copy of the approved reference renders at
`05_Unreal/WTK/tmp/WtkReimport_20260928/look_A_v6_reference/` (the real
`06_Renders/tests/look_A_v6/` was never written to this pass).

## Step 2 -- import pipeline

Ran `import_wtk.py` via `UnrealEditor-Cmd.exe -run=pythonscript` against the
fresh export. The process exited with code 1, but the actual Python
pipeline completed and re-saved `WTK_Import_Check.txt` successfully; the
exit code came from an unrelated, pre-existing `_WtkReimportScratch` scratch
map left over from a prior session colliding with `EditorLevelLibrary.
new_level()` ("Failed to validate the destination. An asset already exists
at this location.") plus a harmless "Handled ensure" in Datasmith's actor
importer (`DatasmithActorImporter.cpp:826`, a known-benign engine-level
assert, not a Python exception) -- neither affected the import result. The
stale scratch map was deleted afterward (`Content/WTK/Maps/` now contains
only `WTK_Main.umap`/`WTK_Main_v2.umap`) so future runs don't hit the same
collision.

**`WTK_Import_Check.txt` (verbatim, this pass's fresh run)**:

```
WTK Import Check — generated by import_wtk.py
Datasmith source: C:\Users\Sam\Documents\Chess\04_Exchange\WTK_Start-3DView-WTK_Datasmith_Export.udatasmith
Imported to: /Game/WTK/Datasmith_v2
Reimport path used: delete_and_reimport
Map saved: /Game/WTK/Maps/WTK_Main_v2 (save_current_level=True)

(a) Base cabinet run length (DB18/SB36/B30/DB24/B12, excl. FX-): PASS (expected 304.80 cm, got 304.80 cm, diff 0.00 cm)
(b) Countertop (FX-01) top Z above floor: PASS (expected 91.44 cm, got 91.44 cm, diff 0.00 cm)
    Floor actor(s) used: ['Floors_Floor_Generic_-_12_']
    Counter actor(s) used: ['Casework_FX-01']
(c) Ceiling bottom Z above floor: PASS (expected 243.84 cm, got 243.84 cm, diff 0.00 cm)
    Ceiling actor(s) used: ['Ceilings_Basic_Ceiling_Generic']
(d) Room interior dims (wall envelope - 2x15.24cm thickness): 365.76 cm x 426.72 cm (expect ~365.76 x 426.72 cm)
    Wall actor(s) used (4): ['Walls_Basic_Wall_WTK_Interior_6in', 'Walls_Basic_Wall_WTK_Interior_6in_2', 'Walls_Basic_Wall_WTK_Interior_6in_3', 'Walls_Basic_Wall_WTK_Interior_6in_4']

Total actors: 45
Static mesh assets: 21
Distinct materials imported: 11
  - Clad_-_White
  - Default_Floor
  - Glass_Clear
  - Metal_SatinBrass
  - Oak_StainedWarmBrown
  - Paint_WarmIvory
  - RNT_Material
  - Steel_Brushed
  - Stone_HonedCream
  - Wall_WarmOffWhite
  - Wood_-_Stained

--- Import guard (unexpected actors) ---
UNEXPECTED_ACTOR_COUNT: 0
Import guard: PASSED

FINAL status: PASS
```

Compared to the pre-reimport check (12 materials incl. `Light_LED3000K`, 58
total actors), this run shows 11 materials (no `Light_LED3000K`) and 45
total actors -- consistent with FX-07's fixture actor(s) and its LED
material genuinely absent from the fresh export, not merely hidden.

**FX-07 / `Light_LED3000K` absence, independently confirmed**: `grep -rn
"FX-07|Light_LED3000K|LED3000K"` over `Content/WTK/Datasmith_v2/` and the
full `import_run.log` returns zero matches. A live in-editor audit script
(`tmp/WtkReimport_20260928/audit_state.py`) also confirms
`FX07_OR_LED3000K_ACTORS: []` and `BAD_ACTORS_FOUND(LED/Can/Fill/Prop): []`
against the loaded `WTK_Main_v2` level.

**Knob smoothing**: log confirms `[SmoothKnobs] Spawned 7 WTK_Knob_*
actor(s) (expected 7 per 03_Revit/WTK_Cabinet_Spec.json: SB36=2, B30=2,
W18=1, W30=2)`; the live audit independently confirms `KNOB_ACTORS(7)` with
all 7 expected labels present.

**Rail-grain slot on B30**: `import_run.log` confirms `[FixRailGrain]
Material slots AFTER: ['Paint_WarmIvory', 'Oak_StainedWarmBrown',
'Metal_SatinBrass', 'MI_Oak_Rift_Rail']` -- the `MI_Oak_Rift_Rail` slot
(index 3) exists on the B30 mesh, with parameters freshly re-synced from
`MI_Oak_Rift_Stained` (`UVRotation_deg` +90) per the script's own
idempotent-reuse logic.

**`PLACE_PROPS` confirmed unchanged**: `place_props_wtk.py:49` still reads
`PLACE_PROPS = False`; not invoked this pass, matching the task's
requirement.

## Step 3 -- look re-apply (materials -> lighting -> cameras) and read-only audit

Ran, in the mandated order, each as its own `UnrealEditor-Cmd.exe
-run=pythonscript` process (`tasklist` checked clear before every launch):
`build_wtk_material_instances.py` -> `set_uv_mode_tiling.py` ->
`remap_materials_wtk.py` -> `setup_lighting_wtk.py` (`WTK_LIGHT_PRESET=hero`;
internally covers `WTK_Blocker_Roof`/two-sided shell shadows, the ground
plane `visible_in_ray_tracing=False` fix, the window backplate, and
`setup_glass_hidden_for_pt()` run after the remap, per its own documented
ordering requirement) -> `setup_cameras_wtk.py` (`WTK_LIGHT_PRESET=hero
WTK_LOOK=A`). All 5 processes exited 0 with "Success - 0 error(s)".

A read-only audit script (`tmp/WtkReimport_20260928/audit_state.py`, no
mutations/saves; had to route through `unreal.log()` + a written result
file rather than bare `print()`, which this project's own `import_wtk.py`
comments already documented as unreliable under `-run=pythonscript`
captured stdout) against the loaded `WTK_Main_v2` confirmed:

- `WTK_GroundPlane_Outside` `visible_in_ray_tracing=False` -- **confirmed**.
- Window backplate (`WTK_WindowBackplate`) rotation `(pitch=0, yaw=0,
  roll=-90)`; its **local +Z face normal** (the mesh's visible face, not the
  actor's raw +X forward axis) computed via `quaternion.rotate_vector()`
  resolves to world `(0.0, -1.0, -0.0)` -- **confirmed facing (0,-1,0)**,
  exactly as this task's own check and `Docs/Lighting.md` Section 21.1's
  documented fix require. (Note: a naive `get_actor_forward_vector()` read
  gives `(1,0,0)` instead -- that's the actor's local +X axis, a different
  axis than the mesh's authored +Z visible-face normal under a -90° roll;
  not a bug, just the wrong vector to read. Re-verified with a dedicated
  second script computing the correct face normal.)
- Window glass slot (`Windows_Window-Fixed_...`, slot 0) = `M_WTK_
  GlassHidden_PT` -- **confirmed**.
- Cameras: `CAM_Wide`/`CAM_Angle` bias=8.5, `CAM_Detail` bias=6.6, all three
  `bloom_intensity=0.0`, `white_temp=3300K`, `white_tint=-0.05`,
  `path_tracing_enable_reference_atmosphere=True` -- **bloom=0 and
  reference-atmosphere=True confirmed** (the per-camera bias/WB values
  themselves match the existing look-A hero tuning documented above in the
  "Bloom off for stills" and Section 20 entries, not literally 0 -- there is
  no separate "0" target for bias/WB in this project's own history, so this
  is read as the intended "reference atmosphere + zero bloom" state).
- No `WTK_LED_*`/`WTK_Can_*`/`WTK_Fill_*`/`WTK_Prop_*` actors in the level --
  **confirmed empty**.

## Step 4 -- render and v6-vs-v7 comparison

Built the MRQ queue (`render_tests_wtk.py`, `WTK_RENDER_MODE=pathtracer
WTK_PT_SPP=1024 WTK_LIGHT_PRESET=hero WTK_LOOK=A`) then rendered headless as
a second, separate `UnrealEditor-Cmd.exe` process per the Phase 5d addendum
pattern above (1920x1080, `-MoviePipelineConfig="MovieRenderPipeline/
QueueManifest.utxt"`). Exit code 0, no leftover Unreal process.

**Comparison** (`tmp/WtkReimport_20260928/compare_v6_v7.py`, PIL/numpy,
against the preserved `look_A_v6` copy):

| Image | Mean abs pixel diff (0-255 scale) |
|---|---|
| Wide | 0.274 |
| Angle | 0.342 |
| Detail | 0.399 |

| CAM_Wide patch | v6 mean RGB | v7 mean RGB | % diff |
|---|---|---|---|
| Upper ivory (y380-600,x1000-1180) | (192.6,168.8,145.1) | (192.6,168.8,145.1) | 0.01% |
| Lower ivory (y900-1040,x560-680) | (156.4,117.2,83.5) | (156.4,117.2,83.5) | 0.04% |
| Ceiling (y40-160,x700-1200) | (199.4,187.0,172.4) | (199.4,187.1,172.4) | 0.01% |
| Back wall (y250-380,x620-880) | (201.3,193.1,179.7) | (201.3,193.2,179.7) | 0.00% |
| Window (y420-560,x640-860) | (101.2,191.4,209.2) | (101.2,191.4,209.2) | 0.00% |

All 5 patches within ±0.05% (well inside the ±3% budget). CAM_Detail oak
patch (y300-600,x300-800): v6=(135.5,84.8,57.8), v7=(135.6,84.8,57.8),
effectively identical. Band check (rows 670-680 minus 640-650,
x300-800): v6 |Δ|=1.32, v7 |Δ|=1.32 -- unchanged, comfortably under the <3
target.

**Honest per-image description** (from the actual rendered pixels):

- **CAM_Wide**: full elevation, ivory upper/lower cabinet doors with
  visible shaker-style frame lines, smooth brass dome knobs on every lower
  door, open oak shelving to the right with visible horizontal grain on the
  shelf undersides, a centered window showing a sharp, detailed exterior
  (blue sky, a neighboring roofline, a tree canopy, a wood fence, a
  flowerbed, and mowed lawn -- not a flat wash), soft even ceiling/wall
  lighting with no light-leak wedges or streaks at any wall/ceiling
  junction, no LED strip or light bar visible under either run of upper
  cabinets, no stray/unexpected geometry anywhere in frame.
- **CAM_Angle**: same window/garden detail as above, muntin bar reads as a
  crisp white frame member with no Fresnel/bloom halo, the brass faucet
  shows only a thin, physically plausible sunlit edge highlight (not a
  glow), knobs read as smooth domes (no faceting), no props on the counter,
  no light leaks.
- **CAM_Detail**: two B30 door fronts filling the frame, continuous vertical
  oak grain on stiles/panels, two smooth brass dome knobs with no visible
  tessellation facets, a clean bevel line along every door edge, no visible
  discontinuity/seam in the oak grain within this crop.

**No regressions found** -- v7 reproduces v6's approved look to within
measurement noise across every checked patch and the band-check guard;
no fix was needed this pass.

## Files

- `05_Unreal/WTK/tmp/WtkReimport_20260928/` -- backups (`WTK_Main_v2.umap.
  bak`, `backup_content/Datasmith_v2/`, `look_A_v6_reference/`), all process
  logs (`import_run.log`, `build_mi.log`, `uv_tiling.log`, `remap.log`,
  `lighting.log`, `cameras.log`, `render_build.log`, `render_run.log`,
  `clean_scratch.log`), the audit scripts (`audit_state.py`,
  `audit_backplate.py`) and their result files (`audit_result.txt`,
  `audit_backplate_result.txt`), and `compare_v6_v7.py`.
- `06_Renders/tests/look_A_v7/{Wide,Angle,Detail}.png` -- new final renders
  this pass.
- `06_Renders/tests/look_A_v6/{Wide,Angle,Detail}.png` -- untouched
  reference (confirmed unmodified: on-disk `LastWriteTime` predates this
  pass throughout).
- `05_Unreal/WTK/Content/WTK/Maps/_WtkReimportScratch` (stale asset) --
  deleted; was causing a harmless but noisy exit-code-1 on every
  `import_wtk.py` run.

# Section 24 -- 2026-09-28 Phase 6 pass: configurable 4K finals + quality gate

Made `Scripts/render_tests_wtk.py`'s resolution and output directory
configurable (`WTK_RES`, default `1920x1080`; `WTK_OUTPUT_DIR`, default
`06_Renders\tests` -- unchanged behavior with no env vars set), added a
stable `WTK_Final_CAM_<cam>` naming scheme (`WTK_FINAL_NAMES=1`), and added
an optional 16-bit EXR master via `MoviePipelineImageSequenceOutput_EXR`
alongside the existing PNG (`WTK_WRITE_EXR=1`) -- confirmed the MRQ Python
API in this UE 5.7 build does support a second output setting on the same
job; both PNG and EXR wrote successfully for all 3 cameras.

Quality gate at 4K: rendered CAM_Wide at 3840x2160 at SPP 1024 and 2048
(path tracer, hero/look-A). 1024 SPP took 1:54.9, 2048 SPP took 5:38.8.
100% crops of the window glazing/exterior, countertop edge, and oak B30
door showed no visible difference between the two sample counts -- no
residual noise, denoiser smearing, halos, or fireflies at either. Accepted
1024 SPP (matches the already-approved `look_A_v7` reference's own SPP,
~3x faster, no measurable quality loss).

Rendered the 3 finals at 3840x2160, SPP 1024, to `06_Renders/final/`
(`WTK_Final_CAM_{Wide,Angle,Detail}_0000.{png,exr}`). Total render time for
all 3 jobs: 5:46.7 (Wide 1:47.7, Angle 1:43.0, Detail 2:12.2). 100%-crop
inspection (6 regions per image) found no 4K-only defects -- no fix or
re-render was needed. Downscaling each 4K final to 1080p and diffing
against `look_A_v7` gave mean abs pixel diffs of 1.4-2.4/255 and
fixed-material-patch diffs of 0.01-0.22%, both well inside the project's
own same-look budget -- the look is unchanged at 4K. CAM_Detail's oak-panel
band check (scaled x2 for 4K: rows 1340-1360 vs 1280-1300, x600-1600) gave
|Delta|=0.45, comfortably under the <2 target.

Full settings, camera transforms/lens data, and the composition-check
table are recorded in `06_Renders/final/RENDER_SETTINGS.md`.

# WTK Dolly animation render (2026-09-28)

The accepted 288-frame Path Tracer render completed in Unreal with exit code
0 at 11:44:17 PDT. Frames `06_Renders/animation/frames/WTK_Dolly_0000.png`
through `WTK_Dolly_0287.png` are 1920x1080, rendered at 512 SPP with 8 path-tracer
bounces and denoising enabled. The sequence is 24 fps. The review encode,
`06_Renders/animation/WTK_Dolly_Review.mp4`, was verified as H.264
`yuv420p`, CRF 18, with 288 decoded frames over 12.000 seconds. Render and
review are accepted. For future WTK animation renders, retain the numbered
image sequence as the source/master and verify the encoded review's codec,
pixel format, frame count, and duration against the sequence before
acceptance.
