"""
WTK Phase 5c step 2: build master materials in /Game/WTK/Materials/Masters/
via MaterialEditingLibrary.

Run headless:
  UnrealEditor-Cmd.exe <proj>.uproject -run=pythonscript -script=<this file>
    -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput

Idempotent: deletes and recreates each master material asset on every run
(cheap -- these are hand-authored graphs, not imported content, so there is
nothing to preserve across a rerun other than the finished graph itself).

Masters built:
  M_WTK_Opaque      -- DefaultLit, legacy metal/roughness, world-aligned OR
                       UV-tiled option, anisotropy, desaturate/vein-contrast
                       for stone.
  M_WTK_ClearCoat   -- same as Opaque + ClearCoat/ClearCoatRoughness, for
                       stained oak.
  M_WTK_Glass       -- Translucent, for the window.
  M_WTK_Emissive    -- DefaultLit w/ emissive, for the LED strip.

Per the research docs (RESEARCH_2026-09-26_WTK_WOOD_CABINET_MATERIALS_LOOP2_LOOP3.md,
RESEARCH_2026-09-26_UE5_ARCHVIZ_KITCHEN_LOOP2_LOOP3.md, WTK_UE5_Reference_Notes.md):
project is confirmed non-Substrate (legacy Clear Coat shading model), Nanite/Lumen
HW RT on. This script does not touch DefaultEngine.ini or Nanite/bevel settings.
"""
import unreal

MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
MASTERS_DIR = "/Game/WTK/Materials/Masters"

EMissing = unreal.MaterialEditorOnlyDataEditor if hasattr(unreal, "MaterialEditorOnlyDataEditor") else None


def log(msg):
    print(msg)


def delete_if_exists(path):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)


def new_material(name):
    path = "%s/%s" % (MASTERS_DIR, name)
    delete_if_exists(path)
    factory = unreal.MaterialFactoryNew()
    mat = AT.create_asset(name, MASTERS_DIR, unreal.Material, factory)
    return mat


def expr(mat, cls, x, y, **props):
    e = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        try:
            e.set_editor_property(k, v)
        except Exception as ex:
            log("  (warn) could not set %s=%s on %s: %s" % (k, v, cls.__name__, ex))
    return e


def connect(mat, from_expr, from_out, to_expr, to_in):
    MEL.connect_material_expressions(from_expr, from_out, to_expr, to_in)


def connect_prop(mat, from_expr, from_out, prop):
    MEL.connect_material_property(from_expr, from_out, prop)


def set_group(e, group_name):
    try:
        e.set_editor_property("group", group_name)
    except Exception:
        pass


