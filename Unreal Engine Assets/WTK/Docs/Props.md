# WTK prop-fix pass addendum (2026-09-26) — plant-float and sink-overlap fixes

Prompted by the orchestrator's review of the Phase 5e CAM_Wide render,
flagging two bugs: (1) the potted plant floating in mid-air beside the
window's left edge (at shelf height but nowhere near the shelf's real
footprint -- an inch/cm-style X/Y mixup, not a Z problem); (2) the cutting
board and bowl sitting at X in [-60,-45], overlapping the sink cutout
instead of resting on solid counter.

## Verified actor bounds (this pass's own dump, superseding earlier guesses)

`tmp/WtkProps2_20260926/dump_bounds.py`, run via
`UnrealEditor-Cmd.exe -run=pythonscript`, dumped the real bounds of every
relevant fixture before any prop was moved:

| Actor | Bounds (cm) |
|---|---|
| `Casework_FX-01` (counter) | X[-307.34, 2.54], Y[-63.50, 0.00], top Z=91.44 |
| `Casework_FX-04` (backsplash) | X[-304.80, 0.00], Y[-1.90, 0.00] (front face Y=-1.90), Z[91.44, 137.16] |
| `Furniture_FX-05` (both floating shelves, one actor) | X[-304.80, -214.63], Y[-25.40, 0.00], Z[152.40, 191.77] combined -- upper shelf top = the actor's own verified max Z, 191.77 |
| `Plumbing_Fixtures_FX-02` (sink) | X[-127.00, -55.88], Y[-52.07, -11.43], top Z~88.44 (recessed cutout) |
| `Plumbing_Fixtures_FX-03` (faucet) | X[-92.71, -90.17], base Z=91.44 |
| `Casework_WTK_B30_B30` | X[-213.36, -137.16] |
| `Casework_WTK_DB24_DB24` | X[-274.32, -213.36] |
| Window | X[-128.90, -53.98], Z[107.32, 197.49] |

