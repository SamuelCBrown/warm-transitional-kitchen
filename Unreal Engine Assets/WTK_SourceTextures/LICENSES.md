# WTK Source Textures — Licenses and Provenance

Phase 5b. All assets below are CC0 (public domain, no attribution legally required, no
account or paid license needed). Downloaded 2026-09-26. Recipe basis:
`Pause\RESEARCH_2026-09-26_WTK_WOOD_CABINET_MATERIALS_LOOP2_LOOP3.md` and
`Pause\RESEARCH_2026-09-26_UE5_ARCHVIZ_KITCHEN_LOOP2_LOOP3.md`.

Normal-map convention note: UE5 expects **DirectX** normals (green channel down /
Y-). Every asset below was downloaded with an explicit DirectX normal file
(`*_NormalDX` / `*_nor_dx`) already provided by the source — no green-channel flip
should be needed at import (5c should still eyeball it against a reference sphere).

---

## 1. OAK — Oak_StainedWarmBrown (B30 doors/rails/stiles, floating shelves)

**Chosen: `white_oak_veneer`** (Poly Haven)
- URL: https://polyhaven.com/a/white_oak_veneer
- Asset ID: `white_oak_veneer`
- License: CC0 1.0 (Poly Haven, no account required)
- Download date: 2026-09-26
- Physical tile size: 500 x 500 mm (0.5 x 0.5 m) per the source's native aspect;
  Poly Haven does not publish an explicit real-world scale for this asset (`scale: null`
  in its API record) — treat 500mm as a working default and verify visually against
  the 2.25 in (57 mm) stile width, per the research doc's guidance to expose a
  tunable tile-size scalar rather than trust the SKU blindly.
