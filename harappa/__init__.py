# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Harappa (原っぱ) — one-click anime grass, trees and flowers for Blender (EEVEE).

by KanaWorks_AI · Tokyo AI Visuals LLC · https://x.com/KanaWorks_AI
Redistribution or modification must keep the attribution in NOTICE.md (GPLv3 section 7(b)).
"""
import colorsys
import math
import random

import bmesh
import bpy
from mathutils import Vector, noise

from . import build, clouds, cumulus, i18n, presets, quality, ridges, scatter, scene as hscene, shading, tree, ui
from .i18n import report
from .util import mod_input, srgb, to_hex

COLOUR_PROPS = [
    # key, label
    ("grass_lit", "Grass Lit"), ("grass_lit2", "Grass Patches"), ("grass_shadow", "Grass Shadow"),
    ("grass_deep", "Grass Deep Shadow"), ("grass_tip", "Grass Tips"),
    ("dirt_lit", "Path Lit"), ("dirt_shadow", "Path Shadow"), ("dirt_deep", "Path Deep Shadow"),
    ("leaf_lit", "Leaves Lit"), ("leaf_mid", "Leaves Mid"), ("leaf_shadow", "Leaves Shadow"),
    ("leaf_deep", "Leaves Deep Shadow"), ("leaf_hi", "Leaves Highlight"),
    ("ever_lit", "Evergreen Lit"), ("ever_mid", "Evergreen Mid"), ("ever_shadow", "Evergreen Shadow"),
    ("ever_deep", "Evergreen Deep Shadow"),
    ("bloom_lit", "Blossom Lit"), ("bloom_shadow", "Blossom Shadow"), ("bloom_deep", "Blossom Deep Shadow"),
    ("bark_lit", "Bark Lit"), ("bark_shadow", "Bark Shadow"),
    ("flower_a", "Flower 1"), ("flower_b", "Flower 2"), ("flower_c", "Flower 3"), ("flower_d", "Flower 4"),
    ("flower_centre", "Flower Centre"), ("flower_shade", "Flower Shade"), ("sun_tint", "Sunlight Tint"),
    ("cloud_lit", "Cloud Lit"), ("cloud_shadow", "Cloud Shadow"), ("cloud_deep", "Cloud Deep Shadow"),
    ("haze_colour", "Haze"), ("rim_colour", "Rim Light"), ("cloud_rim", "Cloud Rim"),
    ("mountain_1", "Near Mountains"), ("mountain_2", "Middle Mountains"), ("mountain_3", "Far Mountains"),
]
VALUE_PROPS = [
    # key, label, min, max, description
    ("threshold", "Light / Shadow Split", 0.0, 1.0, "How much light a surface needs to count as lit"),
    ("deep_threshold", "Deep Shadow Split", 0.0, 1.0, "Below this light level the darkest colour is used"),
    ("softness", "Edge Softness", 0.0, 0.3, "Blend width of the cel edges"),
    ("clump_size", "Clump Size", 0.05, 50.0, "Size in metres of the light/shadow clumps painted across the grass"),
    ("clump_strength", "Clump Strength", 0.0, 5.0, "How strongly the clumps bend the light"),
    ("clump_small", "Small Clumps", 0.0, 2.0, "Amount of a second, smaller clump layer"),
    ("brush_jitter", "Brush Jitter", 0.0, 2.0, "Breaks shadow edges into blade-like strokes"),
    ("root_dark", "Dark Roots", 0.0, 1.0, "Grass gets darker towards the ground"),
    ("tip_light", "Light Tips", 0.0, 1.0, "Grass tips catch the light"),
    ("wind_sheen", "Wind Sheen", 0.0, 1.0, "Light waves that sweep across the grass with the gusts"),
    ("patch_amount", "Colour Patches", 0.0, 1.0, "Large patches of the second grass colour"),
    ("leaf_ao", "Leaf Pockets", 0.0, 1.0, "Dark pockets between leaf clumps (ambient occlusion)"),
    ("leaf_hi_amount", "Leaf Highlights", 0.0, 1.0, "Bright highlight dabs on the sunniest leaves"),
    ("leaf_deep_threshold", "Leaf Deep Split", 0.0, 1.0, "Below this light level leaves use the darkest colour"),
    ("haze_amount", "Haze", 0.0, 1.0, "Distant things fade towards the horizon colour (aerial perspective)"),
    ("haze_start", "Haze Start", 0.0, 100000.0, "Camera distance in metres where the haze begins"),
    ("haze_end", "Haze End", 0.0, 100000.0, "Camera distance in metres where the haze is full"),
    ("flower_dim", "Flower Brightness", 0.0, 2.0, "Brightness of the meadow flowers (lower at night)"),
    ("rim_amount", "Rim Light", 0.0, 1.0, "Warm light along the sun-facing edges of trees"),
    ("grade_sat", "Vividness", 0.0, 2.0, "Makes every colour stronger or weaker, on top of the season and the paint "
                                         "style (saturation). Changing the season does not reset it"),
    ("grade_contrast", "Picture Contrast", 0.5, 2.0, "More or less contrast in the whole picture, on top of the "
                                                     "season and the paint style. Changing the season does not "
                                                     "reset it"),
    ("season_sat", "Season Vividness", 0.0, 2.0, "Colour strength the season adds"),
    ("season_contrast", "Season Contrast", 0.5, 2.0, "Contrast the season adds"),
    ("style_sat", "Style Colour Strength", 0.0, 2.0, "Colour strength the paint style adds on top of the season"),
    ("style_contrast", "Style Contrast", 0.5, 2.0, "Contrast the paint style adds on top of the season"),
    ("sky_brush", "Sky Brushiness", 0.0, 1.0, "Brushy streaks across the sky gradient"),
    ("sky_bands", "Sky Bands", 0.0, 1.0, "Flat poster bands in the sky gradient instead of a smooth blend"),
    ("sky_curve", "Horizon Glow", 0.3, 3.0, "How high the pale horizon colour rises into the sky: higher is a paler, "
                                            "airier sky, lower brings the deep top colour further down. The paint "
                                            "style sets this value"),
    ("cirrus_mult", "Cirrus Amount", 0.0, 3.0, "How much of the season's high cirrus the paint style shows"),
    ("ridge_soft", "Mountain Softness", 0.0, 0.5, "How soft the painted shapes on the distant mountains are"),
    ("cloud_shade", "Cloud Shadows", 0.0, 1.0, "Shadows of the clouds on the open ground in the middle distance. "
                                               "The season sets this value"),
    ("cloud_jitter", "Cloud Brushiness", 0.0, 4.0, "How broken and brushy the edge between a cloud's light and shade is"),
    ("cloud_rim_amount", "Cloud Rim Glow", 0.0, 1.0, "Bright edge on clouds that have the sun behind them"),
    ("cloud_threshold", "Cloud Light / Shadow Split", 0.0, 1.0, "How much of each cloud is in shade"),
]
SKY_PROPS = [("sky_zenith", "Sky Top"), ("sky_horizon", "Sky Horizon")]
TREE_SHAPES = [
    ("ROUND", "Round Tree", "A classic round broadleaf tree"),
    ("TALL", "Tall Tree", "A tall, narrow tree"),
    ("WIDE", "Wide Tree", "A wide umbrella-shaped tree"),
    ("BUSH", "Bush", "A rounded bush without a visible trunk"),
    ("CONIFER", "Conifer", "A pointed evergreen"),
    ("SAKURA", "Cherry Blossom", "A wide cherry tree in full blossom"),
    ("PINE", "Japanese Pine", "A leaning pine with flat pads of needles"),
    ("WILLOW", "Willow", "A willow with hanging curtains of leaves"),
    ("COLUMN", "Poplar", "A tall, slim column of a tree"),
]
LEAF_STYLES = [
    ("ROUND", "Round Leaves", "Broad rounded leaf dabs"),
    ("SMALL", "Small Leaves", "Many small leaf dabs"),
    ("NEEDLE", "Needles", "Thin needle strokes"),
]
_busy = {"on": False}


# ---------------------------------------------------------------------------------------------
# updates
# ---------------------------------------------------------------------------------------------
def _upd_colour(key):
    def f(self, context):
        shading.palette_set(key, tuple(getattr(self, key)))
    return f


SKY_VALUE_KEYS = ("sky_brush", "sky_bands", "sky_curve", "cirrus_mult")


def _upd_value(key):
    def f(self, context):
        shading.palette_set(key, getattr(self, key))
        if key in SKY_VALUE_KEYS and not _busy["on"]:
            _upd_sky(self, context)
    return f


def _upd_sky(self, context):
    w = bpy.data.worlds.get(hscene.WORLD)
    if w is not None:
        ground = to_hex([c * 0.9 + 0.1 * h for c, h in zip(self.sky_horizon, (0.4, 0.5, 0.4))])
        if w.get("hrp_ver") != hscene.SKY_VER:             # a sky from an older version: rebuild it in place
            st, mo = presets.SEASONS[self.season].get("night", (0.0, 0.0))
            sc = context.scene
            was = sc.world
            hscene.sky_world(sc, to_hex(self.sky_zenith), to_hex(self.sky_horizon), ground)
            sc.world = was
            hscene.set_night(w, st, mo, sc.camera)
        hscene.set_sky_colours(w, to_hex(self.sky_zenith), to_hex(self.sky_horizon), ground)
        _sky_extras(self, w)


def _sky_extras(s, world):
    """The parts of the sky a season sets but the panel has no colour for (mid sky, sun glow, cirrus)."""
    sk = presets.SEASONS[s.season].get("sky_more", {})
    custom = (to_hex(s.sky_zenith), to_hex(s.sky_horizon)) != tuple(presets.SEASONS[s.season]["sky"][:2])
    hscene.set_sky_extras(world, None if custom else sk.get("mid"), sk.get("glow", "#FFF6DC"),
                          sk.get("sun", 0.6), min(1.0, sk.get("cirrus", 0.0) * s.cirrus_mult),
                          sk.get("cirrus_colour", "#EEF6FF"), s.sky_brush, s.sky_bands, s.sky_curve)
    hscene.aim_sky(bpy.context.scene, world)


def _upd_sun(self, context):
    if _busy["on"]:
        return
    sun = bpy.data.objects.get(hscene.SUN)
    if sun is not None:
        sc = context.scene
        hscene.key_sun(sc, sc.camera, self.sun_elevation, self.sun_side, to_hex(sun.data.color),
                       sun.data.energy)


def _apply_values(s, palette=None, values=None):
    _busy["on"] = True
    try:
        for k, hx in (palette or {}).items():
            if hasattr(s, k):
                setattr(s, k, srgb(hx))
        for k, v in (values or {}).items():
            if hasattr(s, k):
                setattr(s, k, v)
    finally:
        _busy["on"] = False


def _snapshot(s):
    snap = {}
    for k, _ in COLOUR_PROPS + SKY_PROPS:
        snap[k] = list(getattr(s, k))
    for k, *_ in VALUE_PROPS:
        snap[k] = getattr(s, k)
    snap["sun_elevation"] = s.sun_elevation
    snap["sun_side"] = s.sun_side
    return snap


def _restore(s, snap):
    _busy["on"] = True
    try:
        for k, v in snap.items():
            if hasattr(s, k):
                setattr(s, k, v if not isinstance(v, list) else tuple(v))
    finally:
        _busy["on"] = False


def _season_values(season):
    se = presets.SEASONS[season]
    vals = dict(se["tone"])
    vals["sun_elevation"] = se["sun"]["elevation"]
    vals["sun_side"] = se["sun"]["side"]
    pal = dict(se["palette"])
    pal["sky_zenith"], pal["sky_horizon"] = se["sky"][0], se["sky"][1]
    return pal, vals


def apply_season(self, context):
    if _busy["on"]:
        return
    sc = context.scene
    pal, vals = _season_values(self.season)
    _apply_values(self, pal, vals)
    sun = bpy.data.objects.get(hscene.SUN)
    if sun is not None:
        sp = presets.SEASONS[self.season]["sun"]
        hscene.key_sun(sc, sc.camera, sp["elevation"], sp["side"], sp["colour"], sp["strength"])
    _upd_sky(self, context)
    _season_blossom(sc, presets.SEASONS[self.season].get("blossom", 0.0))
    w = bpy.data.worlds.get(hscene.WORLD)
    if w is not None:
        st, mo = presets.SEASONS[self.season].get("night", (0.0, 0.0))
        hscene.set_night(w, st, mo, sc.camera)
    _rebase(self, context)


def _season_blossom(sc, amount):
    """Spring puts blossom on every broadleaf tree and bush; other seasons give back each tree's own value."""
    for ob in sc.objects:
        if not ob.get("hrp_canopy") or ob.get("hrp_clouds"):
            continue
        mod = ob.modifiers.get("Harappa Foliage")
        if mod is None:
            continue
        root = ob.parent if ob.parent is not None and "hrp_tree" in ob.parent else None
        if root is not None and root.get("hrp_tree") in ("CONIFER", "PINE", "COLUMN"):   # no blossom on these
            continue
        if "hrp_blossom_base" not in ob:
            ob["hrp_blossom_base"] = float(mod_input(mod, "Blossom"))
        base = float(ob["hrp_blossom_base"])
        mod_input(mod, "Blossom", max(base, amount) if amount > 0 else base)
        if amount <= 0:
            del ob["hrp_blossom_base"]


