# WTK_SourceProps — asset sources and licences

Date: 2026-09-26. All assets sourced from Poly Haven (https://polyhaven.com),
via the public API `https://api.polyhaven.com/assets?t=models` (listing) and
`https://api.polyhaven.com/files/<slug>` (per-asset download manifest).
Downloaded format: glTF (`.gltf` + `.bin` + JPEG textures), 2k texture
resolution, per the task's "download the glTF/FBX at 1k-2k textures"
instruction.

**Licence (all Poly Haven assets): CC0 1.0 Universal (public domain).** No
attribution is legally required, but authors are credited below anyway per
Poly Haven's own courtesy convention. Verified via Poly Haven's public
licensing policy (all assets on the site are CC0) and via each asset's own
listing in the `assets?t=models` API response (Poly Haven does not publish a
per-asset license field because it's uniformly CC0 site-wide).

## Assets

### 1. Wooden Cutting Board (`wooden_cutting_board`)

- Poly Haven page: https://polyhaven.com/a/wooden_cutting_board
- Author: Kuutti Siitonen
- Categories: props, food (Poly Haven category: Food & Kitchen/Utensils/Cutting Boards)
- Licence: CC0 1.0
- Downloaded: `wooden_cutting_board_2k.gltf` + `wooden_cutting_board.bin` +
  `textures/wooden_cutting_board_{diff,arm,nor_gl}_2k.jpg`
- Native dimensions (Poly Haven metadata): ~449.9 x 246.7 x 41.3 mm (a single
  board; real-world cutting boards are usually smaller — the asset's stated
  polycount/scale is used as a reference only, scaled to a sane real size on
  import per Task 3's placement notes in `Docs/Props.md`).
- Placement: leaning against the backsplash behind the sink, or lying flat on
  the counter to the right of the sink (see `place_props_wtk.py` /
  `Docs/Props.md`).

### 2. Potted Plant 04 (`potted_plant_04`)

- Poly Haven page: https://polyhaven.com/a/potted_plant_04
- Author: James Ray Cock
- Categories: decorative, plants, potted plants, succulent, nature (Poly
  Haven category: Nature/Plants/Potted Plants)
- Licence: CC0 1.0
- Downloaded: `potted_plant_04_2k.gltf` + `potted_plant_04.bin` +
  `textures/potted_plant_04_{diff,arm,nor_gl}_2k.jpg`
- Description (Poly Haven): small zebra haworthia succulent in a weathered
  ceramic pot. Native dimensions ~170 x 186 x 268 mm — a small, restrained
  accent plant, chosen over the larger potted_plant_01/02 (both ~600-1350mm)
  specifically because it reads as a modest counter/shelf accent rather than
  a dominant floor plant, matching the task's "restrained" instruction.
- Placement: upper floating shelf (FX-05) or the counter's far end (see
  `place_props_wtk.py` / `Docs/Props.md`).

### 3. Wooden Bowl 01 (`wooden_bowl_01`)

- Poly Haven page: https://polyhaven.com/a/wooden_bowl_01
- Author: Oliver Harries
- Categories: props, decorative, dishes (Poly Haven category: Food &
  Kitchen/Tableware/Bowls)
- Licence: CC0 1.0
- Downloaded: `wooden_bowl_01_2k.gltf` + `wooden_bowl_01.bin` +
  `textures/wooden_bowl_01_{diff,arm,nor_gl}_2k.jpg`
- Description (Poly Haven): hand-carved, rustic wooden bowl with irregular
  worn rim, smooth shallow interior, rich aged grain and patina. Used here as
  the "ceramic mug/cup or bowl" prop from the task's list — no plain
  modern mug/cup asset was found on Poly Haven at the time of this search
  (checked model tags/categories for "mug", "cup", "coffee", "ceramic" — the
  only cup-shaped matches were `brass_goblets` and `tea_set_01`, both
  ornate/antique and a poor match for the warm-transitional kitchen's
  restrained look), so a small fruit/utility bowl was substituted, matching
  the task's own "optionally a fruit bowl" allowance.
- Placement: counter near the cutting board, or the floating shelf (see
  `place_props_wtk.py` / `Docs/Props.md`).

## Search notes (for anyone revisiting prop selection later)

Full model listing fetched to
`tmp/Wtk5e_20260926/models_list.json` (543KB, all Poly Haven model assets at
the time of this search) and grepped/filtered by category and tag keywords
(`cutting_board`, `plant`, `bowl`, `mug`, `cup`, `kettle`, `ceramic`,
`ivy`/`herb`). `vintage_electric_kettle` was considered (matches the task's
"optionally... a kettle") but not used, to keep the prop count at 3 restrained
items rather than pushing toward 5 with a more visually assertive metal
appliance that could compete with the B30 feature cabinet for attention.

## Import notes

Import requires the full `UnrealEditor.exe -ExecutePythonScript` path, NOT
`-run=pythonscript` (`AssetToolsHelpers.get_asset_tools().import_asset_tasks()`
touches Slate/ContentBrowser UI code and crashes under the headless
commandlet mode with `Assertion failed: CurrentApplication.IsValid()` — the
same constraint already documented for texture imports in
`Docs/Materials.md`'s "Environment notes" section). See
`05_Unreal/WTK/Scripts/place_props_wtk.py` and `Docs/Props.md` for the import
+ placement script and its results.