- Maps downloaded: Diffuse (Color), Roughness, Normal — DirectX convention
  (`white_oak_veneer_nor_dx_4k.jpg`) — at 4K (per task's "4K for oak if available and
  reasonable" allowance; ~30 MB total for 3 maps).
- Normal convention: DirectX (green down). A GL variant also exists on the source if
  ever needed.
- Path: `Oak/white_oak_veneer/`
- Why chosen: straight, even, linear grain with minimal ray fleck or cathedral
  figure — matches the corrected RIFT-SAWN white oak decision exactly. No visible
  plank seams (raw veneer sheet, not assembled planks), so it tiles cleanly across
  stiles/rails/panel without a seam artifact. Light, warm-neutral base tone suits a
  stain-tint layer without fighting an existing color cast.

**Backup / runner-up: `oak_veneer_05`** (Poly Haven)
- URL: https://polyhaven.com/a/oak_veneer_05
- License: CC0 1.0
- Download date: 2026-09-26
- Maps: Diffuse, Roughness, Normal (DirectX) at 2K
- Path: `Oak/oak_veneer_05/`
- Why kept as backup, not primary: slightly more visible warm grain figure than
  white_oak_veneer — good fallback if the primary reads too flat/plain once stained
  and lit, per the pre-mortem risk in the research doc ("rift-sawn texture reads too
  plain/flat").

**Rejected candidates:**
- `oak_veneer_01` (Poly Haven) — pronounced wavy/cathedral figure and a redder,
  darker cast; violates the "minimal ray fleck / rift look" requirement.
- `oak_veneer_02`, `03`, `04` (Poly Haven) — grain almost invisible at texture scale;
  kept as a mental fallback but not downloaded, since white_oak_veneer already
  strikes the balance between "straight/rift" and "still has visible grain."
- `Wood049` (ambientCG, only true "oak"-tagged material in ambientCG's catalog) —
  visually darker/redder with tighter grain than desired; ambientCG's catalog has no
  dedicated white-oak or rift/quartersawn-specific SKU (confirms the research doc's
  T1 gap finding), so Poly Haven's dedicated oak-veneer series was preferred.
- `Wood083A` (ambientCG) — light and straight-grained but shows visible plank
  seams/butt joints unsuitable for a continuous stile/rail/panel surface.

---

## 2. PAINT — Paint_WarmIvory micro-detail (roughness/normal only; base color is a
constant ivory set in-engine, per the recipe)

**Chosen: `white_plaster_02`** (Poly Haven)
- URL: https://polyhaven.com/a/white_plaster_02
- Asset ID: `white_plaster_02`
- License: CC0 1.0
- Download date: 2026-09-26
- Physical size: 1.5 m x 1.5 m (per source: "scale": "1.5M x 1.5M")
- Maps downloaded: Diffuse, Roughness, Normal (DirectX) at 2K
- Normal convention: DirectX (green down)
- Path: `Paint_WallPlaster/white_plaster_02/`
- Why chosen: "smooth, flat white plaster with a soft matte finish, fine
  micro-roughness and subtle dirt speckling" per the source description — exactly
  the low-contrast, near-invisible bump the recipe calls for (only roughness/normal
  matter; base colour is overridden). Reused for the WALL slot too (see 5. below) —
  one CC0 asset covers both, since both call for the same "subtle painted surface,
  low contrast" brief.

**Rejected candidates:**
- ambientCG's entire `Paint00X` family (`Paint001/002/004/005`) — all tagged
  "cracks, reflective, shiny"; these are dramatic cracked/glossy lacquer finishes,
  not a fine orange-peel satin. Visually confirmed via thumbnail (see contact
  sheet history) — rejected outright.
- ambientCG's `PaintedPlaster0XX` family — all weathered/dirty/damaged/discolored;
  wrong condition for a clean satin-ivory cabinet finish.
- No ambientCG or Poly Haven asset is literally tagged "orange peel"; per the
  research doc this was already flagged as requiring a generic, non-wood-specific
  bump texture rather than a purpose-built SKU — `white_plaster_02`'s fine, even
  micro-roughness satisfies that role.

---

## 3. STONE — Stone_HonedCream (Cambria Everleigh Warm proxy)

**Chosen: `Marble020`** (ambientCG)
- URL: https://ambientcg.com/view?id=Marble020
- Asset ID: `Marble020`
- License: CC0 1.0 (ambientCG, no account required)
- Download date: 2026-09-26
- Physical size: ambientCG does not publish explicit real-world dimensions for this
  material in its API metadata (`dimensionX/Y` were 0 in the search index for this
  ID); treat as a standard ~1–2 m seamless tile and verify scale against the
  30 mm-thick counter run in-engine.
- Maps downloaded: Color, Roughness, Normal (both `NormalDX` and `NormalGL`
  provided), Displacement — at 2K-JPG.
- Normal convention: DirectX (`Marble020_2K-JPG_NormalDX.jpg`); a GL variant is also
  present in the folder if needed.
- Path: `Stone/Marble020/`
- Why chosen: warm cream base with soft, low-contrast tan/gray veining — the closest
  visual match among all candidates to Cambria Everleigh Warm's warm-cream-with-soft-
  veining look. Confirmed via contact-sheet comparison against Poly Haven's
  `marble_01`, `marble_tiles`, and `terrazzo_tiles`.

**Rejected candidates:**
- `Marble012` (ambientCG) — cooler gray-white base with high-gloss preview render;
  veining reads too blue/cold against the warm-cream target.
- `Marble016` (ambientCG) — near-black marble with dramatic white veining; wrong
  value range entirely.
- `Marble021` (ambientCG) — nearly pure white with very faint veining; too cold/pale,
  lacks the warm cream base.
- `marble_01` (Poly Haven) — comes pre-textured as cut floor tiles with visible tile
  seams; wrong pattern for a continuous counter/backsplash slab.
- `marble_tiles` (Poly Haven) — same tiled-pattern problem as above.
- `terrazzo_tiles` (Poly Haven) — speckle is too coarse/brown and busy; the brief
  calls for "very subtle" speckle, and this reads as a much bolder terrazzo.
- No dedicated "quartz" or "engineered stone" SKU exists on either ambientCG or Poly
  Haven (confirmed via direct catalogue search) — consistent with the research doc's
  note that generic natural-stone scans must stand in for engineered quartz.

---

## 4. METAL — Metal_SatinBrass (tint target) / Steel_Brushed

**Chosen (linear brushed, for pulls/faucet, tint-to-brass or use as steel):
`Metal009`** (ambientCG)
- URL: https://ambientcg.com/view?id=Metal009
- License: CC0 1.0
- Download date: 2026-09-26
- Maps downloaded: Color, Roughness, Metalness, Normal (`NormalDX` + `NormalGL`),
  Displacement — at 2K-JPG.
- Normal convention: DirectX (`Metal009_2K-JPG_NormalDX.jpg`)
- Path: `Metal_Brushed/Metal009/`
- Why chosen: tagged "brushed, bumpy, scratches, silver, steel" with a clean linear
  anisotropic streak visible in the preview sphere — feed its normal map into the
  material's Tangent input (per the recipe's Anisotropy+Tangent approach) for both
  brushed steel (used directly, cool gray-tinted F0) and satin brass (recolor the
  Base Color/F0 to a warm gold-tan tint, reuse the same normal/roughness).

**Chosen (radial/circular brushing, for round brass knobs): `Metal051A`**
(ambientCG)
- URL: https://ambientcg.com/view?id=Metal051A
- License: CC0 1.0
- Download date: 2026-09-26
- Maps downloaded: Color, Roughness, Metalness, Normal (DX+GL), Displacement — 2K-JPG
- Normal convention: DirectX
- Path: `Metal_Brushed/Metal051A/`
- Why chosen: tagged "aluminum, brushed, circular" — its lathe-turned circular
  brushing pattern is a ready-made alternative to hand-authoring a radial tangent
  map for the round knobs, exactly as the research doc suggests (Substance
  Painter's "Anisotropic Radial" generator was the other option; this is a
  pre-made equivalent).

**Rejected candidates:**
- No "brass" material exists on either ambientCG or Poly Haven's catalogue
  (confirmed via direct API search) — consistent with the research doc's plan to
  tint a generic brushed metal rather than source a literal brass scan.
- `Metal048A` (ambientCG) — highly polished/mirror gold ball in preview; reads as
  polished brass, not satin/brushed — wrong roughness character for the brief's
  "satin/brushed brass" target.
- `Metal055A`, `Metal061B` (ambientCG) — tagged "iron"/"cobalt" respectively, with
  smoother, less directionally-brushed highlights than Metal009; kept as mental
  fallbacks but not downloaded.
- Poly Haven has no dedicated "brushed metal" material in its texture catalogue
  (only "brushed concrete" hits on a tag search) — ambientCG was the only viable
  CC0 source for this slot.

---

## 5. WALL — Wall_WarmOffWhite (subtle painted wall/plaster)

**Chosen: `white_plaster_02`** (Poly Haven) — same asset as slot 2 (Paint), reused.
- See entry 2 above for full details (URL, license, maps, path).
- Why reused rather than sourcing a second asset: the brief's own wording flags
  this slot as "optional, low contrast" and describes the same character as the
  paint micro-detail slot (a subtle, low-contrast painted surface). Rather than
  introduce a second unnecessary CC0 download, the same fine, even, matte plaster
  scan serves both the cabinet-paint bump layer and the wall/ceiling surface —
  tinted differently (ivory vs. warm off-white) at the material-instance level in
  5c, per the recipe's approach of driving color via a constant/tint layer rather
  than the source texture's own color.

---

## 6. FLOOR — Floor_OakNatural (per Design_Brief.md: #B19372, subdued grain,
6-inch-wide boards running into the room)

