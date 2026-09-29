# WTK Unreal Engine 5 Reference Notes — Phase 5/6 Prep

Compiled from the private research corpus at `Pause\Books` and `Pause\11_books_research`
(pre-extracted page/section text). Scope: Lumen lighting, PBR materials, cinematic
post-process/exposure, CineCamera/DOF, and Movie Render Queue, mapped onto the WTK
kitchen scene (12x14 ft interior, one 30x36 in window, under-cabinet LED, stained oak +
painted cabinets, brass hardware).

---

## 1. Inventory

### Pause\Books (source PDFs/EPUBs) — relevant to UE5/PBR/lighting/cinematics

| File | Type | Verdict |
|---|---|---|
| *Cinematic Photoreal Environments in Unreal Engine 5* — Giovanni Visai (2024, Packt) | EPUB | **Primary source.** Full UE5 5.3 archviz/cinematic pipeline: PBR materials, Lumen lighting, post-process, Sequencer/CineCamera, Movie Render Queue. Read in full for Ch. 5, 6, 11, 12, 13. |
| *Building Open World Landscapes with Unreal Engine 5* — García & Olivero (2025, Packt) | PDF | Secondary. Mostly landscape/terrain/Nanite/World Partition — not interior-relevant. Skimmed TOC and grep hits; nothing added beyond Cinematic Photoreal book for our scope. |
| *Unreal Engine 5 Shaders and Effects Cookbook*, 2nd ed. — Brenlla Ramos & Pimentel (2023, Packt) | PDF | Secondary/not read in depth. Covers custom shaders/Niagara VFX — outside Phase 5/6 scope (no custom HLSL needed for a kitchen archviz shot). Flagged for a later pass only if custom glass/refraction shaders are needed. |
| *Unreal Engine 5 Game Development with C++ Scripting* — Li & Roberts (2023, Packt) | PDF | Not relevant — C++/gameplay programming, no rendering/lighting/materials content for archviz. |
| *GAME DEVELOPMENT PATTERNS WITH UNREAL ENGINE 5* — Butler & Oliver (2023, Packt) | EPUB | Not relevant — software design patterns (ECS, behavior trees, double buffering) for gameplay code. No materials/lighting/cinematics content. |
| *Real-Time Rendering*, 4th ed. — Akenine-Möller, Haines, Hoffman (2023) | EPUB | Not read in depth this pass (large, low pages-per-topic ratio, EPUB by spine section only). Deep GI/AA/BRDF theory exists here if more rigor is wanted later; the practical UE5 book above already gives actionable settings. |
| *Physically Based Rendering*, 4th ed. — Pharr, Jakob, Humphreys (2023) | PDF | Not relevant to practical UE5 workflow — this is an offline path-tracer textbook (pbrt), not UE5-specific. Skipped. |
| *The PBR Guide Part 1: Light and Matter* — Wes McDermott (Allegorithmic/Substance, 2019) | PDF | **Secondary source**, read for metal/dielectric reflectance theory (Fresnel F0, energy conservation). Predates UE5; theory is engine-agnostic and still valid. |
| *The PBR Guide Part 2: Practical Guidelines* — Wes McDermott (2019) | PDF | **Secondary source**, read for metal/roughness workflow guidelines (base color = black for raw metal, dielectric F0 ≈ 0.04/4%, brightness ranges). Directly informs brass hardware and glass values below. |
| *Color and Light: A Guide for the Realist Painter* — James Gurney (2010) | PDF (OCR derivative exists at `11_books_research/ocr/Color_and_Light_OCR.pdf`) | Not read — traditional oil-painting light/color theory (studio lighting analogies), not UE5-specific. Tangential at best for color-grading intuition; skipped given time budget. |
| *[digital] modeling* — William Vaughan (2012) | PDF | Not relevant — 3ds Max/UV modeling book, pre-PBR era, no UE5 content. |
| *Game Engine Architecture*, 3rd ed. — Jason Gregory (2018) | EPUB | Not relevant — general engine architecture (not UE5-specific rendering pipeline settings). |
| *3D Math Primer*, *Blender/Python scripting books*, *Creating High-Quality Vegetation for Games*, GIS/surveying/golf/land-development titles | Various | Not relevant to Phase 5/6 (off-topic domains: math primer, Blender scripting, vegetation, GIS, civil engineering, golf course design). |