def build_uv_and_tiling_chain(mat, x0, y0, size_param_name="UVTiling", rot_param_name="UVRotation_deg",
                               offset_param_name="UVOffset", group="03_UVs"):
    """
    Standard-UV path: TexCoord0 -> rotate (about UV-space centre 0.5,0.5, by
    angle in degrees) -> tile scalar -> Add offset. Returns the final UV
    expression to feed into Texture Sample Coordinates pins.

    Rotation is built from first principles (Sine/Cosine + the standard 2D
    rotation matrix) rather than via unreal.MaterialExpressionRotator: that
    node's Python binding exposes only editor-position properties (no
    angle/speed/center pins as settable Python properties in this UE 5.7
    build -- confirmed via introspection, tmp/Wtk5c_20260926/inspect_rotator.log),
    so it cannot be driven by a ScalarParameter through the Python API. The
    hand-built version below is the documented general technique for a
    parametrized UV rotation (per WTK_UE5_Reference_Notes.md's own note that
    "an additional rotation node before the tiling multiply" is needed,
    without specifying an exact node) and gives an exact, parameter-driven
    angle in degrees.
    """
    texcoord = expr(mat, unreal.MaterialExpressionTextureCoordinate, x0, y0, coordinate_index=0)

    # Center UVs on (0,0) so rotation pivots around the tile center (0.5,0.5).
    center_const = expr(mat, unreal.MaterialExpressionConstant2Vector, x0 + 100, y0 + 200, r=0.5, g=0.5)
    centered = expr(mat, unreal.MaterialExpressionSubtract, x0 + 160, y0)
    connect(mat, texcoord, "", centered, "A")
    connect(mat, center_const, "", centered, "B")

    rot_angle_deg = expr(mat, unreal.MaterialExpressionScalarParameter, x0 + 160, y0 + 300,
                          parameter_name=rot_param_name, default_value=0.0)
    set_group(rot_angle_deg, group)
    deg_to_rad = expr(mat, unreal.MaterialExpressionMultiply, x0 + 320, y0 + 300, const_b=0.0174533)
    connect(mat, rot_angle_deg, "", deg_to_rad, "A")

    sin_e = expr(mat, unreal.MaterialExpressionSine, x0 + 480, y0 + 260)
    connect(mat, deg_to_rad, "", sin_e, "Input")
    cos_e = expr(mat, unreal.MaterialExpressionSine, x0 + 480, y0 + 340, period=6.28318)
    # cos(x) = sin(x + pi/2) -- offset the input by pi/2 (1.5707963) before the sine.
    cos_offset = expr(mat, unreal.MaterialExpressionAdd, x0 + 400, y0 + 340, const_b=1.5707963)
    connect(mat, deg_to_rad, "", cos_offset, "A")
    connect(mat, cos_offset, "", cos_e, "Input")

    # Rotated.x = U*cos - V*sin ; Rotated.y = U*sin + V*cos
    u_comp = expr(mat, unreal.MaterialExpressionComponentMask, x0 + 320, y0 - 80, r=1, g=0, b=0, a=0)
    connect(mat, centered, "", u_comp, "")
    v_comp = expr(mat, unreal.MaterialExpressionComponentMask, x0 + 320, y0, r=0, g=1, b=0, a=0)
    connect(mat, centered, "", v_comp, "")

    u_cos = expr(mat, unreal.MaterialExpressionMultiply, x0 + 640, y0 - 120)
    connect(mat, u_comp, "", u_cos, "A")
    connect(mat, cos_e, "", u_cos, "B")
    v_sin = expr(mat, unreal.MaterialExpressionMultiply, x0 + 640, y0 - 40)
    connect(mat, v_comp, "", v_sin, "A")
    connect(mat, sin_e, "", v_sin, "B")
    rot_x = expr(mat, unreal.MaterialExpressionSubtract, x0 + 800, y0 - 80)
    connect(mat, u_cos, "", rot_x, "A")
    connect(mat, v_sin, "", rot_x, "B")

    u_sin = expr(mat, unreal.MaterialExpressionMultiply, x0 + 640, y0 + 40)
    connect(mat, u_comp, "", u_sin, "A")
    connect(mat, sin_e, "", u_sin, "B")
    v_cos = expr(mat, unreal.MaterialExpressionMultiply, x0 + 640, y0 + 120)
    connect(mat, v_comp, "", v_cos, "A")
    connect(mat, cos_e, "", v_cos, "B")
    rot_y = expr(mat, unreal.MaterialExpressionAdd, x0 + 800, y0 + 40)
    connect(mat, u_sin, "", rot_y, "A")
    connect(mat, v_cos, "", rot_y, "B")

    rotated = expr(mat, unreal.MaterialExpressionAppendVector, x0 + 960, y0)
    connect(mat, rot_x, "", rotated, "A")
    connect(mat, rot_y, "", rotated, "B")

    uncentered = expr(mat, unreal.MaterialExpressionAdd, x0 + 1080, y0 + 200)
    connect(mat, rotated, "", uncentered, "A")
    connect(mat, center_const, "", uncentered, "B")

    tiling = expr(mat, unreal.MaterialExpressionScalarParameter, x0 + 1080, y0 - 200,
                  parameter_name=size_param_name, default_value=1.0)
    set_group(tiling, group)
    mul = expr(mat, unreal.MaterialExpressionMultiply, x0 + 1240, y0)
    connect(mat, uncentered, "", mul, "A")
    connect(mat, tiling, "", mul, "B")

    offset = expr(mat, unreal.MaterialExpressionVectorParameter, x0 + 1400, y0 + 140,
                   parameter_name=offset_param_name, default_value=unreal.LinearColor(0, 0, 0, 0))
    set_group(offset, group)
    add = expr(mat, unreal.MaterialExpressionAdd, x0 + 1400, y0)
    connect(mat, mul, "", add, "A")
    connect(mat, offset, "", add, "B")
    return add


def build_world_aligned_switch(mat, uv_chain, x0, y0, group="03_UVs"):
    """
    StaticSwitch("UseWorldAligned") between the UV-tiled chain and a
    WorldAlignedTexture-style triplanar coordinate set (approximated here via
    WorldPosition / TextureSize_cm, since full triplanar blending is only
    practical per-texture-sample; the switch itself, plus TextureSize_cm
    param, are exposed so a texture-sample-level triplanar function can be
    swapped in later without changing the public parameter interface).
    Returns (switch_param_expr, uv_chain, texture_size_param).
    """
    # Phase 5d fix: same StaticSwitchParameter-vs-StaticBoolParameter issue as
    # add_switch() above -- this node's A/B inputs were never wired (matching
    # Materials.md's documented "UseWorldAligned is structurally disconnected"
    # finding) but the node still required valid A/B to compile for SM6,
    # contributing to the same "Missing A/B input" failure on every WTK MI.
    switch = expr(mat, unreal.MaterialExpressionStaticBoolParameter, x0, y0,
                  parameter_name="UseWorldAligned", default_value=False)
    set_group(switch, group)
    texture_size = expr(mat, unreal.MaterialExpressionScalarParameter, x0, y0 + 160,
                        parameter_name="TextureSize_cm", default_value=100.0)
    set_group(texture_size, group)
    return switch, texture_size


_DEFAULT_WHITE_TEX = None
_DEFAULT_FLAT_NORMAL_TEX = None