**Chosen: `WoodFloor051`** (ambientCG)
- URL: https://ambientcg.com/view?id=WoodFloor051
- Asset ID: `WoodFloor051`
- License: CC0 1.0
- Download date: 2026-09-26
- Physical size: ambientCG lists this asset's dimensions as 180 x 180 (cm) in its
  catalogue index — verify against the brief's 6-inch (15.24 cm) board width when
  tiling (each plank appears to be a fraction of the 180 cm tile width; confirm
  visually or adjust UV scale to match the 6 in module).
- Maps downloaded: Color, Roughness, Normal (DX+GL), AmbientOcclusion, Displacement
  — at 2K-JPG.
- Normal convention: DirectX (`WoodFloor051_2K-JPG_NormalDX.jpg`)
- Path: `Floor/WoodFloor051/`
- Why chosen: light-to-mid warm plank tone with subdued, straight grain and clean
  parallel boards (no herringbone/parquet pattern) — closest visual and tonal match
  to the brief's Floor_OakNatural (#B19372) among all wood-floor candidates
  compared.

**Rejected candidates:**
- `WoodFloor062` (ambientCG) — close second; slightly more saturated
  orange/yellow cast than WoodFloor051.
- `plank_flooring`, `plank_flooring_02` (Poly Haven) — one reads as a dark,
  patchwork parquet with strong contrast between boards (too busy/dark); the other
  has visible dark knots/mineral streaks inconsistent with "subdued grain."