### Pause\11_books_research (extracted corpus)

This folder is **not a separate set of books** — it is a pre-extracted, page/section-level
markdown corpus of the exact same files listed above (`inventory.json` and
`source_catalog.json` map each `source_id`/sha256 to a `book-<hash>/pages/*.md` or
`book-<hash>/sections/*.md` directory; PDFs → `pages`, EPUBs → `sections`). No additional
research notes or markdown files relating to UE5 exist in this folder beyond the extracted
book text itself; `ocr_derivatives.json` only documents the Gurney OCR pass. No inaccessible
(DRM'd or image-only-scan) sources were encountered — all PDFs/EPUBs used had extractable
text.

---

## 2. Version flag

The primary source (*Cinematic Photoreal Environments in UE5*, 2024) is written against
**UE 5.0–5.3** (explicitly states "In this book, we will use version 5.3.1"). The project
plan targets a presumably newer engine (5.7 context implied by the task). Flag the
following as **likely to have changed or been renamed by 5.7** and verify in-editor:

- Lumen Project Settings layout ("Use Hardware Ray Tracing when available", "Support
  Hardware Ray Tracing") — these toggles have been consolidated/renamed across 5.x releases;
  confirm exact labels in your version's Project Settings > Rendering > Global Illumination.
- Nanite/Lumen defaults: newer versions enable Lumen by default more aggressively and have
  improved software Lumen quality (Hardware Ray Tracing is optional, not required — this
  still holds true in 5.7).
- Movie Render Queue UI has been iterated release-to-release (job panel, console variable
  search) but the core workflow (add render, choose Deferred Rendering, choose export
  format, set anti-aliasing samples, set output resolution) is stable across 5.0–5.7.
- Path Tracer, Sky Atmosphere/Sky Light, CineCameraActor, and PPV Local Exposure settings
  described below are stable APIs unlikely to have changed materially by 5.7.

---

## 3. Phase 5 guidance: Lumen, materials, lighting

### Lumen GI/reflections setup
- Enable in Project Settings > Rendering > Global Illumination: **Use Hardware Ray Tracing
  when available** and **Support Hardware Ray Tracing** if an RTX-class GPU is available;
  Lumen requires **DirectX 12** and (in 5.3) **SM6** shader format. Software Lumen (no RT
  hardware) still works and is the fallback. *(Cinematic Photoreal Environments in UE5,
  Ch. 6, "Setting projects up to use Lumen")*
- Lumen replaces baked lightmaps; for a cinematic single-shot interior, use fully **movable**
  lights (no light-baking needed) — real-time GI updates as you adjust anything, at some
  perf cost that doesn't matter for offline MRQ rendering. *(Ch. 6, "Lighting movability")*
- Use the **Env. Light Mixer** tool (Windows menu) as a starting point for any interior
  daylight setup — it auto-creates Sky Light, Directional Light, Sky Atmosphere, Exponential
  Height Fog, and Volumetric Cloud in one click, pre-wired so rotating the Directional Light
  drives time-of-day. *(Ch. 6, "Step 1: Creating base lighting")*
- Shadow quality: Lumen defaults to **Virtual Shadow Maps**; for smoother/softer shadows
  (e.g., soft daylight through a window), set the light's **Cast Ray Traced Shadows** to
  Enabled (requires Support Hardware Ray Tracing). *(Ch. 6, "Improving shadow quality")*
- Emissive materials contribute to Lumen GI in real time — useful for simulating bounce
  light from the under-cabinet LED strip if modeled as a thin emissive strip rather than
  (or in addition to) a Rect Light. *(Ch. 6, "Illuminating with emissive materials")*

### Light types and settings (mapped to WTK)
- **Directional Light**: simulates the sun; use **Source Angle ≈ 0.53°** default (real sun
  angle) for hard-ish but naturally soft shadows; enable **Use Temperature**, default
  6500 K = white; lower Kelvin = warmer, raise = cooler. Align its rotation to any HDRI's
  sun direction if an HDRI backdrop is used outside the window. *(Ch. 6, "Directional
  Light")*
- **Rect Light**: the *correct* light type for (a) light coming through the 30x36 in window
  opening and (b) the under-cabinet LED strip. Scale **Source Width/Height** to the window
  opening (or LED strip length); bigger source = softer shadow, but **increase Intensity**
  to compensate for apparent brightness falloff as source size grows. *(Ch. 6, "Rect
  Light")*
- **Point Light / Spot Light**: less relevant for this scene except possibly a small accent
  spot; note **Intensity Units** can be switched to **Lumens** or **Candelas** for
  architecturally realistic photometric values (useful if matching a real LED spec sheet in
  lumens). IES profiles (from ieslibrary.com) can simulate realistic fixture beam shapes if
  wanted for the under-cabinet strip. *(Ch. 6, "Point Light", "Spot Light")*
- **Sky Light**: needed for ambient fill/GI from the exterior visible through the window.
  **Sky Distance Threshold** must be lowered from the 150,000-unit default to actually
  capture a small interior scene — set it low (e.g., 1–500) so it captures the room/exterior
  properly rather than treating everything as "inside" the threshold sphere and going dark.
  Can alternatively feed an HDRI via **SLS Specified Cube Map**. *(Ch. 6, "Sky Light")*
- **Volumetric Scattering Intensity** on the Directional Light (try 5–10, paired with
  **Exponential Height Fog** density ~0.02 and **Volumetric Fog** enabled) creates visible
  god-rays through the window — a nice-to-have, not essential for a clean kitchen shot, but
  cheap to add for atmosphere. *(Ch. 6, "Step 3: Adding God rays")*
- **Lighting Channels** let specific lights affect only specific objects — could be used to
  isolate the under-cabinet LED's influence if it's causing unwanted spill.

### Exposure
- **Disable Auto Exposure** in Project Settings (or set PPV Metering Mode to **Manual**,
  Exposure Compensation starting at 0) for a controlled, repeatable look rather than the
  camera "auto-adjusting" as it moves through the small room. *(Ch. 6, "Step 2: Managing
  exposure")*
- Place one **infinite/unbound Post Process Volume** (check "Infinite Extent (Unbound)")
  covering the whole level so exposure/color settings apply everywhere, then adjust
  **Exposure Compensation** by eye. *(Ch. 6, "Step 2")*
- Reference albedo values for calibration: true black ≈ 0.04, true white ≈ 0.85 (fresh snow
  is ~0.8–0.9), mid-gray card ≈ 0.18 (not 0.5 — human exposure perception is logarithmic in
  stops). Placing "helper" spheres (black/gray/white/chrome) in-scene is a good sanity check
  before finalizing exposure. *(Ch. 6, "Exploring the Directional Light Details panel")*

### PBR material authoring (stained oak / warm-ivory paint / cream stone / satin brass / glass / brushed steel)
- UE5 PBR primary inputs: **Base Color** (never pure 0 or pure 1), **Metallic** (binary
  0/1 in practice — this is a material *category* choice, not a dial), **Roughness**
  (0 = mirror, 1 = matte; the main knob for perceived material "feel"), **Specular**
  (leave at default 0.5 unless stylizing). *(Cinematic Photoreal Environments, Ch. 5,
  "Primary PBR inputs")*
- **Metal/roughness workflow guidance from The PBR Guide Part 2** (applies to satin brass
  hardware and brushed steel):
  - Base Color for **raw/bare metal areas should be near-black (0.0)** — metal has no
    diffuse/albedo color, its color comes entirely from specular reflectance tinting.
    Any warmth/color on "brass" comes from the Base Color acting as the *reflectance
    tint* on a Metallic=1 surface, not from a painted diffuse color.
  - Dielectric (non-metal) surfaces default to **F0 ≈ 0.04 (4% reflectivity)**,
    hard-coded in UE5's metal/roughness shading model — this is why "Specular" stays at
    0.5 by default and rarely needs touching for painted cabinets, stone, or oak.
  - Base color brightness ranges (measured-data guideline): dark values not below
    ~30–50 sRGB, bright values not above ~240 sRGB — avoid pure black/white base color
    textures for any material, including the warm-ivory paint and cream stone.
  - Roughness is the primary differentiator between **satin brass** (mid roughness,
    ~0.3–0.45, soft directional highlight) and **polished/brushed steel** (brushed = fine
    anisotropic-looking streaks from a directional roughness map or normal detail rather
    than pure roughness value; a plain brushed-steel *look* without true anisotropic
    shading can be approximated with a subtle streaked normal/roughness texture plus
    roughness ~0.2–0.35).
- **Glass**: set **Blend Mode = Translucent** on the material (Material Domain stays
  Surface); this exposes an Opacity input and disables several opaque-only inputs. For a
  window pane, a low-roughness, slightly tinted, translucent material with the Fresnel
  effect handled by UE5's default translucent lighting model is the standard approach; keep
  Metallic = 0, Roughness low (~0.05–0.1) for clean panes. *(Cinematic Photoreal
  Environments, Ch. 5, "Material Domain"/"Blend Mode"; the dust Niagara material in Ch. 12
  demonstrates the same Translucent + Opacity-from-Alpha pattern.)*
- **Master Material + Material Instances** workflow (strongly recommended over one-off
  materials per surface): build one Master Material with texture-sample parameters (Base
  Color/Roughness/Normal/AO, or a packed ORDp/ARM-style texture), expose **Tiling U/V** and
  **Panning U/V** parameters via a TextureCoordinate → Multiply/AppendVector → Add node
  chain feeding every Texture Sample's UV input, and a **FlattenNormal** node (Normal +
  Flatness scalar) to dial normal-map intensity per instance. Convert constants to
  **parameters** (right-click > Convert to Parameter), organize into numbered groups
  (`01_Textures`, `02_Color`, `03_UVs`, `04_Physical`) so they sort predictably in the
  Material Instance editor. Use a **StaticSwitchParameter** ("Metallic?") to let one Master
  Material serve both metal and non-metal instances (stained oak vs. brass hardware) from a
  single graph. *(Ch. 5, "Creating a Master Material", steps 1–8)*
- **Texture scale / grain direction** (oak specifically): control tiling via the UV
  parameter chain above so wood grain repeats can be scaled per-instance without re-export;
  grain **direction** is controlled by rotating UVs (an additional rotation node before the
  tiling multiply, or by re-orienting the texture's UV unwrap on the mesh) — the book's UV
  system as described only covers tiling/panning, not rotation, so add a
  `Custom Rotator` or `TexCoord Rotate` material function if grain needs to run a specific
  way on cabinet doors vs. countertop edges.
- Recommended texture set per surface (from the ORDp/Megascans convention referenced in
  Ch. 5): Base Color (D), Roughness (R stored in green channel of a packed ORDp texture),
  AO (red channel), optional Displacement (blue channel), plus a separate Normal map. Naming
  convention: `T_Name_TextureType` (B/R/N/AO/M/D), materials as `M_Name` (master) and
  `MI_Name` (instance). *(Ch. 3, "Using a clear naming convention"; Ch. 5)*

---

## 4. Phase 6 guidance: CineCamera, DOF, Movie Render Queue, AA

### CineCameraActor
- Place via Place Actors > Cinematic, or use **Create Camera Here** from the Level
  Viewport's hamburger menu (be sure to pick **Cine Camera Actor**, not the plain Camera
  Actor). Enter **Pilot** mode (Viewport Mode menu > Placed Cameras) and enable the camera
  icon to see exactly through its lens; enable **Cinematic Viewport** to preview at the
  camera's true sensor aspect ratio instead of the editor viewport's aspect ratio.
  *(Cinematic Photoreal Environments, Ch. 11)*
- **Filmback** (sensor size) should be chosen first — it changes both the framing and how
  the lens/focal length reads. For an interior kitchen shot, a real digital-cinema sensor
  preset (e.g., a Super 35 preset) is a reasonable default; a custom sensor is also fine.
- **Current Focal Length**: wide shot ≈ 20–40 mm, medium shot ≈ 35–85 mm, close-up ≈ 80 mm+.
  For a 12x14 ft kitchen, a wide-to-medium lens (24–35 mm) will likely be needed to fit the
  cabinet run/island in frame without excessive distortion; test in Pilot mode.
- **Depth of Field**: Focus Method = Manual; set **Manual Focal Distance** to the subject
  distance; use **Draw Debug Focus Plane** to visualize the exact focus plane in-viewport;
  **Current Aperture** (f-stop) controls DOF strength — lower f-stop = shallower DOF/more
  background blur. For an archviz still/short cinematic emphasizing the whole cabinet wall,
  a higher f-stop (e.g., f/8–f/16) keeps more of the room in focus; a lower f-stop (f/2.8–f/4)
  isolates a detail (e.g., brass pull hardware) with background blur.
- **Rule of thirds overlay**: enable via the Cinematic Tools grid icon (Grid 3x3) in the
  Level Viewport for composition. *(Ch. 11, "Exploring framing fundamentals")*

### Post-process / exposure (Phase 5+6 overlap)
- PPV **Bloom**, **Vignette** (0.2–0.4 typical), and **Local Exposure** (Highlight/Shadow
  Contrast Scale, Detail Strength) are the most useful artistic controls for a clean interior
  archviz look — avoid overdoing Chromatic Aberration/Lens Flares/Film Grain for a clean
  product-style kitchen render. **Color Grading > Temperature** (White Balance method,
  Kelvin slider) is the fastest way to push the shot warmer/cooler without touching any
  light asset. *(Ch. 12, "Exploring PPV settings")*
- A **Color LUT** can be authored externally (Photoshop, starting from Epic's neutral LUT
  PNG) and applied via PPV > Color Grading LUT if a specific graded look is wanted beyond
  in-engine color grading; optional for this project.

### Movie Render Queue (target: 3840x2160)
- Enable the **Movie Render Queue** plugin (Edit > Plugins) and restart. Open via Window >
  Cinematics > Movie Render Queue, or via the Sequencer's render-method dropdown (which
  auto-adds the open Level Sequence as a job). *(Ch. 13, "Discovering the Movie Render
  Queue plugin")*
- Before rendering: make sure **Camera Cuts** in the Level Sequence records the intended
  CineCameraActor(s), **Lock Viewport to Camera Cuts** is enabled, the Level Sequence is
  placed in the Level (visible in Outliner) with **Auto Play** checked, and the green/red
  Timeline range bars bound exactly the frames to render.
- Recommended render settings (delete Movie Render Queue's default settings and rebuild
  explicitly):
  - **Rendering type**: Deferred Rendering (standard real-time-quality output; Path Tracer
    is the offline-quality alternative if maximum GI fidelity is wanted at the cost of much
    longer render times — viable for a small static interior scene given no animation).
  - **Export format**: PNG sequence for most cases (good quality/size balance); EXR
    (16-bit) if compositing/color work will happen outside UE5.
  - **Output Resolution**: set explicitly to **3840x2160** (UE5 default is 1920x1080 — must
    be changed).
  - **Anti-Aliasing**: add the Anti-Aliasing setting; **Spatial Sample Count = 1**,
    **Temporal Sample Count** up to **16** (or higher, e.g., 32–64, for a static/slow camera
    move where render time matters less) is the book's recommended balance for a
    dynamic/moving shot. If a warning appears that Temporal x Spatial exceeds
    `r.TemporalAASamples`, either raise that CVar or check **Override Anti Aliasing**.
  - **Render/Engine Warm Up Count**: ~32 frames each, to avoid auto-exposure/effects
    popping in the first rendered frames.
  - **Console Variables** worth adding for interior quality: `r.MotionBlurQuality=4`,
    `r.DepthOfFieldQuality=4`, `r.BloomQuality=5`, `r.ShadowQuality=5`; if volumetric fog is
    used for window god-rays, also `r.VolumetricFog.GridSizeZ=256`,
    `r.VolumetricFog.GridPixelSize=2`, `r.VolumetricFog.TemporalReprojection=1`.
  - **Game Overrides**: add this setting as-is (forces max quality, ignores scalability
    settings) — always include for final renders.
  - **Use Custom Frame Rate**: enable and set to match the Level Sequence's native frame
    rate to avoid timing drift.
  - Save the finished config as a named preset (e.g., `4k_PNG_TAA_32`) for repeatable
    re-renders as the scene is iterated.
  *(Ch. 13, "Setting up a render")*
- **Letterboxing**: if the CineCameraActor's custom sensor aspect ratio doesn't match
  16:9 at 3840x2160, a black letterbox will appear in the output — either match the
  Filmback aspect ratio to 16:9, or crop/resize in post if a non-16:9 look is intentional.
  *(Ch. 13, "Exporting the final shot")*
- Real-time vs. offline framing: MRQ output is *not* identical to the real-time Level
  Viewport preview — it re-renders each frame at the configured AA/quality settings, so
  final quality will exceed what's seen live in the editor. *(Ch. 13, "Fundamentals of
  real-time rendering")*

---

## 5. Applicability to WTK — recommended Phase 5 defaults

Scene: 12x14 ft interior kitchen, one 30x36 in window, single under-cabinet LED run,
stained white oak + warm-ivory painted cabinets, honed cream stone counters, satin brass
hardware, glass (window + maybe cabinet fronts), brushed steel (appliances/fixtures).

- **Lumen**: enable both Hardware Ray Tracing options if the workstation has an RTX GPU;
  otherwise leave software Lumen — a single static interior room is well within software
  Lumen's comfort zone. Confirm DirectX 12 + SM6 project settings.
- **Sky Light**: set **Sky Distance Threshold low** (start ~50–200, not the 150,000 default)
  since the "exterior" visible through a single small window is close/simple — this is the
  single most common "why is my interior black" mistake per the source material.
- **Directional Light**: rotate to **~15° elevation** per the plan's spec (low, warm
  late-day/morning angle appropriate for a single-window kitchen); Source Angle default
  0.53°; Temperature ~4500–5500 K depending on desired warm/cool mood (default Env Light
  Mixer output tends warm — the book's own example needed cooling from 6500 K down to
  ~4500 K to match a colder reference).
- **Sky Atmosphere + Sky Light** combo (from Env. Light Mixer) for physically based ambient
  fill; skip HDRi Backdrop unless a visible exterior background through the window is
  wanted in-frame (a plain Sky Atmosphere is sufficient if the window mostly shows sky/blur).
- **Rect Light for the window** sized to the 30x36 in opening, placed just outside it, to
  punch up and soften daylight fill without needing a full HDRi setup.
- **Rect Light for the under-cabinet LED**: size to the strip length under the upper
  cabinets; set **Intensity Units to Lumens or Candelas** and target **~3000 K** via Use
  Temperature (matches the plan's stated LED color temp); keep the source thin
  (small Source Height) to mimic a real LED strip's narrow emitter; consider pairing with a
  thin emissive material on the strip mesh itself for correct Lumen bounce contribution onto
  the countertop.
- **Exposure**: disable Auto Exposure; one unbound PPV; start Exposure Compensation at 0 and
  tune by eye against the 0.18-mid-gray / 0.85-white / 0.04-black helper-sphere method before
  final grading.
- **Materials**: build a single Master Material for opaque architectural surfaces (oak,
  painted MDF/wood, stone) with the parameter-group + StaticSwitchParameter("Metallic?")
  pattern, then Material Instances per surface:
  - Stained white oak: Metallic off, Roughness ~0.35–0.5 (satin/lightly worn poly finish),
    tiled+panned grain texture, rotate UVs so grain runs vertically on doors / horizontally
    on long horizontal runs as needed.
  - Warm-ivory paint: Metallic off, Roughness ~0.3–0.4 (satin painted finish, not flat, not
    glossy), flat/near-uniform base color within the 30–240 sRGB safe range.
  - Honed cream stone: Metallic off, Roughness ~0.4–0.55 (honed = matte, not polished),
    subtle normal detail for the honed texture, no strong specular highlight.
  - Satin brass hardware: **Metallic on**, Base Color as the brass reflectance tint (near-
    black diffuse contribution is not applicable here since Metallic=1 routes color into
    reflectance, not diffuse — use a realistic brass RGB, e.g., warm gold-tan, as the tinted
    F0), Roughness ~0.3–0.45 for satin (vs. ~0.05–0.15 if polished brass were wanted instead).
  - Brushed steel (appliances/fixtures): Metallic on, Roughness ~0.2–0.35, add a subtle
    directional streak in the normal/roughness map to fake the brushed anisotropic look if
    a plain isotropic material looks too "clean."
  - Glass (window pane): Blend Mode Translucent, Metallic off, Roughness ~0.05–0.1, slight
    tint if desired, Opacity tuned for a realistic but not fully invisible pane.
- **Phase 6 defaults**: CineCameraActor with a Super-35-ish filmback matched to 16:9 (to
  avoid letterboxing at 3840x2160 output); 24–35 mm focal length for room-establishing
  shots, higher focal length (50–85 mm) for detail/hardware close-ups; f/8–f/11 for
  whole-room-in-focus establishing shots, f/2.8–f/4 for shallow-DOF hardware/material
  close-ups; MRQ config: Deferred Rendering, PNG sequence (or EXR if compositing is planned),
  3840x2160, Spatial Sample Count 1 / Temporal Sample Count 16–32, Render/Engine Warm Up 32,
  Game Overrides on, the four `r.*Quality` CVars above, saved as a reusable preset.
