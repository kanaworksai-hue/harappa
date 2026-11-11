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
from .util import BUILDING, G, VERSION_KEY, fresh_group, iface, only, srgb, stamp

SHADER_VER = 35
PALETTE = "HRP Palette"
CLUMP = "HRP Clump Normal"
CEL = "HRP Cel"
GRADE = "HRP Grade"
MAT_GROUND = "HRP Ground"
MAT_GRASS = "HRP Grass"
MAT_FLOWER = "HRP Flower"
MAT_LEAVES = "HRP Leaves"
MAT_BARK = "HRP Bark"
MAT_FILL = "HRP Canopy Fill"
MAT_CLOUD = "HRP Cloud"
MAT_CLOUD_FILL = "HRP Cloud Fill"
MAT_CUMULUS = "HRP Cumulus"
MAT_RIDGE = "HRP Ridge"
SUN = "HRP Sun"

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
    "ever_lit": ("RGB", "#8FCB46"),         # evergreens (conifer, pine): they keep their green in autumn
    "ever_mid": ("RGB", "#3F9440"),
    "ever_shadow": ("RGB", "#1F6B52"),
    "ever_deep": ("RGB", "#0C3A44"),
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
    # sky and clouds (1.1)
    "cloud_rim": ("RGB", "#FFF6D6"),        # the bright edge of a cloud with the sun behind it
    "cloud_rim_amount": ("VALUE", 0.35),
    "cloud_threshold": ("VALUE", 0.4),      # where a cloud turns from lit to shaded
    "mountain_1": ("RGB", "#3F9A6A"),       # distant ridges, near to far
    "mountain_2": ("RGB", "#5AA0B4"),
    "mountain_3": ("RGB", "#8FBFE0"),
    "style_sat": ("VALUE", 1.0),            # the paint style's share of the grade (the season sets grade_*)
    "style_contrast": ("VALUE", 1.0),
    "ridge_soft": ("VALUE", 0.02),          # softness of the painted shapes on the distant ridges
    "sky_brush": ("VALUE", 0.0),            # kept with the palette so presets carry them; the sky reads them
    "sky_bands": ("VALUE", 0.0),
    "sky_curve": ("VALUE", 1.0),
    "cirrus_mult": ("VALUE", 1.0),
    "cloud_jitter": ("VALUE", 1.0),         # how broken the painted edge between cloud tones is
    "season_sat": ("VALUE", 1.0),           # the season's share of the grade
    "season_contrast": ("VALUE", 1.0),
    "grade_sat": ("VALUE", 1.0),            # overall colour strength of everything Harappa paints
    "grade_contrast": ("VALUE", 1.0),       # overall contrast (around mid grey)
    "sun_x": ("VALUE", 0.0),                # direction to the sun (world), written with the sun
    "sun_y": ("VALUE", 0.0),
    "sun_z": ("VALUE", 1.0),
}


def _lin(v):
    return (*srgb(v), 1.0) if isinstance(v, str) else v


# ----------------------------------------------------------------------------------------------
# palette
# ----------------------------------------------------------------------------------------------
def palette_group():
    ng = bpy.data.node_groups.get(PALETTE)
    if ng is not None and ng.get(VERSION_KEY) == SHADER_VER:
        _rebuild_stale()
        return ng
    kept = _palette_values(ng)             # a scene made with an older version keeps its colours
    ng, _rebuilt = fresh_group(PALETTE, "ShaderNodeTree", SHADER_VER)
    g = G(ng)
    out = g.n("NodeGroupOutput", 600, 0)
    y = 0
    for key, (kind, default) in PALETTE_KEYS.items():
        if kind == "RGB":
            iface(ng, key, "OUTPUT", "NodeSocketColor")
            n = g.n("ShaderNodeRGB", 0, y, label=key)
            g.out(n).default_value = _lin(default)
        else:
            iface(ng, key, "OUTPUT", "NodeSocketFloat")
            n = g.n("ShaderNodeValue", 0, y, label=key)
            g.out(n).default_value = default
        g.links.new(g.out(n), out.inputs[key])
        y -= 120
    for key, value in kept.items():
        only(ng.nodes[key].outputs).default_value = value
    stamp(ng, SHADER_VER)
    _rebuild_stale()
    return ng


def _palette_values(ng):
    """Colours and numbers stored in an existing palette group (of any version)."""
    kept = {}
    if ng is None:
        return kept
    for key, (kind, _default) in PALETTE_KEYS.items():
        n = ng.nodes.get(key)
        live = [s for s in n.outputs if s.enabled] if n is not None else []
        if len(live) == 1:
            v = live[0].default_value
            kept[key] = tuple(v) if kind == "RGB" else float(v)
    return kept


_stale = {"busy": False}


def _rebuild_stale():
    """Rebuild every Harappa material an older version left in the file, in one go.

    All materials read HRP Palette, HRP Cel and HRP Clump Normal. Rebuilding one of those groups gives its
    sockets new identifiers, and a material that still holds the old ones loses those links without any error
    (it renders grey). So when the version changes, nothing may be left behind for 'the next time it is used'."""
    if _stale["busy"]:
        return
    builders = {MAT_GROUND: ground_material, MAT_GRASS: grass_material, MAT_FLOWER: flower_material,
                MAT_BARK: bark_material, MAT_FILL: fill_material, MAT_CLOUD: cloud_material,
                MAT_CLOUD_FILL: cloud_fill_material, MAT_CUMULUS: cumulus_material,
                MAT_RIDGE: ridge_material}
    for style in LEAF_STYLES:
        builders[leaves_name(style)] = lambda style=style: leaves_material(style)
    old = [name for name in builders
           if bpy.data.materials.get(name) is not None
           and bpy.data.materials[name].get(VERSION_KEY) not in (SHADER_VER, BUILDING)]
    if not old:
        return
    _stale["busy"] = True
    try:
        for name in old:
            builders[name]()
        sun = bpy.data.objects.get(SUN)
        if sun is not None and sun.type == "LIGHT":
            drive_light_scale(sun)             # the drivers sat on the old palette nodes
            drive_sun_dir(sun)
    finally:
        _stale["busy"] = False


def palette_set(key, value):
    ng = palette_group()
    n = ng.nodes.get(key)
    if n is None:
        return
    if PALETTE_KEYS[key][0] == "RGB":
        only(n.outputs).default_value = _lin(value) if isinstance(value, str) else (*value[:3], 1.0)
    else:
        only(n.outputs).default_value = float(value)


def palette_get(key):
    n = palette_group().nodes.get(key)
    v = only(n.outputs).default_value
    return tuple(v[:3]) if PALETTE_KEYS[key][0] == "RGB" else float(v)


def drive_light_scale(sun):
    """light_scale = sun strength x brightest colour channel, as a driver (follows edits live)."""
    ng = palette_group()
    sock = only(ng.nodes["light_scale"].outputs)
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