def apply_style(self, context):
    if _busy["on"]:
        return
    _apply_values(self, None, presets.STYLES[self.style]["keys"])
    _upd_sky(self, context)                               # the style also paints the sky
    _rebase(self, context)


def _rebase(s, context):
    sc = context.scene
    if "hrp_base" in sc:
        del sc["hrp_base"]
    if s.variation:
        apply_variation(s, context)


def _shift(hexrgb_lin, dh, ds, dv):
    r, g, b = [c ** (1 / 2.2) for c in hexrgb_lin]
    h, l_, sat = colorsys.rgb_to_hls(r, g, b)
    h = (h + dh) % 1.0
    sat = min(1.0, max(0.0, sat * (1 + ds)))
    l_ = min(1.0, max(0.0, l_ * (1 + dv)))
    r, g, b = colorsys.hls_to_rgb(h, l_, sat)
    return tuple(max(0.0, c) ** 2.2 for c in (r, g, b))


def apply_variation(self, context):
    if _busy["on"]:
        return
    sc = context.scene
    if "hrp_base" not in sc:
        sc["hrp_base"] = _snapshot(self)
    base = {k: (list(v) if hasattr(v, "__len__") else v) for k, v in sc["hrp_base"].items()}
    _restore(self, base)
    if self.variation == 0:
        del sc["hrp_base"]
        _reseed(sc, None)
        _refresh_all(self, context)
        return
    rng = random.Random(self.variation * 7907 + 11)
    gh, gs, gv = rng.uniform(-0.035, 0.03), rng.uniform(-0.15, 0.2), rng.uniform(-0.06, 0.06)
    lh, ls, lv = rng.uniform(-0.04, 0.035), rng.uniform(-0.15, 0.2), rng.uniform(-0.06, 0.06)
    _busy["on"] = True
    try:
        for k, _ in COLOUR_PROPS:
            v = tuple(base[k])
            if k.startswith("grass"):
                setattr(self, k, _shift(v, gh, gs, gv))
            elif k.startswith("leaf"):
                setattr(self, k, _shift(v, lh, ls, lv))
        fs = rng.choice(presets.FLOWER_SETS)
        for k, hx in zip(("flower_a", "flower_b", "flower_c", "flower_d"), fs):
            setattr(self, k, srgb(hx))
        self.threshold = min(0.8, max(0.1, base["threshold"] + rng.uniform(-0.07, 0.07)))
        self.clump_size = base["clump_size"] * rng.uniform(0.7, 1.45)
        self.clump_strength = base["clump_strength"] * rng.uniform(0.85, 1.2)
        self.clump_small = base["clump_small"] * rng.uniform(0.6, 1.5)
        self.brush_jitter = base["brush_jitter"] * rng.uniform(0.6, 1.6)
        self.patch_amount = min(1.0, max(0.0, base["patch_amount"] + rng.uniform(-0.25, 0.25)))
        self.tip_light = min(1.0, base["tip_light"] * rng.uniform(0.7, 1.3))
        self.sun_side = base["sun_side"] + rng.uniform(-25, 25)
        self.sun_elevation = min(70.0, max(10.0, base["sun_elevation"] + rng.uniform(-10, 10)))
    finally:
        _busy["on"] = False
    # every tree gets its own tint and a new shape, meadows and clouds a new scatter
    _reseed(sc, rng)
    _refresh_all(self, context)