- `wood_floor` (Poly Haven) — attractive but noticeably darker/higher-contrast
  than the brief's #B19372 mid-light target.

---

## 7. HDRI — soft daylight exterior for window view / sky reflection

**Chosen: `farmland_overcast`** (Poly Haven)
- URL: https://polyhaven.com/a/farmland_overcast
- Asset ID: `farmland_overcast`
- License: CC0 1.0
- Download date: 2026-09-26
- Resolution downloaded: 4K (`.hdr`, 25.7 MB)
- Path: `HDRI/farmland_overcast/farmland_overcast_4k.hdr`
- Why chosen: bright, soft, evenly overcast sky over a green field — gives clean,
  diffuse, shadowless fill light appropriate for a suburban kitchen window view
  without introducing a distracting dramatic sky, mountain silhouette, or strong
  directional sun that would compete with the interior lighting rig.

**Rejected candidates:**
- `kloofendal_overcast`, `kloofendal_48d_partly_cloudy` — attractive but include a
  rocky/scrubland horizon (savanna-like terrain) that reads as a specific dramatic
  landscape rather than a neutral suburban garden backdrop.
- `killesberg_park` — has a strong foreground retaining-wall/stair structure that
  would read as an odd, specific piece of architecture through a kitchen window.
- `garden_nook` — nice greenery but a busy foreground tree trunk/branch silhouette
  right at camera height; distracting for a background window view.

---

## 8. HDRI (path-tracer pass, 2026-09-27) — clear-sky exterior for the hero/alt_soft window view

**Chosen: `sunny_vondelpark`** (Poly Haven)
- URL: https://polyhaven.com/a/sunny_vondelpark
- Asset ID: `sunny_vondelpark`
- License: CC0 1.0 (Poly Haven, no account required)
- Download date: 2026-09-27
- Resolution downloaded: 4K (`.hdr`, ~28 MB, direct CDN download confirmed
  200 OK / Content-Length 29318417 bytes from
  `https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/sunny_vondelpark_4k.hdr`)
- Path: `HDRI/sunny_vondelpark/sunny_vondelpark_4k.hdr`
- Why added: the task's orchestrator review flagged the window exterior as "a
  pale grey void with no landscape" and the hero/alt_soft presets were both
  using `farmland_overcast.hdr` (an overcast sky, chosen originally for its
  soft, shadowless fill) — wrong sky character for a hero look meant to read
  as a bright, clear, sunlit day matching the 65,000 lux clear-sun rig.
  `sunny_vondelpark` is a clear-sky, sunny park/tree-line HDRI with visible
  ground/foliage detail and blue sky, giving the window a believable, bright
  exterior distinct from the overcast preset's own HDRI. `farmland_overcast`
  is kept, unchanged, as the dedicated overcast-preset backdrop (task's
  Variant D).