SUN_AXES = (("x", "cos(rz)*sin(ry)*cos(rx) + sin(rz)*sin(rx)"),
            ("y", "sin(rz)*sin(ry)*cos(rx) - cos(rz)*sin(rx)"),
            ("z", "cos(ry)*cos(rx)"))


def drive_direction(sock, sun, expression):
    """Drive one component of 'the direction to the sun' from the sun object's rotation (simple expressions, so
    it works with auto-run scripts off)."""
    try:
        sock.driver_remove("default_value")
    except TypeError:
        pass
    if sun is None:
        return
    d = sock.driver_add("default_value").driver
    d.type = "SCRIPTED"
    for name, kind in (("rx", "ROT_X"), ("ry", "ROT_Y"), ("rz", "ROT_Z")):
        v = d.variables.new()
        v.name = name
        v.type = "TRANSFORMS"
        v.targets[0].id = sun
        v.targets[0].transform_type = kind
        v.targets[0].rotation_mode = "XYZ"
        v.targets[0].transform_space = "WORLD_SPACE"
    d.expression = expression


def drive_sun_dir(sun):
    """sun_x / sun_y / sun_z follow the sun object, so cloud rims stay right when the user turns the sun."""
    ng = palette_group()
    for axis, expr in SUN_AXES:
        drive_direction(only(ng.nodes["sun_" + axis].outputs), sun, expr)


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
    g.link(sz, 0, q, ("Vector", 1))
    warp = g.n("ShaderNodeTexNoise", -1000, 400, noise_dimensions="2D")
    g.set(warp, "Scale", 0.9)
    g.set(warp, "Detail", 2.0)
    g.link(q, 0, warp, "Vector")
    wc = g.vmath("SUBTRACT", -800, 400, g.out(warp, "Color"), (0.5, 0.5, 0.5))
    wq = g.vmath("MULTIPLY_ADD", -600, 250, g.out(wc), (0.9, 0.55, 0.0))   # stretched sideways
    g.link(q, 0, wq, ("Vector", 2))

    def dome(scale, x, y):
        sc = g.vmath("SCALE", x, y, g.out(wq), scale=scale)
        v = g.n("ShaderNodeTexVoronoi", x + 180, y, voronoi_dimensions="2D", feature="F1")
        g.set(v, "Scale", 1.0)
        g.set(v, "Randomness", 0.9)
        g.link(sc, 0, v, "Vector")
        d = g.vmath("SUBTRACT", x + 380, y, g.out(sc), g.out(v, "Position"))
        dist = g.out(v, "Distance")
        return d, dist

    d1, dist1 = dome(1.0, -400, 300)
    d2, dist2 = dome(2.7, -400, -50)
    d3, dist3 = dome(7.0, -400, -200)
    small = g.vmath("SCALE", 100, -50, g.out(d2), scale=g.out(gi, "Small"))
    tiny_w = g.math("MULTIPLY", 0, -250, g.out(gi, "Small"), 0.45)
    tiny = g.vmath("SCALE", 100, -200, g.out(d3), scale=g.out(tiny_w))
    tot0 = g.vmath("ADD", 200, 150, g.out(d1), g.out(small))
    tot = g.vmath("ADD", 300, 150, g.out(tot0), g.out(tiny))

    # brush jitter: fine noise so the terminator breaks into blade-like strokes
    jq = g.vmath("SCALE", -400, -350, g.out(q), scale=1.0)
    jn = g.n("ShaderNodeTexNoise", -200, -350, noise_dimensions="3D")
    g.set(jn, "Scale", 28.0)
    g.set(jn, "Detail", 1.0)
    g.link(jq, 0, jn, "Vector")
    jc = g.vmath("SUBTRACT", 0, -350, g.out(jn, "Color"), (0.5, 0.5, 0.5))
    js = g.vmath("SCALE", 200, -350, g.out(jc), scale=g.out(gi, "Jitter"))
    tot2 = g.vmath("ADD", 500, 0, g.out(tot), g.out(js))
    st = g.vmath("SCALE", 700, 0, g.out(tot2), scale=g.out(gi, "Strength"))
    flat = g.vmath("MULTIPLY", 880, 0, g.out(st), (1.0, 1.0, 0.0))
    nb = g.vmath("NORMALIZE", 880, -200, g.out(gi, "Base Normal"))
    add = g.vmath("ADD", 1050, 0, g.out(nb), g.out(flat))
    nn = g.vmath("NORMALIZE", 1220, 0, g.out(add))
    g.link(nn, 0, go, "Normal")
    g.links.new(dist1, go.inputs["Clump"])
    stamp(ng, SHADER_VER)
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
    g.link(dif, 0, s2r, "Shader")
    bw = g.n("ShaderNodeRGBToBW", -420, 200)
    g.link(s2r, "Color", bw, "Color")
    # v = lum * pi / light_scale + offset
    m1 = g.math("MULTIPLY", -250, 200, g.out(bw), math.pi)
    m2 = g.math("DIVIDE", -80, 200, g.out(m1), g.out(pal, "light_scale"))
    v = g.math("ADD", 90, 200, g.out(m2), g.out(gi, "Offset"))
    soft = g.math("MAXIMUM", -80, -60, g.out(gi, "Softness"), 0.002)   # From Min == From Max -> 0
    lo = g.math("SUBTRACT", 90, 0, g.out(gi, "Threshold"), g.out(soft))
    hi = g.math("ADD", 90, -120, g.out(gi, "Threshold"), g.out(soft))
    f1 = g.maprange(260, 200, g.out(v), g.out(lo), g.out(hi), smooth=True)
    dlo = g.math("SUBTRACT", 90, -260, g.out(gi, "Deep Threshold"), g.out(soft))
    dhi = g.math("ADD", 90, -380, g.out(gi, "Deep Threshold"), g.out(soft))
    f2 = g.maprange(260, -100, g.out(v), g.out(dlo), g.out(dhi), smooth=True)
    sh = g.mix(450, -50, fac=g.out(f2, "Result"), a=g.out(gi, "Deep"), b=g.out(gi, "Shadow"))
    lit = g.mix(450, 250, "MULTIPLY", fac=1.0, a=g.out(gi, "Lit"), b=g.out(pal, "sun_tint"))
    col = g.mix(700, 100, fac=g.out(f1, "Result"), a=g.mixout(sh), b=g.mixout(lit))
    g.links.new(g.mixout(col), go.inputs["Color"])
    g.link(v, 0, go, "Light")
    g.link(f1, "Result", go, "Lit Mask")
    stamp(ng, SHADER_VER)
    return ng