def _reseed(sc, rng):
    """Variation N re-rolls tree shapes / scatters; variation 0 brings the original seeds back."""
    for ob in sc.objects:
        if ob.get("hrp_canopy"):
            ob["hrp_hue"] = rng.uniform(-0.03, 0.03) if rng else 0.0
            ob["hrp_value"] = float(ob.get("hrp_value_base", 0.0)) + (rng.uniform(-0.08, 0.08) if rng else 0.0)
            ob.update_tag()
        if "hrp_tree" in ob:
            ts = ob.harappa_tree
            if "hrp_seed_base" not in ob:
                ob["hrp_seed_base"] = ts.seed
            new = rng.randint(0, 99999) if rng else int(ob["hrp_seed_base"])
            if rng is None:
                del ob["hrp_seed_base"]
            if new != ts.seed:
                _busy["on"] = True
                ts.seed = new
                _busy["on"] = False
                rebuild_tree(bpy.context, ob)
        if ob.get("hrp_clouds") or ob.get(cumulus.TAG):
            continue
        for m in ob.modifiers:
            if m.type == "NODES" and m.name in (build.GRASS_MOD, build.FLOWER_MOD):
                cur = mod_input(m, "Seed")
                base = ob.get(f"hrp_seed_{m.name}")
                if base is None:
                    ob[f"hrp_seed_{m.name}"] = base = cur
                mod_input(m, "Seed", rng.randint(0, 9999) if rng else int(base))
                if rng is None:
                    del ob[f"hrp_seed_{m.name}"]
    rl = sc.get("hrp_ridge_layout")
    if rl is not None and ridges.ridges_of(sc) and not ridges.touched(sc):   # new shapes, unless they are the user's
        layers, rseed = list(rl)
        base = sc.get("hrp_ridge_seed_base")
        if base is None:
            base = int(rseed)
        new = rng.randint(0, 99999) if rng else int(base)
        if new != int(rseed):
            ridges.build(bpy.context, _main_ground(sc), new, int(layers))
        if rng is None:
            if "hrp_ridge_seed_base" in sc:
                del sc["hrp_ridge_seed_base"]
        else:
            sc["hrp_ridge_seed_base"] = int(base)
    lay = sc.get("hrp_cloud_layout")
    if lay is not None and (cumulus.clouds_of(sc) or lay[0] == 0):
        cnt, cseed, dist_ = list(lay)
        base = sc.get("hrp_cloud_seed_base")
        if base is None:
            base = int(cseed)
        new = rng.randint(0, 99999) if rng else int(base)
        if new != int(cseed):
            cumulus.layout(bpy.context, int(cnt), new, float(dist_))
        if rng is None:
            if "hrp_cloud_seed_base" in sc:
                del sc["hrp_cloud_seed_base"]
        else:
            sc["hrp_cloud_seed_base"] = int(base)


def _main_ground(sc):
    """The meadow the scenery is built around: the biggest ground in the scene."""
    grounds = [o for o in sc.objects if o.get("hrp_ground") and not o.get("hrp_far_hills")]
    return max(grounds, key=lambda o: max(o.dimensions.x, o.dimensions.y), default=None)


def _refresh_all(s, context):
    for k, _ in COLOUR_PROPS:
        shading.palette_set(k, tuple(getattr(s, k)))
    for k, *_ in VALUE_PROPS:
        shading.palette_set(k, getattr(s, k))
    _upd_sky(s, context)
    _upd_sun(s, context)


# ---------------------------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------------------------
def _enum_items(d):
    return [(k, v["name"], v["desc"]) for k, v in d.items()]


def _active_cloud(context=None):
    ob = (context or bpy.context).active_object
    return ob if ob is not None and ob.get(cumulus.TAG) else None


def _cloud_args(ob):
    a = list(ob.get("hrp_cloud_args", [0, 0.0]))
    return int(a[0]), float(a[1])


def _reshape(ob, seed, tower):
    cumulus.shape_cloud(ob, seed, tower)
    if "hrp_cloud_auto" in ob:                 # a cloud the user shaped is theirs: a re-roll keeps it
        del ob["hrp_cloud_auto"]


def _cloud_props():
    def g_seed(self):
        ob = _active_cloud()
        return _cloud_args(ob)[0] if ob else 0

    def s_seed(self, v):
        ob = _active_cloud()
        if ob:
            _reshape(ob, v, _cloud_args(ob)[1])

    def g_tower(self):
        ob = _active_cloud()
        return _cloud_args(ob)[1] if ob else 0.0

    def s_tower(self, v):
        ob = _active_cloud()
        if ob:
            _reshape(ob, _cloud_args(ob)[0], v)

    def g_width(self):
        ob = _active_cloud()
        return ob.scale.x if ob else 1.0

    def s_width(self, v):
        ob = _active_cloud()
        if ob:
            k = v / max(ob.scale.x, 1e-9)                      # keeps a flattened cloud flat
            ob.scale = (v, ob.scale.y * k, ob.scale.z * k)
            if "hrp_cloud_auto" in ob:
                del ob["hrp_cloud_auto"]
    return {
        "cloud_seed": bpy.props.IntProperty(name="Cloud Shape", min=0, max=2 ** 31 - 1, soft_max=99999,
                                            get=g_seed, set=s_seed,
                                            description="Pick another shape for this cloud (it stays where it is)"),
        "cloud_tower": bpy.props.FloatProperty(name="Tower", min=0.0, max=1.0, get=g_tower, set=s_tower,
                                               description="How high the cloud piles up: flat cumulus at 0, a "
                                                           "towering summer cloud at 1"),
        "cloud_width": bpy.props.FloatProperty(name="Cloud Width", min=0.01, max=1e6, get=g_width, set=s_width,
                                               subtype="DISTANCE", description="Width of this cloud"),
    }