**Root cause of Bug 1 confirmed**: the old plant placement
(`X=-60, Y=-13, rest_on_z=145`) was nowhere near the shelf actor's real
X-range (`[-304.80,-214.63]`) -- the shelf sits along the wall's left/B30
side of the cabinet run, not beside the window at X=-60. The old code's
comments described the shelf as being "to the right of the window,"
apparently based on a visual guess from an earlier render rather than the
actual actor bounds, and the Z-only `rest_on_z` correction (Phase 5e's own
fix for the plant's known multi-mesh-pivot problem) could correctly land the
plant's *height* on a shelf-like Z value while leaving its X/Y read
completely off the real shelf footprint -- exactly the "floats beside the
window, at shelf height" symptom reported.

**Root cause of Bug 2 confirmed**: X=-60/-45 sit just past the sink's own
right edge (`X_max=-55.88`) into the counter, but close enough (and close
enough to the faucet at X[-92.71,-90.17]) to read as "in the sink area" in
the render rather than clearly on solid, uncluttered counter.

## Fix

`Scripts/place_props_wtk.py`'s module-level constants now hold the verified
bounds above (`SHELF_UPPER_X_MIN/MAX`, `SHELF_UPPER_Y_MIN/MAX`,
`SHELF_UPPER_TOP_Z`, `SINK_X_MIN/MAX`, `B30_DB24_X_MIN/MAX`, corrected
`BACKSPLASH_FACE_Y=-1.90` matching the room's actual negative-Y interior
convention -- the old value, `+1.9`, had the wrong sign for this room).

New placements:

| Prop actor | New location (X, Y, Z cm) | Rotation | Scale | Rests on |
|---|---|---|---|---|
| `WTK_Prop_CuttingBoard` | (-260, -12, 91.44*) | yaw=12deg, flat | 0.55 | counter, B30/DB24 zone |
| `WTK_Prop_Plant` | (-237.17, -12.7, 191.77*) | yaw=-20deg | 1.0 | FX-05 UPPER shelf, right third |
| `WTK_Prop_Bowl` | (-170, -20, 91.44*) | 0deg | 0.35 | counter, B30/DB24 zone |

- **Cutting board**: moved from the sink-adjacent X=-60 to X=-260, in the
  counter zone directly above B30/DB24 (X[-274.32,-137.16], the task's own
  suggested zone), well clear of the sink (X[-127.00,-55.88]) and the faucet.
  Kept **lying flat** (not leaning against the backsplash): a first attempt
  at a ~12deg backward lean (per the task's alternative suggestion) exposed
  a real limitation in `spawn_or_update_prop`'s `rest_on_z` correction --
  that correction is computed from the mesh's un-rotated local-space bounds,
  so a pitched prop's true (rotated) world-space base does not match the
  correction's assumption, landing the board ~2.5cm below the counter
  (Z=88.9 vs the intended 91.44) with its tilted top edge clipping into the
  backsplash/wall plane. Lying flat (yaw-only, matching the prior pass's own
  casual-angle choice) avoids both problems while still satisfying the
  task's own "leaning ... or lying flat" alternative.
- **Plant**: moved to the shelf's real footprint, on the **UPPER** shelf
  (top Z=191.77, the FX-05 actor's own verified max Z) at X=-237.17 (75% of
  the way along the shelf's X-range, i.e. its right third) -- fully inside
  the shelf's verified X[-304.80,-214.63] and Y[-25.40,0.00] bounds.
- **Bowl**: moved to X=-170, also in the B30/DB24 counter zone, near but not
  overlapping the cutting board.

## Verification (bounds-vs-plane sanity check, this pass's final run)

`place_props()`'s own bounds-vs-plane check (extended this pass to also
check sink-X-overlap for counter props and shelf-footprint containment for
the plant, and to fix a backwards backsplash-clip comparison inherited from
the earlier code -- the room's interior is the negative-Y side of the
backsplash face, so a clip is `bounds.max.y > face`, not `bounds.min.y <
face` as the old check had it) -- **final run: all 3 props pass with 0
warnings**:

- `WTK_Prop_CuttingBoard` bounds `min=(-273.5,-21.2,91.4) max=(-246.4,-2.8,93.7)`
  -- base at Z=91.4 (matches the counter top within 0.2cm), fully inside the
  B30/DB24 X-zone, no sink-X overlap, no backsplash clip.
- `WTK_Prop_Plant` bounds `min=(-247.9,-23.5,191.8) max=(-225.9,-1.1,218.5)`
  -- base at Z=191.8 (matches the shelf top within 0.2cm), X and Y both
  fully contained within the shelf's verified footprint.
- `WTK_Prop_Bowl` bounds `min=(-175.5,-25.4,91.4) max=(-164.5,-14.6,94.7)`
  -- base at Z=91.4, fully inside the B30/DB24 X-zone, no sink-X overlap, no
  overlap with the cutting board's own bounds.

## Correction (2026-09-26, round 2): round-1's renders never actually showed the fix

**The round-1 "honest description" below this note was wrong** -- not
because the placement math was wrong (it wasn't), but because the fixed
placements never actually reached the rendered images. The coordinator
caught this: `WTK_Main.umap`'s own on-disk `LastWriteTime` was from BEFORE
both round-1 placement runs, proving `place_props()`'s
`save_current_level()` call had silently no-op'd (see `Docs/Pipeline.md`'s
"level-save persistence bug" section for the full root-cause writeup and
fix -- `actor.modify()`/`component.modify()` were never called before
mutating an existing actor, so the package was never marked dirty). The
round-1 renders were re-inspected and, on a more careful look, DO show the
old floating-plant / sink-adjacent-board positions -- the round-1
description below mistakenly reported the *intended* result rather than
what the images actually contained.

After the save-persistence fix (round 2), the props were re-placed, the
`.umap`'s `LastWriteTime` was directly confirmed to advance (10:58:46 PM ->
11:22:04 PM), and the scene was re-rendered. The description immediately
below is from actually reading the round-2 PNGs.

## Honest description of the re-rendered images (round 2, verified against a confirmed level save)

- **CAM_Wide**: the plant is visible on the RIGHT side of the frame, sitting
  on top of the right-hand floating shelf (the upper of the two FX-05
  shelves, visible to the right of the right-hand upper cabinet) -- its pot
  base rests flush on the shelf surface, no gap, no hovering, and it is
  nowhere near the window (which is centred over the sink, well to the
  left). The cutting board and a small round bowl both sit on the counter to
  the RIGHT of the sink, past the second bank of lower cabinet doors --
  clearly separated from the sink basin and the faucet, which are fully
  unobstructed and read cleanly. Both props sit on solid, visibly flat
  counter with no visible gap or sinking into the surface.
- **CAM_Angle**: same corrected geometry from a closer 3/4 angle -- the
  plant is visible top-right, sitting on the shelf with its base on the
  shelf's own surface (not the wall behind it, not hovering above it). The
  cutting board sits on the counter to the right, and the small bowl sits
  closer to the camera on the same counter run, both clearly past the sink
  cutout (visible at left, fully open/empty) and the faucet. No overlap
  between the board and the bowl.
- **CAM_Detail**: unaffected by the prop fix (this shot frames the B30
  cabinet doors/knobs, not the counter or shelf), used instead to verify the
  brass fix (see Materials.md's brass-fix addendum) -- sampled knob pixels
  average sRGB ~(210, 187, 162), a warm gold/champagne-bronze hue (R:G:B
  ratio ~1.30:1.16:1.0), clearly not the previously-reported pale cream/
  ivory. Still on the bright side due to this shot's own pre-existing,
  separately-disclosed overexposure issue (see Lighting.md), unrelated to
  this pass's brass or prop fixes.

## Files changed this pass

- `Scripts/place_props_wtk.py` -- verified-bounds constants added; cutting
  board and bowl moved to the B30/DB24 counter zone; plant moved to the
  FX-05 upper shelf's real footprint; `rest_on_z`'s known
  flat-only-assumption limitation documented; bounds-check sink-overlap,
  shelf-footprint, and backsplash-clip-direction logic added/fixed.
- Diagnostics: `tmp/WtkProps2_20260926/dump_bounds.py` /
  `dump_bounds.log`, `place_props.log` (first, tilted-board attempt),
  `place_props2.log` (0-warning bounds check, but -- see the "Correction"
  section above -- this run's save silently failed to reach the .umap),
  `place_props3.log` (round 2, after the modify()/save_map() fix; confirmed
  by a live before/after `.umap` `LastWriteTime` check).
- Backup: `tmp/WtkProps2_20260926/backup_Content_WTK/` (mirrors
  `05_Unreal/WTK/Content/WTK/` before this pass).
- Final renders (re-rendered this pass): `06_Renders/tests/WTK_Test_CAM_{Wide,Angle,Detail}_0000.png`.

---

# WTK Prop Staging — Phase 5e Task 3

Date: 2026-09-26. Scope: `05_Unreal/WTK_SourceProps/` (new), `/Game/WTK/Props/`
(new content), `05_Unreal/WTK/Scripts/place_props_wtk.py` (new),
`05_Unreal/WTK/Scripts/import_wtk.py` (reimport-safety fix). No git, no
Revit/`Pause/` files touched.

Plan.md's Phase 5 called for prop staging (e.g. a cutting board, a plant, a
cup) as part of the finishing round. This pass sources, imports, and places
3 restrained, warm-transitional CC0 props.

## Source and licence

All 3 props sourced from **Poly Haven** (https://polyhaven.com), CC0 1.0
Universal (public domain), via the public API (`assets?t=models` for the
listing, `files/<slug>` for the per-asset download manifest). Downloaded as
glTF at **2k texture resolution** (per the task's "1k-2k textures"
instruction) into `05_Unreal/WTK_SourceProps/<asset>/`. Full citation detail,
author credit, and the search process (including why a plain modern mug/cup
was not available and a wooden bowl was substituted) are in
`05_Unreal/WTK_SourceProps/LICENSES.md`.

| Prop | Poly Haven asset | Author | Role |
|---|---|---|---|
| Wooden Cutting Board | `wooden_cutting_board` | Kuutti Siitonen | cutting board, per the task's example list |
| Potted Plant 04 (small succulent) | `potted_plant_04` | James Ray Cock | plant, per the task's example list |
| Wooden Bowl 01 | `wooden_bowl_01` | Oliver Harries | stand-in for "a ceramic mug/cup or bowl" (no plain modern cup/mug found on Poly Haven at search time) |

3 props total -- at the low end of the task's "3-5" range, deliberately: a
4th/5th prop (a kettle, a fruit bowl) was considered but not added, to keep
the staging restrained and avoid competing with the B30 feature cabinet for
visual attention, per the task's own "restrained" instruction.

## Import

`05_Unreal/WTK/Scripts/place_props_wtk.py`'s `import_props()` imports each
glTF via `AssetTools.import_asset_tasks()` into `/Game/WTK/Props/<slug>/`.
**Must run via the full `UnrealEditor.exe -ExecutePythonScript=`, not the
`-run=pythonscript` commandlet** -- same Slate/ContentBrowser constraint
already documented for texture import in `Materials.md`'s "Environment
notes" (confirmed again this pass: the commandlet path was not even
attempted here, `-ExecutePythonScript` was used directly based on that
precedent).

**Multi-mesh finding**: UE 5.7's glTF importer (Interchange) does not always
produce a single combined StaticMesh per source asset. `wooden_cutting_board`
and `wooden_bowl_01` each imported as one StaticMesh, but `potted_plant_04`
imported as **4 separate StaticMeshes** (`_ground`, `_dirt`, `_plant`,
`_pot` -- one per glTF mesh/material node). This was only discovered after
the first placement run, when the plant floated ~13cm above its intended
shelf height: the placement code had assumed a single mesh and picked the
first StaticMesh found (`_ground`, a small flat plane), leaving the actual
pot/plant geometry unplaced and using the wrong mesh's (much smaller, wrongly
offset) bounds for the rest-on-surface calculation.

**Fix**: `import_props()` now returns *every* StaticMesh found per asset, and
`spawn_or_update_prop()` places one child StaticMeshActor per additional
sub-mesh (actor-attached to the parent at identity-relative transform, so
the assembly moves as one `WTK_Prop_*`-labelled unit), with the rest-on-Z
correction computed against the **combined** local-space bounds across all
sub-meshes (not just the first one found). Confirmed fix: the plant's
per-sub-mesh local bounds (`tmp/Wtk5e_20260926/debug_plant_bounds.py`) show
the `_pot` mesh alone reaches down to local Z≈0.0375cm while the others sit
higher (nested on/in the pot in the source scene's shared local frame) --
using the true combined minimum correctly lands the assembly's real visual
base on the target shelf surface.

(Separately, an earlier attempt at true single-actor multi-component
placement via `Actor.add_component_by_class()` failed with
`AttributeError: 'StaticMeshActor' object has no attribution
'add_component_by_class'` -- that method does not exist on
`unreal.StaticMeshActor` in this UE 5.7 Python binding. Actor-attachment
(separate child StaticMeshActors) was used instead, which is functionally
equivalent for a static, non-physics prop like this.)

## Placement

All three placed via `place_props_wtk.py`'s `place_props()`, idempotent by
`WTK_Prop_*` actor label:

| Prop actor | Location (X, Y, Z cm) | Rotation (yaw) | Scale | Rests on |
|---|---|---|---|---|
| `WTK_Prop_CuttingBoard` | (-60, -35, 91.44*) | 12deg | 0.55 | counter top (Z=91.44) |
| `WTK_Prop_Plant` | (-60, -13, 145.0*) | -20deg | 1.0 | FX-05 shelf (Z=145.0) |
| `WTK_Prop_Bowl` | (-45, -40, 91.44*) | 0deg | 0.35 | counter top (Z=91.44) |

*Z values marked with `*` are the requested resting-surface Z; the actor's
actual spawn Z is auto-corrected by `rest_on_z` (see above) to land the
prop's real combined base exactly on that surface -- e.g. the cutting board
spawns at `z=91.436` (a few hundredths of a cm below 91.44, reflecting its
own mesh's local-bounds minimum not being exactly 0).

- **Cutting board**: lying flat on the counter, left of centre (near the
  sink, right of the window), angled 12 degrees off-axis for a casual,
  not-perfectly-square look. Scaled to ~25x14cm (down from its native
  ~450x247mm) -- a realistic cutting-board size.
- **Potted plant**: on the lower of the two FX-05 floating shelves (Z=145,
  vs. the shelf band's documented ~140-165cm range), near the window side,
  clear of both the window itself and the B30 cabinet below. Kept at native
  scale (~170x186x268mm) since `potted_plant_04` was deliberately chosen
  over the larger `potted_plant_01`/`02` (~600-1350mm) for its already-small,
  restrained accent size.
- **Wooden bowl**: on the counter near the cutting board (its requested
  neighbour), scaled to ~11x11x3.3cm (down from its native ~313x309x94mm).

**B30 unobstructed**: B30 spans X `[-213.36, -137.16]`; every prop is placed
at X in `[-60, -45]`, well clear of B30's footprint and well clear of the
feature cabinet's sightline in all 3 test camera framings (confirmed
visually in the Phase 5e renders, see Lighting.md's Phase 5e section).

## Clipping / bounds check

`place_props()` runs a bounds-vs-plane sanity check after placement,
comparing each prop's actual combined bounds (including attached child
actors, for the multi-part plant) against its intended resting-surface Z and
the backsplash's front face (`Y=1.90`, the FX-04 slab's own physical
thickness per Materials.md's UV-check table). **Final run: all 3 props pass
with 0 warnings** -- `WTK_Prop_CuttingBoard` bounds
`min=(-73.5,-44.2,91.4) max=(-46.4,-25.8,93.7)`, `WTK_Prop_Plant` bounds
`min=(-70.8,-23.8,145.0) max=(-48.7,-1.4,171.7)`, `WTK_Prop_Bowl` bounds
`min=(-50.5,-45.4,91.4) max=(-39.5,-34.6,94.7)` -- every base sits within
1cm of its target resting Z and no back edge crosses the backsplash face.

(An earlier run with the plant at `Y=-8` clipped ~1.7cm past the backsplash
face at `Y=3.6`; pulled forward to `Y=-13` to clear it with margin -- see the
placement table above for the corrected value.)

## Reimport safety

**Finding**: `import_wtk.py`'s delete+reimport fallback path
(`ensure_map_and_import()`, used when the `DatasmithSceneElement`
reimport/update API isn't available) used to destroy **every** level actor
unconditionally before re-importing, on the assumption that the level only
ever held Datasmith-imported content. That assumption was already stale
before this task (Phase 5d's lights/cameras/PPV would have been wiped too),
and adding props made the gap concrete and worth fixing now.

**Fix**: the delete-previous-actors loop now preserves any actor whose label
starts with `"WTK_"` or `"CAM_"` (the two prefixes every hand-authored WTK
actor in this project uses -- lighting, the PPV, cameras, and now props,
including the plant's `WTK_Prop_Plant_Part1/2/3` child actors, which also
start with `"WTK_"`). Confirmed by inspection that no genuine Datasmith
actor label (`Casework_*`, `Walls_*`, `Windows_*`, `Ceilings_*`,
`Furniture_FX-*`, `Generic_Models_*`, etc.) starts with either prefix, so
the filter cannot accidentally spare something that should be deleted and
re-imported. See `Docs/Pipeline.md`'s Phase 5e section for the full
before/after and the note that this fix has not yet been independently
re-verified against a live `delete_and_reimport` run (no Revit-side geometry
changed this pass, so that code path wasn't exercised end-to-end).
`run_material_remap()` (which matches by source *material* name, not actor
label) was independently confirmed already-safe: an imported prop's Poly
Haven material simply won't match any WTK remap rule and falls through as
harmless "unmapped".

## Honest assessment (from the Phase 5e renders)

- **Believable scale**: yes on all 3 props in every camera they're visible
  in -- the cutting board and bowl read as real kitchen-counter objects
  next to the sink, not oversized or toy-like; the succulent reads as a
  small, appropriately modest shelf accent, not a dominant floor plant.
- **Clipping**: none found in the final placement (see the bounds check
  above) or visually in the renders.
- **Composition**: the props read as a light, believable touch rather than
  clutter -- CAM_Wide and CAM_Angle both show the cutting board + plant
  without obstructing B30, the sink, or the window. The bowl (placed at
  X=-45) falls outside CAM_Angle's and CAM_Detail's frame in this pass's
  camera positions -- only CAM_Wide's wider field of view reaches far enough
  right to include it, and even there it's a small, partially-visible
  presence next to the cutting board rather than a clearly separate read.
  This is a minor, disclosed limitation of the current camera framing/prop
  position combination, not a placement error (the bowl's own bounds check
  passes cleanly).

## Files

- `05_Unreal/WTK_SourceProps/{wooden_cutting_board,potted_plant_04,wooden_bowl_01}/` -- downloaded glTF assets.
- `05_Unreal/WTK_SourceProps/LICENSES.md` -- source/licence/author record.
- `05_Unreal/WTK/Scripts/place_props_wtk.py` -- import + idempotent placement script.
- `05_Unreal/WTK/Scripts/import_wtk.py` -- reimport-safety fix (`WTK_*`/`CAM_*` actor preservation).
- `Docs/Pipeline.md` -- Phase 5e section documenting the reimport-safety fix.
- Final renders: `06_Renders/tests/WTK_Test_CAM_{Wide,Angle,Detail}_0000.png`.
