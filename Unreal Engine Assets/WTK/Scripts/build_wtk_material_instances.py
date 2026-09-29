"""
WTK Phase 5c step 3: material instances in /Game/WTK/Materials/ built from the
Masters (M_WTK_Opaque / M_WTK_ClearCoat / M_WTK_Glass / M_WTK_Emissive) via
MaterialEditingLibrary.set_material_instance_* calls.

Run headless after build_wtk_masters.py and import_wtk_textures.py:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput

Idempotent: deletes and recreates each MI asset on every run.

Colour math note: all *_linear tuples below are already in *linear* light
space (0-1), matching the material's VectorParameter convention (UE5
MaterialExpressionVectorParameter defaults expect linear values internally;
the values below were derived from sRGB hex/LRV figures via the standard
sRGB->linear transfer function, s<=0.04045: l=s/12.92 else l=((s+0.055)/1.055)^2.4).
See Materials.md for the per-value derivation and citations.
"""
import unreal

MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
MASTERS = "/Game/WTK/Materials/Masters"
MI_DIR = "/Game/WTK/Materials"
TEX_DIR = "/Game/WTK/Textures"


def log(msg):
    print(msg)


def load(path):
    a = unreal.EditorAssetLibrary.load_asset(path)
    if a is None:
        log("WARNING: could not load %s" % path)
    return a


def delete_if_exists(path):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)


def new_mi(name, parent_path):
    """
    parent_path: the parent Material's content path (string), e.g.
    "/Game/WTK/Materials/Masters/M_WTK_Opaque".
    Sets the parent via MaterialEditingLibrary.set_material_instance_parent
    (the documented approach): MaterialInstanceConstantFactoryNew has no
    Python-settable 'initial_parent' property in this UE 5.7 build (confirmed
    via introspection, tmp/Wtk5c_20260926/find_factory_props.log) -- the
    factory-level parent assignment is a Slate-editor-only affordance,
    not exposed to headless scripting.
    """
    path = "%s/%s" % (MI_DIR, name)
    delete_if_exists(path)
    factory = unreal.MaterialInstanceConstantFactoryNew()
    mi = AT.create_asset(name, MI_DIR, unreal.MaterialInstanceConstant, factory)
    parent_mat = unreal.EditorAssetLibrary.load_asset(parent_path)
    if parent_mat is None:
        log("ERROR: could not load parent material %s for MI %s" % (parent_path, name))
    else:
        MEL.set_material_instance_parent(mi, parent_mat)
    return mi


def set_scalar(mi, name, value):
    MEL.set_material_instance_scalar_parameter_value(mi, name, value)


def set_vector(mi, name, rgb, a=1.0):
    MEL.set_material_instance_vector_parameter_value(mi, name, unreal.LinearColor(rgb[0], rgb[1], rgb[2], a))


def set_switch(mi, name, value):
    MEL.set_material_instance_static_switch_parameter_value(mi, name, value)


def set_tex(mi, name, tex_path):
    tex = load(tex_path)
    if tex is not None:
        MEL.set_material_instance_texture_parameter_value(mi, name, tex)


def save(mi):
    unreal.EditorAssetLibrary.save_loaded_asset(mi, only_if_is_dirty=False)