def _settings_annotations():
    ann = {
        "detail_level": bpy.props.EnumProperty(
            name="Detail Level", default="BALANCED", update=quality.update,
            description="Richness against speed: how much grass and how many flowers are drawn and how fine the "
                        "clouds are. Switching it also sets the render samples. Your own densities and sizes are "
                        "never changed",
            items=[("FAST", "Fast", "Less grass and fewer flowers, coarser clouds, quick renders: for slower "
                                    "computers and for working in the viewport"),
                   ("BALANCED", "Balanced", "The default: looks complete and renders in a few seconds"),
                   ("BEST", "Best", "More and finer grass, smoother clouds, more samples: for final renders "
                                    "(about twice as slow as Balanced)")]),
        "season": bpy.props.EnumProperty(name="Season", items=_enum_items(presets.SEASONS), default="SUMMER",
                                         description="Colours, sunlight and sky", update=apply_season),
        "style": bpy.props.EnumProperty(name="Paint Style", items=_enum_items(presets.STYLES), default="ANIME",
                                        description="How the light and shadow are painted", update=apply_style),
        "variation": bpy.props.IntProperty(
            name="Variation", default=0, min=0, max=99999, update=apply_variation,
            description="Re-rolls colours, clumps, flowers, sun angle, each tree's tint, the mountain shapes and "
                        "the clouds Make Clouds placed, around the current season and style. 0 = off"),
        "sun_elevation": bpy.props.FloatProperty(name="Sun Height", default=42.0, min=2.0, max=89.0,
                                                 description="Sun elevation in degrees", update=_upd_sun),
        "sun_side": bpy.props.FloatProperty(name="Sun Direction", default=-55.0, min=-180.0, max=180.0,
                                            description="Sun angle around the camera in degrees (0 = behind the "
                                                        "camera)", update=_upd_sun),
        "new_shape": bpy.props.EnumProperty(name="Tree Shape", items=TREE_SHAPES, default="ROUND",
                                            description="Shape of the next tree"),
        "new_height": bpy.props.FloatProperty(name="Tree Height", default=5.0, min=0.2, max=200.0,
                                              subtype="DISTANCE", description="Height of the next tree"),
        "new_blossom": bpy.props.FloatProperty(name="Blossom", default=0.0, min=0.0, max=1.0,
                                               description="Share of blossom dabs on the next tree"),
        "plant_count": bpy.props.IntProperty(name="Trees", default=8, min=1, max=500,
                                             description="How many trees Plant Trees adds"),
        "ridge_layers": bpy.props.IntProperty(name="Mountain Layers", default=3, min=0, max=3,
                                              description="How many layers of mountains Distant Mountains builds "
                                                          "(0 removes them)"),
        "cloud_count": bpy.props.IntProperty(name="Clouds", default=6, min=0, max=60,
                                             description="How many clouds Make Clouds builds (0 removes them)"),
        "mask_paint": bpy.props.EnumProperty(name="Paint", items=[("GRASS", "Grass", "Paint grass back in"),
                                                                  ("PATH", "Path", "Paint a bare path")],
                                             default="PATH", description="What the brush paints"),
    }
    ann.update(_cloud_props())
    defaults = presets.SEASONS["SUMMER"]["palette"]
    for k, label in COLOUR_PROPS:
        ann[k] = bpy.props.FloatVectorProperty(name=label, subtype="COLOR", size=3, min=0.0, max=1.0,
                                               default=srgb(defaults[k]), update=_upd_colour(k),
                                               description=label)
    sky = presets.SEASONS["SUMMER"]["sky"]
    for (k, label), hx in zip(SKY_PROPS, sky[:2]):
        ann[k] = bpy.props.FloatVectorProperty(name=label, subtype="COLOR", size=3, min=0.0, max=1.0,
                                               default=srgb(hx), update=_upd_sky, description=label)
    tone = dict(presets.SEASONS["SUMMER"]["tone"])
    tone.update(presets.STYLES["ANIME"]["keys"])
    for k, label, lo, hi, desc in VALUE_PROPS:
        ann[k] = bpy.props.FloatProperty(name=label, default=tone.get(k, shading.PALETTE_KEYS[k][1]), min=lo, max=hi, description=desc,
                                         update=_upd_value(k))
    return ann


HRP_Settings = type("HRP_Settings", (bpy.types.PropertyGroup,), {"__annotations__": _settings_annotations()})


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def tree_root(ob):
    while ob is not None:
        if "hrp_tree" in ob:
            return ob
        ob = ob.parent
    return None


def tree_canopy(root):
    return next((c for c in root.children if c.get("hrp_canopy")), None) if root else None


def meadow_of(ob):
    if ob is not None and ob.type == "MESH" and ob.modifiers.get(build.GRASS_MOD):
        return ob
    return None


def _scene_ready(sc):
    return (sc.world is not None and sc.world.name == hscene.WORLD
            and bpy.data.objects.get(hscene.SUN) is not None)


def setup_scene(context):
    sc = context.scene
    s = sc.harappa
    hscene.setup_render(sc)
    se = presets.SEASONS[s.season]
    hscene.sky_world(sc, to_hex(s.sky_zenith), to_hex(s.sky_horizon), se["sky"][2])
    sp = se["sun"]
    hscene.key_sun(sc, sc.camera, s.sun_elevation, s.sun_side, sp["colour"], sp["strength"])
    st, mo = se.get("night", (0.0, 0.0))
    hscene.set_night(sc.world, st, mo, sc.camera)
    _refresh_all(s, context)


def _is_default_cube(ob):
    """Blender's untouched startup cube (never grow a meadow on it by accident)."""
    return (ob.type == "MESH" and ob.name == "Cube" and len(ob.data.vertices) == 8 and not ob.modifiers
            and all(abs(d - 2.0) < 1e-4 for d in ob.dimensions) and ob.location.length < 1e-4)


def _hide_startup_objects(sc):
    """Hide (not delete) the startup cube and point light so a new meadow starts clean."""
    for ob in sc.objects:
        default_light = (ob.type == "LIGHT" and ob.name == "Light" and ob.data.type == "POINT"
                         and abs(ob.data.energy - 1000.0) < 1e-3)
        if _is_default_cube(ob) or default_light:
            ob.hide_set(True)
            ob.hide_render = True


def _make_hill(context, size=40.0, seed=0):
    me = bpy.data.meshes.new("Meadow")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=160, y_segments=160, size=size / 2)
    rs = random.Random(seed * 977 + 3)
    seed = Vector((rs.random() * 100, rs.random() * 100, 0))
    for v in bm.verts:
        p = v.co * (1.0 / size)
        h = noise.noise(p * 2.0 + seed) * 0.08 + noise.noise(p * 5.0 + seed) * 0.015
        v.co.z = h * size
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Meadow", me)
    ob.location = context.scene.cursor.location
    (context.collection or context.scene.collection).objects.link(ob)
    return ob