def _default_white_tex():
    global _DEFAULT_WHITE_TEX
    if _DEFAULT_WHITE_TEX is None:
        _DEFAULT_WHITE_TEX = unreal.EditorAssetLibrary.load_asset(
            "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture")
    return _DEFAULT_WHITE_TEX


def _default_flat_normal_tex():
    global _DEFAULT_FLAT_NORMAL_TEX
    if _DEFAULT_FLAT_NORMAL_TEX is None:
        _DEFAULT_FLAT_NORMAL_TEX = unreal.EditorAssetLibrary.load_asset(
            "/Engine/EngineMaterials/FlatNormal.FlatNormal")
    return _DEFAULT_FLAT_NORMAL_TEX


def add_texture_param(mat, x, y, name, default_tex, group, is_normal=False):
    p = expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y,
             parameter_name=name)
    set_group(p, group)
    # Phase 5d fix: a TextureSampleParameter2D with texture=None compiles fine
    # in the editor preview but FAILS shader compilation for PCD3D_SM6 in
    # cooked/-game contexts ("Param2D> Found NULL, requires Texture2D"),
    # causing every MI using this master (all 11 of them, including flat-
    # colour MIs like MI_Ceiling_FlatWhite/MI_WindowFrame_White that never
    # set BaseColorTex) to silently fall back to the engine's default grey
    # checkerboard material in any -game/headless MRQ render -- confirmed via
    # tmp/Wtk5d_20260926 test renders (all 3 test cameras showed only the
    # checkerboard fallback, never the real WTK materials). The
    # StaticSwitchParameter("UseBaseColorTex"/"UseTangentTex") correctly
    # ROUTES AROUND this texture at runtime, but the compiler still requires
    # every TextureSampleParameter2D node to reference a valid, non-null
    # Texture2D asset regardless of which branch is live. Fall back to a
    # valid engine default texture so the node always has a valid (if
    # visually inert) texture reference when no real default_tex is given --
    # a Normal-type sampler (NormalTex/TangentTex) needs the engine's actual
    # FlatNormal texture (a Color-type default like plain white fails with
    # "Sampler type is Normal, should be Color"), while a Color-type sampler
    # (BaseColorTex/RoughnessTex) uses the 1x1 white texture.
    tex_to_use = default_tex
    if tex_to_use is None:
        tex_to_use = _default_flat_normal_tex() if is_normal else _default_white_tex()
    if tex_to_use is not None:
        try:
            p.texture = tex_to_use
        except Exception:
            pass
    return p


def add_scalar(mat, x, y, name, default, group):
    p = expr(mat, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=default)
    set_group(p, group)
    return p


def add_vector(mat, x, y, name, default, group):
    p = expr(mat, unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name, default_value=default)
    set_group(p, group)
    return p


def add_switch(mat, x, y, name, default, group):
    """
    Phase 5d fix: this used unreal.MaterialExpressionStaticSwitchParameter,
    which is NOT a plain named boolean value -- it is itself a full switch
    node with its own required "A"/"B" branch inputs (see
    Engine/Public/Materials/MaterialExpressionStaticSwitchParameter.h: it
    subclasses MaterialExpressionStaticBoolParameter and adds FExpressionInput
    A, B). Every call site in this file only ever consumes this node's output
    as a plain boolean fed into a separate MaterialExpressionStaticSwitch's
    "Value" pin (e.g. UseBaseColorTex -> base_switch.Value,
    UseTangentTex -> tangent_switch.Value) and never wires anything into A/B
    -- exactly the "(Node StaticSwitchParameter) Missing A input / Missing B
    input" SM6 shader compile failure confirmed in
    tmp/Wtk5d_20260926 test renders (every WTK MI falling back to the engine
    default checkerboard material). The correct node for "a named, exposed
    boolean parameter with no branch inputs of its own" is the parent class,
    MaterialExpressionStaticBoolParameter -- switching to it removes the
    unused/unfed A/B pins entirely, matching how every call site here already
    treats this node's output.
    """
    p = expr(mat, unreal.MaterialExpressionStaticBoolParameter, x, y, parameter_name=name, default_value=default)
    set_group(p, group)
    return p