def build_oak_rift_stained():
    """
    MI_Oak_Rift_Stained -- ClearCoat master; white_oak_veneer; stained a
    neutral warm mid-brown ("golden/early-American" stain on white oak),
    NOT the old reddish/mahogany-leaning recipe.

    Phase 5e fix: the prior tint (0.2423,0.1144,0.0543) at BaseColorBrightness
    1.8 had an R:G ratio of 2.19 (derived directly from sRGB hex #866044
    treating the raw texture as if it were a flat, near-white average) --
    in the actual full-scene render (CAM_Wide) this read as reddish/mahogany
    on B30 and pinkish-orange on the open shelves, not the intended neutral
    warm-brown stain. Task's own guidance: shift toward yellow/olive, reduce
    red saturation, target linear tint around (0.55,0.42,0.26) x texture,
    tuned so the final (texture x tint x brightness) luminance lands in
    0.2-0.3.

    New tint (0.55,00.42,0.26) has R:G ratio 1.31 (down from 2.19) -- a much
    more olive/neutral warm-brown, less red-dominant. BaseColorBrightness
    solved against the same texture-luminance proxy used for the original
    recipe (old recipe: tint_lum 0.1381 x brightness 1.8 -> result luminance
    ~0.25, i.e. an empirical texture/graph factor k = 0.25/(0.1381*1.8) =
    1.006): new_tint_lum = 0.2126*0.55 + 0.7152*0.42 + 0.0722*0.26 = 0.4361;
    brightness = 0.25 / (1.006*0.4361) = 0.57 lands at the 0.25 luminance
    midpoint of the 0.2-0.3 target. Effective tint*brightness =
    (0.314, 0.239, 0.148) -- every channel scaled down together, olive-brown
    undertone preserved, no channel re-reddened. Tuned/sampled against the
    actual CAM_Wide render (see Docs/Materials.md Phase 5e section for the
    before/after sampled pixel values). ClearCoat (grain still visible under
    a satin lacquer) and grain-vertical UV rotation unchanged from Phase 5c/5d.
    """
    mi = new_mi("MI_Oak_Rift_Stained", "%s/M_WTK_ClearCoat" % MASTERS)
    set_switch(mi, "UseBaseColorTex", True)
    set_tex(mi, "BaseColorTex", "%s/Oak/T_Oak_Color" % TEX_DIR)
    # 2026-09-27 relight pass: after the ceiling-seal + relight, CAM_Detail's
    # B30 close-up measured a cool grey-mauve (sRGB B>G, e.g. 130,120,126) at
    # every exposure tried across 3 render rounds (1.8 too dark, 3.6 blown
    # pink-grey, 2.5 landed the right OVERALL brightness but still wrong
    # channel order) -- the tint below is correct on paper (R>G>B, ratio
    # 1.31) but the room's cooler SkyLight/fill ambient plus the ClearCoat's
    # broad specular sheen at this tight framing was washing the saturation
    # out toward neutral grey. Warmed the tint (less blue, slightly more red)
    # and raised brightness a touch so the surface reads as a saturated warm
    # mid-brown even under a cooler ambient, instead of relying on exposure
    # alone to fix a color-ratio problem.
    # 2026-09-27 Round 2 (honey-tan warm-up): Round 1's ClearCoatRoughness
    # fix (0.2->0.35) reduced the cool sky-reflection wash but the surface
    # still read cool mauve-brown rather than warm golden-tan/mid-brown.
    # Per the task's own guidance, tuning the clear coat first (Round 1)
    # before touching tint: now warming the tint toward honey-tan, close to
    # the task's own suggested linear (0.62,0.45,0.25) starting point.
    # 2026-09-27 Round 4: Round 3's Specular/ClearCoat easing landed the
    # panel's B/R ratio at 0.646 (just above the <=0.6 target) with R/G
    # (111.9,83.9) slightly below the 120-160/85-115 target bands. A small
    # brightness lift (0.70->0.78) raises R/G into range while the already-
    # fixed clear-coat/specular keep the cool-reflection contribution low,
    # so B should rise proportionally less than R/G (multiplicative
    # brightness scales all 3 channels by the same factor -- true only if
    # the residual cool cast is now mostly additive/reflection-driven rather
    # than multiplicative-tint-driven, which Round 3's result suggests).
    set_vector(mi, "BaseColorTint", (0.62, 0.45, 0.25))
    set_scalar(mi, "BaseColorBrightness", 0.78)
    set_tex(mi, "RoughnessTex", "%s/Oak/T_Oak_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.35)
    set_scalar(mi, "RoughnessMax", 0.55)
    set_tex(mi, "NormalTex", "%s/Oak/T_Oak_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 1.0)
    set_scalar(mi, "Metallic", 0.0)
    # 2026-09-27 Round 3: Rounds 1-2 confirmed the base-colour tint was NOT
    # the dominant contributor (warming tint from (0.60,0.42,0.20) to
    # (0.62,0.45,0.25) barely moved the sampled panel colour: 117.5,92.8,85.1
    # -> 121.0,95.6,87.4, B/R ratio still ~0.72 vs the 0.6 target) --
    # the cool wash is coming from the base dielectric specular reflection
    # (Specular=0.5 is a fairly strong dielectric reflectance) plus the
    # clear coat, both picking up the room's cool SkyLight/fill. Lowering
    # base Specular (0.5 -> 0.35) and easing the clear coat further
    # (0.7->0.5 ClearCoat, 0.35->0.4 ClearCoatRoughness -- slightly softer/
    # less mirror-like satin) to further reduce the cool reflected component
    # relative to the underlying diffuse/albedo colour.
    set_scalar(mi, "Specular", 0.35)
    set_scalar(mi, "ClearCoat", 0.5)
    set_scalar(mi, "ClearCoatRoughness", 0.4)
    set_switch(mi, "UseWorldAligned", False)
    set_scalar(mi, "UVTiling", 1.0)          # 1:1 with mesh UVs (world-aligned false; tile size handled below)
    # 2026-09-27 WtkPTFix pass: TextureSize_cm raised 50.0 -> 90.0. Root
    # cause of the CAM_Detail horizontal seam across both B30 doors AND the
    # centre stiles at the same height (~y=660/1080): a 50cm tile repeat
    # boundary landed mid-door on every door-height mesh (B30 doors are
    # >=76cm tall), so the texture's own top/bottom edge discontinuity (the
    # source white_oak_veneer scan is not a seamlessly tileable plank -- it
    # has a visible grain-tone break at its own wrap point) was crossing the
    # visible door face at 50/76 ~= 66% of the door height, matching the
    # observed ~660/1080 seam position almost exactly. 90cm comfortably
    # covers a full door height in one tile (no repeat boundary crosses the
    # visible face at all on any door in frame), same value used for
    # MI_Oak_Shelf below so doors and shelves keep reading as the same
    # wood/finish family. Grain scale at 90cm on the source 4K texture is
    # still fine, straight rift-oak grain, not visibly coarsened -- checked
    # against the approved CAM_Detail flat-panel colour target (unaffected
    # by tile size, only by tint/brightness) and the visual grain frequency
    # in the re-rendered CAM_Detail.
    set_scalar(mi, "TextureSize_cm", 90.0)
    set_scalar(mi, "UVRotation_deg", 90.0)   # grain vertical on stiles/panel -- placeholder, tune after UV check
    save(mi)
    return mi


def build_oak_shelf():
    """
    MI_Oak_Shelf -- identical to MI_Oak_Rift_Stained (Phase 5e neutral warm
    mid-brown recipe), grain along shelf length (rotation 0). Only
    UVRotation_deg differs between this MI and MI_Oak_Rift_Stained -- see
    that function's docstring for the full tint/brightness derivation.
    """
    mi = new_mi("MI_Oak_Shelf", "%s/M_WTK_ClearCoat" % MASTERS)
    set_switch(mi, "UseBaseColorTex", True)
    set_tex(mi, "BaseColorTex", "%s/Oak/T_Oak_Color" % TEX_DIR)
    # 2026-09-27 Round 4: same tint/brightness as MI_Oak_Rift_Stained (see
    # that function's docstring for the full derivation) so the shelves and
    # B30 door continue to read as the same wood/finish family.
    set_vector(mi, "BaseColorTint", (0.62, 0.45, 0.25))
    set_scalar(mi, "BaseColorBrightness", 0.78)
    set_tex(mi, "RoughnessTex", "%s/Oak/T_Oak_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.35)
    set_scalar(mi, "RoughnessMax", 0.55)
    set_tex(mi, "NormalTex", "%s/Oak/T_Oak_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 1.0)
    set_scalar(mi, "Metallic", 0.0)
    # 2026-09-27 Round 3: same Specular/ClearCoat easing as
    # MI_Oak_Rift_Stained (see that function's docstring for the reasoning)
    # so shelves and B30 continue to read as the same wood/finish family.
    set_scalar(mi, "Specular", 0.35)
    set_scalar(mi, "ClearCoat", 0.5)
    set_scalar(mi, "ClearCoatRoughness", 0.4)
    set_switch(mi, "UseWorldAligned", False)
    set_scalar(mi, "UVTiling", 1.0)
    # 2026-09-27 WtkPTFix pass: matches MI_Oak_Rift_Stained's 90.0 fix (see
    # that function's docstring) so the shelves keep no visible tile seam
    # and stay the same wood/finish family as B30's doors/stiles.
    set_scalar(mi, "TextureSize_cm", 90.0)
    set_scalar(mi, "UVRotation_deg", 0.0)  # grain along shelf length
    save(mi)
    return mi


def build_paint_warmivory():
    """
    MI_Paint_WarmIvory -- Opaque; constant base ~linear(0.70,0.66,0.58) ivory,
    luminance ~0.66-0.68, all channels <0.8; roughness 0.35-0.45 via narrow
    remap of white_plaster_02; normal strength 0.1-0.2; world-aligned 60-100cm.
    """
    mi = new_mi("MI_Paint_WarmIvory", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", False)  # flat constant tint per recipe
    set_vector(mi, "BaseColorTint", (0.70, 0.66, 0.58))
    set_scalar(mi, "BaseColorBrightness", 1.0)
    set_tex(mi, "RoughnessTex", "%s/Paint_WallPlaster/T_Plaster_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.35)
    set_scalar(mi, "RoughnessMax", 0.45)
    set_tex(mi, "NormalTex", "%s/Paint_WallPlaster/T_Plaster_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 0.15)
    set_scalar(mi, "Metallic", 0.0)
    set_scalar(mi, "Specular", 0.5)
    set_switch(mi, "UseWorldAligned", True)
    set_scalar(mi, "TextureSize_cm", 80.0)  # 60-100cm midpoint
    save(mi)
    return mi


def build_wall_warmoffwhite():
    """MI_Wall_WarmOffWhite -- lighter warm white, luminance ~0.7, roughness 0.8-0.9, faint normal.

    2026-09-28 realism pass: a 2x crop of the round-5 wall/ceiling render
    (CAM_Wide, back-wall and ceiling patches) showed a perfectly smooth
    gradient -- NO visible plaster texture at all -- despite NormalTex/
    NormalStrength already being wired here. NormalStrength=0.08 was too
    subtle to read at this room's lighting/exposure (a flat, mostly-
    perpendicular-lit wall gives normal-mapped micro-bumps very little
    shading contrast to begin with, so a strength tuned for a raking-light
    close-up reads as nothing at a soft, mostly-frontal room light angle).
    Raised to 0.22 (still subtle -- barely-visible eggshell-paint texture is
    the target per the task, not an obvious bump pattern) and RoughnessMin/
    Max spread widened slightly (0.8-0.9 -> 0.75-0.92) so the accompanying
    sheen/specular response also varies a little across the surface, not
    just the normal -- re-verified by a live re-render's own 2x crop (see
    Docs/Lighting.md Section 20).
    """
    mi = new_mi("MI_Wall_WarmOffWhite", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", False)
    # WtkThree_20260928 (Issue 2): rendered G-R was -10.2 to -14.7 (too
    # orange/peach) despite the tint's own raw ratio only being -0.04
    # (0.70/0.74) -- the room's warm sun (5200K) + White Balance tonemap
    # compounds a small per-channel material bias into a much larger
    # rendered shift. Raised G specifically (0.70->0.745, +0.045) to pull
    # the rendered G-R toward 0 without touching R or B (keeps B/R in its
    # already-good 0.90-0.95 band, per the task's own constraint that the
    # fix must be at the material/albedo level, not white balance, since WB
    # moves every zone together and can't selectively fix just this wall).
    # WtkWindow2_20260928 (orchestrator review of v3): v3's G=0.745
    # overcorrected -- rendered wall read pale yellow-green instead of a
    # neutral warm white. Came back about halfway toward the pre-v3 0.70
    # baseline: 0.745 -> 0.72 (R/B unchanged). Target: rendered G-R in
    # [-7,-3], B-G in [-14,-8] (a slight warm cream, not peach/green).
    set_vector(mi, "BaseColorTint", (0.74, 0.72, 0.63))
    set_scalar(mi, "BaseColorBrightness", 1.0)
    set_tex(mi, "RoughnessTex", "%s/Paint_WallPlaster/T_Plaster_Roughness" % TEX_DIR)
    # WtkThree_20260928 (Issue 3): widened further (was 0.75-0.92) so the
    # eggshell sheen VARIATION reads more even under soft frontal light --
    # the min end lowered toward the task's requested 0.45-0.6 "slightly
    # higher specular / lower roughness" band so grazing light near the
    # window/corners catches real sheen breakup, not just a uniform matte.
    set_scalar(mi, "RoughnessMin", 0.55)
    set_scalar(mi, "RoughnessMax", 0.92)
    set_tex(mi, "NormalTex", "%s/Paint_WallPlaster/T_Plaster_Normal" % TEX_DIR)
    # WtkThree_20260928 (Issue 3): raised further from the prior pass's 0.45
    # (which was itself a 5.6x increase from 0.08 and still read as barely
    # visible at this room's soft frontal light) to 0.65 -- still a fine,
    # mm-scale orange-peel texture per the task's "not stucco" ceiling, not
    # a strength multiplier change to the physical bump scale itself
    # (TextureSize_cm below controls that).
    set_scalar(mi, "NormalStrength", 0.65)
    set_scalar(mi, "Metallic", 0.0)
    set_scalar(mi, "Specular", 0.5)
    # NOTE (WtkThree_20260928, Issue 3): UseWorldAligned/TextureSize_cm set
    # here are NOT the load-bearing lever for this MI's actual tile scale --
    # set_uv_mode_tiling.py runs AFTER this script in the mandated re-run
    # order and unconditionally forces UseWorldAligned=False + computes
    # UVTiling from ITS OWN TILE_SIZE_CM["MI_Wall_WarmOffWhite"] table for
    # every MI in its UV_CAPABLE_MASTERS_MIS list (this MI included),
    # silently overriding whatever is set here -- same class of bug already
    # documented for MI_Stone_HonedCream's veining scale. The real fix for
    # the orange-peel bump scale is set_uv_mode_tiling.py's own
    # TILE_SIZE_CM entry (150.0 -> 60.0cm), not this line. Left here
    # unchanged/inert rather than removed, matching this project's own
    # established practice of cross-referencing rather than silently
    # deleting an ineffective-but-harmless setting.
    set_switch(mi, "UseWorldAligned", True)
    set_scalar(mi, "TextureSize_cm", 60.0)
    save(mi)
    return mi


def build_ceiling_flatwhite():
    """MI_Ceiling_FlatWhite -- ~0.75 luminance neutral-warm, roughness 0.9."""
    mi = new_mi("MI_Ceiling_FlatWhite", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", False)
    # WtkThree_20260928 (Issue 2): rendered G-R was -13.8 (too orange),
    # same class of fix as MI_Wall_WarmOffWhite above -- raised G specifically
    # (0.75->0.775) to pull toward neutral warm-white without touching B/R
    # (already close to the 0.90-0.95 band at 0.877). Round 2 (live
    # re-render): G-R improved to -9.9 but not fully to the +/-4 target --
    # nudged G further (0.775->0.80).
    # WtkWindow2_20260928 (orchestrator review of v3): v3's G=0.80
    # overcorrected -- rendered ceiling read pale yellow-green. Came back
    # about halfway: 0.80 -> 0.775. Target: rendered G-R in [-7,-3], B-G in
    # [-14,-8] (a slight warm cream like BM White Dove, not peach/green).
    set_vector(mi, "BaseColorTint", (0.76, 0.775, 0.71))
    set_scalar(mi, "BaseColorBrightness", 1.0)
    set_scalar(mi, "RoughnessMin", 0.9)
    set_scalar(mi, "RoughnessMax", 0.9)
    set_scalar(mi, "NormalStrength", 0.0)
    set_scalar(mi, "Metallic", 0.0)
    set_scalar(mi, "Specular", 0.5)
    set_switch(mi, "UseWorldAligned", False)
    save(mi)
    return mi


def build_stone_honedcream():
    """
    MI_Stone_HonedCream -- Marble020 desaturated ~50%, vein contrast reduced
    via the master's LERP-toward-mean (NOT a power law -- see build_wtk_masters.py
    Phase 5d-7 fix note), warm cream tint, luminance ~0.55, roughness 0.45-0.5,
    world-aligned ~120cm.

    Phase 5d-7 root-cause finding: a neutral pass-through test (tint (1,1,1),
    brightness 1, desaturate 0, vein contrast 1) rendered CAM_Wide as a
    correctly light warm cream/tan counter with visible veining -- proving
    the base_color chain itself was NOT broken. The prior recipe's own tint
    (0.62,0.57,0.48) at brightness 1.0 darkened the ~0.376-luminance raw
    texture down to ~0.22 luminance BEFORE the (now-removed) vein-contrast
    Power(x,0.7) curve and the scene's warm/underlit exposure compounded on
    top, reading as near-black/dark-brown in the full render. Fix: a lighter
    warm tint + higher brightness multiplier that targets ~0.55 luminance
    with every channel kept under 0.8 (checked numerically against the
    source texture's real sampled average, tmp/Wtk5d7_20260926/dump_mi_params.py
    and the accompanying by-hand chain trace in this session's report).
    Raw T_Stone_Color average (3000 random samples, tmp/Wtk5d7_20260926):
    sRGB (177.8,162.5,149.2) -> linear (0.444,0.364,0.301), luminance 0.376.
    tint(1.0,0.94,0.82) x brightness 1.55 -> (0.688,0.530,0.383), luminance
    0.553, max channel 0.688 (< 0.8 as required).
    """
    mi = new_mi("MI_Stone_HonedCream", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", True)
    set_tex(mi, "BaseColorTex", "%s/Stone/T_Stone_Color" % TEX_DIR)
    set_vector(mi, "BaseColorTint", (1.0, 0.94, 0.82))  # light warm cream tint multiply
    set_scalar(mi, "BaseColorBrightness", 1.55)
    # 2026-09-28 realism pass: spec is Cambria Everleigh Warm -- a warm white
    # quartz with SOFT, LARGE, FLOWING grey/taupe veining (02_AutoCAD/WTK_BOM.md).
    # Marble020 at the old TextureSize_cm=120 read as tiny, repetitive speckle
    # rather than large flowing veins (a 120cm tile repeating across a 3m
    # counter run repeats ~2.5x, and Marble020's own vein frequency is tuned
    # for a much smaller physical tile than that, so the veining reads busy/
    # speckled rather than slab-scale). Rescaled to 260cm (within the
    # requested 200-300cm slab-scale band) so the same vein pattern now
    # repeats <1.2x across the 3m run -- effectively reads as a single
    # continuous slab, not a tiled repeat. Softened DesaturateTex/VeinContrast
    # further (0.5->0.62, 0.6->0.45) so the now-larger veins don't read as
    # harsh/graphic at the bigger scale -- a real polished quartz slab's
    # veining is soft-edged/diffused, not a sharp desaturated marble vein.
    set_scalar(mi, "DesaturateTex", 0.62)
    set_scalar(mi, "VeinContrast", 0.45)  # <1.0 softens vein contrast via LERP-toward-mean (not a darkening power law)
    set_tex(mi, "RoughnessTex", "%s/Stone/T_Stone_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.45)
    set_scalar(mi, "RoughnessMax", 0.5)
    set_tex(mi, "NormalTex", "%s/Stone/T_Stone_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 0.5)
    set_scalar(mi, "Metallic", 0.0)
    set_scalar(mi, "Specular", 0.5)
    set_switch(mi, "UseWorldAligned", True)
    # NOTE: UseWorldAligned/TextureSize_cm set here are both UNCONDITIONALLY
    # overridden by the mandatory post-rebuild set_uv_mode_tiling.py re-run
    # (UseWorldAligned->False, tiling driven by that script's own
    # TILE_SIZE_CM/UVTiling instead) -- kept here at a matching 260cm value
    # only so this MI's own recipe/intent stays self-documenting and correct
    # if UseWorldAligned ever became the live path again; the ACTUAL
    # rendered slab scale is set in set_uv_mode_tiling.py's TILE_SIZE_CM
    # table (2026-09-28 realism pass, see that file's own comment).
    set_scalar(mi, "TextureSize_cm", 260.0)  # slab-scale veining (200-300cm target), was 120cm (tiny repetitive speckle)
    save(mi)
    return mi


def build_brass_satin():
    """
    MI_Brass_Satin -- Metallic 1, base linear (0.62,0.46,0.25) champagne-bronze
    satin brass, roughness 0.35-0.45, Metal009 roughness/normal for brushing,
    Anisotropy 0.4.

    WTK prop-fix pass (2026-09-26): the prior tint (0.80,0.60,0.33) at
    Roughness 0.3-0.4 read pale cream/ivory rather than a warm metal in the
    CAM_Detail close-up -- too bright/desaturated for a satin brass at this
    metallic/roughness combo (a high, close-to-white base tint on a Metallic=1
    surface loses most of its perceived colour once lit, reading closer to a
    bright neutral highlight than "brass"). Fix: a more saturated, slightly
    darker base per the task's own target, (0.62,0.46,0.25) linear, and
    roughness raised slightly to 0.35-0.45 (a touch less mirror-like,
    consistent with a "satin" finish holding more of its own colour in
    reflection). Anisotropy (0.4) and the Metal009 brushing maps unchanged.
    """
    mi = new_mi("MI_Brass_Satin", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", False)
    set_vector(mi, "BaseColorTint", (0.62, 0.46, 0.25))
    set_scalar(mi, "BaseColorBrightness", 1.0)
    set_tex(mi, "RoughnessTex", "%s/Metal_Brushed/T_Metal009_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.35)
    set_scalar(mi, "RoughnessMax", 0.45)
    set_tex(mi, "NormalTex", "%s/Metal_Brushed/T_Metal009_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 1.0)
    set_scalar(mi, "Metallic", 1.0)
    set_scalar(mi, "Specular", 0.5)
    set_scalar(mi, "Anisotropy", 0.4)
    set_switch(mi, "UseTangentTex", True)
    set_tex(mi, "TangentTex", "%s/Metal_Brushed/T_Metal009_Normal" % TEX_DIR)  # linear brushed direction map
    set_switch(mi, "UseWorldAligned", False)
    set_scalar(mi, "TextureSize_cm", 20.0)
    save(mi)
    return mi


def build_brass_knob_radial():
    """
    MI_Brass_Knob_Radial -- same champagne-bronze recipe as MI_Brass_Satin
    (see that function's docstring for the WTK prop-fix pass rationale) but
    Metal051A (radial brushing) for the knob-scale tile.
    """
    mi = new_mi("MI_Brass_Knob_Radial", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", False)
    set_vector(mi, "BaseColorTint", (0.62, 0.46, 0.25))
    set_scalar(mi, "BaseColorBrightness", 1.0)
    set_tex(mi, "RoughnessTex", "%s/Metal_Brushed/T_Metal051A_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.35)
    set_scalar(mi, "RoughnessMax", 0.45)
    set_tex(mi, "NormalTex", "%s/Metal_Brushed/T_Metal051A_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 1.0)
    set_scalar(mi, "Metallic", 1.0)
    set_scalar(mi, "Specular", 0.5)
    set_scalar(mi, "Anisotropy", 0.4)
    set_switch(mi, "UseTangentTex", True)
    set_tex(mi, "TangentTex", "%s/Metal_Brushed/T_Metal051A_Normal" % TEX_DIR)  # radial brushing direction map
    set_switch(mi, "UseWorldAligned", False)
    set_scalar(mi, "TextureSize_cm", 5.0)  # knob-scale tile
    save(mi)
    return mi


def build_steel_brushed():
    """MI_Steel_Brushed -- Metallic 1, base ~(0.56,0.57,0.58), roughness 0.25-0.35, Metal009, Anisotropy 0.5."""
    mi = new_mi("MI_Steel_Brushed", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", False)
    set_vector(mi, "BaseColorTint", (0.56, 0.57, 0.58))
    set_scalar(mi, "BaseColorBrightness", 1.0)
    set_tex(mi, "RoughnessTex", "%s/Metal_Brushed/T_Metal009_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.25)
    set_scalar(mi, "RoughnessMax", 0.35)
    set_tex(mi, "NormalTex", "%s/Metal_Brushed/T_Metal009_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 1.0)
    set_scalar(mi, "Metallic", 1.0)
    set_scalar(mi, "Specular", 0.5)
    set_scalar(mi, "Anisotropy", 0.5)
    set_switch(mi, "UseTangentTex", True)
    set_tex(mi, "TangentTex", "%s/Metal_Brushed/T_Metal009_Normal" % TEX_DIR)
    set_switch(mi, "UseWorldAligned", False)
    set_scalar(mi, "TextureSize_cm", 20.0)
    save(mi)
    return mi


def build_glass_clear():
    """MI_Glass_Clear -- clear window glass instance of M_WTK_Glass.

    2026-09-27 WtkPTFix2 pass: this MI is what's actually assigned to the
    window mesh (confirmed live via remap_materials_wtk.py's rule table --
    the window's material slot maps to THIS MI, not the M_WTK_Glass master
    directly). Its own explicit overrides below had silently been left at
    OLD pre-fix values this whole time -- near-white BaseColorTint
    (0.9,0.95,0.95, the original "milky panel" tint Docs/Lighting.md Section
    14 documented fixing on the MASTER), Specular=0.5 (mirror-smooth
    dielectric reflectance, confirmed by a real diagnostic render this pass
    to dominate over the transmitted background regardless of Opacity), and
    IOR=1.5 (a real-glass IOR that the task's own spec called out as wrong
    for this thin-pane look, "IOR=1.0 per the task spec" -- see the master's
    own build_glass() docstring). Every one of those earlier "fixes" to
    build_wtk_masters.py's build_glass() master defaults was a no-op for the
    actual rendered window, because build_material_instances()'s own
    set_vector()/set_scalar() calls here explicitly re-override the MI's
    parameters to these old values on every rebuild (an MI's own explicit
    parameter override always wins over its parent master's default,
    regardless of what the master's default is set to) -- confirmed by a
    real garish-magenta-backdrop diagnostic render this pass (magenta did
    NOT show through the glass at all, proving the pane's own reflectance/
    tint, not the backdrop, was blocking the exterior view). Fixed by
    bringing this MI's own values in line with the master's already-correct
    intent: near-black BaseColorTint (matches the master's fixed default),
    Specular 0.5 -> 0.0 (removes the fixed dielectric reflectance term that
    was reading as a uniform pale reflection sheet), IOR 1.5 -> 1.0 (thin
    glass, no visible refraction bend, per the task's own spec), Opacity
    raised slightly (0.12 -> 0.16, still within the task's ~0.1-0.2 target
    band) so the transmitted exterior reads clearly once the competing
    reflectance term is gone.
    """
    mi = new_mi("MI_Glass_Clear", "%s/M_WTK_Glass" % MASTERS)
    # 2026-09-27 WtkPTFix2 pass, round 2: round 1 (BaseColorTint near-black
    # (0.02,0.025,0.03), Opacity=0.16, Specular=0.0) fixed the "no exterior
    # visible" reflection problem but overcorrected into an opaque-looking
    # near-black hole (measured mean sRGB ~4-8 in-pane, versus the room's own
    # ~120-130 -- the window read DARKER than the interior, worse than the
    # original milky-panel bug). Diagnosis: this engine's DefaultLit+
    # Translucent Surface-ForwardShading blend does not behave as a simple
    # "Background*(1-Opacity) + LitBaseColor*Opacity" alpha-over in the path
    # tracer -- a near-black BaseColorTint at low Opacity is instead reading
    # as a mostly-opaque dark surface. Root-caused by the same disclosed
    # "Thin Translucent node not exposed to this engine's Python API"
    # limitation documented on the master (build_glass()) -- DefaultLit
    # translucency is not a physically-correct thin-glass transmission model,
    # so both extremes (bright tint = milky opaque reflection, near-black
    # tint = opaque dark hole) fail for a different reason. Round 2: raise
    # Opacity substantially (0.16 -> 0.35, still well under the task's own
    # upper guidance and short of looking like a solid pane) and lighten the
    # tint off pure near-black to a very dark neutral grey (0.02,0.025,0.03
    # -> 0.08,0.09,0.10) so more of the transmitted background actually
    # reaches the shaded output, while Specular stays at 0.0 (the actual
    # fix for the reflection-dominates-everything problem, confirmed by the
    # garish-magenta diagnostic and unrelated to this opacity retune).
    # Round 3 (tested, reverted): explicitly setting the master's
    # refraction_mode to RM_INDEX_OF_REFRACTION and returning to a
    # near-black tint/Opacity=0.14 reproduced round 1's near-black result
    # almost exactly (measured ~4-5 mean sRGB in-pane, same as round 1) --
    # proving refraction_mode was not the missing piece either. This
    # confirms the root limitation is structural: DefaultLit+Translucent's
    # Surface-ForwardShading blend in this engine's path tracer does not
    # transmit background IMAGE DETAIL through a low-Opacity, dark-tinted
    # pane -- it only lets background COLOR bleed through as a flat wash,
    # darkening toward the tint as Opacity drops, rather than acting like a
    # true partially-transmissive dielectric. This is the same disclosed
    # "Thin Translucent node not exposed to this engine's Python API" gap
    # documented on the master's own build_glass() docstring -- no
    # DefaultLit-translucent parameter combination found this pass produces
    # real see-through sky/tree/grass detail.
    #
    # 2026-09-27 WtkPTFix5 pass: revisited after WtkPTFix4 shipped
    # path_tracing_enable_reference_atmosphere=True on all 3 cameras (see
    # Docs/Lighting.md section 17.1) -- the real SkyAtmosphere gradient/
    # horizon is now genuinely reaching the path-traced camera through the
    # window opening for the first time (previously it was invisible
    # regardless of glass settings, per section 15.2/16.2's own diagnostics,
    # so round 2's Opacity=0.35/tint=(0.08,0.09,0.10) was tuned against a
    # scene that had NO real backdrop to transmit -- that constraint no
    # longer holds). Task A4 asks to lower Opacity toward ~0.10 (less of the
    # tint blocking the now-real sky) and lighten the tint toward a neutral
    # 0.5-0.7 grey, with Specular small (0-0.2) for a faint reflection.
    # Two variants tested this pass, both real re-renders (see this pass's
    # section of Docs/Lighting.md for the numbers):
    #   Variant A (lighter, shipped): BaseColorTint=(0.55,0.58,0.60),
    #     Opacity=0.10, Specular=0.15.
    #   Variant B (kept dark, tested for comparison): BaseColorTint=
    #     (0.08,0.09,0.10), Opacity=0.10, Specular=0.15.
    # Variant A produced a visibly brighter, clearer sky-through-glass read
    # without losing the pane's own presence (a faint 0.15 specular sheen
    # keeps it legible as glass, not an open hole) -- shipped.
    # 2026-09-28 realism pass: adding a real, in-scene backplate photo
    # (WTK_WindowBackplate, see setup_lighting_wtk.py) still rendered as a
    # flat blue-white wash through the glass (live-confirmed in a full-3-
    # camera re-render, Wide.png/Angle.png both show no tree/foliage detail
    # despite the backplate genuinely being visible_in_ray_tracing=True and
    # much closer/larger than the old HDRI dome) -- consistent with this
    # MI's own already-exhaustively-documented finding above (WtkPTFix5
    # pass): DefaultLit+Translucent's Surface-ForwardShading blend in this
    # engine's path tracer transmits background COLOR but not IMAGE DETAIL,
    # regardless of what real geometry sits behind the glass. Tried lowering
    # Opacity further (0.10 -> 0.04) and Specular (0.15 -> 0.05) as the most
    # direct lever available without the unexposed Thin Translucent shading
    # model -- a live re-render confirmed this did NOT restore real image
    # detail either (window patch std dev stayed ~5-8, i.e. still an
    # essentially flat wash -- see Docs/Lighting.md Section 20 for the
    # honest disclosure, a real limitation of this engine build's
    # Python-exposed material API, same as every prior glass pass found).
    # Settled on a slightly less extreme 0.08/0.10 (between the pre-pass
    # 0.10/0.15 and the tested-but-ineffective 0.04/0.05) purely so the pane
    # keeps a legible glass presence (a faint real specular sheen and body
    # tint) rather than reading as an open hole, since going all the way to
    # near-zero opacity bought no transmission benefit worth that tradeoff.
    set_vector(mi, "BaseColorTint", (0.55, 0.58, 0.60))
    set_scalar(mi, "Opacity", 0.08)
    set_scalar(mi, "Roughness", 0.02)
    set_scalar(mi, "Specular", 0.10)
    set_scalar(mi, "Metallic", 0.0)
    set_scalar(mi, "IOR", 1.0)
    save(mi)
    return mi


def build_led_3000k():
    """MI_LED_3000K -- straight instance of M_WTK_Emissive; warm 3000K, low emissive strength."""
    mi = new_mi("MI_LED_3000K", "%s/M_WTK_Emissive" % MASTERS)
    set_vector(mi, "BaseColorTint", (0.05, 0.05, 0.05))
    set_scalar(mi, "Roughness", 0.6)
    set_vector(mi, "EmissiveColor3000K", (1.0, 0.588, 0.281))
    set_scalar(mi, "EmissiveStrength", 5.0)  # low -- real light comes from Rect Lights per research doc
    save(mi)
    return mi


def build_floor_oak():
    """
    MI_Floor_Oak -- WoodFloor051, warm natural tone, roughness 0.45-0.6,
    world-aligned so boards ~6in (15.24cm) wide. Asset tile is 180x180cm per
    LICENSES.md; plank count across that tile is not published by ambientCG,
    so TextureSize_cm is set to the 6in target board width directly
    (15.24cm) as the tunable scalar -- this assumes the master's world-aligned
    tiling maps TextureSize_cm to one board-repeat, to be visually confirmed
    once the level is open (flagged in Materials.md as an open verification
    item, since a precise plank-count-from-tile computation was not possible
    from published metadata).
    """
    mi = new_mi("MI_Floor_Oak", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", True)
    set_tex(mi, "BaseColorTex", "%s/Floor/T_Floor_Color" % TEX_DIR)
    set_vector(mi, "BaseColorTint", (1.0, 0.95, 0.85))  # warm natural tone multiply
    set_scalar(mi, "BaseColorBrightness", 1.0)
    set_tex(mi, "RoughnessTex", "%s/Floor/T_Floor_Roughness" % TEX_DIR)
    set_scalar(mi, "RoughnessMin", 0.45)
    set_scalar(mi, "RoughnessMax", 0.6)
    set_tex(mi, "NormalTex", "%s/Floor/T_Floor_Normal" % TEX_DIR)
    set_scalar(mi, "NormalStrength", 1.0)
    set_scalar(mi, "Metallic", 0.0)
    set_scalar(mi, "Specular", 0.5)
    set_switch(mi, "UseWorldAligned", True)
    set_scalar(mi, "TextureSize_cm", 15.24)  # 6 in board width target
    save(mi)
    return mi


def build_windowframe_white():
    """
    MI_WindowFrame_White -- white frame/muntin paint.

    2026-09-28 WtkMuntin_20260928 pass (muntin/sash glow fix): the vertical
    window muntin bar (Generic_Models_Muntin_Pattern_2x2_Muntin_Pattern_2x2,
    slots 0/1 both on this MI) read as a wide (~27px half-max, vs the bar's
    own ~12-13px geometric footprint at CAM_Angle's framing), overexposed
    white/near-clipped glow in look_A_v4's Angle.png (x~430-470,y80-640) and
    a bright edge-line on the horizontal bar in Wide.png (y~560-570). Root
    cause, isolated via single-variable CAM_Angle diagnostics (256 SPP,
    tmp/WtkMuntin_20260928/diag/): NOT bloom (PPV bloom_intensity=0.3 is
    already subtle and a bloom=0 test only partially narrowed the glow), NOT
    the path-tracer denoiser (WTK_PT_DENOISER=0 raw-image render was
    pixel-identical to the denoised final), NOT Local Exposure detail_strength
    (forcing 1.0 had zero measurable effect), NOT the visible sun disk
    (atmosphere_sun_light=False had zero effect), NOT the M_WTK_GlassHidden_PT
    material or a masking-edge gap at the muntin/glass seam (a garish-red
    BaseColorTint sanity-check test confirmed the muntin DOES correctly
    receive and render this MI's own tint at that exact screen location --
    ruling out any "ray skips the muntin, hits something else" hypothesis).
    Zeroing WTK_Sun's intensity DID fully eliminate the glow (confirmed
    live), proving it is direct-sun illumination on the muntin's own
    sun-facing front face. With the original Roughness=0.5/Specular=0.5, the
    grazing-angle Fresnel term (which UE's dielectric BRDF still produces
    even at Specular=0, since Specular only scales the base F0 reflectance,
    not the Schlick grazing-angle rise) plus a very high direct 65000 lux
    hit combined to overexpose the surface toward a near-neutral white,
    masking the paint's own tint entirely. RoughnessMin/Max raised to 1.0
    (fully diffuse -- eliminates the grazing Fresnel glint entirely; a
    garish-red diagnostic at Roughness=1.0/Specular=0.0 rendered as
    genuinely saturated red at the peak (R~250, G/B~160-190), confirming the
    tint now survives correctly under direct sun instead of being
    overwhelmed by a neutral specular highlight) and Specular lowered to
    0.0 (removes the residual F0 reflectance component). BaseColorBrightness
    lowered 1.0->0.6 (a moderate, not drastic, cut -- the diagnostic rounds
    found the remaining peak brightness at full roughness/zero specular is
    dominantly direct-diffuse sun illumination, largely insensitive to this
    parameter once already very bright, so a moderate trim was kept rather
    than an aggressive one that would have made the frame read implausibly
    grey elsewhere in the image away from the sun hotspot). Verified:
    half-max glow width narrowed ~27px->24px, peak 240.9->234.9 (CAM_Angle,
    256 SPP diagnostic), and -- the more important qualitative fix -- the
    muntin no longer reads as a false neutral-white halo, instead reading as
    a physically plausible bright-but-tinted sun-facing paint surface with a
    thin, crisp bright edge, per the task's own "if genuinely direct sun,
    keep a thin realistic edge reduced to physically plausible" fallback.
    Room-patch/garden-view/sun-patch impact: none of these parameters are
    referenced by any other MI or the backplate/room materials, so this is a
    scoped, single-surface fix.
    """
    mi = new_mi("MI_WindowFrame_White", "%s/M_WTK_Opaque" % MASTERS)
    set_switch(mi, "UseBaseColorTex", False)
    set_vector(mi, "BaseColorTint", (0.78, 0.78, 0.76))
    set_scalar(mi, "BaseColorBrightness", 0.6)
    set_scalar(mi, "RoughnessMin", 1.0)
    set_scalar(mi, "RoughnessMax", 1.0)
    set_scalar(mi, "NormalStrength", 0.0)
    set_scalar(mi, "Metallic", 0.0)
    set_scalar(mi, "Specular", 0.0)
    set_switch(mi, "UseWorldAligned", False)
    save(mi)
    return mi


def main():
    log("=== WTK5c material instances build start ===")
    build_oak_rift_stained()
    build_oak_shelf()
    build_paint_warmivory()
    build_wall_warmoffwhite()
    build_ceiling_flatwhite()
    build_stone_honedcream()
    build_brass_satin()
    build_brass_knob_radial()
    build_steel_brushed()
    build_glass_clear()
    build_led_3000k()
    build_floor_oak()
    build_windowframe_white()
    log("WTK5C_MI_DONE")


main()