def _add_camera(context, target):
    sc = context.scene
    cd = bpy.data.cameras.new("Harappa Camera")
    cd.lens = 35
    cam = bpy.data.objects.new("Harappa Camera", cd)
    sc.collection.objects.link(cam)
    c = target.matrix_world.translation
    size = max(target.dimensions.x, target.dimensions.y, 1.0)
    loc = c + Vector((0, -size * 0.36, 0))
    inv = target.matrix_world.inverted()
    ok, hit, _n, _i = target.ray_cast(inv @ (loc + Vector((0, 0, 1000))), inv.to_3x3() @ Vector((0, 0, -1)))
    z = (target.matrix_world @ hit).z if ok else c.z
    cam.location = Vector((loc.x, loc.y, z + 1.7 + size * 0.02))
    cam.rotation_euler = (math.radians(93.5), 0, 0)
    cd.clip_end = max(200.0, size * 4)
    sc.camera = cam
    return cam


def _ground_hit(context, loc, ignore=()):
    dg = context.evaluated_depsgraph_get()
    origin = Vector((loc.x, loc.y, loc.z + 1000.0))
    for _ in range(8):
        ok, hit, _n, _i, ob, _m = context.scene.ray_cast(dg, origin, Vector((0, 0, -1)))
        if not ok:
            return None
        root = tree_root(ob)
        if root is None and ob not in ignore:
            return hit
        origin = hit + Vector((0, 0, -0.01))
    return None


# ---------------------------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------------------------
class HRP_OT_make_meadow(bpy.types.Operator):
    bl_idname = "harappa.make_meadow"
    bl_label = "Make Anime Meadow"
    bl_description = ("Grow anime grass and flowers on the selected meshes (or on a new hill when nothing is "
                      "selected), and set up the sky and sun")
    bl_options = {"REGISTER", "UNDO"}

    flowers: bpy.props.BoolProperty(name="Flowers", default=True, description="Scatter flowers in the grass")
    density: bpy.props.FloatProperty(name="Density", default=40.0, min=0.1, max=2000.0,
                                     description="Grass tufts per square metre")
    height: bpy.props.FloatProperty(name="Grass Height", default=0.35, min=0.01, max=50.0, subtype="DISTANCE",
                                    description="Grass height in metres")

    def execute(self, context):
        sc = context.scene
        targets = [o for o in context.selected_objects if o.type == "MESH" and tree_root(o) is None
                   and not o.get("hrp_canopy") and not _is_default_cube(o)]
        created = False
        if not targets:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            _hide_startup_objects(sc)
            targets = [_make_hill(context, seed=sc.harappa.variation)]
            created = True
        for ob in targets:
            build.make_meadow(context, ob, density=self.density, height=self.height, flowers=self.flowers,
                              seed=sc.harappa.variation)
        if sc.camera is None or created:
            _add_camera(context, targets[0])
        if not _scene_ready(sc):
            setup_scene(context)
        elif sc.world.get("hrp_ver") != hscene.SKY_VER:               # a sky from an older version: bring it up
            _upd_sky(sc.harappa, context)
        size = max(max(targets[0].dimensions.x, targets[0].dimensions.y), 1.0)
        s = sc.harappa
        _busy["on"] = True
        s.haze_start = size * 0.6
        s.haze_end = size * 3.0
        _busy["on"] = False
        shading.palette_set("haze_start", s.haze_start)
        shading.palette_set("haze_end", s.haze_end)
        if created:
            clouds.far_hills(context, targets[0], seed=s.variation)
        if sc.get("hrp_ridge_layout") is None:                    # also around the user's own ground, once
            ridges.build(context, targets[0], seed=s.variation)
        if sc.get("hrp_cloud_layout") is None and not cumulus.clouds_of(sc):     # behind the farthest ridge
            cumulus.layout(context, s.cloud_count, seed=s.variation, distance=max(160.0, size * 12))
        quality.apply(sc)
        if created:
            for o in context.selected_objects:
                o.select_set(False)
            targets[0].select_set(True)
            context.view_layer.objects.active = targets[0]
        self.report({"INFO"}, report(f"Anime meadow on {len(targets)} object(s)"))
        return {"FINISHED"}


class HRP_OT_add_tree(bpy.types.Operator):
    bl_idname = "harappa.add_tree"
    bl_label = "Add Anime Tree"
    bl_description = "Add an anime tree at the 3D cursor, standing on the ground below it"
    bl_options = {"REGISTER", "UNDO"}

    shape: bpy.props.EnumProperty(name="Tree Shape", items=TREE_SHAPES, default="ROUND",
                                  description="Shape of the tree")
    height: bpy.props.FloatProperty(name="Tree Height", default=5.0, min=0.2, max=200.0, subtype="DISTANCE",
                                    description="Height of the tree")
    seed: bpy.props.IntProperty(name="Seed", default=-1, min=-1, max=99999,
                                description="Shape seed (-1 = random)")
    blossom: bpy.props.FloatProperty(name="Blossom", default=-1.0, min=-1.0, max=1.0,
                                     description="Share of blossom dabs (-1 = use the panel value)")

    def invoke(self, context, event):
        s = context.scene.harappa
        self.shape = s.new_shape
        self.height = s.new_height
        return self.execute(context)

    def execute(self, context):
        sc = context.scene
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        seed = self.seed if self.seed >= 0 else random.randint(0, 99999)
        bl = self.blossom if self.blossom >= 0 else max(sc.harappa.new_blossom, tree.SHAPES[self.shape]["bloom"])
        loc = sc.cursor.location.copy()
        hit = _ground_hit(context, loc)
        if hit is not None:
            loc.z = hit.z - 0.02 * self.height
        root = tree.add_tree(context, self.shape, self.height, seed, loc, blossom=bl)
        init_tree_settings(root, self.shape, self.height, seed, tree.SHAPES[self.shape]["style"])
        if not _scene_ready(sc):
            setup_scene(context)
        for o in context.selected_objects:
            o.select_set(False)
        root.select_set(True)
        context.view_layer.objects.active = root
        self.report({"INFO"}, report(f"Tree added (seed {seed})"))
        return {"FINISHED"}


def _onto_third(sc, cam, ground, co, h, others, mask):
    """Slide the focal tree sideways onto the nearer third of the frame, onto the ground, if there is room."""
    from bpy_extras.object_utils import world_to_camera_view
    q = world_to_camera_view(sc, cam, co)
    target = 1 / 3 if q.x < 0.5 else 2 / 3
    tr, br, _bl, _tl = cam.data.view_frame(scene=sc)
    half = abs(tr.x) / max(abs(tr.z), 1e-6)                    # half the frame width per metre of depth
    right = cam.matrix_world.to_quaternion() @ Vector((1, 0, 0))
    right.z = 0.0
    if right.length < 1e-6:
        return co
    p = co + right.normalized() * (target - q.x) * 2.0 * half * q.z
    inv = ground.matrix_world.inverted()
    hit, loc, _n, idx = ground.ray_cast(inv @ (p + Vector((0, 0, 1000.0))), Vector((0, 0, -1)))
    if not hit:
        return co
    p = ground.matrix_world @ loc
    if mask is not None:
        poly = ground.data.polygons[idx]
        if min(mask.data[v].color[0] for v in poly.vertices) < 0.7:   # not onto a painted path
            return co
    if any((p - o).length < h * 0.9 for o in others):
        return co
    return p