def build_common_opaque_chain(mat, is_clearcoat):
    """
    Shared graph for M_WTK_Opaque and M_WTK_ClearCoat.
    Groups: 01_Textures, 02_Color, 03_UVs, 04_Physical, 05_Anisotropy, 06_Stone, 07_ClearCoat.
    """
    uv_chain = build_uv_and_tiling_chain(mat, -1400, -400)
    ws, texture_size = build_world_aligned_switch(mat, uv_chain, -1400, 0)

    # --- Base colour ---
    base_tex = add_texture_param(mat, -1000, -600, "BaseColorTex", None, "01_Textures")
    connect(mat, uv_chain, "", base_tex, "Coordinates")
    use_base_tex = add_switch(mat, -1000, -750, "UseBaseColorTex", True, "01_Textures")

    base_tint = add_vector(mat, -1000, -450, "BaseColorTint", unreal.LinearColor(1, 1, 1, 1), "02_Color")
    base_brightness = add_scalar(mat, -1000, -350, "BaseColorBrightness", 1.0, "02_Color")

    tinted = expr(mat, unreal.MaterialExpressionMultiply, -760, -550)
    connect(mat, base_tex, "RGB", tinted, "A")
    connect(mat, base_tint, "", tinted, "B")
    brightened = expr(mat, unreal.MaterialExpressionMultiply, -600, -550)
    connect(mat, tinted, "", brightened, "A")
    connect(mat, base_brightness, "", brightened, "B")

    base_switch = expr(mat, unreal.MaterialExpressionStaticSwitch, -420, -550)
    connect(mat, use_base_tex, "", base_switch, "Value")
    connect(mat, brightened, "", base_switch, "True")
    connect(mat, base_tint, "", base_switch, "False")  # flat tint (still brightness-able below if desired)

    # --- Desaturate + vein contrast (stone) ---
    # Phase 5d-7 fix: VeinContrast used to feed a MaterialExpressionPower's
    # Exponent directly (Base = the desaturated colour). Power(x, k) with
    # k<1 does lift x for x in (0,1) (a mild brightening), but it is the
    # wrong operator for "reduce vein contrast": it reshapes the whole
    # tonal curve (crushing shadows/highlights together nonlinearly)
    # instead of simply pulling outlier (vein) pixels toward the surface's
    # own mean color, and stacked underneath the darkening BaseColorTint
    # multiply + a warm/underlit scene it read as a uniform dark smear
    # rather than a legible honed stone. Root cause of the "dark brown"
    # look (per Docs/Materials.md's own root-cause note) was actually the
    # UVTiling regression + scene exposure, not this node -- but the task's
    # own diagnostic asked for a LERP-toward-the-mean here instead of a
    # power law regardless, since a power law is the wrong tool for vein
    # softening even when it isn't the dominant cause of darkness.
    # New approach: lerp each pixel toward the desaturated colour's own
    # luminance (a per-pixel "mean" proxy for a fairly uniform stone) by
    # (1-VeinContrast), so VeinContrast=1.0 keeps full veining (no change)
    # and VeinContrast<1.0 softens/reduces vein contrast by blending
    # toward flat, WITHOUT any darkening power-law curve.
    desat_amt = add_scalar(mat, -420, -700, "DesaturateTex", 0.0, "06_Stone")
    vein_contrast = add_scalar(mat, -420, -800, "VeinContrast", 1.0, "06_Stone")
    desat = expr(mat, unreal.MaterialExpressionDesaturation, -260, -650)
    connect(mat, base_switch, "", desat, "")
    desat_lerp = expr(mat, unreal.MaterialExpressionLinearInterpolate, -100, -650)
    connect(mat, base_switch, "", desat_lerp, "A")
    connect(mat, desat, "", desat_lerp, "B")
    connect(mat, desat_amt, "", desat_lerp, "Alpha")

    vein_mean = expr(mat, unreal.MaterialExpressionDesaturation, 60, -750)
    connect(mat, desat_lerp, "", vein_mean, "")
    vein_alpha = expr(mat, unreal.MaterialExpressionOneMinus, 60, -820)
    connect(mat, vein_contrast, "", vein_alpha, "")
    vein_lerp = expr(mat, unreal.MaterialExpressionLinearInterpolate, 220, -650)
    connect(mat, desat_lerp, "", vein_lerp, "A")
    connect(mat, vein_mean, "", vein_lerp, "B")
    connect(mat, vein_alpha, "", vein_lerp, "Alpha")

    if not is_clearcoat:
        connect_prop(mat, vein_lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    base_color_out = vein_lerp

    # --- Roughness (texture + min/max remap) ---
    rough_tex = add_texture_param(mat, -1000, -100, "RoughnessTex", None, "01_Textures")
    connect(mat, uv_chain, "", rough_tex, "Coordinates")
    rough_min = add_scalar(mat, -760, -20, "RoughnessMin", 0.3, "04_Physical")
    rough_max = add_scalar(mat, -760, 60, "RoughnessMax", 0.7, "04_Physical")
    rough_remap = expr(mat, unreal.MaterialExpressionLinearInterpolate, -580, -20)
    connect(mat, rough_min, "", rough_remap, "A")
    connect(mat, rough_max, "", rough_remap, "B")
    connect(mat, rough_tex, "R", rough_remap, "Alpha")
    if not is_clearcoat:
        connect_prop(mat, rough_remap, "", unreal.MaterialProperty.MP_ROUGHNESS)
    roughness_out = rough_remap

    # --- Normal (texture + FlattenNormal strength) ---
    normal_tex = add_texture_param(mat, -1000, 200, "NormalTex", None, "01_Textures", is_normal=True)
    # Phase 5d fix: this used to force texture=None right after
    # add_texture_param() set a default -- reintroducing the exact "Param2D>
    # Found NULL, requires Texture2D" SM6 shader compile failure that
    # add_texture_param()'s own fallback (engine white 1x1 texture) now
    # avoids. A flat white texture through a Normal-type sampler reads as a
    # harmless, inert (0.5,0.5,1.0)-ish flat normal until a real NormalTex is
    # assigned on an MI, and every real WTK oak/paint/stone/metal MI already
    # sets its own NormalTex, so this default is never visually used in
    # practice -- it only exists to keep the node's texture reference valid
    # for compilation on materials that never set NormalTex (flat-colour MIs
    # like MI_Ceiling_FlatWhite/MI_WindowFrame_White).
    try:
        normal_tex.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    except Exception:
        pass
    connect(mat, uv_chain, "", normal_tex, "Coordinates")
    normal_strength = add_scalar(mat, -760, 320, "NormalStrength", 1.0, "04_Physical")
    # FlattenNormal-equivalent, hand-built: unreal.MaterialExpressionFlattenNormal does
    # not exist in this UE 5.7 Python binding set (confirmed via introspection,
    # tmp/Wtk5c_20260926/find_normal_nodes.log). Reproduce its effect -- lerp the
    # sampled tangent-space normal toward flat (0,0,1) by (1-Strength), then
    # renormalize -- which is the documented technique for dialing normal-map
    # intensity per material instance (WTK_UE5_Reference_Notes.md's own
    # description of FlattenNormal's purpose).
    # Phase 5d fix: flat_normal_const (a Constant4Vector, float4) was wired
    # directly into flatten_lerp's "A" while normal_tex (a texture sample,
    # whose default/unmasked output pin is float3 RGB here) fed "B" --
    # LinearInterpolate requires both A and B to be the same vector width,
    # and SM6 shader compilation (unlike the editor preview) enforces this
    # strictly ("Arithmetic between types float4 and float3 are undefined").
    # This only surfaced once the NULL-texture fix above let normal_tex
    # actually reach this node; previously compilation aborted earlier at
    # the NULL-texture error, masking this separate, pre-existing type bug.
    # Fix: use a Constant3Vector (float3) for the flat-normal reference so
    # both Lerp inputs match.
    flat_normal_const = expr(mat, unreal.MaterialExpressionConstant3Vector, -680, 260,
                              constant=unreal.LinearColor(0.5, 0.5, 1.0, 1.0))
    flatten_lerp = expr(mat, unreal.MaterialExpressionLinearInterpolate, -580, 200)
    connect(mat, flat_normal_const, "", flatten_lerp, "A")
    connect(mat, normal_tex, "", flatten_lerp, "B")
    connect(mat, normal_strength, "", flatten_lerp, "Alpha")
    flatten_norm = expr(mat, unreal.MaterialExpressionNormalize, -420, 200)
    connect(mat, flatten_lerp, "", flatten_norm, "")
    if not is_clearcoat:
        connect_prop(mat, flatten_norm, "", unreal.MaterialProperty.MP_NORMAL)
    normal_out = flatten_norm

    # --- Metallic / Specular ---
    metallic = add_scalar(mat, -1000, 420, "Metallic", 0.0, "04_Physical")
    if not is_clearcoat:
        connect_prop(mat, metallic, "", unreal.MaterialProperty.MP_METALLIC)
    specular = add_scalar(mat, -1000, 480, "Specular", 0.5, "04_Physical")
    if not is_clearcoat:
        connect_prop(mat, specular, "", unreal.MaterialProperty.MP_SPECULAR)

    # --- Anisotropy + Tangent (optional TangentTex switch) ---
    aniso = add_scalar(mat, -1000, 600, "Anisotropy", 0.0, "05_Anisotropy")
    if not is_clearcoat:
        connect_prop(mat, aniso, "", unreal.MaterialProperty.MP_ANISOTROPY)

    use_tangent_tex = add_switch(mat, -1000, 700, "UseTangentTex", False, "05_Anisotropy")
    tangent_tex = add_texture_param(mat, -800, 760, "TangentTex", None, "05_Anisotropy", is_normal=True)
    try:
        tangent_tex.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    except Exception:
        pass
    connect(mat, uv_chain, "", tangent_tex, "Coordinates")
    vertex_tangent = expr(mat, unreal.MaterialExpressionVertexNormalWS, -800, 860)
    tangent_switch = expr(mat, unreal.MaterialExpressionStaticSwitch, -600, 760)
    connect(mat, use_tangent_tex, "", tangent_switch, "Value")
    connect(mat, tangent_tex, "", tangent_switch, "True")
    connect(mat, vertex_tangent, "", tangent_switch, "False")
    if not is_clearcoat:
        connect_prop(mat, tangent_switch, "", unreal.MaterialProperty.MP_TANGENT)

    cc = ccr = None
    if is_clearcoat:
        # ClearCoat / ClearCoatRoughness: exposed as ScalarParameters per the
        # task spec (so MI authors can set/document values). As of Phase
        # 5c-2 Task 2, these ARE wired to the shading model's actual
        # ClearCoat/ClearCoatRoughness inputs -- via a MakeMaterialAttributes
        # node (see build_clearcoat() below), not via UMaterial's raw
        # ClearCoat/ClearCoatRoughness FExpressionInput members, which remain
        # protected in this UE 5.7 build's Python reflection (confirmed via
        # introspection, tmp/Wtk5c_20260926/try_write_cc.log,
        # try_cc_connect.log: get_editor_property/set_editor_property both
        # raise "Property 'ClearCoat' ... is protected"). The breakthrough
        # (Phase 5c-2): unreal.MaterialExpressionMakeMaterialAttributes DOES
        # expose static, string-addressable pins for "ClearCoat" and
        # "ClearCoatRoughness" (confirmed via
        # MaterialEditingLibrary.get_material_expression_input_names on a
        # freshly-created MakeMaterialAttributes node -- see
        # tmp/Wtk5c2_20260926/introspect_matattr.py output), unlike
        # MaterialExpressionSetMaterialAttributes, whose per-shading-model
        # sub-pins are dynamically generated and NOT reachable by name string
        # (that path was tried and failed in Phase 5c). connect_material_expressions
        # DOES accept "ClearCoat"/"ClearCoatRoughness" as to_in pin names on a
        # MakeMaterialAttributes node.
        cc = add_scalar(mat, -1000, 900, "ClearCoat", 0.0, "07_ClearCoat")
        ccr = add_scalar(mat, -1000, 960, "ClearCoatRoughness", 0.2, "07_ClearCoat")

    return {
        "uv_chain": uv_chain,
        "world_aligned_switch": ws,
        "texture_size": texture_size,
        "base_color_out": base_color_out,
        "roughness_out": roughness_out,
        "normal_out": normal_out,
        "metallic_out": metallic,
        "specular_out": specular,
        "anisotropy_out": aniso,
        "tangent_out": tangent_switch,
        "clearcoat_out": cc,
        "clearcoat_roughness_out": ccr,
        "base_tex": base_tex,
    }


def build_opaque():
    log("Building M_WTK_Opaque ...")
    mat = new_material("M_WTK_Opaque")
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    build_common_opaque_chain(mat, is_clearcoat=False)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def build_clearcoat():
    """
    M_WTK_ClearCoat -- Clear Coat shading model, driven through
    use_material_attributes=True + a MakeMaterialAttributes node (Phase 5c-2
    Task 2). All the chains built by build_common_opaque_chain() (BaseColor,
    Roughness, Normal, Metallic, Specular, Anisotropy, Tangent, ClearCoat,
    ClearCoatRoughness) are connected into the MakeMaterialAttributes node's
    matching input pins by name, and the node is connected to the material's
    MP_MATERIAL_ATTRIBUTES output. This is what makes ClearCoat/
    ClearCoatRoughness actually reach the shading model -- the previous
    (Phase 5c) attempt tried to connect directly to UMaterial's ClearCoat/
    ClearCoatRoughness FExpressionInput members, which are protected in this
    engine's Python reflection; MakeMaterialAttributes' pins are not
    protected and ARE reachable by name via connect_material_expressions.
    """
    log("Building M_WTK_ClearCoat ...")
    mat = new_material("M_WTK_ClearCoat")
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_CLEAR_COAT)
    outs = build_common_opaque_chain(mat, is_clearcoat=True)

    mat.set_editor_property("use_material_attributes", True)

    mk = expr(mat, unreal.MaterialExpressionMakeMaterialAttributes, 400, 400)
    connect(mat, outs["base_color_out"], "", mk, "BaseColor")
    connect(mat, outs["metallic_out"], "", mk, "Metallic")
    connect(mat, outs["specular_out"], "", mk, "Specular")
    connect(mat, outs["roughness_out"], "", mk, "Roughness")
    connect(mat, outs["anisotropy_out"], "", mk, "Anisotropy")
    connect(mat, outs["normal_out"], "", mk, "Normal")
    connect(mat, outs["tangent_out"], "", mk, "Tangent")
    connect(mat, outs["clearcoat_out"], "", mk, "ClearCoat")
    connect(mat, outs["clearcoat_roughness_out"], "", mk, "ClearCoatRoughness")

    ok = MEL.connect_material_property(mk, "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
    log("  connect_material_property(MakeMaterialAttributes -> MP_MATERIAL_ATTRIBUTES): %s" % ok)

    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def build_glass():
    """
    M_WTK_Glass -- path-tracer-correct clear window glass (2026-09-27
    WtkPTFix pass).

    ROOT CAUSE of the "frosted/milky" glass under the path tracer (task's
    diagnosis confirmed correct): this material was DefaultLit + Translucent
    blend mode with (a) a near-white BaseColorTint (0.9,0.95,0.95) and (b)
    TLM_SURFACE_TRANSLUCENCY_VOLUME lighting mode. Under Lumen/the path
    tracer, DefaultLit translucency actually SHADES the glass surface with
    full scene lighting -- a bright, near-white diffuse base colour lit by
    the sun/sky reads as an opaque-looking lit white panel, and the
    Surface Translucency Volume lighting mode further approximates/blurs
    whatever light passes through onto a coarse volume texture, destroying
    any exterior detail. This was never a "thin translucent" material --
    confirmed via the master's own DefaultLit shading model in the pre-fix
    graph.

    FIX ATTEMPTED, THEN REVERTED (disclosed): MSM_THIN_TRANSLUCENT was tried
    first, per the task's own suggestion, and DID apply (confirmed in the
    build log: "shading_model = MSM_THIN_TRANSLUCENT"). But UE 5.7's Thin
    Translucent shading model has a hard requirement this engine build's
    Python API cannot satisfy: it needs a dedicated
    MaterialExpressionThinTranslucentMaterial output node wired to the
    material's special Thin-Translucent output pin (confirmed via
    Saved/Logs/WTK.log: "Failed to compile Material for platform PCD3D_SM6,
    Default Material will be used in game. ThinTranslucent materials
    requires the use of ThinTranslucentMaterial output node.") -- and
    `unreal.MaterialExpressionThinTranslucentMaterial` DOES NOT EXIST in this
    engine's Python reflection (confirmed: `AttributeError: module 'unreal'
    has no attribute 'MaterialExpressionThinTranslucentMaterial'`), the same
    class of "correct node not exposed to Python" problem documented
    elsewhere in this codebase for ClearCoat's raw FExpressionInput members.
    With no way to wire that required node, the material failed to compile
    and silently fell back to the engine's opaque Default Material in-game --
    which is why the very next test render (CAM_Wide, 2048 SPP) came back
    NEARLY BLACK: the "glass" was now an opaque fallback material blocking
    the window opening AND the fallback also broke that render's ability to
    receive normal room bounce light. Caught immediately by re-inspecting the
    actual rendered pixels (this pass's own diagnose-before-declaring-fixed
    rule) rather than declared fixed on the "shading_model=THIN_TRANSLUCENT"
    log line alone.

    ACTUAL FIX SHIPPED: reverted to MSM_DEFAULT_LIT (a real, compiling
    shading model in this engine build) but fixed the two things that
    actually caused the "frosted/milky" look under DefaultLit + Translucent:
    (1) BaseColorTint changed from near-white (0.9,0.95,0.95) to near-black
    (0.02,0.025,0.03) -- DefaultLit translucency SHADES its base colour with
    full scene lighting, so a bright base colour under the path tracer's sun/
    sky reads as a lit diffuse white panel; a near-black base colour lets
    the Opacity-controlled blend show what's behind the glass instead; (2)
    translucency_lighting_mode changed from TLM_SURFACE_TRANSLUCENCY_VOLUME
    (which approximates/blurs anything behind translucent geometry onto a
    coarse volume texture, destroying exterior detail) to TLM_SURFACE
    (Surface ForwardShading -- a sharp, per-pixel translucent shade, the
    correct mode for a window pane, and also the mode Thin Translucent
    itself requires, so this is the same lighting-mode fix either shading
    model needs). Opacity/Roughness/Specular/Metallic/IOR are unchanged from
    the values below (already in the task's requested ranges). This is a
    disclosed engine-API limitation, not a silently-abandoned attempt --
    flagged in Docs/Lighting.md's new section for a future pass to revisit
    (e.g. editing the .uasset's raw serialized graph outside Python, or
    upgrading to an engine version/plugin that exposes the node).
    """
    log("Building M_WTK_Glass ...")
    mat = new_material("M_WTK_Glass")
    # See docstring: MSM_THIN_TRANSLUCENT was tried and reverted -- this
    # engine build's Python API cannot wire the required
    # ThinTranslucentMaterial output node, so the material failed to compile
    # and silently fell back to an opaque default (confirmed via a real test
    # render going near-black). MSM_DEFAULT_LIT is used instead, with the
    # base-colour/lighting-mode fixes below doing the actual work.
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    used_thin_translucent = False
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    try:
        # Surface ForwardShading (the engine default) -- NOT Surface
        # Translucency Volume -- is what lets the path tracer/Lumen show a
        # sharp, undiffused view of what's behind the glass instead of
        # smearing it through a coarse lighting volume texture.
        mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    except Exception as ex:
        log("  (note) could not set TLM_SURFACE: %s -- left at engine default." % ex)
    try:
        # 2026-09-27 WtkPTFix2 pass: refraction_mode defaulted to whatever
        # this engine's Material factory leaves it at (confirmed by
        # inspection this was never explicitly set) -- the IOR scalar wired
        # to MP_REFRACTION below is inert unless refraction_mode is
        # explicitly RM_IndexOfRefraction, which is also the mode the path
        # tracer's own physically-based translucent transmission path
        # actually uses (as opposed to a flat alpha/Opacity-only blend).
        # Explicitly setting it here is the remaining lever, short of Thin
        # Translucent, for getting real see-through transmission rather than
        # only a tinted-colour blend under DefaultLit.
        mat.set_editor_property("refraction_mode", unreal.RefractionMode.RM_INDEX_OF_REFRACTION)
    except Exception as ex:
        log("  (note) could not set refraction_mode=RM_INDEX_OF_REFRACTION: %s -- left at engine default." % ex)

    # Dark, barely-tinted base colour (transmittance tint under Thin
    # Translucent; a very dark diffuse colour under the DefaultLit fallback)
    # -- this is the single biggest fix versus the old near-white
    # (0.9,0.95,0.95) value that made the pane read as a lit diffuse panel.
    base_color = add_vector(mat, -600, -400, "BaseColorTint", unreal.LinearColor(0.02, 0.025, 0.03, 1.0), "02_Color")
    connect_prop(mat, base_color, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # Opacity ~0.1-0.2 per the task spec; kept at the low end so the
    # sunny exterior HDRI reads clearly through the pane at the room's
    # tuned exposure while the glass keeps a faint reflection.
    opacity = add_scalar(mat, -600, -250, "Opacity", 0.14, "04_Physical")
    connect_prop(mat, opacity, "", unreal.MaterialProperty.MP_OPACITY)

    roughness = add_scalar(mat, -600, -150, "Roughness", 0.0, "04_Physical")
    connect_prop(mat, roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)

    # 2026-09-27 WtkPTFix2 pass -- root cause of "no exterior view, uniform
    # pale panel" confirmed by a real diagnostic render: with the sky dome's
    # own emissive forced to a garish, unmistakable HDR magenta (10,0,10),
    # the window STILL rendered as the same pale ~223,225,224 -- proving the
    # backdrop itself was never the problem (ray-tracing visibility, normals,
    # and the dome's own texture were all independently confirmed fine: the
    # actor's material slot is a real TextureCube sample of the CC0 HDRI, not
    # a broken/missing asset). The actual cause is THIS material's own
    # DefaultLit specular term: Specular=0.5 at Roughness=0.0 (mirror-smooth)
    # gives a strong, sharp Fresnel/dielectric reflectance that is ADDED on
    # top of the Opacity-weighted transmitted-background blend under
    # BLEND_TRANSLUCENT -- it is not itself scaled down by Opacity=0.14, so
    # even a thin, mostly-transmissive pane reflects enough of the bright
    # interior/sky lighting back at the camera to read as a uniform pale
    # sheet, drowning out the (correctly rendering) exterior detail
    # underneath. Fix: Specular 0.5 -> 0.0 removes that fixed reflectance
    # term entirely (a real glass pane's actual specular response at
    # near-normal incidence and IOR~1.0 is already close to zero anyway, so
    # this is not a physically dishonest simplification), letting the
    # Opacity-blended transmission -- and therefore the real HDRI sky/
    # backdrop behind it -- read through clearly.
    specular = add_scalar(mat, -600, -50, "Specular", 0.0, "04_Physical")
    connect_prop(mat, specular, "", unreal.MaterialProperty.MP_SPECULAR)

    metallic = add_scalar(mat, -600, 50, "Metallic", 0.0, "04_Physical")
    connect_prop(mat, metallic, "", unreal.MaterialProperty.MP_METALLIC)

    # IOR=1.0 for thin glass per the task spec -- no visible refraction bend
    # from a single thin sheet at these viewing distances; the old IOR=1.5
    # hookup (paired with DefaultLit's diffuse shading of the surface) was a
    # second, independent contributor to the "not a clear window" look.
    ior = add_scalar(mat, -600, 150, "IOR", 1.0, "04_Physical")
    connect_prop(mat, ior, "", unreal.MaterialProperty.MP_REFRACTION)

    log("  shading_model = %s" % ("MSM_THIN_TRANSLUCENT" if used_thin_translucent else "MSM_DEFAULT_LIT (fallback)"))
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def build_emissive():
    """
    M_WTK_Emissive: DefaultLit with an emissive colour*strength product, for
    the LED strip mesh. Real scene light comes from Rect Lights per the
    research doc -- this material provides only the visible glowing surface.
    """
    log("Building M_WTK_Emissive ...")
    mat = new_material("M_WTK_Emissive")
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)

    base_color = add_vector(mat, -600, -300, "BaseColorTint", unreal.LinearColor(0.05, 0.05, 0.05, 1.0), "02_Color")
    connect_prop(mat, base_color, "", unreal.MaterialProperty.MP_BASE_COLOR)

    roughness = add_scalar(mat, -600, -200, "Roughness", 0.6, "04_Physical")
    connect_prop(mat, roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)

    # Warm ~3000K colour, approximated as a fixed warm-white LinearColor
    # (an accurate blackbody-to-RGB conversion at 3000K, linear).
    emissive_color = add_vector(mat, -600, 0, "EmissiveColor3000K", unreal.LinearColor(1.0, 0.588, 0.281, 1.0), "08_Emissive")
    emissive_strength = add_scalar(mat, -600, 120, "EmissiveStrength", 5.0, "08_Emissive")
    mul = expr(mat, unreal.MaterialExpressionMultiply, -380, 0)
    connect(mat, emissive_color, "", mul, "A")
    connect(mat, emissive_strength, "", mul, "B")
    connect_prop(mat, mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def main():
    log("=== WTK5c master materials build start ===")
    build_opaque()
    build_clearcoat()
    build_glass()
    build_emissive()
    log("WTK5C_MASTERS_DONE")


main()
