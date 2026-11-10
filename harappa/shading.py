# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shader side of Harappa.

HRP Palette      one shared group holding every colour/number the look uses (written by the add-on, so
                 files render the same without it installed)
HRP Clump Normal the anime-grass trick without baking: Voronoi domes projected straight down in world
                 space (two sizes) + a high-frequency 'brush' jitter, added to the ground normal. Ground
                 and every blade sample the same field, so lit/shadow clumps run across both
HRP Cel          Diffuse -> Shader to RGB -> normalised by the key light -> 3-tone cel split
Materials        HRP Ground, HRP Grass, HRP Flower, HRP Leaves, HRP Bark
"""
import math

import bpy

from . import assets
from .util import G, fresh_group, iface, srgb

SHADER_VER = 24
PALETTE = "HRP Palette"
CLUMP = "HRP Clump Normal"
CEL = "HRP Cel"
MAT_GROUND = "HRP Ground"
MAT_GRASS = "HRP Grass"
MAT_FLOWER = "HRP Flower"
MAT_LEAVES = "HRP Leaves"
MAT_BARK = "HRP Bark"
MAT_FILL = "HRP Canopy Fill"
MAT_CLOUD = "HRP Cloud"
MAT_CLOUD_FILL = "HRP Cloud Fill"

# key -> (kind, default). Colours are sRGB hex here, stored linear.
PALETTE_KEYS = {
    # grass
    "grass_lit": ("RGB", "#8CC63F"),
    "grass_lit2": ("RGB", "#B5D350"),      # second patch colour (field variation)
    "grass_shadow": ("RGB", "#3E8A4A"),
    "grass_deep": ("RGB", "#1F5640"),
    "grass_tip": ("RGB", "#D8EC7A"),
    "dirt_lit": ("RGB", "#D9C9A0"),
    "dirt_shadow": ("RGB", "#A89878"),
    "dirt_deep": ("RGB", "#7D6F5E"),
    # foliage
    "leaf_lit": ("RGB", "#BCDF5E"),
    "leaf_mid": ("RGB", "#5FA040"),
    "leaf_shadow": ("RGB", "#3F7F66"),
    "leaf_deep": ("RGB", "#183C46"),
    "leaf_hi": ("RGB", "#DDF08F"),
    "bloom_lit": ("RGB", "#FFD3E2"),
    "bloom_shadow": ("RGB", "#D58FB6"),
    "bloom_deep": ("RGB", "#B58AB0"),
    "bark_lit": ("RGB", "#6E5444"),
    "bark_shadow": ("RGB", "#3A3440"),
    # meadow flowers
    "flower_a": ("RGB", "#FFFFFF"),
    "flower_b": ("RGB", "#FFE45C"),
    "flower_c": ("RGB", "#FF9EC4"),
    "flower_d": ("RGB", "#B79CFF"),
    "flower_centre": ("RGB", "#FFC531"),
    "flower_shade": ("RGB", "#B7B9E8"),     # multiplied in on the shadow side
    # light & tone
    "sun_tint": ("RGB", "#FFFFFF"),
    "haze_colour": ("RGB", "#CFE6F2"),
    "rim_colour": ("RGB", "#F4C478"),
    "cloud_lit": ("RGB", "#FFFFFF"),
    "cloud_shadow": ("RGB", "#CDD0E6"),
    "cloud_deep": ("RGB", "#D6D2E6"),
    "light_scale": ("VALUE", 4.0),          # key light strength x brightest channel (driven)
    "threshold": ("VALUE", 0.42),           # lit / shadow split
    "deep_threshold": ("VALUE", 0.12),      # shadow / deep split
    "softness": ("VALUE", 0.035),
    "clump_size": ("VALUE", 1.8),           # metres
    "clump_strength": ("VALUE", 1.6),
    "clump_small": ("VALUE", 0.35),         # weight of the small clumps
    "brush_jitter": ("VALUE", 0.22),
    "root_dark": ("VALUE", 0.35),
    "tip_light": ("VALUE", 0.45),
    "wind_sheen": ("VALUE", 0.35),
    "patch_amount": ("VALUE", 0.5),
    "leaf_ao": ("VALUE", 0.65),
    "leaf_deep_threshold": ("VALUE", 0.24),
    "haze_amount": ("VALUE", 0.3),
    "haze_start": ("VALUE", 10.0),
    "haze_end": ("VALUE", 90.0),
    "flower_dim": ("VALUE", 1.0),
    "rim_amount": ("VALUE", 0.0),
    "leaf_hi_amount": ("VALUE", 0.5),
}


def _lin(v):
    return (*srgb(v), 1.0) if isinstance(v, str) else v


# ----------------------------------------------------------------------------------------------
# palette
# ----------------------------------------------------------------------------------------------
def palette_group():
    ng, rebuilt = fresh_group(PALETTE, "ShaderNodeTree", SHADER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    out = g.n("NodeGroupOutput", 600, 0)
    y = 0
    for key, (kind, default) in PALETTE_KEYS.items():
        if kind == "RGB":
            iface(ng, key, "OUTPUT", "NodeSocketColor")
            n = g.n("ShaderNodeRGB", 0, y, label=key)
            n.outputs[0].default_value = _lin(default)
        else:
            iface(ng, key, "OUTPUT", "NodeSocketFloat")
            n = g.n("ShaderNodeValue", 0, y, label=key)
            n.outputs[0].default_value = default
        g.links.new(n.outputs[0], out.inputs[key])
        y -= 120
    return ng


def palette_set(key, value):
    ng = palette_group()
    n = ng.nodes.get(key)
    if n is None:
        return
    if PALETTE_KEYS[key][0] == "RGB":
        n.outputs[0].default_value = _lin(value) if isinstance(value, str) else (*value[:3], 1.0)
    else:
        n.outputs[0].default_value = float(value)


def palette_get(key):
    n = palette_group().nodes.get(key)
    v = n.outputs[0].default_value
    return tuple(v[:3]) if PALETTE_KEYS[key][0] == "RGB" else float(v)


def drive_light_scale(sun):
    """light_scale = sun strength x brightest colour channel, as a driver (follows edits live)."""
    ng = palette_group()
    sock = ng.nodes["light_scale"].outputs[0]
    try:
        sock.driver_remove("default_value")
    except TypeError:
        pass
    if sun is None:
        return
    fc = sock.driver_add("default_value")
    d = fc.driver
    d.type = "SCRIPTED"
    for name, path in (("e", "energy"), ("r", "color[0]"), ("g", "color[1]"), ("b", "color[2]")):
        v = d.variables.new()
        v.name = name
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "LIGHT"
        v.targets[0].id = sun.data
        v.targets[0].data_path = path
    d.expression = "max(e * max(r, g, b), 0.001)"


# ----------------------------------------------------------------------------------------------
# clump normal
# ----------------------------------------------------------------------------------------------
def clump_group():
    ng, rebuilt = fresh_group(CLUMP, "ShaderNodeTree", SHADER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Position", "INPUT", "NodeSocketVector")
    iface(ng, "Base Normal", "INPUT", "NodeSocketVector")
    iface(ng, "Size", "INPUT", "NodeSocketFloat", 1.2)
    iface(ng, "Strength", "INPUT", "NodeSocketFloat", 1.6)
    iface(ng, "Small", "INPUT", "NodeSocketFloat", 0.45)
    iface(ng, "Jitter", "INPUT", "NodeSocketFloat", 0.35)
    iface(ng, "Normal", "OUTPUT", "NodeSocketVector")
    iface(ng, "Clump", "OUTPUT", "NodeSocketFloat")
    gi = g.n("NodeGroupInput", -1400, 0)
    go = g.n("NodeGroupOutput", 1400, 0)

    # q = P / size, gently warped so clumps aren't round cells
    q = g.vmath("DIVIDE", -1200, 200, g.out(gi, "Position"))
    sz = g.n("ShaderNodeCombineXYZ", -1400, 300)
    for c in "XYZ":
        g.link(gi, "Size", sz, c)
    g.link(sz, 0, q, 1)
    warp = g.n("ShaderNodeTexNoise", -1000, 400, noise_dimensions="2D")
    g.set(warp, "Scale", 0.9)
    g.set(warp, "Detail", 2.0)
    g.link(q, 0, warp, "Vector")
    wc = g.vmath("SUBTRACT", -800, 400, g.out(warp, "Color"), (0.5, 0.5, 0.5))
    wq = g.vmath("MULTIPLY_ADD", -600, 250, g.out(wc, 0), (0.9, 0.55, 0.0))   # stretched sideways
    g.link(q, 0, wq, 2)

    def dome(scale, x, y):
        sc = g.vmath("SCALE", x, y, g.out(wq, 0), scale=scale)
        v = g.n("ShaderNodeTexVoronoi", x + 180, y, voronoi_dimensions="2D", feature="F1")
        g.set(v, "Scale", 1.0)
        g.set(v, "Randomness", 0.9)
        g.link(sc, 0, v, "Vector")
        d = g.vmath("SUBTRACT", x + 380, y, g.out(sc, 0), g.out(v, "Position"))
        dist = g.out(v, "Distance")
        return d, dist

    d1, dist1 = dome(1.0, -400, 300)
    d2, dist2 = dome(2.7, -400, -50)
    d3, dist3 = dome(7.0, -400, -200)
    small = g.vmath("SCALE", 100, -50, g.out(d2, 0), scale=g.out(gi, "Small"))
    tiny_w = g.math("MULTIPLY", 0, -250, g.out(gi, "Small"), 0.45)
    tiny = g.vmath("SCALE", 100, -200, g.out(d3, 0), scale=g.out(tiny_w, 0))
    tot0 = g.vmath("ADD", 200, 150, g.out(d1, 0), g.out(small, 0))
    tot = g.vmath("ADD", 300, 150, g.out(tot0, 0), g.out(tiny, 0))

    # brush jitter: fine noise so the terminator breaks into blade-like strokes
    jq = g.vmath("SCALE", -400, -350, g.out(q, 0), scale=1.0)
    jn = g.n("ShaderNodeTexNoise", -200, -350, noise_dimensions="3D")
    g.set(jn, "Scale", 28.0)
    g.set(jn, "Detail", 1.0)
    g.link(jq, 0, jn, "Vector")
    jc = g.vmath("SUBTRACT", 0, -350, g.out(jn, "Color"), (0.5, 0.5, 0.5))
    js = g.vmath("SCALE", 200, -350, g.out(jc, 0), scale=g.out(gi, "Jitter"))
    tot2 = g.vmath("ADD", 500, 0, g.out(tot, 0), g.out(js, 0))
    st = g.vmath("SCALE", 700, 0, g.out(tot2, 0), scale=g.out(gi, "Strength"))
    flat = g.vmath("MULTIPLY", 880, 0, g.out(st, 0), (1.0, 1.0, 0.0))
    nb = g.vmath("NORMALIZE", 880, -200, g.out(gi, "Base Normal"))
    add = g.vmath("ADD", 1050, 0, g.out(nb, 0), g.out(flat, 0))
    nn = g.vmath("NORMALIZE", 1220, 0, g.out(add, 0))
    g.link(nn, 0, go, "Normal")
    g.links.new(dist1, go.inputs["Clump"])
    return ng


# ----------------------------------------------------------------------------------------------
# cel
# ----------------------------------------------------------------------------------------------
def cel_group():
    ng, rebuilt = fresh_group(CEL, "ShaderNodeTree", SHADER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Normal", "INPUT", "NodeSocketVector")
    iface(ng, "Lit", "INPUT", "NodeSocketColor", (0.5, 0.8, 0.3, 1))
    iface(ng, "Shadow", "INPUT", "NodeSocketColor", (0.2, 0.5, 0.3, 1))
    iface(ng, "Deep", "INPUT", "NodeSocketColor", (0.1, 0.3, 0.2, 1))
    iface(ng, "Threshold", "INPUT", "NodeSocketFloat", 0.42)
    iface(ng, "Deep Threshold", "INPUT", "NodeSocketFloat", 0.12)
    iface(ng, "Softness", "INPUT", "NodeSocketFloat", 0.035)
    iface(ng, "Offset", "INPUT", "NodeSocketFloat", 0.0)
    iface(ng, "Color", "OUTPUT", "NodeSocketColor")
    iface(ng, "Light", "OUTPUT", "NodeSocketFloat")
    iface(ng, "Lit Mask", "OUTPUT", "NodeSocketFloat")
    gi = g.n("NodeGroupInput", -1000, 0)
    go = g.n("NodeGroupOutput", 1000, 0)
    pal = g.n("ShaderNodeGroup", -1000, -400)
    pal.node_tree = palette_group()

    dif = g.n("ShaderNodeBsdfDiffuse", -800, 200)
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    g.link(gi, "Normal", dif, "Normal")
    s2r = g.n("ShaderNodeShaderToRGB", -600, 200)
    g.link(dif, 0, s2r, 0)
    bw = g.n("ShaderNodeRGBToBW", -420, 200)
    g.link(s2r, "Color", bw, 0)
    # v = lum * pi / light_scale + offset
    m1 = g.math("MULTIPLY", -250, 200, g.out(bw, 0), math.pi)
    m2 = g.math("DIVIDE", -80, 200, g.out(m1, 0), g.out(pal, "light_scale"))
    v = g.math("ADD", 90, 200, g.out(m2, 0), g.out(gi, "Offset"))
    soft = g.math("MAXIMUM", -80, -60, g.out(gi, "Softness"), 0.002)   # From Min == From Max -> 0
    lo = g.math("SUBTRACT", 90, 0, g.out(gi, "Threshold"), g.out(soft, 0))
    hi = g.math("ADD", 90, -120, g.out(gi, "Threshold"), g.out(soft, 0))
    f1 = g.maprange(260, 200, g.out(v, 0), g.out(lo, 0), g.out(hi, 0), smooth=True)
    dlo = g.math("SUBTRACT", 90, -260, g.out(gi, "Deep Threshold"), g.out(soft, 0))
    dhi = g.math("ADD", 90, -380, g.out(gi, "Deep Threshold"), g.out(soft, 0))
    f2 = g.maprange(260, -100, g.out(v, 0), g.out(dlo, 0), g.out(dhi, 0), smooth=True)
    sh = g.mix(450, -50, fac=g.out(f2, "Result"), a=g.out(gi, "Deep"), b=g.out(gi, "Shadow"))
    lit = g.mix(450, 250, "MULTIPLY", fac=1.0, a=g.out(gi, "Lit"), b=g.out(pal, "sun_tint"))
    col = g.mix(700, 100, fac=g.out(f1, "Result"), a=g.mixout(sh), b=g.mixout(lit))
    g.links.new(g.mixout(col), go.inputs["Color"])
    g.link(v, 0, go, "Light")
    g.link(f1, "Result", go, "Lit Mask")
    return ng


# ----------------------------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------------------------
def _fresh_mat(name):
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("hrp_ver") == SHADER_VER:
        return mat, False
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat["hrp_ver"] = SHADER_VER
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat, True


def _attr(g, name, kind, x, y):
    return g.n("ShaderNodeAttribute", x, y, label=name, attribute_name=name, attribute_type=kind)


def _haze(g, pal, x, y, color_sock, amount=1.0):
    """Aerial perspective: fade towards the horizon colour with camera distance."""
    cd = g.n("ShaderNodeCameraData", x - 600, y - 300)
    mr = g.maprange(x - 420, y - 300, g.out(cd, "View Distance"), g.out(pal, "haze_start"), g.out(pal, "haze_end"))
    pw = g.math("POWER", x - 260, y - 300, g.out(mr, "Result"), 0.8)
    am = g.math("MULTIPLY", x - 120, y - 300, g.out(pw, 0), g.out(pal, "haze_amount"))
    if isinstance(amount, bpy.types.NodeSocket) or amount != 1.0:
        am = g.math("MULTIPLY", x - 40, y - 400, g.out(am, 0), amount)
        am = g.math("MINIMUM", x, y - 400, g.out(am, 0), 0.92)
    m = g.mix(x - 40, y - 150, fac=g.out(am, 0), a=color_sock, b=g.out(pal, "haze_colour"))
    return g.mixout(m)


def _emit_out(g, color_sock, x, y, alpha=None, shadow_off=False, pal=None, haze=1.0):
    """Emission of the cel colour (+ haze); optional alpha cut-out; optional 'no cast shadow'."""
    if pal is not None and (isinstance(haze, bpy.types.NodeSocket) or haze > 0):
        color_sock = _haze(g, pal, x, y, color_sock, haze)
    em = g.n("ShaderNodeEmission", x, y)
    g.links.new(color_sock, em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    shader = em.outputs[0]
    if alpha is not None:
        tr = g.n("ShaderNodeBsdfTransparent", x, y + 150)
        step = g.math("GREATER_THAN", x - 180, y + 250, alpha, 0.5)
        ms = g.n("ShaderNodeMixShader", x + 200, y + 50)
        g.link(step, 0, ms, 0)
        g.links.new(tr.outputs[0], ms.inputs[1])
        g.links.new(shader, ms.inputs[2])
        shader = ms.outputs[0]
    if shadow_off:
        lp = g.n("ShaderNodeLightPath", x + 200, y + 300)
        tr2 = g.n("ShaderNodeBsdfTransparent", x + 200, y + 200)
        ms2 = g.n("ShaderNodeMixShader", x + 400, y + 50)
        g.link(lp, "Is Shadow Ray", ms2, 0)
        g.links.new(shader, ms2.inputs[1])
        g.links.new(tr2.outputs[0], ms2.inputs[2])
        shader = ms2.outputs[0]
    out = g.n("ShaderNodeOutputMaterial", x + 600, y)
    g.links.new(shader, out.inputs["Surface"])
    return out


def _grass_colours(g, pal, x, y, mask, pos):
    """Lit/shadow/deep for the grass+dirt mix at a world position (field patches included)."""
    pn = g.n("ShaderNodeTexNoise", x, y + 300, noise_dimensions="2D")
    g.set(pn, "Scale", 0.12)
    g.set(pn, "Detail", 3.0)
    g.links.new(pos, pn.inputs["Vector"])
    pf = g.maprange(x + 180, y + 300, g.out(pn, "Fac"), 0.45, 0.62, smooth=True)
    pa = g.math("MULTIPLY", x + 360, y + 300, g.out(pf, "Result"), g.out(pal, "patch_amount"))
    glit = g.mix(x + 540, y + 300, fac=g.out(pa, 0), a=g.out(pal, "grass_lit"), b=g.out(pal, "grass_lit2"))
    # dirt <-> grass by the painted mask (crisp, slightly broken edge)
    en = g.n("ShaderNodeTexNoise", x, y - 200, noise_dimensions="2D")
    g.set(en, "Scale", 9.0)
    g.links.new(pos, en.inputs["Vector"])
    me = g.math("MULTIPLY_ADD", x + 180, y - 200, g.out(en, "Fac"), 0.3, -0.15)
    m2 = g.math("ADD", x + 360, y - 200, mask, g.out(me, 0))
    mf = g.maprange(x + 540, y - 200, g.out(m2, 0), 0.38, 0.5, smooth=True)
    f = g.out(mf, "Result")
    lit = g.mix(x + 720, y + 200, fac=f, a=g.out(pal, "dirt_lit"), b=g.mixout(glit))
    sh = g.mix(x + 720, y, fac=f, a=g.out(pal, "dirt_shadow"), b=g.out(pal, "grass_shadow"))
    dp = g.mix(x + 720, y - 200, fac=f, a=g.out(pal, "dirt_deep"), b=g.out(pal, "grass_deep"))
    return g.mixout(lit), g.mixout(sh), g.mixout(dp), f


def _cel_node(g, pal, x, y, normal, lit, sh, deep, offset=None, deep_key="deep_threshold"):
    cel = g.n("ShaderNodeGroup", x, y)
    cel.node_tree = cel_group()
    g.links.new(normal, cel.inputs["Normal"])
    g.links.new(lit, cel.inputs["Lit"])
    g.links.new(sh, cel.inputs["Shadow"])
    g.links.new(deep, cel.inputs["Deep"])
    for k, pk in (("Threshold", "threshold"), ("Deep Threshold", deep_key), ("Softness", "softness")):
        g.link(pal, pk, cel, k)
    if offset is not None:
        g.links.new(offset, cel.inputs["Offset"])
    return cel


def _clump_node(g, pal, x, y, pos, base_n):
    cl = g.n("ShaderNodeGroup", x, y)
    cl.node_tree = clump_group()
    g.links.new(pos, cl.inputs["Position"])
    g.links.new(base_n, cl.inputs["Base Normal"])
    for k, pk in (("Size", "clump_size"), ("Strength", "clump_strength"), ("Small", "clump_small"),
                  ("Jitter", "brush_jitter")):
        g.link(pal, pk, cl, k)
    return cl


def ground_material():
    mat, rebuilt = _fresh_mat(MAT_GROUND)
    if not rebuilt:
        return mat
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1400, 0)
    pal.node_tree = palette_group()
    geo = g.n("ShaderNodeNewGeometry", -1400, 500)
    mask = _attr(g, "hrp_grass", "GEOMETRY", -1400, 700)
    has = g.math("ADD", -1200, 700, g.out(mask, "Fac"), 0.0)
    lit, sh, dp, f = _grass_colours(g, pal, -1000, 0, g.out(has, 0), g.out(geo, "Position"))
    cl = _clump_node(g, pal, -400, 500, g.out(geo, "Position"), g.out(geo, "Normal"))
    rel = g.maprange(-400, 750, f, 0.0, 1.0, 0.3, 1.0)
    # far away the clump field would turn into stripes: fade it out (40..150 m) and soften the split
    cdat = g.n("ShaderNodeCameraData", -600, 900)
    far = g.maprange(-400, 900, g.out(cdat, "View Distance"), 40.0, 150.0)
    near = g.math("SUBTRACT", -250, 900, 1.0, g.out(far, "Result"))
    boost0 = _attr(g, "hrp_haze_boost", "OBJECT", -600, 1100)             # Far Hills: no clump texture at all
    nofar = g.math("SUBTRACT", -400, 1100, 1.0, g.math("MINIMUM", -500, 1150, g.out(boost0, "Fac"), 1.0).outputs[0])
    near2 = g.math("MULTIPLY", -300, 1000, g.out(near, 0), g.out(nofar, 0))
    rel2 = g.math("MULTIPLY", -250, 750, g.out(rel, "Result"), g.out(near2, 0))
    nmix = g.mix(-150, 600, "MIX", "VECTOR", fac=g.out(rel2, 0), a=g.out(geo, "Normal"),
                 b=g.out(cl, "Normal"))
    dp2 = g.mix(-150, -100, fac=f, a=dp, b=sh)
    fwd = g.n("ShaderNodeVectorTransform", -1300, -650, vector_type="VECTOR", convert_from="CAMERA",
              convert_to="WORLD")
    fwd.inputs[0].default_value = (0.0, 0.0, -1.0)
    fsep = g.n("ShaderNodeSeparateXYZ", -1150, -650)
    g.link(fwd, 0, fsep, 0)
    fxy = g.n("ShaderNodeCombineXYZ", -1000, -650)
    g.link(fsep, "X", fxy, "X")
    g.link(fsep, "Y", fxy, "Y")
    fn_ = g.vmath("NORMALIZE", -900, -650, g.out(fxy, 0))
    side = g.vmath("CROSS_PRODUCT", -800, -700, g.out(fn_, 0), (0.0, 0.0, 1.0))
    pu = g.vmath("DOT_PRODUCT", -700, -550, g.out(geo, "Position"), g.out(side, 0))
    pv = g.vmath("DOT_PRODUCT", -700, -650, g.out(geo, "Position"), g.out(fn_, 0))
    stp = g.n("ShaderNodeCombineXYZ", -600, -600)
    g.link(g.math("MULTIPLY", -650, -500, g.out(pu, "Value"), 40.0), 0, stp, "X")
    g.link(g.math("MULTIPLY", -650, -700, g.out(pv, "Value"), 6.0), 0, stp, "Y")
    stn = g.n("ShaderNodeTexNoise", -750, -500, noise_dimensions="2D")
    g.set(stn, "Scale", 1.0)
    g.set(stn, "Detail", 1.0)
    g.link(stp, 0, stn, "Vector")
    stf = g.maprange(-600, -500, g.out(stn, "Fac"), 0.44, 0.56)
    stroke = g.mix(-450, -400, fac=g.out(stf, "Result"), a=g.out(pal, "grass_shadow"), b=g.out(pal, "grass_lit2"))
    ffar = g.maprange(-600, -600, g.out(g.n("ShaderNodeCameraData", -800, -600), "View Distance"), 6.0, 25.0, 0.3, 0.0)
    stg = g.math("MULTIPLY", -450, -500, g.out(ffar, "Result"), f)
    lit_s = g.mix(-300, -450, fac=g.out(stg, 0), a=lit, b=g.mixout(stroke))
    near_path = g.maprange(-600, -700, g.out(g.n("ShaderNodeCameraData", -800, -700), "View Distance"), 3.0, 15.0,
                           0.86, 1.0)
    npf = g.math("SUBTRACT", -450, -700, 1.0, f)
    npm = g.mix(-300, -700, "MIX", "FLOAT", fac=g.out(npf, 0), a=1.0, b=g.out(near_path, "Result"))
    npc = g.n("ShaderNodeCombineColor", -200, -700)
    for c in ("Red", "Green", "Blue"):
        g.links.new(g.mixout(npm), npc.inputs[c])
    lit_p = g.mix(-150, -500, "MULTIPLY", fac=1.0, a=g.mixout(lit_s), b=npc.outputs[0])
    cel = _cel_node(g, pal, 0, 200, g.mixout(nmix), g.mixout(lit_p), sh, g.mixout(dp2))
    sft0 = g.math("MULTIPLY_ADD", -150, 0, g.out(far, "Result"), 0.12, g.out(pal, "softness"))
    sft = g.math("MULTIPLY_ADD", -150, -150, g.math("MINIMUM", -300, -150, g.out(boost0, "Fac"), 1.0).outputs[0],
                 0.25, g.math("ADD", -300, -250, g.out(sft0, 0), 0.04).outputs[0])
    g.link(sft, 0, cel, "Softness")
    boost = _attr(g, "hrp_haze_boost", "OBJECT", 300, 500)
    hz = g.math("ADD", 450, 500, g.out(boost, "Fac"), 1.0)          # Far Hills get extra haze
    vn = g.n("ShaderNodeTexNoise", 200, 650, noise_dimensions="2D")
    g.set(vn, "Scale", 0.03)
    g.links.new(g.out(geo, "Position"), vn.inputs["Vector"])
    vj = g.maprange(350, 650, g.out(vn, "Fac"), 0.3, 0.7, 0.94, 1.06)
    vjc = g.n("ShaderNodeCombineColor", 500, 650)
    for c in ("Red", "Green", "Blue"):
        g.link(vj, "Result", vjc, c)
    cv = g.mix(600, 300, "MULTIPLY", fac=1.0, a=g.out(cel, "Color"), b=vjc.outputs[0])
    _emit_out(g, g.mixout(cv), 1300, 200, pal=pal, haze=g.out(hz, 0))
    mat["hrp_kind"] = "ground"
    return mat


def grass_material():
    mat, rebuilt = _fresh_mat(MAT_GRASS)
    if not rebuilt:
        return mat
    mat.use_backface_culling = False
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1600, 0)
    pal.node_tree = palette_group()
    geo = g.n("ShaderNodeNewGeometry", -1600, 500)
    gn = _attr(g, "hrp_gn", "INSTANCER", -1600, 800)
    mask = _attr(g, "hrp_mask", "INSTANCER", -1600, 1000)
    wind = _attr(g, "hrp_wind", "INSTANCER", -1600, 1200)
    hgt = _attr(g, "hrp_h", "GEOMETRY", -1600, 1400)
    lit0, sh, dp, f = _grass_colours(g, pal, -1200, 0, 1.0, g.out(geo, "Position"))
    # tufts at the path edge sink towards the shadow green instead of turning into dirt
    edge = g.maprange(-700, 1600, g.out(mask, "Fac"), 0.1, 0.65, smooth=True)
    edge_lit = g.mix(-500, 1600, fac=g.out(edge, "Result"), a=sh, b=lit0)
    # every blade a little lighter / darker
    rnd = _attr(g, "hrp_rand", "INSTANCER", -1600, 1600)
    wn = g.n("ShaderNodeTexWhiteNoise", -1400, 1700, noise_dimensions="1D")
    g.link(rnd, "Fac", wn, "W")
    jv = g.maprange(-1200, 1700, g.out(wn, "Value"), 0.0, 1.0, 0.9, 1.08)
    cc = g.n("ShaderNodeCombineColor", -800, 1750)
    for c in ("Red", "Green", "Blue"):
        g.link(jv, "Result", cc, c)
    lit = g.mixout(g.mix(-350, 1600, "MULTIPLY", fac=1.0, a=g.mixout(edge_lit), b=cc.outputs[0]))
    # tips catch the light: lighter + yellower on the lit side, wind gusts sweep a sheen across
    tipf = g.maprange(-500, 1300, g.out(hgt, "Fac"), 0.55, 1.0, smooth=True)
    tipa = g.math("MULTIPLY", -320, 1300, g.out(tipf, "Result"), g.out(pal, "tip_light"))
    sheen = g.maprange(-500, 1150, g.out(wind, "Fac"), 0.55, 0.85, smooth=True)
    sha = g.math("MULTIPLY", -320, 1150, g.out(sheen, "Result"), g.out(pal, "wind_sheen"))
    lit2 = g.mix(-150, 1250, fac=g.out(tipa, 0), a=lit, b=g.out(pal, "grass_tip"))
    lit3 = g.mix(30, 1150, "SCREEN", fac=g.out(sha, 0), a=g.mixout(lit2), b=g.out(pal, "grass_tip"))
    # roots sink into shadow
    rootf = g.maprange(-500, 900, g.out(hgt, "Fac"), 0.0, 0.5, smooth=True)
    rinv = g.math("SUBTRACT", -320, 900, 1.0, g.out(rootf, "Result"))
    rdk = g.math("MULTIPLY", -150, 900, g.out(rinv, 0), g.out(pal, "root_dark"))
    off0 = g.math("MULTIPLY", 30, 900, g.out(rdk, 0), -1.0)
    # each blade catches the light a little differently (blade-level cel steps up close)
    bvar = g.math("MULTIPLY", 30, 750, g.math("SUBTRACT", -100, 750, g.out(wn, "Value"), 0.5).outputs[0], 0.45)
    off = g.math("ADD", 180, 850, g.out(off0, 0), g.out(bvar, 0))
    cl = _clump_node(g, pal, -400, 500, g.out(geo, "Position"), g.out(gn, "Vector"))
    cel = _cel_node(g, pal, 250, 300, g.out(cl, "Normal"), g.mixout(lit3), sh, dp, offset=g.out(off, 0))
    hue = g.n("ShaderNodeHueSaturation", 450, 300)
    g.link(g.maprange(300, 450, g.out(wn, "Value"), 0.0, 1.0, 0.485, 0.515), "Result", hue, "Hue")
    g.link(cel, "Color", hue, "Color")
    _emit_out(g, g.out(hue, "Color"), 1150, 300, pal=pal)
    mat["hrp_kind"] = "grass"
    return mat


def _atlas_uv(g, x, y, rand_sock, per_side):
    """UV of one random tile of an N x N atlas (tile = floor(rand * N^2))."""
    uv = g.n("ShaderNodeUVMap", x, y + 200)
    n2 = per_side * per_side
    idx = g.math("MULTIPLY", x, y, rand_sock, n2 - 0.001)
    fl = g.math("FLOOR", x + 160, y, g.out(idx, 0))
    tx = g.math("MODULO", x + 320, y + 60, g.out(fl, 0), per_side)
    ty = g.math("FLOOR", x + 480, y - 60, g.math("DIVIDE", x + 320, y - 60, g.out(fl, 0), per_side).outputs[0])
    off = g.n("ShaderNodeCombineXYZ", x + 640, y)
    g.link(tx, 0, off, "X")
    g.link(ty, 0, off, "Y")
    a = g.vmath("ADD", x + 800, y + 100, g.out(uv, "UV"), g.out(off, 0))
    s = g.vmath("SCALE", x + 960, y + 100, g.out(a, 0), scale=1.0 / per_side)
    return s.outputs[0]


def flower_material():
    mat, rebuilt = _fresh_mat(MAT_FLOWER)
    if not rebuilt:
        return mat
    mat.use_backface_culling = False
    mat.surface_render_method = "DITHERED"
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1600, 0)
    pal.node_tree = palette_group()
    geo = g.n("ShaderNodeNewGeometry", -1600, 500)
    rnd = _attr(g, "hrp_rand", "INSTANCER", -1600, 800)
    ci = _attr(g, "hrp_col", "INSTANCER", -1600, 1000)
    gn = _attr(g, "hrp_gn", "INSTANCER", -1600, 1200)
    uvs = _atlas_uv(g, -1300, 900, g.out(rnd, "Fac"), assets.FLOWER_N)
    tex = g.n("ShaderNodeTexImage", -200, 900, interpolation="Linear")
    tex.image = assets.flower_atlas()
    tex.extension = "CLIP"
    g.links.new(uvs, tex.inputs["Vector"])
    # pick one of four colours: index 0..3
    c01 = g.mix(-200, 400, fac=g.math("GREATER_THAN", -400, 450, g.out(ci, "Fac"), 0.5).outputs[0],
                a=g.out(pal, "flower_a"), b=g.out(pal, "flower_b"))
    c23 = g.mix(-200, 250, fac=g.math("GREATER_THAN", -400, 300, g.out(ci, "Fac"), 2.5).outputs[0],
                a=g.out(pal, "flower_c"), b=g.out(pal, "flower_d"))
    c = g.mix(0, 350, fac=g.math("GREATER_THAN", -200, 550, g.out(ci, "Fac"), 1.5).outputs[0],
              a=g.mixout(c01), b=g.mixout(c23))
    # petal shading from the atlas R, yellow centre where R ~ 0
    pet = g.mix(200, 400, "MULTIPLY", fac=1.0, a=g.mixout(c),
                b=g.out(tex, "Color"))
    sep = g.n("ShaderNodeSeparateColor", 0, 700)
    g.link(tex, "Color", sep, 0)
    isc = g.math("LESS_THAN", 200, 700, g.out(sep, 0), 0.12)
    cdk = g.mix(300, 550, fac=0.45, a=g.mixout(c), b=g.out(pal, "flower_centre"))
    cdk2 = g.mix(300, 650, "MULTIPLY", fac=0.35, a=g.mixout(cdk), b=g.out(pal, "flower_shade"))
    col = g.mix(400, 450, fac=g.out(isc, 0), a=g.mixout(pet), b=g.mixout(cdk2))
    shc = g.mix(600, 350, "MULTIPLY", fac=1.0, a=g.mixout(col), b=g.out(pal, "flower_shade"))
    cl = _clump_node(g, pal, -200, -100, g.out(geo, "Position"), g.out(gn, "Vector"))
    cel = _cel_node(g, pal, 800, 300, g.out(cl, "Normal"), g.mixout(col), g.mixout(shc), g.mixout(shc))
    dim = g.n("ShaderNodeCombineColor", 900, 500)
    for c in ("Red", "Green", "Blue"):
        g.link(pal, "flower_dim", dim, c)
    dm = g.mix(1000, 400, "MULTIPLY", fac=1.0, a=g.out(cel, "Color"), b=dim.outputs[0])
    _emit_out(g, g.mixout(dm), 1650, 300, alpha=g.out(tex, "Alpha"), shadow_off=True, pal=pal)
    mat["hrp_kind"] = "flower"
    return mat


LEAF_STYLES = ("ROUND", "SMALL", "NEEDLE")


def leaves_name(style):
    return MAT_LEAVES if style == "ROUND" else f"{MAT_LEAVES} {style.title()}"


def leaves_material(style="ROUND"):
    mat, rebuilt = _fresh_mat(leaves_name(style))
    if not rebuilt:
        return mat
    mat.use_backface_culling = False
    mat.surface_render_method = "DITHERED"
    try:
        mat.use_transparent_shadow = True
    except AttributeError:
        pass
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1800, 0)
    pal.node_tree = palette_group()
    rnd = _attr(g, "hrp_rand", "INSTANCER", -1800, 800)
    nrm = _attr(g, "hrp_n", "INSTANCER", -1800, 1000)
    blm = _attr(g, "hrp_bloom", "INSTANCER", -1800, 1200)
    depth = _attr(g, "hrp_depth", "INSTANCER", -1800, 1400)
    uvs = _atlas_uv(g, -1500, 900, g.out(rnd, "Fac"), assets.ATLAS_N)
    tl = g.n("ShaderNodeTexImage", -300, 1100, label="leaf atlas")
    tl.image = assets.leaf_atlas(style=style)
    tl.extension = "CLIP"
    tb = g.n("ShaderNodeTexImage", -300, 800, label="blossom atlas")
    tb.image = assets.blossom_atlas()
    tb.extension = "CLIP"
    g.links.new(uvs, tl.inputs["Vector"])
    g.links.new(uvs, tb.inputs["Vector"])
    isb = g.math("GREATER_THAN", -300, 600, g.out(blm, "Fac"), 0.5)
    alpha = g.mix(0, 900, "MIX", "FLOAT", fac=g.out(isb, 0), a=g.out(tl, "Alpha"), b=g.out(tb, "Alpha"))
    shade = g.mix(0, 1100, fac=g.out(isb, 0), a=g.out(tl, "Color"), b=g.out(tb, "Color"))
    # normal: the canopy normal, nudged per card so neighbouring dabs break the terminator
    rn = g.n("ShaderNodeTexWhiteNoise", -1500, 300, noise_dimensions="1D")
    g.link(rnd, "Fac", rn, "W")
    rc = g.vmath("SUBTRACT", -1300, 300, g.out(rn, "Color"), (0.5, 0.5, 0.5))
    rj = g.vmath("SCALE", -1100, 300, g.out(rc, 0), scale=0.3)
    na = g.vmath("ADD", -900, 400, g.out(nrm, "Vector"), g.out(rj, 0))
    nn = g.vmath("NORMALIZE", -700, 400, g.out(na, 0))
    # inner cards (low depth) sink into shadow; AO darkens the pockets
    ao = g.n("ShaderNodeAmbientOcclusion", -900, -100)
    ao.samples = 8
    g.set(ao, "Distance", 1.5)
    aop = g.math("POWER", -700, -100, g.out(ao, "AO"), 1.5)
    aol = g.mix(-500, -100, "MIX", "FLOAT", fac=g.out(pal, "leaf_ao"), a=1.0, b=g.out(aop, 0))
    dpt = g.maprange(-700, -300, g.out(depth, "Fac"), 0.0, 1.0, -0.45, 0.08)
    off = g.math("MULTIPLY_ADD", -300, -200, g.out(aol, 0), 0.5, -0.5)
    off2 = g.math("ADD", -100, -200, g.out(off, 0), g.out(dpt, "Result"))
    # colours: leaves 4-tone (deep, shadow, mid, lit) / blossoms 2-tone
    lit = g.mix(-300, 300, fac=g.out(isb, 0), a=g.out(pal, "leaf_lit"), b=g.out(pal, "bloom_lit"))
    mid = g.mix(-300, 150, fac=g.out(isb, 0), a=g.out(pal, "leaf_mid"), b=g.out(pal, "bloom_lit"))
    shd = g.mix(-300, 0, fac=g.out(isb, 0), a=g.out(pal, "leaf_shadow"), b=g.out(pal, "bloom_shadow"))
    dp = g.mix(-300, -150, fac=g.out(isb, 0), a=g.out(pal, "leaf_deep"), b=g.out(pal, "bloom_deep"))
    # per-dab tone from the atlas (R): darker dabs read as separate brush marks
    litd = g.mix(-100, 300, "MULTIPLY", fac=0.6, a=g.mixout(lit), b=g.mixout(shade))
    midd = g.mix(-100, 150, "MULTIPLY", fac=0.6, a=g.mixout(mid), b=g.mixout(shade))
    shd = g.mix(-100, 0, "MULTIPLY", fac=0.55, a=g.mixout(shd), b=g.mixout(shade))
    dp = g.mix(-100, -150, "MULTIPLY", fac=0.35, a=g.mixout(dp), b=g.mixout(shade))
    cj = g.maprange(-300, -350, g.out(rn, "Value"), 0.0, 1.0, 0.8, 1.2)        # each card its own value
    cjc = g.n("ShaderNodeCombineColor", -200, -400)
    for c in ("Red", "Green", "Blue"):
        g.link(cj, "Result", cjc, c)
    shd = g.mix(50, 0, "MULTIPLY", fac=1.0, a=g.mixout(shd), b=cjc.outputs[0])
    dp = g.mix(50, -150, "MULTIPLY", fac=1.0, a=g.mixout(dp), b=cjc.outputs[0])
    cel = _cel_node(g, pal, 200, 200, g.out(nn, 0), g.mixout(litd), g.mixout(shd), g.mixout(dp),
                    offset=g.out(off2, 0), deep_key="leaf_deep_threshold")
    # second split inside the lit side: mid -> lit, plus a highlight rim on the brightest dabs
    v = g.out(cel, "Light")
    f3 = g.maprange(400, 0, v, 0.7, 0.76, smooth=True)
    sub = g.mix(600, 150, fac=g.out(f3, "Result"), a=g.mixout(midd), b=g.out(cel, "Color"))
    litm = g.out(cel, "Lit Mask")
    col = g.mix(800, 250, fac=litm, a=g.out(cel, "Color"), b=g.mixout(sub))
    f4 = g.maprange(600, -100, v, 0.95, 1.0, smooth=True)
    f4b = g.math("MULTIPLY", 800, -100, g.out(f4, "Result"), g.out(pal, "leaf_hi_amount"))
    f4c = g.math("MULTIPLY", 950, -100, g.out(f4b, 0), g.math("SUBTRACT", 800, -250, 1.0, g.out(isb, 0)).outputs[0])
    col2a = g.mix(1000, 250, fac=g.out(f4c, 0), a=g.mixout(col), b=g.out(pal, "leaf_hi"))
    # warm rim on sun-facing silhouette edges (golden hour)
    lw = g.n("ShaderNodeLayerWeight", 800, -400)
    g.links.new(nn.outputs[0], lw.inputs["Normal"])
    g.set(lw, "Blend", 0.35)
    rimf = g.maprange(950, -400, g.out(lw, "Facing"), 0.55, 0.8, smooth=True)
    outer = g.maprange(950, -550, g.out(depth, "Fac"), 0.62, 0.8, smooth=True)
    rl0 = g.math("MULTIPLY", 1050, -450, g.out(rimf, "Result"), g.out(outer, "Result"))
    rl = g.math("MULTIPLY", 1100, -400, g.out(rl0, 0), litm)
    ra = g.math("MULTIPLY", 1200, -450, g.out(rl, 0), g.out(pal, "rim_amount"))
    col2 = g.mix(1250, 250, fac=g.out(ra, 0), a=g.mixout(col2a), b=g.out(pal, "rim_colour"))
    # per-tree variation (object custom properties; 0 when missing = no change)
    hue = _attr(g, "hrp_hue", "OBJECT", 900, 600)
    val = _attr(g, "hrp_value", "OBJECT", 900, 800)
    hs = g.n("ShaderNodeHueSaturation", 1150, 450)
    g.link(g.math("ADD", 1050, 600, g.out(hue, "Fac"), 0.5), 0, hs, "Hue")
    g.link(g.math("ADD", 1050, 800, g.out(val, "Fac"), 1.0), 0, hs, "Value")
    g.links.new(g.mixout(col2), hs.inputs["Color"])
    _emit_out(g, g.out(hs, "Color"), 1950, 250, alpha=g.mixout(alpha), pal=pal)
    mat["hrp_kind"] = "leaves"
    mat["hrp_style"] = style
    return mat


def bark_material():
    mat, rebuilt = _fresh_mat(MAT_BARK)
    if not rebuilt:
        return mat
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -800, 0)
    pal.node_tree = palette_group()
    geo = g.n("ShaderNodeNewGeometry", -800, 400)
    # vertical bark strokes: stretched noise darkens a few streaks
    tc = g.n("ShaderNodeTexCoord", -800, 700)
    mp = g.vmath("MULTIPLY", -600, 700, g.out(tc, "Object"), (14.0, 14.0, 1.5))
    nz = g.n("ShaderNodeTexNoise", -400, 700)
    g.set(nz, "Scale", 1.0)
    g.link(mp, 0, nz, "Vector")
    st = g.maprange(-200, 700, g.out(nz, "Fac"), 0.55, 0.6, 0.0, 0.25)
    lit = g.mix(0, 500, fac=g.out(st, "Result"), a=g.out(pal, "bark_lit"), b=g.out(pal, "bark_shadow"))
    cel = _cel_node(g, pal, 200, 200, g.out(geo, "Normal"), g.mixout(lit), g.out(pal, "bark_shadow"),
                    g.out(pal, "bark_shadow"))
    _emit_out(g, g.out(cel, "Color"), 1050, 200, pal=pal)
    mat["hrp_kind"] = "bark"
    return mat


def fill_material():
    mat, rebuilt = _fresh_mat(MAT_FILL)
    if not rebuilt:
        return mat
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -600, 0)
    pal.node_tree = palette_group()
    geo = g.n("ShaderNodeNewGeometry", -600, 300)
    cel = _cel_node(g, pal, -200, 100, g.out(geo, "Normal"), g.out(pal, "leaf_shadow"), g.out(pal, "leaf_deep"),
                    g.out(pal, "leaf_deep"))
    _emit_out(g, g.out(cel, "Color"), 700, 100, pal=pal)
    mat["hrp_kind"] = "fill"
    return mat


def cloud_material(fill=False):
    """Painted cumulus: puff cards (or the fill mesh behind them) shaded as one soft form per cloud."""
    mat, rebuilt = _fresh_mat(MAT_CLOUD_FILL if fill else MAT_CLOUD)
    kind = "GEOMETRY" if fill else "INSTANCER"
    if not rebuilt:
        return mat
    mat.use_backface_culling = False
    if not fill:
        mat.surface_render_method = "DITHERED"
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1600, 0)
    pal.node_tree = palette_group()
    rnd = _attr(g, "hrp_rand", kind, -1600, 800)
    nrm = _attr(g, "hrp_n", kind, -1600, 1000)
    uvs = _atlas_uv(g, -1400, 900, g.out(rnd, "Fac"), assets.ATLAS_N)
    tex = g.n("ShaderNodeTexImage", -300, 900)
    tex.image = assets.cloud_atlas()
    tex.extension = "CLIP"
    g.links.new(uvs, tex.inputs["Vector"])
    geo = g.n("ShaderNodeNewGeometry", -1600, 300)
    cc = _attr(g, "hrp_cc", kind, -1600, 100)
    ch = _attr(g, "hrp_chalf", kind, -1600, -100)
    # screen-aligned sphere impostor per cloud: the normal depends only on where the pixel sits relative to
    # the cloud's centre on screen, never on which card (at which depth) drew it -> no visible discs
    rel = g.vmath("SUBTRACT", -1300, 200, g.out(geo, "Position"), g.out(cc, "Vector"))
    vt = g.n("ShaderNodeVectorTransform", -1150, 200, vector_type="VECTOR", convert_from="WORLD",
             convert_to="CAMERA")
    g.link(rel, 0, vt, 0)
    sp = g.n("ShaderNodeSeparateXYZ", -1000, 200)
    g.link(vt, 0, sp, 0)
    hs = g.n("ShaderNodeSeparateXYZ", -1300, -100)
    g.link(ch, "Vector", hs, 0)
    sx = g.math("MAXIMUM", -1150, -100, g.math("MULTIPLY", -1150, -50, g.math("ADD", -1250, -50, g.out(hs, "X"),
                g.out(hs, "Y")).outputs[0], 0.55).outputs[0], 0.01)
    sy = g.math("MAXIMUM", -1150, -250, g.math("MULTIPLY", -1250, -250, g.out(hs, "Z"), 1.15).outputs[0], 0.01)
    nx0 = g.math("DIVIDE", -900, 250, g.out(sp, "X"), g.out(sx, 0))
    ny0 = g.math("DIVIDE", -900, 100, g.out(sp, "Y"), g.out(sy, 0))
    uvm = g.n("ShaderNodeUVMap", -1100, 500)
    ub = g.vmath("SUBTRACT", -950, 500, g.out(uvm, "UV"), (0.5, 0.5, 0.0))
    usep = g.n("ShaderNodeSeparateXYZ", -850, 500)
    g.link(ub, 0, usep, 0)
    bulge = 0.0 if fill else 0.3
    nx = g.math("MULTIPLY_ADD", -850, 250, g.out(usep, "X"), bulge, g.out(nx0, 0))
    ny = g.math("MULTIPLY_ADD", -850, 100, g.out(usep, "Y"), bulge, g.out(ny0, 0))
    r2 = g.math("ADD", -700, 200, g.math("MULTIPLY", -780, 250, g.out(nx, 0), g.out(nx, 0)).outputs[0],
                g.math("MULTIPLY", -780, 100, g.out(ny, 0), g.out(ny, 0)).outputs[0])
    nz = g.math("SQRT", -550, 150, g.math("MAXIMUM", -620, 150, g.math("SUBTRACT", -700, 100, 1.0,
                g.out(r2, 0)).outputs[0], 0.04).outputs[0])
    cn = g.n("ShaderNodeCombineXYZ", -450, 200)
    g.link(nx, 0, cn, "X")
    g.link(ny, 0, cn, "Y")
    g.link(nz, 0, cn, "Z")
    cnn = g.vmath("NORMALIZE", -350, 200, g.out(cn, 0))
    vw = g.n("ShaderNodeVectorTransform", -250, 200, vector_type="NORMAL", convert_from="CAMERA",
             convert_to="WORLD")
    g.link(cnn, 0, vw, 0)
    nn = g.vmath("NORMALIZE", -150, 400, g.out(vw, 0))
    # light from the sun (Shader to RGB) blended with "up-ness" so tops read lit and only the underside shades
    dif = g.n("ShaderNodeBsdfDiffuse", -500, 200)
    g.links.new(nn.outputs[0], dif.inputs["Normal"])
    s2r = g.n("ShaderNodeShaderToRGB", -350, 200)
    g.link(dif, 0, s2r, 0)
    bw = g.n("ShaderNodeRGBToBW", -200, 200)
    g.link(s2r, "Color", bw, 0)
    lv = g.math("DIVIDE", -50, 200, g.math("MULTIPLY", -120, 260, g.out(bw, 0), math.pi).outputs[0],
                g.out(pal, "light_scale"))
    sz = g.n("ShaderNodeSeparateXYZ", -500, 600)
    g.link(nn, 0, sz, 0)
    up = g.math("MULTIPLY_ADD", -300, 600, g.out(sz, "Z"), 0.5, 0.5)
    v = g.mix(100, 400, "MIX", "FLOAT", fac=0.55, a=g.out(lv, 0), b=g.out(up, 0))
    vv = g.math("ADD", 250, 400, g.mixout(v), 0.0)
    ramp = g.n("ShaderNodeValToRGB", 400, 400, label="cloud ramp")
    g.links.new(g.out(vv, 0), ramp.inputs[0])
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    cr.elements[0].position = 0.03
    cr.elements[1].position = 0.34
    cr.elements.new(0.13)
    cr.elements.new(0.29)
    # drive the ramp stops from the palette: under (warm bounce) -> shadow -> lit
    mix_under = g.mix(600, 600, fac=g.out(ramp, "Alpha"), a=g.out(pal, "cloud_deep"), b=g.out(pal, "cloud_shadow"))
    cr.elements[0].alpha = 0.0
    cr.elements[1].alpha = 1.0
    els = sorted(cr.elements, key=lambda e: e.position)
    els[0].color = (0, 0, 0, 0.0)          # bounce
    els[1].color = (0, 0, 0, 1.0)          # flat shadow mid-tone ...
    els[2].color = (0, 0, 0, 1.0)          # ... held flat
    els[3].color = (1, 1, 1, 1.0)          # crisp step to lit
    sep = g.n("ShaderNodeSeparateColor", 600, 400)
    g.link(ramp, "Color", sep, 0)
    col = g.mix(800, 500, fac=g.out(sep, 0), a=g.mixout(mix_under), b=g.out(pal, "cloud_lit"))
    tint = g.mix(950, 500, "MULTIPLY", fac=1.0, a=g.mixout(col), b=g.out(pal, "sun_tint"))
    _emit_out(g, g.mixout(tint), 1600, 200, alpha=None if fill else g.out(tex, "Alpha"), pal=pal, haze=0.6)
    mat["hrp_kind"] = "cloud_fill" if fill else "cloud"
    return mat


def cloud_fill_material():
    return cloud_material(fill=True)


def all_materials():
    return [ground_material(), grass_material(), flower_material(), bark_material(), fill_material(),
            cloud_material(), cloud_fill_material()] + \
        [leaves_material(st) for st in LEAF_STYLES]