class HRP_OT_plant_trees(bpy.types.Operator):
    bl_idname = "harappa.plant_trees"
    bl_label = "Plant Trees"
    bl_description = "Scatter anime trees over the active meadow, keeping off painted paths"
    bl_options = {"REGISTER", "UNDO"}

    count: bpy.props.IntProperty(name="Trees", default=8, min=1, max=500, description="How many trees to add")
    seed: bpy.props.IntProperty(name="Seed", default=0, min=0, max=99999, description="Placement seed")
    height: bpy.props.FloatProperty(name="Tree Height", default=5.0, min=0.2, max=200.0, subtype="DISTANCE",
                                    description="Average tree height")
    mixed: bpy.props.BoolProperty(name="Mix Shapes", default=True,
                                  description="Mix tree shapes; off = use the panel's tree shape")

    @classmethod
    def poll(cls, context):
        if meadow_of(context.active_object) is not None:
            return True
        cls.poll_message_set(i18n.t("Select a meadow first"))
        return False

    def invoke(self, context, event):
        s = context.scene.harappa
        self.count = s.plant_count
        self.height = s.new_height
        self.seed = random.randint(0, 99999)
        return self.execute(context)

    def execute(self, context):
        sc = context.scene
        ground = meadow_of(context.active_object)
        rng = random.Random(self.seed)
        me = ground.data
        mw = ground.matrix_world
        mask = me.color_attributes.get(scatter.MASK_ATTR)
        polys = list(me.polygons)
        areas = [p.area for p in polys]
        tot = sum(areas)
        placed = []
        tries = 0
        cam = sc.camera
        shapes = (["ROUND", "ROUND", "TALL", "WIDE", "BUSH", "CONIFER", "PINE", "WILLOW", "COLUMN"]
                  if self.mixed else [sc.harappa.new_shape])
        while len(placed) < self.count and tries < self.count * 60:
            tries += 1
            r = rng.uniform(0, tot)
            acc = 0.0
            for p in polys:
                acc += p.area
                if acc >= r:
                    break
            vi = p.vertices[rng.randrange(len(p.vertices))]
            if mask is not None and mask.data[vi].color[0] < 0.7:
                continue
            co = mw @ p.center
            h = self.height * rng.uniform(0.7, 1.3)
            if any((co - q).length < (h + hq) * 0.45 for q, hq in placed):
                continue
            if cam is not None:
                rel = co - cam.matrix_world.translation
                fwd = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
                if rel.length < h * 3.0 or (rel.dot(fwd) > 0 and rel.length < h * 4.5
                                           and abs(rel.normalized().dot(fwd)) > 0.85):
                    continue
            placed.append((co, h))
        # mixed planting gets a focal point: the tree nearest a third of the frame becomes a big round broadleaf,
        # the other trees in view step down in size, so they are not three equal trees in a row
        roles = {}
        if self.mixed and cam is not None and placed:
            from bpy_extras.object_utils import world_to_camera_view
            seen = []
            for k, (co, h) in enumerate(placed):
                q = world_to_camera_view(sc, cam, co + Vector((0, 0, h * 0.5)))
                if q.z > 0 and 0.08 < q.x < 0.92 and -0.2 < q.y < 1.0:
                    seen.append((min(abs(q.x - 1 / 3), abs(q.x - 2 / 3)), k))
            seen.sort()
            for rank, (_d, k) in enumerate(seen):
                roles[k] = rank
        for k, (co, h) in enumerate(placed):
            shape = rng.choice(shapes)
            rank = roles.get(k)
            if rank == 0:
                shape, h = "ROUND", h * 1.15
                co = _onto_third(sc, cam, ground, co, h, [q for j, (q, _hq) in enumerate(placed) if j != k], mask)
            elif rank is not None:
                h *= (0.8, 0.62, 0.5)[min(rank - 1, 2)] * rng.uniform(0.95, 1.1)
            if shape == "BUSH":
                h *= 0.4
            bl = max(sc.harappa.new_blossom, tree.SHAPES[shape]["bloom"])     # a cherry is always in blossom
            sd = rng.randint(0, 99999)
            root = tree.add_tree(context, shape, h, sd, co - Vector((0, 0, 0.02 * h)), blossom=bl)
            init_tree_settings(root, shape, h, sd, tree.SHAPES[shape]["style"])
        self.report({"INFO"}, report(f"Planted {len(placed)} tree(s)"))
        return {"FINISHED"}


def rebuild_tree(context, root):
    ts = root.harappa_tree
    shape, height, seed, style = ts.shape, ts.height, ts.seed, ts.leaf_style
    root["hrp_tree"] = shape
    tm, cm = tree.build_meshes(shape, height, seed, root.name)
    canopy = tree_canopy(root)
    trunk = next((c for c in root.children if not c.get("hrp_canopy")), None)
    if canopy is not None:
        old = canopy.data
        canopy.data = cm
        if old.users == 0:
            bpy.data.meshes.remove(old)
    if tm is not None:
        tm.materials.append(shading.bark_material())
        if trunk is None:
            trunk = bpy.data.objects.new(root.name + " Trunk", tm)
            for c in root.users_collection:
                c.objects.link(trunk)
            trunk.parent = root
        else:
            old = trunk.data
            trunk.data = tm
            if old.users == 0:
                bpy.data.meshes.remove(old)
    elif trunk is not None:
        bpy.data.objects.remove(trunk)
    if canopy is not None:
        mod = canopy.modifiers.get("Harappa Foliage")
        sp = tree.SHAPES[shape]
        delta = float(canopy.get("hrp_value", 0.0)) - float(canopy.get("hrp_value_base", 0.0))
        canopy["hrp_value_base"] = sp.get("value", 0.0)
        canopy["hrp_value"] = sp.get("value", 0.0) + delta
        if mod is not None:
            mod_input(mod, "Leaf Size", sp["leaf"] * height)
            mod_input(mod, "Density", float(sp["dens"]) * (5.0 / max(height, 0.1)) ** 2)
            mod_input(mod, "Inflate", 0.025 * height)
            mod_input(mod, "Roundness", sp["roundness"])
            mod_input(mod, "Blossom Scale", 0.16 * height)
            mod_input(mod, "Card", tree.card_object(context.scene, "leaf", style))


def _upd_tree(self, context):
    if _busy["on"]:
        return
    root = self.id_data
    if isinstance(root, bpy.types.Object) and "hrp_tree" in root:
        rebuild_tree(context, root)


class HRP_TreeSettings(bpy.types.PropertyGroup):
    shape: bpy.props.EnumProperty(name="Tree Shape", items=TREE_SHAPES, default="ROUND", update=_upd_tree,
                                  description="Shape of this tree")
    leaf_style: bpy.props.EnumProperty(name="Leaf Style", items=LEAF_STYLES, default="ROUND", update=_upd_tree,
                                       description="Brush dab used for the leaves")
    height: bpy.props.FloatProperty(name="Height", default=5.0, min=0.2, max=200.0, subtype="DISTANCE",
                                    update=_upd_tree, description="Tree height")
    seed: bpy.props.IntProperty(name="Seed", default=0, min=0, max=99999, update=_upd_tree,
                                description="Shape seed: each number is a different tree")


def init_tree_settings(root, shape, height, seed, style):
    _busy["on"] = True
    try:
        ts = root.harappa_tree
        ts.shape, ts.height, ts.seed, ts.leaf_style = shape, height, seed, style
    finally:
        _busy["on"] = False