def grade_group():
    """One grade for every Harappa material: colour strength and contrast, read from the palette. It sits in
    the materials (not in the compositor), so the viewport shows what the render shows and the user's own
    compositing is left alone. At 1.0 / 1.0 it changes nothing."""
    ng, rebuilt = fresh_group(GRADE, "ShaderNodeTree", SHADER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Color", "INPUT", "NodeSocketColor", (0.5, 0.5, 0.5, 1))
    iface(ng, "Color", "OUTPUT", "NodeSocketColor")
    gi = g.n("NodeGroupInput", -900, 0)
    go = g.n("NodeGroupOutput", 900, 0)
    pal = g.n("ShaderNodeGroup", -900, -300)
    pal.node_tree = palette_group()
    bw = g.n("ShaderNodeRGBToBW", -700, 150)
    g.link(gi, "Color", bw, "Color")
    grey = g.n("ShaderNodeCombineColor", -620, 0)
    for ch in ("Red", "Green", "Blue"):
        g.links.new(g.out(bw), grey.inputs[ch])
    amount = g.math("MULTIPLY", -700, -150, g.out(pal, "grade_sat"), g.out(pal, "style_sat"))
    amount = g.math("MULTIPLY", -600, -150, g.out(amount), g.out(pal, "season_sat"))
    power = g.math("MULTIPLY", -100, -500, g.out(pal, "grade_contrast"), g.out(pal, "style_contrast"))
    power = g.math("MULTIPLY", 0, -500, g.out(power), g.out(pal, "season_contrast"))
    sat = g.mix(-500, 0, dtype="RGBA", fac=g.out(amount), a=g.out(grey), b=g.out(gi, "Color"))
    sat.clamp_factor = False                       # above 1 = stronger than the palette colour
    sep = g.n("ShaderNodeSeparateColor", -300, 0)
    g.links.new(g.mixout(sat), sep.inputs["Color"])
    comb = g.n("ShaderNodeCombineColor", 500, 0)
    for i, ch in enumerate(("Red", "Green", "Blue")):
        y = 200 - i * 200
        pos = g.math("MAXIMUM", -120, y, g.out(sep, ch), 0.0)
        rel = g.math("DIVIDE", 20, y, g.out(pos), 0.18)
        pw = g.math("POWER", 160, y, g.out(rel), g.out(power))
        g.links.new(g.out(g.math("MULTIPLY", 300, y, g.out(pw), 0.18)), comb.inputs[ch])
    g.link(comb, "Color", go, "Color")
    stamp(ng, SHADER_VER)
    return ng


# ----------------------------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------------------------
def _fresh_mat(name):
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(VERSION_KEY) == SHADER_VER:
        return mat, False
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat[VERSION_KEY] = BUILDING
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat, True


def _done(mat, kind):
    """The material is complete: only now it counts as built (see util.fresh_group)."""
    mat["hrp_kind"] = kind
    stamp(mat, SHADER_VER)


def _attr(g, name, kind, x, y):
    return g.n("ShaderNodeAttribute", x, y, label=name, attribute_name=name, attribute_type=kind)


def _haze(g, pal, x, y, color_sock, amount=1.0, cap=0.92):
    """Aerial perspective: fade towards the horizon colour with camera distance (boosted haze stops at cap)."""
    cd = g.n("ShaderNodeCameraData", x - 600, y - 300)
    mr = g.maprange(x - 420, y - 300, g.out(cd, "View Distance"), g.out(pal, "haze_start"), g.out(pal, "haze_end"))
    pw = g.math("POWER", x - 260, y - 300, g.out(mr, "Result"), 0.8)
    am = g.math("MULTIPLY", x - 120, y - 300, g.out(pw), g.out(pal, "haze_amount"))
    if isinstance(amount, bpy.types.NodeSocket) or amount != 1.0:
        am = g.math("MULTIPLY", x - 40, y - 400, g.out(am), amount)
        am = g.math("MINIMUM", x, y - 400, g.out(am), cap)
    m = g.mix(x - 40, y - 150, fac=g.out(am), a=color_sock, b=g.out(pal, "haze_colour"))
    return g.mixout(m)


def _emit_out(g, color_sock, x, y, alpha=None, shadow_off=False, pal=None, haze=1.0, haze_cap=0.92):
    """Emission of the cel colour (+ haze); optional alpha cut-out; optional 'no cast shadow'."""
    if pal is not None:
        gr = g.n("ShaderNodeGroup", x - 760, y + 120, label="grade")
        gr.node_tree = grade_group()
        g.links.new(color_sock, gr.inputs["Color"])
        color_sock = g.out(gr, "Color")
    if pal is not None and (isinstance(haze, bpy.types.NodeSocket) or haze > 0):
        color_sock = _haze(g, pal, x, y, color_sock, haze, haze_cap)
    em = g.n("ShaderNodeEmission", x, y)
    g.links.new(color_sock, em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    shader = g.out(em)
    if alpha is not None:
        tr = g.n("ShaderNodeBsdfTransparent", x, y + 150)
        step = g.math("GREATER_THAN", x - 180, y + 250, alpha, 0.5)
        ms = g.n("ShaderNodeMixShader", x + 200, y + 50)
        g.link(step, 0, ms, "Fac")
        g.link(tr, 0, ms, ("Shader", 0))
        g.link(shader, None, ms, ("Shader", 1))
        shader = g.out(ms)
    if shadow_off:
        lp = g.n("ShaderNodeLightPath", x + 200, y + 300)
        tr2 = g.n("ShaderNodeBsdfTransparent", x + 200, y + 200)
        ms2 = g.n("ShaderNodeMixShader", x + 400, y + 50)
        g.link(lp, "Is Shadow Ray", ms2, "Fac")
        g.link(shader, None, ms2, ("Shader", 0))
        g.link(tr2, 0, ms2, ("Shader", 1))
        shader = g.out(ms2)
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
    glit = g.mix(x + 540, y + 300, fac=g.out(pa), a=g.out(pal, "grass_lit"), b=g.out(pal, "grass_lit2"))
    # dirt <-> grass by the painted mask (crisp, slightly broken edge)
    en = g.n("ShaderNodeTexNoise", x, y - 200, noise_dimensions="2D")
    g.set(en, "Scale", 9.0)
    g.links.new(pos, en.inputs["Vector"])
    me = g.math("MULTIPLY_ADD", x + 180, y - 200, g.out(en, "Fac"), 0.3, -0.15)
    m2 = g.math("ADD", x + 360, y - 200, mask, g.out(me))
    mf = g.maprange(x + 540, y - 200, g.out(m2), 0.38, 0.5, smooth=True)
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
    lit, sh, dp, f = _grass_colours(g, pal, -1000, 0, g.out(has), g.out(geo, "Position"))
    cl = _clump_node(g, pal, -400, 500, g.out(geo, "Position"), g.out(geo, "Normal"))
    rel = g.maprange(-400, 750, f, 0.0, 1.0, 0.3, 1.0)
    # far away the clump field would turn into stripes: fade it out (40..150 m) and soften the split
    cdat = g.n("ShaderNodeCameraData", -600, 900)
    far = g.maprange(-400, 900, g.out(cdat, "View Distance"), 40.0, 150.0)
    near = g.math("SUBTRACT", -250, 900, 1.0, g.out(far, "Result"))
    boost0 = _attr(g, "hrp_haze_boost", "OBJECT", -600, 1100)             # Far Hills: no clump texture at all
    nofar = g.math("SUBTRACT", -400, 1100, 1.0, g.out(g.math("MINIMUM", -500, 1150, g.out(boost0, "Fac"), 1.0)))
    near2 = g.math("MULTIPLY", -300, 1000, g.out(near), g.out(nofar))
    rel2 = g.math("MULTIPLY", -250, 750, g.out(rel, "Result"), g.out(near2))
    nmix = g.mix(-150, 600, "MIX", "VECTOR", fac=g.out(rel2), a=g.out(geo, "Normal"),
                 b=g.out(cl, "Normal"))
    dp2 = g.mix(-150, -100, fac=f, a=dp, b=sh)
    fwd = g.n("ShaderNodeVectorTransform", -1300, -650, vector_type="VECTOR", convert_from="CAMERA",
              convert_to="WORLD")
    g.set(fwd, "Vector", (0.0, 0.0, -1.0))
    fsep = g.n("ShaderNodeSeparateXYZ", -1150, -650)
    g.link(fwd, 0, fsep, "Vector")
    fxy = g.n("ShaderNodeCombineXYZ", -1000, -650)
    g.link(fsep, "X", fxy, "X")
    g.link(fsep, "Y", fxy, "Y")
    fn_ = g.vmath("NORMALIZE", -900, -650, g.out(fxy))
    side = g.vmath("CROSS_PRODUCT", -800, -700, g.out(fn_), (0.0, 0.0, 1.0))
    pu = g.vmath("DOT_PRODUCT", -700, -550, g.out(geo, "Position"), g.out(side))
    pv = g.vmath("DOT_PRODUCT", -700, -650, g.out(geo, "Position"), g.out(fn_))
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
    lit_s = g.mix(-300, -450, fac=g.out(stg), a=lit, b=g.mixout(stroke))
    near_path = g.maprange(-600, -700, g.out(g.n("ShaderNodeCameraData", -800, -700), "View Distance"), 3.0, 15.0,
                           0.86, 1.0)
    npf = g.math("SUBTRACT", -450, -700, 1.0, f)
    npm = g.mix(-300, -700, "MIX", "FLOAT", fac=g.out(npf), a=1.0, b=g.out(near_path, "Result"))
    npc = g.n("ShaderNodeCombineColor", -200, -700)
    for c in ("Red", "Green", "Blue"):
        g.links.new(g.mixout(npm), npc.inputs[c])
    lit_p = g.mix(-150, -500, "MULTIPLY", fac=1.0, a=g.mixout(lit_s), b=g.out(npc))
    cel = _cel_node(g, pal, 0, 200, g.mixout(nmix), g.mixout(lit_p), sh, g.mixout(dp2))
    sft0 = g.math("MULTIPLY_ADD", -150, 0, g.out(far, "Result"), 0.12, g.out(pal, "softness"))
    sft = g.math("MULTIPLY_ADD", -150, -150, g.out(g.math("MINIMUM", -300, -150, g.out(boost0, "Fac"), 1.0)),
                 0.25, g.out(g.math("ADD", -300, -250, g.out(sft0), 0.04)))
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
    cv = g.mix(600, 300, "MULTIPLY", fac=1.0, a=g.out(cel, "Color"), b=g.out(vjc))
    _emit_out(g, g.mixout(cv), 1300, 200, pal=pal, haze=g.out(hz))
    _done(mat, "ground")
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
    lit = g.mixout(g.mix(-350, 1600, "MULTIPLY", fac=1.0, a=g.mixout(edge_lit), b=g.out(cc)))
    # tips catch the light: lighter + yellower on the lit side, wind gusts sweep a sheen across
    tipf = g.maprange(-500, 1300, g.out(hgt, "Fac"), 0.55, 1.0, smooth=True)
    tipa = g.math("MULTIPLY", -320, 1300, g.out(tipf, "Result"), g.out(pal, "tip_light"))
    sheen = g.maprange(-500, 1150, g.out(wind, "Fac"), 0.55, 0.85, smooth=True)
    sha = g.math("MULTIPLY", -320, 1150, g.out(sheen, "Result"), g.out(pal, "wind_sheen"))
    lit2 = g.mix(-150, 1250, fac=g.out(tipa), a=lit, b=g.out(pal, "grass_tip"))
    lit3 = g.mix(30, 1150, "SCREEN", fac=g.out(sha), a=g.mixout(lit2), b=g.out(pal, "grass_tip"))
    # roots sink into shadow
    rootf = g.maprange(-500, 900, g.out(hgt, "Fac"), 0.0, 0.5, smooth=True)
    rinv = g.math("SUBTRACT", -320, 900, 1.0, g.out(rootf, "Result"))
    rdk = g.math("MULTIPLY", -150, 900, g.out(rinv), g.out(pal, "root_dark"))
    off0 = g.math("MULTIPLY", 30, 900, g.out(rdk), -1.0)
    # each blade catches the light a little differently (blade-level cel steps up close)
    bvar = g.math("MULTIPLY", 30, 750, g.out(g.math("SUBTRACT", -100, 750, g.out(wn, "Value"), 0.5)), 0.45)
    off1 = g.math("ADD", 180, 850, g.out(off0), g.out(bvar))
    cl = _clump_node(g, pal, -400, 500, g.out(geo, "Position"), g.out(gn, "Vector"))
    # Far Hills fringe (hrp_haze_boost on the object): shade each tuft exactly like the hill under its root -
    # the hill's normal, no blade detail, the same soft split and extra haze. On the slope the tufts then
    # disappear into the hill and along the crest they only soften its outline, instead of standing there as
    # sparse dark marks
    boost = _attr(g, "hrp_haze_boost", "OBJECT", -900, 2000)
    far_f = g.math("MINIMUM", -750, 2000, g.out(boost, "Fac"), 1.0)
    near_f = g.math("SUBTRACT", -600, 2000, 1.0, g.out(far_f))
    off = g.math("MULTIPLY", 330, 850, g.out(off1), g.out(near_f))
    nrm = g.mix(-150, 550, "MIX", "VECTOR", fac=g.out(far_f), a=g.out(cl, "Normal"), b=g.out(gn, "Vector"))
    lit4 = g.mix(180, 1150, fac=g.out(far_f), a=g.mixout(lit3), b=lit0)
    cel = _cel_node(g, pal, 250, 300, g.mixout(nrm), g.mixout(lit4), sh, dp, offset=g.out(off))
    cdat = g.n("ShaderNodeCameraData", -900, 2200)
    far = g.maprange(-750, 2200, g.out(cdat, "View Distance"), 40.0, 150.0)
    sft0 = g.math("MULTIPLY_ADD", -600, 2200, g.out(far, "Result"), 0.12, 0.29)     # as in the ground material
    sft = g.math("MULTIPLY_ADD", -450, 2200, g.out(sft0), g.out(far_f), g.out(pal, "softness"))
    g.link(sft, 0, cel, "Softness")
    hz = g.math("ADD", 330, 600, g.out(boost, "Fac"), 1.0)
    hcap = g.math("MULTIPLY_ADD", 330, 450, g.out(far_f), -0.08, 1.0)     # 0.92 on the far hills like their ground
    hue = g.n("ShaderNodeHueSaturation", 450, 300)
    g.link(g.maprange(300, 450, g.out(wn, "Value"), 0.0, 1.0, 0.485, 0.515), "Result", hue, "Hue")
    g.link(cel, "Color", hue, "Color")
    _emit_out(g, g.out(hue, "Color"), 1150, 300, pal=pal, haze=g.out(hz), haze_cap=g.out(hcap))
    _done(mat, "grass")
    return mat


def _atlas_uv(g, x, y, rand_sock, per_side):
    """UV of one random tile of an N x N atlas (tile = floor(rand * N^2))."""
    uv = g.n("ShaderNodeUVMap", x, y + 200)
    n2 = per_side * per_side
    idx = g.math("MULTIPLY", x, y, rand_sock, n2 - 0.001)
    fl = g.math("FLOOR", x + 160, y, g.out(idx))
    tx = g.math("MODULO", x + 320, y + 60, g.out(fl), per_side)
    ty = g.math("FLOOR", x + 480, y - 60, g.out(g.math("DIVIDE", x + 320, y - 60, g.out(fl), per_side)))
    off = g.n("ShaderNodeCombineXYZ", x + 640, y)
    g.link(tx, 0, off, "X")
    g.link(ty, 0, off, "Y")
    a = g.vmath("ADD", x + 800, y + 100, g.out(uv, "UV"), g.out(off))
    s = g.vmath("SCALE", x + 960, y + 100, g.out(a), scale=1.0 / per_side)
    return g.out(s)


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
    c01 = g.mix(-200, 400, fac=g.out(g.math("GREATER_THAN", -400, 450, g.out(ci, "Fac"), 0.5)),
                a=g.out(pal, "flower_a"), b=g.out(pal, "flower_b"))
    c23 = g.mix(-200, 250, fac=g.out(g.math("GREATER_THAN", -400, 300, g.out(ci, "Fac"), 2.5)),
                a=g.out(pal, "flower_c"), b=g.out(pal, "flower_d"))
    c = g.mix(0, 350, fac=g.out(g.math("GREATER_THAN", -200, 550, g.out(ci, "Fac"), 1.5)),
              a=g.mixout(c01), b=g.mixout(c23))
    # petal shading from the atlas R, yellow centre where R ~ 0
    pet = g.mix(200, 400, "MULTIPLY", fac=1.0, a=g.mixout(c),
                b=g.out(tex, "Color"))
    sep = g.n("ShaderNodeSeparateColor", 0, 700)
    g.link(tex, "Color", sep, "Color")
    isc = g.math("LESS_THAN", 200, 700, g.out(sep, "Red"), 0.12)
    cdk = g.mix(300, 550, fac=0.45, a=g.mixout(c), b=g.out(pal, "flower_centre"))
    cdk2 = g.mix(300, 650, "MULTIPLY", fac=0.35, a=g.mixout(cdk), b=g.out(pal, "flower_shade"))
    col = g.mix(400, 450, fac=g.out(isc), a=g.mixout(pet), b=g.mixout(cdk2))
    shc = g.mix(600, 350, "MULTIPLY", fac=1.0, a=g.mixout(col), b=g.out(pal, "flower_shade"))
    cl = _clump_node(g, pal, -200, -100, g.out(geo, "Position"), g.out(gn, "Vector"))
    cel = _cel_node(g, pal, 800, 300, g.out(cl, "Normal"), g.mixout(col), g.mixout(shc), g.mixout(shc))
    dim = g.n("ShaderNodeCombineColor", 900, 500)
    for c in ("Red", "Green", "Blue"):
        g.link(pal, "flower_dim", dim, c)
    dm = g.mix(1000, 400, "MULTIPLY", fac=1.0, a=g.out(cel, "Color"), b=g.out(dim))
    _emit_out(g, g.mixout(dm), 1650, 300, alpha=g.out(tex, "Alpha"), shadow_off=True, pal=pal)
    _done(mat, "flower")
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
    alpha = g.mix(0, 900, "MIX", "FLOAT", fac=g.out(isb), a=g.out(tl, "Alpha"), b=g.out(tb, "Alpha"))
    shade = g.mix(0, 1100, fac=g.out(isb), a=g.out(tl, "Color"), b=g.out(tb, "Color"))
    # normal: the canopy normal, nudged per card so neighbouring dabs break the terminator
    rn = g.n("ShaderNodeTexWhiteNoise", -1500, 300, noise_dimensions="1D")
    g.link(rnd, "Fac", rn, "W")
    rc = g.vmath("SUBTRACT", -1300, 300, g.out(rn, "Color"), (0.5, 0.5, 0.5))
    rj = g.vmath("SCALE", -1100, 300, g.out(rc), scale=0.3)
    na = g.vmath("ADD", -900, 400, g.out(nrm, "Vector"), g.out(rj))
    nn = g.vmath("NORMALIZE", -700, 400, g.out(na))
    # inner cards (low depth) sink into shadow; AO darkens the pockets
    ao = g.n("ShaderNodeAmbientOcclusion", -900, -100)
    ao.samples = 8
    g.set(ao, "Distance", 1.5)
    aop = g.math("POWER", -700, -100, g.out(ao, "AO"), 1.5)
    aol = g.mix(-500, -100, "MIX", "FLOAT", fac=g.out(pal, "leaf_ao"), a=1.0, b=g.out(aop))
    dpt = g.maprange(-700, -300, g.out(depth, "Fac"), 0.0, 1.0, -0.45, 0.08)
    off = g.math("MULTIPLY_ADD", -300, -200, g.out(aol), 0.5, -0.5)
    off2 = g.math("ADD", -100, -200, g.out(off), g.out(dpt, "Result"))
    # colours: leaves 4-tone (deep, shadow, mid, lit) / blossoms 2-tone
    ever = _attr(g, "hrp_evergreen", "OBJECT", -700, 500)
    leaf = {k: g.mixout(g.mix(-500, 300 - 150 * i, fac=g.out(ever, "Fac"), a=g.out(pal, "leaf_" + k),
                              b=g.out(pal, "ever_" + k)))
            for i, k in enumerate(("lit", "mid", "shadow", "deep"))}
    lit = g.mix(-300, 300, fac=g.out(isb), a=leaf["lit"], b=g.out(pal, "bloom_lit"))
    mid = g.mix(-300, 150, fac=g.out(isb), a=leaf["mid"], b=g.out(pal, "bloom_lit"))
    shd = g.mix(-300, 0, fac=g.out(isb), a=leaf["shadow"], b=g.out(pal, "bloom_shadow"))
    dp = g.mix(-300, -150, fac=g.out(isb), a=leaf["deep"], b=g.out(pal, "bloom_deep"))
    # per-dab tone from the atlas (R): darker dabs read as separate brush marks
    litd = g.mix(-100, 300, "MULTIPLY", fac=0.6, a=g.mixout(lit), b=g.mixout(shade))
    midd = g.mix(-100, 150, "MULTIPLY", fac=0.6, a=g.mixout(mid), b=g.mixout(shade))
    shd = g.mix(-100, 0, "MULTIPLY", fac=0.55, a=g.mixout(shd), b=g.mixout(shade))
    dp = g.mix(-100, -150, "MULTIPLY", fac=0.35, a=g.mixout(dp), b=g.mixout(shade))
    cj = g.maprange(-300, -350, g.out(rn, "Value"), 0.0, 1.0, 0.8, 1.2)        # each card its own value
    cjc = g.n("ShaderNodeCombineColor", -200, -400)
    for c in ("Red", "Green", "Blue"):
        g.link(cj, "Result", cjc, c)
    shd = g.mix(50, 0, "MULTIPLY", fac=1.0, a=g.mixout(shd), b=g.out(cjc))
    dp = g.mix(50, -150, "MULTIPLY", fac=1.0, a=g.mixout(dp), b=g.out(cjc))
    cel = _cel_node(g, pal, 200, 200, g.out(nn), g.mixout(litd), g.mixout(shd), g.mixout(dp),
                    offset=g.out(off2), deep_key="leaf_deep_threshold")
    # second split inside the lit side: mid -> lit, plus a highlight rim on the brightest dabs
    v = g.out(cel, "Light")
    f3 = g.maprange(400, 0, v, 0.7, 0.76, smooth=True)
    sub = g.mix(600, 150, fac=g.out(f3, "Result"), a=g.mixout(midd), b=g.out(cel, "Color"))
    litm = g.out(cel, "Lit Mask")
    col = g.mix(800, 250, fac=litm, a=g.out(cel, "Color"), b=g.mixout(sub))
    f4 = g.maprange(600, -100, v, 0.95, 1.0, smooth=True)
    f4b = g.math("MULTIPLY", 800, -100, g.out(f4, "Result"), g.out(pal, "leaf_hi_amount"))
    f4c = g.math("MULTIPLY", 950, -100, g.out(f4b), g.out(g.math("SUBTRACT", 800, -250, 1.0, g.out(isb))))
    col2a = g.mix(1000, 250, fac=g.out(f4c), a=g.mixout(col), b=g.out(pal, "leaf_hi"))
    # warm rim on sun-facing silhouette edges (golden hour)
    lw = g.n("ShaderNodeLayerWeight", 800, -400)
    g.links.new(g.out(nn), lw.inputs["Normal"])
    g.set(lw, "Blend", 0.35)
    rimf = g.maprange(950, -400, g.out(lw, "Facing"), 0.55, 0.8, smooth=True)
    outer = g.maprange(950, -550, g.out(depth, "Fac"), 0.62, 0.8, smooth=True)
    rl0 = g.math("MULTIPLY", 1050, -450, g.out(rimf, "Result"), g.out(outer, "Result"))
    # the rim sits on lit edges - and, against the light, on every edge that leans towards the sun, where the cel
    # light is zero: a backlit crown gets its glowing outline instead of being a plain dark shape
    sdir = g.n("ShaderNodeCombineXYZ", 800, -700)
    for c in "xyz":
        g.link(pal, "sun_" + c, sdir, c.upper())
    lean = g.vmath("DOT_PRODUCT", 950, -700, g.out(nn), g.out(sdir))
    toward = g.maprange(1050, -700, g.out(lean, "Value"), -0.1, 0.4, smooth=True)
    gate = g.math("MAXIMUM", 1100, -550, litm, g.out(toward, "Result"))
    rl = g.math("MULTIPLY", 1100, -400, g.out(rl0), g.out(gate))
    ra = g.math("MULTIPLY", 1200, -450, g.out(rl), g.out(pal, "rim_amount"))
    col2 = g.mix(1250, 250, fac=g.out(ra), a=g.mixout(col2a), b=g.out(pal, "rim_colour"))
    # per-tree variation (object custom properties; 0 when missing = no change)
    hue = _attr(g, "hrp_hue", "OBJECT", 900, 600)
    val = _attr(g, "hrp_value", "OBJECT", 900, 800)
    hs = g.n("ShaderNodeHueSaturation", 1150, 450)
    g.link(g.math("ADD", 1050, 600, g.out(hue, "Fac"), 0.5), 0, hs, "Hue")
    g.link(g.math("ADD", 1050, 800, g.out(val, "Fac"), 1.0), 0, hs, "Value")
    g.links.new(g.mixout(col2), hs.inputs["Color"])
    _emit_out(g, g.out(hs, "Color"), 1950, 250, alpha=g.mixout(alpha), pal=pal)
    _done(mat, "leaves")
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
    _done(mat, "bark")
    return mat


def fill_material():
    mat, rebuilt = _fresh_mat(MAT_FILL)
    if not rebuilt:
        return mat
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -600, 0)
    pal.node_tree = palette_group()
    geo = g.n("ShaderNodeNewGeometry", -600, 300)
    ever = _attr(g, "hrp_evergreen", "OBJECT", -700, 400)
    fsh = g.mixout(g.mix(-450, 300, fac=g.out(ever, "Fac"), a=g.out(pal, "leaf_shadow"), b=g.out(pal, "ever_shadow")))
    fdp = g.mixout(g.mix(-450, 150, fac=g.out(ever, "Fac"), a=g.out(pal, "leaf_deep"), b=g.out(pal, "ever_deep")))
    cel = _cel_node(g, pal, -200, 100, g.out(geo, "Normal"), fsh, fdp, fdp)
    _emit_out(g, g.out(cel, "Color"), 700, 100, pal=pal)
    _done(mat, "fill")
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
    g.link(rel, 0, vt, "Vector")
    sp = g.n("ShaderNodeSeparateXYZ", -1000, 200)
    g.link(vt, 0, sp, "Vector")
    hs = g.n("ShaderNodeSeparateXYZ", -1300, -100)
    g.link(ch, "Vector", hs, "Vector")
    sx = g.math("MAXIMUM", -1150, -100, g.out(g.math("MULTIPLY", -1150, -50, g.out(g.math("ADD", -1250, -50, g.out(hs, "X"),
                g.out(hs, "Y"))), 0.55)), 0.01)
    sy = g.math("MAXIMUM", -1150, -250, g.out(g.math("MULTIPLY", -1250, -250, g.out(hs, "Z"), 1.15)), 0.01)
    nx0 = g.math("DIVIDE", -900, 250, g.out(sp, "X"), g.out(sx))
    ny0 = g.math("DIVIDE", -900, 100, g.out(sp, "Y"), g.out(sy))
    uvm = g.n("ShaderNodeUVMap", -1100, 500)
    ub = g.vmath("SUBTRACT", -950, 500, g.out(uvm, "UV"), (0.5, 0.5, 0.0))
    usep = g.n("ShaderNodeSeparateXYZ", -850, 500)
    g.link(ub, 0, usep, "Vector")
    # each card bulges a little so a big cloud reads as puffs. On a cloud that is small in the frame the same
    # bulge only shreds the lit/shadow edge into dark specks, so it fades out with the cloud's apparent size
    bulge = 0.0
    if not fill:
        cdat = g.n("ShaderNodeCameraData", -1150, 400)
        apparent = g.math("DIVIDE", -1000, 400, g.out(sx), g.out(cdat, "View Distance"))
        bulge = g.out(g.maprange(-850, 400, g.out(apparent), 0.035, 0.07, 0.0, 0.3, smooth=True), "Result")
    nx = g.math("MULTIPLY_ADD", -850, 250, g.out(usep, "X"), bulge, g.out(nx0))
    ny = g.math("MULTIPLY_ADD", -850, 100, g.out(usep, "Y"), bulge, g.out(ny0))
    r2 = g.math("ADD", -700, 200, g.out(g.math("MULTIPLY", -780, 250, g.out(nx), g.out(nx))),
                g.out(g.math("MULTIPLY", -780, 100, g.out(ny), g.out(ny))))
    nz = g.math("SQRT", -550, 150, g.out(g.math("MAXIMUM", -620, 150, g.out(g.math("SUBTRACT", -700, 100, 1.0,
                g.out(r2))), 0.04)))
    cn = g.n("ShaderNodeCombineXYZ", -450, 200)
    g.link(nx, 0, cn, "X")
    g.link(ny, 0, cn, "Y")
    g.link(nz, 0, cn, "Z")
    cnn = g.vmath("NORMALIZE", -350, 200, g.out(cn))
    vw = g.n("ShaderNodeVectorTransform", -250, 200, vector_type="NORMAL", convert_from="CAMERA",
             convert_to="WORLD")
    g.link(cnn, 0, vw, "Vector")
    nn = g.vmath("NORMALIZE", -150, 400, g.out(vw))
    # light from the sun (Shader to RGB) blended with "up-ness" so tops read lit and only the underside shades
    dif = g.n("ShaderNodeBsdfDiffuse", -500, 200)
    g.links.new(g.out(nn), dif.inputs["Normal"])
    s2r = g.n("ShaderNodeShaderToRGB", -350, 200)
    g.link(dif, 0, s2r, "Shader")
    bw = g.n("ShaderNodeRGBToBW", -200, 200)
    g.link(s2r, "Color", bw, "Color")
    lv = g.math("DIVIDE", -50, 200, g.out(g.math("MULTIPLY", -120, 260, g.out(bw), math.pi)),
                g.out(pal, "light_scale"))
    sz = g.n("ShaderNodeSeparateXYZ", -500, 600)
    g.link(nn, 0, sz, "Vector")
    up = g.math("MULTIPLY_ADD", -300, 600, g.out(sz, "Z"), 0.5, 0.5)
    v = g.mix(100, 400, "MIX", "FLOAT", fac=0.55, a=g.out(lv), b=g.out(up))
    vv = g.math("ADD", 250, 400, g.mixout(v), 0.0)
    ramp = g.n("ShaderNodeValToRGB", 400, 400, label="cloud ramp")
    g.link(vv, 0, ramp, "Fac")
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
    g.link(ramp, "Color", sep, "Color")
    col = g.mix(800, 500, fac=g.out(sep, "Red"), a=g.mixout(mix_under), b=g.out(pal, "cloud_lit"))
    tint = g.mix(950, 500, "MULTIPLY", fac=1.0, a=g.mixout(col), b=g.out(pal, "sun_tint"))
    _emit_out(g, g.mixout(tint), 1600, 200, alpha=None if fill else g.out(tex, "Alpha"), pal=pal, haze=0.6)
    _done(mat, "cloud_fill" if fill else "cloud")
    return mat


def cumulus_material():
    """Solid cumulus (cumulus.py): three painted tones per puff, a broken hand-drawn edge between them and a
    bright rim when the sun is behind the cloud. Opaque: no cards, no alpha, nothing to sort."""
    mat, rebuilt = _fresh_mat(MAT_CUMULUS)
    if not rebuilt:
        return mat
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1700, 0)
    pal.node_tree = palette_group()
    nat = _attr(g, "hrp_n", "GEOMETRY", -1700, 500)
    vt = g.n("ShaderNodeVectorTransform", -1500, 500, vector_type="NORMAL", convert_from="OBJECT",
             convert_to="WORLD")
    g.link(nat, "Vector", vt, "Vector")
    nn = g.vmath("NORMALIZE", -1330, 500, g.out(vt))
    dif = g.n("ShaderNodeBsdfDiffuse", -1150, 500)
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    g.links.new(g.out(nn), dif.inputs["Normal"])
    s2r = g.n("ShaderNodeShaderToRGB", -980, 500)
    g.link(dif, 0, s2r, "Shader")
    bw = g.n("ShaderNodeRGBToBW", -820, 500)
    g.link(s2r, "Color", bw, "Color")
    lv = g.math("DIVIDE", -500, 500, g.out(g.math("MULTIPLY", -660, 500, g.out(bw), math.pi)),
                g.out(pal, "light_scale"))
    ch = _attr(g, "hrp_ch", "GEOMETRY", -1700, 250)
    # light, lifted towards the crown and broken up by a painted noise
    tc = g.n("ShaderNodeTexCoord", -1700, -300)
    noi = g.n("ShaderNodeTexNoise", -1500, -300, noise_dimensions="3D")
    g.link(tc, "Object", noi, "Vector")
    for k, v in (("Scale", 11.0), ("Detail", 3.0), ("Roughness", 0.55), ("Distortion", 0.3)):   # per cloud width
        g.set(noi, k, v)
    jit = g.math("MULTIPLY", -1300, -300, g.out(g.math("SUBTRACT", -1400, -300, g.out(noi, "Fac"), 0.5)),
                 g.out(g.math("MULTIPLY", -1400, -450, g.out(pal, "cloud_jitter"), 0.22)))
    v = g.math("MULTIPLY_ADD", -330, 500, g.out(ch, "Fac"), 0.28, g.out(g.math("MULTIPLY", -420, 420, g.out(lv), 0.78)))
    v = g.math("ADD", -180, 500, g.out(v), g.out(jit))
    # clouds keep their painted steps in every style: a soft style only softens the edge a little (a fully
    # blended cloud reads as modelling clay)
    soft = g.math("ADD", -330, 250, g.out(g.math("MINIMUM", -480, 250, g.out(pal, "softness"), 0.07)), 0.012)
    thr = g.out(pal, "cloud_threshold")
    f1 = g.maprange(0, 500, g.out(v), g.out(g.math("SUBTRACT", -180, 300, thr, g.out(soft))),
                    g.out(g.math("ADD", -180, 180, thr, g.out(soft))), smooth=True)
    # the deepest tone: undersides low in the cloud
    sz = g.n("ShaderNodeSeparateXYZ", -1150, 150)
    g.link(nn, 0, sz, "Vector")
    under = g.maprange(-980, 150, g.out(sz, "Z"), -0.15, -0.6, smooth=True)
    lowc = g.maprange(-980, -50, g.out(ch, "Fac"), 0.45, 0.1, smooth=True)
    d0 = g.math("MULTIPLY", -800, 100, g.out(under, "Result"), g.out(lowc, "Result"))
    d1 = g.math("ADD", -640, 100, g.out(d0), g.out(g.math("MULTIPLY", -720, -50, g.out(jit), 1.5)))
    f2 = g.maprange(-480, 100, g.out(d1), 0.3, 0.42, smooth=True)
    sh = g.mix(200, 200, fac=g.out(f2, "Result"), a=g.out(pal, "cloud_shadow"), b=g.out(pal, "cloud_deep"))
    lit = g.mix(200, 500, "MULTIPLY", fac=1.0, a=g.out(pal, "cloud_lit"), b=g.out(pal, "sun_tint"))
    col = g.mix(400, 350, fac=g.out(f1, "Result"), a=g.mixout(sh), b=g.mixout(lit))
    # rim: grazing surfaces glow when the camera looks towards the sun through the cloud
    geo = g.n("ShaderNodeNewGeometry", -1700, -700)
    facing = g.vmath("DOT_PRODUCT", -1500, -700, g.out(geo, "Normal"), g.out(geo, "Incoming"))
    fres = g.math("SUBTRACT", -1180, -700, 1.0, g.out(g.math("ABSOLUTE", -1340, -700, g.out(facing, "Value"))))
    fres = g.math("POWER", -1020, -700, g.out(fres), 3.6)
    sd = g.n("ShaderNodeCombineXYZ", -1500, -950)
    for c in "xyz":
        g.link(pal, "sun_" + c, sd, c.upper())
    tow = g.vmath("DOT_PRODUCT", -1300, -950, g.out(g.vmath("SCALE", -1500, -820, g.out(geo, "Incoming"), scale=-1.0)),
                  g.out(sd))
    back = g.maprange(-1120, -950, g.out(tow, "Value"), 0.05, 0.85, smooth=True)
    rim = g.math("MULTIPLY", -860, -800, g.out(fres), g.out(back, "Result"))
    # ... only on the side of the cloud that faces the sun, and not along the flat base: a rim, not an outline
    sunside = g.vmath("DOT_PRODUCT", -1300, -1150, g.out(geo, "Normal"), g.out(sd))
    side = g.maprange(-1120, -1150, g.out(sunside, "Value"), -0.15, 0.6, 0.12, 1.0, smooth=True)
    nobase = g.maprange(-1120, -1350, g.out(ch, "Fac"), 0.06, 0.3, smooth=True)
    rim = g.math("MULTIPLY", -860, -1000, g.out(rim), g.out(g.math("MULTIPLY", -960, -1150, g.out(side, "Result"),
                                                                  g.out(nobase, "Result"))))
    rim = g.math("MULTIPLY", -700, -800, g.out(rim), g.out(g.math("MULTIPLY", -780, -950, g.out(pal, "cloud_rim_amount"), 2.2)),
                 clamp=True)
    col = g.mix(600, 350, fac=g.out(rim), a=g.mixout(col), b=g.out(pal, "cloud_rim"))
    _emit_out(g, g.mixout(col), 1000, 200, pal=pal, haze=0.25)
    _done(mat, "cumulus")
    return mat