## 9. BACKPLATE (realism pass, 2026-09-28) — exterior tree/garden card for the window view, Look A

**Chosen: `suburban_garden`** (Poly Haven), tonemapped JPG render, cropped

- URL: https://polyhaven.com/a/suburban_garden
- Asset ID: `suburban_garden`
- License: CC0 1.0 (Poly Haven, no account required)
- Download date: 2026-09-28
- Source file: the asset's own published "Tonemapped JPG" full equirectangular
  render (`https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Tonemapped%20JPG/suburban_garden.jpg`,
  8192x4096, ~48.9 MB) — this is Poly Haven's own LDR photographic render of
  the HDRI capture, still CC0, not a separately-licensed photo.
- Processing (this pass, `tmp/WtkRealism_20260928/`, not a network asset):
  cropped a horizontal band (28%-72% of the panorama's height, i.e. mostly
  foliage/ground with a strip of sky, avoiding the zenith/nadir stitching
  poles) at longitude offset x=2048px (1/4 turn from the panorama's front),
  width 1.7x the crop height, then downsampled to 2048x1204 JPG (quality 92).
  This specific crop was chosen (out of 4 previewed longitude offsets) for
  showing a large well-lit tree, a trimmed hedge/flowerbed line, and open blue
  sky with no black/void edges, fence-post lines, or building rooflines
  dominating the frame — the most "believable garden glimpsed through a
  kitchen window" composition of the 4 candidates.
- Path: `Backplate/WTK_ExteriorBackplate.jpg` (2048x1204 JPG)
- Used by: `Scripts/setup_lighting_wtk.py`'s `setup_window_backplate()` —
  a large (~14m wide) unlit-emissive plane, `WTK_WindowBackplate`, placed
  ~12m outside the window facing into the room, sized/positioned to fill the
  view through all 3 cameras (see Lighting.md Section 20 for the full
  geometry/emissive-level derivation and the room-brightness-impact
  verification).

## Download summary

| Slot | Asset | Source | Res | Approx. size |
|---|---|---|---|---|
| Oak (primary) | white_oak_veneer | Poly Haven | 4K (3 maps) | ~30 MB |
| Oak (backup) | oak_veneer_05 | Poly Haven | 2K (3 maps) | ~6.5 MB |
| Paint/Wall | white_plaster_02 | Poly Haven | 2K (3 maps) | ~7.6 MB |
| Stone | Marble020 | ambientCG | 2K-JPG (5 maps) | ~12 MB |
| Metal (linear) | Metal009 | ambientCG | 2K-JPG (6 maps) | ~17 MB |
| Metal (radial) | Metal051A | ambientCG | 2K-JPG (6 maps) | ~9 MB |
| Floor | WoodFloor051 | ambientCG | 2K-JPG (6 maps) | ~16 MB |
| HDRI | farmland_overcast | Poly Haven | 4K .hdr | ~25.7 MB |
| Backplate | suburban_garden (tonemapped, cropped) | Poly Haven | 2048x1204 JPG | ~1.1 MB |

**Total on-disk size of `05_Unreal/WTK_SourceTextures/`: ~119 MB** (53 files,
including each ambientCG asset's bundled `.blend`/`.mtlx`/`.tres`/`.usdc`
convenience files and a 512px catalogue thumbnail `.png`, which ship inside the
ambientCG zip alongside the JPG maps and were left in place rather than
hand-pruned).

All eight slots requested by the task are covered (Oak, Paint, Stone, Metal x2
purposes from one pair of assets, Wall reusing the Paint asset, Floor, HDRI).