class HRP_OT_rebuild_tree(bpy.types.Operator):
    bl_idname = "harappa.rebuild_tree"
    bl_label = "New Shape"
    bl_description = "Rebuild the active tree with a new random seed"
    bl_options = {"REGISTER", "UNDO"}

    new_seed: bpy.props.BoolProperty(name="New Seed", default=False, description="Roll a new random seed",
                                     options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return tree_root(context.active_object) is not None

    def execute(self, context):
        root = tree_root(context.active_object)
        if self.new_seed:
            _busy["on"] = True
            root.harappa_tree.seed = random.randint(0, 99999)
            _busy["on"] = False
        rebuild_tree(context, root)
        return {"FINISHED"}


class HRP_OT_set_tree_enum(bpy.types.Operator):
    bl_idname = "harappa.set_tree_enum"
    bl_label = "Set"
    bl_description = "Choose this option"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    prop: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    value: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        root = tree_root(context.active_object)
        if root is not None:
            setattr(root.harappa_tree, self.prop, self.value)
        return {"FINISHED"}


class HRP_OT_edit_canopy(bpy.types.Operator):
    bl_idname = "harappa.edit_canopy"
    bl_label = "Shape Canopy"
    bl_description = ("Edit the canopy clumps (move, scale or add spheres) — the leaves follow live. Shows the "
                      "clump spheres while editing")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        root = tree_root(ob)
        return (root is not None and tree_canopy(root) is not None) or (ob is not None and ob.get("hrp_canopy"))

    def execute(self, context):
        ob = context.active_object
        root = tree_root(ob)
        canopy = tree_canopy(root) if root is not None else ob
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in context.selected_objects:
            o.select_set(False)
        canopy.select_set(True)
        context.view_layer.objects.active = canopy
        mod = canopy.modifiers.get("Harappa Foliage")
        if mod is not None:
            mod.show_in_editmode = True
            mod.show_on_cage = False
        bpy.ops.object.mode_set(mode="EDIT")
        self.report({"INFO"}, report("Edit the clump spheres; Tab to finish"))
        return {"FINISHED"}


class HRP_OT_make_foliage(bpy.types.Operator):
    bl_idname = "harappa.make_foliage"
    bl_label = "Make Foliage"
    bl_description = ("Cover the selected meshes with camera-facing anime leaf dabs (shape a bush, a hedge, a "
                      "canopy — or a cloud — from any mesh)")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type == "MESH" and not meadow_of(o)]
        if not obs:
            self.report({"WARNING"}, report("Select one or more mesh objects"))
            return {"CANCELLED"}
        for ob in obs:
            mod = ob.modifiers.get("Harappa Foliage") or ob.modifiers.new("Harappa Foliage", "NODES")
            mod.node_group = scatter.foliage_group()
            mod_input(mod, "Card", tree.card_object(context.scene, "leaf", "ROUND"))
            size = max(ob.dimensions) or 1.0
            mod_input(mod, "Leaf Size", max(0.02, size * 0.09))
            mod_input(mod, "Density", 45.0 * (4.0 / size) ** 2)
            mod_input(mod, "Inflate", size * 0.02)
            mod_input(mod, "Blossom", context.scene.harappa.new_blossom)
            mod_input(mod, "Blossom Scale", size * 0.25)
            mod_input(mod, "Fill Material", shading.fill_material())
            mod_input(mod, "Fill Inside", True)
            ob["hrp_canopy"] = True
            ob["hrp_hue"] = 0.0
            ob["hrp_value"] = 0.0
        if not _scene_ready(context.scene):
            setup_scene(context)
        self.report({"INFO"}, report(f"Foliage on {len(obs)} object(s)"))
        return {"FINISHED"}


class HRP_OT_add_clouds(bpy.types.Operator):
    bl_idname = "harappa.add_clouds"
    bl_label = "Make Clouds"
    bl_description = ("Lay out new clouds in front of the camera (again to re-roll them). Each cloud is a normal "
                      "object: move, scale or delete it. Clouds you have moved are kept")
    bl_options = {"REGISTER", "UNDO"}

    count: bpy.props.IntProperty(name="Clouds", default=4, min=0, max=60, description="How many clouds")
    seed: bpy.props.IntProperty(name="Seed", default=-1, min=-1, max=99999, description="Cloud seed (-1 = random)")
    distance: bpy.props.FloatProperty(name="Distance", default=0.0, min=0.0, max=1000000.0, subtype="DISTANCE",
                                      description="How far away the clouds float (0 = behind the farthest mountains)")

    def invoke(self, context, event):
        self.count = context.scene.harappa.cloud_count
        return self.execute(context)

    def execute(self, context):
        if self.count <= 0:
            cumulus.layout(context, 0)
            return {"FINISHED"}
        seed = self.seed if self.seed >= 0 else random.randint(0, 99999)
        made = cumulus.layout(context, self.count, seed, self.distance)
        if not _scene_ready(context.scene):
            setup_scene(context)
        self.report({"INFO"}, report(f"Made {len(made)} cloud(s)"))
        return {"FINISHED"}


class HRP_OT_add_ridges(bpy.types.Operator):
    bl_idname = "harappa.add_ridges"
    bl_label = "Distant Mountains"
    bl_description = ("Build layers of distant mountains around the meadow (again for new shapes, 0 layers removes "
                      "them). Each layer is a normal object: move, scale or delete it")
    bl_options = {"REGISTER", "UNDO"}

    layers: bpy.props.IntProperty(name="Mountain Layers", default=3, min=0, max=3,
                                  description="How many layers of mountains (0 removes them)")
    seed: bpy.props.IntProperty(name="Seed", default=-1, min=-1, max=99999, description="Shape seed (-1 = random)")

    def invoke(self, context, event):
        self.layers = context.scene.harappa.ridge_layers
        return self.execute(context)

    def execute(self, context):
        sc = context.scene
        seed = self.seed if self.seed >= 0 else random.randint(0, 99999)
        made = ridges.build(context, _main_ground(sc), seed, self.layers)
        if made and not _scene_ready(sc):
            setup_scene(context)
        self.report({"INFO"}, report(f"{len(made)} mountain layer(s)"))
        return {"FINISHED"}


class HRP_OT_setup_scene(bpy.types.Operator):
    bl_idname = "harappa.setup_scene"
    bl_label = "Anime Sky & Sun"
    bl_description = "Switch to EEVEE with the Standard view, add the anime sky and a key sun"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        setup_scene(context)
        self.report({"INFO"}, report("Sky and sun ready"))
        return {"FINISHED"}


class HRP_OT_paint_mask(bpy.types.Operator):
    bl_idname = "harappa.paint_mask"
    bl_label = "Paint Grass"
    bl_description = "Vertex-paint where grass grows on the active meadow: black = bare path, white = grass"
    bl_options = {"REGISTER", "UNDO"}

    value: bpy.props.FloatProperty(name="Value", default=0.0, min=0.0, max=1.0, options={"SKIP_SAVE"},
                                   description="Brush value (0 path, 1 grass)")

    @classmethod
    def poll(cls, context):
        return meadow_of(context.active_object) is not None

    def execute(self, context):
        ob = context.active_object
        build.ensure_mask(ob.data)
        if context.mode != "PAINT_VERTEX":
            bpy.ops.object.mode_set(mode="VERTEX_PAINT")
        ts = context.tool_settings
        col = (self.value, self.value, self.value)
        done = False
        for holder in (getattr(ts, "unified_paint_settings", None), getattr(ts.vertex_paint, "unified_paint_settings", None)):
            if holder is not None and hasattr(holder, "color"):
                try:
                    holder.color = col
                    done = True
                except (AttributeError, TypeError):
                    pass
        brush = getattr(ts.vertex_paint, "brush", None)
        if brush is not None:
            try:
                brush.color = col
                done = True
            except (AttributeError, TypeError):
                pass
        self.report({"INFO"}, report("Paint the path in black, grass in white" if done else
                                     "Vertex Paint: pick black for paths, white for grass"))
        return {"FINISHED"}