def ridge_material():
    """Distant ridges (ridges.py): one flat colour per layer with a few broad darker shapes on the nearer ones,
    fading to the haze colour at the foot."""
    mat, rebuilt = _fresh_mat(MAT_RIDGE)
    if not rebuilt:
        return mat
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1300, 0)
    pal.node_tree = palette_group()
    lay = _attr(g, "hrp_layer", "OBJECT", -1300, 400)
    t = _attr(g, "hrp_t", "GEOMETRY", -1300, 200)
    f12 = g.maprange(-1050, 450, g.out(lay, "Fac"), 0.0, 1.0)
    f23 = g.maprange(-1050, 250, g.out(lay, "Fac"), 1.0, 2.0)
    c12 = g.mix(-850, 400, fac=g.out(f12, "Result"), a=g.out(pal, "mountain_1"), b=g.out(pal, "mountain_2"))
    col = g.mix(-650, 350, fac=g.out(f23, "Result"), a=g.mixout(c12), b=g.out(pal, "mountain_3"))
    # broad shaded shapes, strongest on the nearest layer and gone on the farthest
    tc = g.n("ShaderNodeTexCoord", -1300, -300)
    sc = g.vmath("MULTIPLY", -1120, -300, g.out(tc, "Object"), (0.48, 0.48, 2.0))      # per ground width
    noi = g.n("ShaderNodeTexNoise", -950, -300, noise_dimensions="3D")
    g.links.new(g.out(sc), g.inp(noi, "Vector"))
    for k, v in (("Scale", 1.0), ("Detail", 2.0), ("Roughness", 0.5), ("Distortion", 0.6)):
        g.set(noi, k, v)
    shape = g.math("SUBTRACT", -780, -300, g.out(noi, "Fac"), g.out(g.math("MULTIPLY", -880, -450, g.out(t, "Fac"), 0.3)))
    cut = g.maprange(-620, -300, g.out(shape), 0.36, g.out(g.math("ADD", -780, -450, g.out(pal, "ridge_soft"), 0.36)),
                     smooth=True)
    amt = g.maprange(-620, -500, g.out(lay, "Fac"), 0.0, 2.0, 0.26, 0.1)
    dk = g.math("MULTIPLY", -450, -350, g.out(cut, "Result"), g.out(amt, "Result"))
    shade = g.mix(-250, 200, "MULTIPLY", fac=g.out(dk), a=g.mixout(col), b=(0.55, 0.62, 0.9, 1.0))
    # air at the foot
    foot = g.maprange(-620, 0, g.out(t, "Fac"), 0.0, 0.5, 0.75, 0.0, smooth=True)
    out = g.mix(-50, 200, fac=g.out(foot, "Result"), a=g.mixout(shade), b=g.out(pal, "haze_colour"))
    _emit_out(g, g.mixout(out), 700, 200, pal=pal, haze=0.0)
    _done(mat, "ridge")
    return mat


def cloud_fill_material():
    return cloud_material(fill=True)


def all_materials():
    return [ground_material(), grass_material(), flower_material(), bark_material(), fill_material(),
            cloud_material(), cloud_fill_material(), cumulus_material(), ridge_material()] + \
        [leaves_material(st) for st in LEAF_STYLES]