class HRP_OT_shuffle(bpy.types.Operator):
    bl_idname = "harappa.shuffle"
    bl_label = "Shuffle"
    bl_description = "Roll a new variation of the current season and style"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.harappa
        s.variation = random.randint(1, 99999)
        self.report({"INFO"}, report(f"Variation {s.variation}"))
        return {"FINISHED"}


class HRP_OT_reset(bpy.types.Operator):
    bl_idname = "harappa.reset"
    bl_label = "Reset to Defaults"
    bl_description = "Summer Meadow, Anime Background style, no variation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        s = sc.harappa
        if "hrp_base" in sc:
            del sc["hrp_base"]
        _busy["on"] = True
        s.variation = 0
        s.season = "SUMMER"
        s.style = "ANIME"
        _busy["on"] = False
        apply_season(s, context)
        apply_style(s, context)
        for ob in sc.objects:
            if ob.get("hrp_canopy"):
                ob["hrp_hue"] = 0.0
                ob["hrp_value"] = 0.0
        return {"FINISHED"}


class HRP_OT_revert(bpy.types.Operator):
    bl_idname = "harappa.revert"
    bl_label = "Remove Grass"
    bl_description = "Remove Harappa grass/flowers/foliage from the selected objects and restore their materials"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = 0
        for ob in context.selected_objects:
            hit = False
            for name in (build.GRASS_MOD, build.FLOWER_MOD, "Harappa Foliage"):
                m = ob.modifiers.get(name)
                if m is not None:
                    ob.modifiers.remove(m)
                    hit = True
            prev = ob.get("hrp_prev_mats")
            if prev is not None and ob.type == "MESH":
                for i, nm in enumerate(prev):
                    if i < len(ob.data.materials):
                        ob.data.materials[i] = bpy.data.materials.get(nm) if nm else None
                del ob["hrp_prev_mats"]
            for k in ("hrp_ground", "hrp_canopy"):
                if k in ob:
                    del ob[k]
            if hit:
                ob.visible_shadow = True
                n += 1
        self.report({"INFO"}, report(f"Removed from {n} object(s)"))
        return {"FINISHED"}


class HRP_OT_set_detail(bpy.types.Operator):
    bl_idname = "harappa.set_detail"
    bl_label = "Set Detail Level"
    bl_description = "Switch the detail level; it also sets the render samples"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    level: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        try:
            prop = context.scene.harappa.bl_rna.properties["detail_level"]
            it = next(i for i in prop.enum_items if i.identifier == props.level)
            return i18n.t(it.description) + " " + i18n.t("It also sets the render samples")
        except (KeyError, StopIteration, AttributeError):
            return ""

    def execute(self, context):
        if self.level not in quality.LEVELS:
            return {"CANCELLED"}
        context.scene.harappa.detail_level = self.level
        lv = quality.LEVELS[self.level]
        name = next(i.name for i in context.scene.harappa.bl_rna.properties["detail_level"].enum_items
                    if i.identifier == self.level)
        self.report({"INFO"}, report(f"{name}: grass {round(lv['grass'] * 100)}%, flowers "
                                     f"{round(lv['flowers'] * 100)}%, render samples {lv['samples']}"))
        return {"FINISHED"}


class HRP_OT_cloud_new_shape(bpy.types.Operator):
    bl_idname = "harappa.cloud_new_shape"
    bl_label = "New Shape"
    bl_description = "Give this cloud another shape; it stays where it is, and from now on it is yours"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_cloud(context) is not None

    def execute(self, context):
        ob = _active_cloud(context)
        _reshape(ob, random.randint(0, 99999), _cloud_args(ob)[1])
        return {"FINISHED"}


class HRP_OT_cloud_give_back(bpy.types.Operator):
    bl_idname = "harappa.cloud_give_back"
    bl_label = "Give Back to Auto Layout"
    bl_description = "Let Make Clouds manage this cloud again: the next re-roll may move, replace or remove it"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_cloud(context) is not None

    def execute(self, context):
        n = 0
        for ob in {*context.selected_objects, _active_cloud(context)}:
            if ob is not None and ob.get(cumulus.TAG):
                cumulus.mark_auto(ob)
                n += 1
        self.report({"INFO"}, report(f"{n} cloud(s) given back to the auto layout"))
        return {"FINISHED"}


class HRP_OT_set_enum(bpy.types.Operator):
    bl_idname = "harappa.set_enum"
    bl_label = "Set"
    bl_description = "Choose this option"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    prop: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    value: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        try:
            prop = context.scene.harappa.bl_rna.properties[props.prop]
            it = next(i for i in prop.enum_items if i.identifier == props.value)
            return i18n.t(it.description)
        except (KeyError, StopIteration, AttributeError):
            return ""

    def execute(self, context):
        setattr(context.scene.harappa, self.prop, self.value)
        return {"FINISHED"}


CLASSES = (
    HRP_Settings, HRP_TreeSettings, HRP_OT_make_meadow, HRP_OT_add_tree, HRP_OT_plant_trees,
    HRP_OT_rebuild_tree, HRP_OT_set_tree_enum, HRP_OT_edit_canopy,
    HRP_OT_make_foliage, HRP_OT_add_clouds, HRP_OT_add_ridges, HRP_OT_setup_scene, HRP_OT_paint_mask, HRP_OT_shuffle, HRP_OT_reset,
    HRP_OT_revert, HRP_OT_set_enum, HRP_OT_set_detail, HRP_OT_cloud_give_back, HRP_OT_cloud_new_shape,
)


_sky_seen = {}


@bpy.app.handlers.persistent
def _follow_camera(scene, _depsgraph=None):
    """Keep the sky gradient fitted to the camera when the user moves it, changes the lens or the format."""
    try:
        w = scene.world
        if w is None or w.name != hscene.WORLD or w.get("hrp_ver") != hscene.SKY_VER:
            return
        sig = hscene.camera_signature(scene, _depsgraph)
        if _sky_seen.get(scene.name) != sig:
            _sky_seen[scene.name] = sig
            hscene.aim_sky(scene, w, update=False, depsgraph=_depsgraph)
    except (AttributeError, ReferenceError):
        pass


@bpy.app.handlers.persistent
def _forget_cameras(*_args):
    """A newly opened file has its own cameras: fit its skies afresh."""
    _sky_seen.clear()


def register():
    for h in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        if _follow_camera not in h:
            h.append(_follow_camera)
    if _forget_cameras not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_forget_cameras)
    i18n.register()
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.harappa = bpy.props.PointerProperty(type=HRP_Settings)
    bpy.types.Object.harappa_tree = bpy.props.PointerProperty(type=HRP_TreeSettings)
    ui.register()


def unregister():
    for h in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        if _follow_camera in h:
            h.remove(_follow_camera)
    if _forget_cameras in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_forget_cameras)
    ui.unregister()
    del bpy.types.Object.harappa_tree
    del bpy.types.Scene.harappa
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    i18n.unregister()
