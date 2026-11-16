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

from . import build, clouds, fauna, i18n, pondlife, presets, rocks, scatter, scene as hscene, shading, tree, ui, \
    water, waterfall, weather
from .i18n import report
from .util import mod_input, srgb, to_hex

COLOUR_PROPS = [
    # key, label
    ("grass_lit", "Grass Lit"), ("grass_lit2", "Grass Patches"), ("grass_shadow", "Grass Shadow"),
    ("grass_deep", "Grass Deep Shadow"), ("grass_tip", "Grass Tips"),
    ("dirt_lit", "Path Lit"), ("dirt_shadow", "Path Shadow"), ("dirt_deep", "Path Deep Shadow"),
    ("leaf_lit", "Leaves Lit"), ("leaf_mid", "Leaves Mid"), ("leaf_shadow", "Leaves Shadow"),
    ("leaf_deep", "Leaves Deep Shadow"), ("leaf_hi", "Leaves Highlight"),
    ("bloom_lit", "Blossom Lit"), ("bloom_shadow", "Blossom Shadow"), ("bloom_deep", "Blossom Deep Shadow"),
    ("bark_lit", "Bark Lit"), ("bark_shadow", "Bark Shadow"),
    ("flower_a", "Flower 1"), ("flower_b", "Flower 2"), ("flower_c", "Flower 3"), ("flower_d", "Flower 4"),
    ("flower_centre", "Flower Centre"), ("flower_shade", "Flower Shade"), ("sun_tint", "Sunlight Tint"),
    ("cloud_lit", "Cloud Lit"), ("cloud_shadow", "Cloud Shadow"), ("cloud_deep", "Cloud Deep Shadow"),
    ("haze_colour", "Haze"), ("rim_colour", "Rim Light"),
    ("water_shallow", "Water Shallow"), ("water_mid", "Water Mid"), ("water_deep", "Water Deep"),
    ("water_foam", "Water Foam"), ("water_line", "Water Lines"), ("water_sky", "Water Reflection"),
    ("water_shade", "Water Shade"),
    ("rock_lit", "Rock Lit"), ("rock_lit2", "Rock Patches"), ("rock_shadow", "Rock Shadow"),
    ("rock_deep", "Rock Deep Shadow"), ("firefly_colour", "Firefly Colour"),
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
    ("water_caustics", "Caustics", 0.0, 1.0, "Light net on the bottom of shallow water"),
    ("water_rain", "Rain Ripples", 0.0, 1.0, "How many raindrop rings spread on the water"),
    ("water_glints", "Glints", 0.0, 2.0, "Small sparkles of sunlight on the water"),
    ("water_glow", "Water Glow", 0.0, 3.0, "Foam, ripples and the water itself give off light (night)"),
    ("rock_moss", "Moss", 0.0, 1.0, "Moss on the tops of rocks, in the meadow's grass colours"),
    ("fireflies", "Firefly Glow", 0.0, 2.0, "How brightly the fireflies glow (none by day)"),
]
SKY_PROPS = [("sky_zenith", "Sky Top"), ("sky_horizon", "Sky Horizon")]
TREE_SHAPES = [
    ("ROUND", "Round Tree", "A classic round broadleaf tree"),
    ("TALL", "Tall Tree", "A tall, narrow tree"),
    ("WIDE", "Wide Tree", "A wide umbrella-shaped tree (cherry style)"),
    ("BUSH", "Bush", "A rounded bush without a visible trunk"),
    ("CONIFER", "Conifer", "A pointed evergreen"),
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


def _upd_value(key):
    def f(self, context):
        shading.palette_set(key, getattr(self, key))
    return f


def _upd_sky(self, context):
    w = bpy.data.worlds.get(hscene.WORLD)
    if w is not None:
        ground = to_hex([c * 0.9 + 0.1 * h for c, h in zip(self.sky_horizon, (0.4, 0.5, 0.4))])
        hscene.set_sky_colours(w, to_hex(self.sky_zenith), to_hex(self.sky_horizon), ground)


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
    for o in sc.objects:                                         # autumn: leaves afloat on the ponds
        m = o.modifiers.get(pondlife.LIFE_MOD) if water.is_water(o) else None
        if m is not None:
            try:
                mod_input(m, "Fallen Leaves", 1.0 if self.season == "AUTUMN" else 0.0)
            except KeyError:
                pass
    _weather_overlay(self, context)
    w = bpy.data.worlds.get(hscene.WORLD)
    if w is not None:
        st, mo = presets.SEASONS[self.season].get("night", (0.0, 0.0))
        hscene.set_night(w, st, mo, sc.camera)
    _rebase(self, context)


def _grey(rgb, k, target=(0.36, 0.40, 0.45)):
    lum = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
    g = [lum * 0.6 + t * 0.4 for t in target]
    return tuple(c * (1 - k) + gg * k for c, gg in zip(rgb, g))


LIT_TO_SHADOW = (("grass_lit", "grass_shadow"), ("grass_lit2", "grass_shadow"), ("grass_tip", "grass_shadow"),
                 ("leaf_lit", "leaf_mid"), ("leaf_hi", "leaf_mid"), ("dirt_lit", "dirt_shadow"),
                 ("rock_lit", "rock_shadow"), ("rock_lit2", "rock_shadow"), ("bloom_lit", "bloom_shadow"))


def _weather_overlay(s, context):
    """Clouds, rain and storm as a layer on top of the season: the palette and the world are changed, the user's
    colour settings are not (Clear puts the palette back from them)."""
    _n, _d, grey, sunk, haze, rain, cgrey = weather.WEATHERS[s.weather]
    k = {"CLEAR": 0.0, "CLOUDY": 0.45, "RAIN": 0.6, "STORM": 0.8}[s.weather]
    if s.rainbow and k > 0:                                              # a rainbow: the sun comes back out
        k, grey, cgrey, haze = min(k, 0.2), max(0.5, min(grey, 0.6)), min(cgrey, 0.4), min(haze, 0.08)   # rain curtain
    for key, _lb in COLOUR_PROPS:
        shading.palette_set(key, tuple(getattr(s, key)))
    for key, *_ in VALUE_PROPS:
        shading.palette_set(key, getattr(s, key))
    if k > 0:
        for lit, sh in LIT_TO_SHADOW:                                    # no sunlit side under a grey sky
            a, b = getattr(s, lit), getattr(s, sh)
            shading.palette_set(lit, tuple(x * (1 - k) + y * k * 1.12 for x, y in zip(a, b)))
        cg = (0.42, 0.46, 0.55) if s.weather == "STORM" else (0.62, 0.65, 0.72)
        for key, dk in (("cloud_lit", 1.0), ("cloud_shadow", 0.82), ("cloud_deep", 0.7)):
            c = getattr(s, key)
            shading.palette_set(key, tuple(x * (1 - cgrey) + y * dk * cgrey for x, y in zip(c, cg)))
        shading.palette_set("sun_tint", tuple(x * (1 - k * 0.6) + y * k * 0.6
                                              for x, y in zip(s.sun_tint, (0.78, 0.82, 0.9))))
        shading.palette_set("threshold", min(0.9, s.threshold + 0.18 * k))
        shading.palette_set("rim_amount", 0.0)
        shading.palette_set("haze_amount", min(1.0, s.haze_amount + haze))
        if s.weather == "STORM":                                           # slate sky, grey-teal water, muted meadow
            for key in ("grass_lit", "grass_lit2", "grass_shadow", "grass_tip", "leaf_lit", "leaf_mid", "leaf_hi",
                        "leaf_shadow", "water_shallow", "water_mid", "water_deep", "bloom_lit", "flower_a",
                        "flower_b", "flower_c"):
                c = shading.palette_get(key)
                lum = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
                shading.palette_set(key, tuple(x * 0.5 + lum * 0.5 for x in c))
        w = bpy.data.worlds.get(hscene.WORLD)
        if w is not None:
            if s.weather == "STORM":                                       # #5A6070 slate, not a dust storm
                slate = (0.102, 0.117, 0.162)
                z = tuple(c * 0.1 + t * 0.9 for c, t in zip(s.sky_zenith, slate))
                h = tuple(c * 0.15 + t * 0.85 for c, t in zip(s.sky_horizon, (0.15, 0.17, 0.2)))
                shading.palette_set("haze_colour", tuple(c * 0.2 + t * 0.8 for c, t in
                                                          zip(s.haze_colour, (0.195, 0.216, 0.181))))
            else:
                z = _grey(tuple(s.sky_zenith), grey)
                h = _grey(tuple(s.sky_horizon), grey * 0.8)
            ground = to_hex([c * 0.9 + 0.1 * hh for c, hh in zip(h, (0.4, 0.5, 0.4))])
            hscene.set_sky_colours(w, to_hex(z), to_hex(h), ground)
    else:
        _upd_sky(s, context)
    sun = bpy.data.objects.get(hscene.SUN)
    if sun is not None:
        sun.data.energy = presets.SEASONS[s.season]["sun"]["strength"] * (sunk if not s.rainbow else max(sunk, 0.8))
    amt = rain * s.rain_amount / 0.6 if rain > 0 else 0.0
    if s.rainbow and amt > 0:
        amt *= 0.07                                                      # the rain thins out when the bow appears
    if amt > 0 or bpy.data.objects.get(weather.RAIN_OB) is not None:
        weather.ensure_rain(context, min(1.0, amt), radius=s.rain_radius, follow=s.rain_follow,
                            wind=0.8 if s.weather == "STORM" else 0.25)
    _storm_wind(context.scene, s.weather == "STORM")
    shading.palette_set("water_rain", max(s.water_rain, min(1.0, amt * 1.1)))


def _storm_wind(scene, on):
    """Storm doubles the wind in the grass and trees; any other weather puts it back."""
    for ob in scene.objects:
        for m in ob.modifiers:
            if m.type != "NODES" or m.node_group is None or ob.name == weather.RAIN_OB:
                continue
            key = "hrp_wind0_" + m.name
            try:
                cur = mod_input(m, "Wind Strength")
            except KeyError:
                continue
            if on:
                if key not in ob:
                    ob[key] = float(cur)
                    mod_input(m, "Wind Strength", min(2.0, ob[key] * 2.0))
            elif key in ob:
                mod_input(m, "Wind Strength", ob[key])
                del ob[key]
            ob.update_tag()


def _upd_culling(self, context):
    for ob in context.scene.objects:
        if ob.type != "MESH" or not ob.get("hrp_ground"):
            continue
        for name in (build.GRASS_MOD, build.FLOWER_MOD):
            m = ob.modifiers.get(name)
            if m is None or m.node_group is None:
                continue
            try:
                mod_input(m, "Camera Culling", bool(self.camera_culling))
            except KeyError:                                     # an older grass group: rebuild it first
                pass
            ob.update_tag()


def _upd_rain_follow(self, context):
    ob = bpy.data.objects.get(weather.RAIN_OB)
    if ob is not None:
        weather.follow_camera(ob, context.scene, self.rain_follow)
        water.drive_rain_zone()


def _upd_weather(self, context):
    if _busy["on"]:
        return
    _weather_overlay(self, context)


def _upd_rainbow(self, context):
    _weather_overlay(self, context)
    ob = bpy.data.objects.get(weather.RAINBOW_OB)
    if self.rainbow:
        if ob is None:
            ob = weather.add_rainbow(context, self.rainbow_strength)
        if ob is not None:
            ob["hrp_rainbow"] = float(self.rainbow_strength)
            ob.hide_render = ob.hide_viewport = False
            ob.update_tag()
    elif ob is not None:
        ob.hide_render = ob.hide_viewport = True


def _upd_dragonflies(self, context):
    if self.dragonfly_count > 0 or bpy.data.objects.get(fauna.DRAGON_OB) is not None:
        fauna.ensure_dragonflies(context, self.dragonfly_count)


def _upd_fireflies(self, context):
    ob = bpy.data.objects.get(weather.FLIES_OB)
    if self.firefly_count > 0:
        gnd = next(iter(water.meadows(context.scene)), None)
        if gnd is not None:
            weather.ensure_fireflies(context, gnd, self.firefly_count)
    elif ob is not None:
        bpy.data.objects.remove(ob)


def _season_blossom(sc, amount):
    """Spring puts blossom on every broadleaf tree and bush; other seasons give back each tree's own value."""
    for ob in sc.objects:
        if not ob.get("hrp_canopy") or ob.get("hrp_clouds"):
            continue
        mod = ob.modifiers.get("Harappa Foliage")
        if mod is None:
            continue
        root = ob.parent if ob.parent is not None and "hrp_tree" in ob.parent else None
        if root is not None and root.get("hrp_tree") == "CONIFER":
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
        if ob.get("hrp_clouds") and ob.get("hrp_cloud_args") is not None:
            cnt, cseed, dist_ = list(ob["hrp_cloud_args"])
            if "hrp_cloud_seed_base" not in ob:
                ob["hrp_cloud_seed_base"] = int(cseed)
            new = rng.randint(0, 99999) if rng else int(ob["hrp_cloud_seed_base"])
            if rng is None:
                del ob["hrp_cloud_seed_base"]
            if new != int(cseed):
                base_seed = ob.get("hrp_cloud_seed_base")
                clouds.add_clouds(bpy.context, int(cnt), new, float(dist_))
                if base_seed is not None:
                    ob["hrp_cloud_seed_base"] = base_seed
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


def _settings_annotations():
    ann = {
        "season": bpy.props.EnumProperty(name="Season", items=_enum_items(presets.SEASONS), default="SUMMER",
                                         description="Colours, sunlight and sky", update=apply_season),
        "style": bpy.props.EnumProperty(name="Paint Style", items=_enum_items(presets.STYLES), default="ANIME",
                                        description="How the light and shadow are painted", update=apply_style),
        "variation": bpy.props.IntProperty(
            name="Variation", default=0, min=0, max=99999, update=apply_variation,
            description="Re-rolls colours, clumps, flowers, sun angle and each tree's tint around the current "
                        "season and style. 0 = off"),
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
        "cloud_count": bpy.props.IntProperty(name="Clouds", default=4, min=0, max=60,
                                             description="How many clouds Add Clouds builds (0 removes them)"),
        "weather": bpy.props.EnumProperty(name="Weather", items=[(k, v[0], v[1]) for k, v in weather.WEATHERS.items()],
                                          default="CLEAR", update=_upd_weather,
                                          description="Clouds, rain or storm on top of the season"),
        "rain_amount": bpy.props.FloatProperty(name="Rain", default=0.6, min=0.0, max=1.0, update=_upd_weather,
                                               description="How hard it rains (Rain and Storm)"),
        "rain_radius": bpy.props.FloatProperty(name="Rain Area", default=25.0, min=1.0, max=1000.0,
                                               subtype="DISTANCE", update=_upd_weather,
                                               description="Size of the rain area (the circle in the viewport)"),
        "camera_culling": bpy.props.BoolProperty(
            name="Grass Only in Camera View", default=False, update=_upd_culling,
            description="Grow grass and flowers only where the active camera can see (with a margin). Big scenes get "
                        "much lighter and faster; the rendered picture stays the same"),
        "rain_follow": bpy.props.BoolProperty(name="Follow Camera", default=True, update=_upd_rain_follow,
                                              description="Rain over wherever the camera looks. Off: it rains only "
                                                          "where Rain Here put the rain area"),
        "rainbow": bpy.props.BoolProperty(name="Rainbow", default=False, update=_upd_rainbow,
                                          description="A rainbow in the sky behind the scene"),
        "rainbow_strength": bpy.props.FloatProperty(name="Rainbow Strength", default=1.0, min=0.0, max=2.0,
                                                    update=_upd_rainbow, description="How bright the rainbow is"),
        "dragonfly_count": bpy.props.IntProperty(name="Dragonflies", default=0, min=0, max=500,
                                                 update=_upd_dragonflies,
                                                 description="Dragonflies hovering over the ponds and streams, "
                                                             "darting from spot to spot"),
        "firefly_count": bpy.props.IntProperty(name="Fireflies", default=0, min=0, max=3000, update=_upd_fireflies,
                                               description="Fireflies by the water (they glow at dusk and night)"),
        "mask_paint": bpy.props.EnumProperty(name="Paint", items=[("GRASS", "Grass", "Paint grass back in"),
                                                                  ("PATH", "Path", "Paint a bare path")],
                                             default="PATH", description="What the brush paints"),
    }
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
    cam.rotation_euler = (math.radians(85), 0, 0)
    cd.clip_end = max(200.0, size * 4)
    sc.camera = cam
    return cam


def _mesh_hit(ob, dg, origin):
    """Hit on an object's evaluated MESH only (a meadow's grass and flowers are instances: rays stop on blade tips,
    and a rock or tree put there floats a grass-height above the ground)."""
    from mathutils.bvhtree import BVHTree
    ev = ob.evaluated_get(dg)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return None
    mw = ob.matrix_world
    bvh = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    ev.to_mesh_clear()
    return bvh.ray_cast(origin, Vector((0, 0, -1)))[0]


def _ground_hit(context, loc, ignore=(), through_water=False):
    dg = context.evaluated_depsgraph_get()
    origin = Vector((loc.x, loc.y, loc.z + 1000.0))
    for _ in range(12):
        ok, hit, _n, _i, ob, _m = context.scene.ray_cast(dg, origin, Vector((0, 0, -1)))
        if not ok:
            return None
        root = tree_root(ob)
        if through_water and water.is_water(ob):
            pass
        elif root is None and ob not in ignore:
            if ob.get("hrp_ground"):
                g = _mesh_hit(ob, dg, Vector((loc.x, loc.y, loc.z + 1000.0)))
                if g is not None:
                    return g
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
        size = max(max(targets[0].dimensions.x, targets[0].dimensions.y), 1.0)
        s = sc.harappa
        _busy["on"] = True
        s.haze_start = size * 0.25
        s.haze_end = size * 3.0
        _busy["on"] = False
        shading.palette_set("haze_start", s.haze_start)
        shading.palette_set("haze_end", s.haze_end)
        if created and bpy.data.objects.get(clouds.CLOUDS) is None:
            clouds.add_clouds(context, s.cloud_count, seed=s.variation, distance=max(160.0, size * 8))
        if created:
            clouds.far_hills(context, targets[0], seed=s.variation)
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
        bl = self.blossom if self.blossom >= 0 else sc.harappa.new_blossom
        loc = sc.cursor.location.copy()
        hit = _ground_hit(context, loc)
        if water.in_water(context, loc.x, loc.y, margin=self.height * 0.08, z=hit.z if hit is not None else loc.z):
            self.report({"WARNING"}, report("Trees don't grow in water: put the 3D cursor on dry ground"))
            return {"CANCELLED"}
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
        return meadow_of(context.active_object) is not None

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
        wet = None
        if ground.modifiers.get(water.CARVE_MOD) is not None:          # not in ponds, streams or on their banks
            ev = ground.evaluated_get(context.evaluated_depsgraph_get())
            em = ev.to_mesh()
            wa = em.attributes.get("hrp_wet")
            if wa is not None and len(wa.data) == len(me.vertices):
                wet = [d.value for d in wa.data]
            ev.to_mesh_clear()
        polys = list(me.polygons)
        areas = [p.area for p in polys]
        tot = sum(areas)
        placed = []
        tries = 0
        cam = sc.camera
        shapes = ["ROUND", "ROUND", "TALL", "WIDE", "BUSH", "CONIFER"] if self.mixed else [sc.harappa.new_shape]
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
            if wet is not None and max(wet[v] for v in p.vertices) > 0.02:
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
        for co, h in placed:
            shape = rng.choice(shapes)
            if shape == "BUSH":
                h *= 0.4
            bl = sc.harappa.new_blossom
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
    bl_label = "Add Clouds"
    bl_description = "Build painted cumulus clouds in front of the scene camera (again to re-roll them)"
    bl_options = {"REGISTER", "UNDO"}

    count: bpy.props.IntProperty(name="Clouds", default=4, min=0, max=60, description="How many clouds")
    seed: bpy.props.IntProperty(name="Seed", default=-1, min=-1, max=99999, description="Cloud seed (-1 = random)")
    distance: bpy.props.FloatProperty(name="Distance", default=320.0, min=5.0, max=100000.0, subtype="DISTANCE",
                                      description="How far away the clouds float")

    def invoke(self, context, event):
        self.count = context.scene.harappa.cloud_count
        return self.execute(context)

    def execute(self, context):
        if self.count <= 0:
            ob = bpy.data.objects.get(clouds.CLOUDS)
            if ob is not None:
                bpy.data.objects.remove(ob)
            return {"FINISHED"}
        seed = self.seed if self.seed >= 0 else random.randint(0, 99999)
        clouds.add_clouds(context, self.count, seed, self.distance)
        if not _scene_ready(context.scene):
            setup_scene(context)
        self.report({"INFO"}, report(f"{self.count} cloud(s) added"))
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
        gnd0 = meadow_of(context.active_object)
        if gnd0 is not None and gnd0.get("hrp_banks_frozen"):           # the bake would hide every stroke
            water.freeze_banks(context, gnd0, False)
            self.report({"INFO"}, report("Banks are live while you paint (Freeze Banks again when done)"))
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
            for name in (build.GRASS_MOD, build.FLOWER_MOD, "Harappa Foliage", water.CARVE_MOD):
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


# ---------------------------------------------------------------------------------------------
# water
# ---------------------------------------------------------------------------------------------
def ensure_shading(context):
    """After an upgrade the palette node group is rebuilt (new keys) and every material linked to it loses its
    links: rebuild the materials, put the scene's colours back and re-attach the drivers."""
    ng = bpy.data.node_groups.get(shading.PALETTE)
    stale = [m for m in bpy.data.materials if m.get("hrp_ver") is not None and m.get("hrp_ver") != shading.SHADER_VER]
    if ng is None or (ng.get("hrp_ver") == shading.SHADER_VER and not stale):
        return False
    shading.palette_group()
    for mat in bpy.data.materials:                          # every Harappa material lost its palette links
        if mat.get("hrp_ver") is not None:
            mat["hrp_ver"] = -1
            if "hrp_water_ver" in mat:
                mat["hrp_water_ver"] = -1
    shading.all_materials()
    if bpy.data.materials.get(water.MAT_WATER) is not None:
        water.water_material()
    _refresh_all(context.scene.harappa, context)
    shading.drive_light_scale(bpy.data.objects.get(hscene.SUN))
    water.drive_time(context.scene)
    return True


@bpy.app.handlers.persistent
def _on_load(_dummy):
    try:
        ensure_shading(bpy.context)
    except Exception as e:                                  # never block opening a file
        print("[Harappa] upgrade skipped:", e)


def _upd_water(self, context):
    if _busy["on"]:
        return
    ob = self.id_data
    water.set_look(ob, hrp_hue=self.hue, hrp_sat=self.saturation, hrp_val=self.brightness,
                   hrp_clarity=self.clarity)


def _upd_water_kind(self, context):
    if _busy["on"]:
        return
    _busy["on"] = True
    try:
        self.clarity = water.WATER_TYPES[self.kind][2]                  # hue / saturation / brightness are kept
    finally:
        _busy["on"] = False
    water.set_look(self.id_data, self.kind)


def _upd_water_size(self, context):
    if _busy["on"]:
        return
    water.resize_pond(context, self.id_data, self.size)


def _upd_water_shape(self, context):
    if not _busy["on"]:
        water.reshape_pond(context, self.id_data, self.shape_seed)


class HRP_WaterSettings(bpy.types.PropertyGroup):
    kind: bpy.props.EnumProperty(
        name="Water Type", default="SEASON", update=_upd_water_kind, description="What kind of water this is",
        items=[(k, v[0], v[1]) for k, v in water.WATER_TYPES.items()])
    hue: bpy.props.FloatProperty(name="Hue Shift", default=0.0, min=-0.5, max=0.5, update=_upd_water,
                                 description="Shifts the colour of this water")
    saturation: bpy.props.FloatProperty(name="Saturation", default=0.0, min=-1.0, max=1.0, update=_upd_water,
                                        description="More or less colourful water")
    brightness: bpy.props.FloatProperty(name="Brightness", default=0.0, min=-1.0, max=1.0, update=_upd_water,
                                        description="Lighter or darker water")
    clarity: bpy.props.FloatProperty(name="Clarity", default=0.0, min=-1.0, max=1.0, update=_upd_water,
                                     description="Clear water shows a wide bright shelf and caustics; murky water "
                                                 "turns deep quickly")
    size: bpy.props.FloatProperty(name="Pond Scale", default=1.0, min=0.1, max=20.0, update=_upd_water_size,
                                  description="Scale this pond around its centre (x1 = as made)")
    shape_seed: bpy.props.IntProperty(name="Shape", default=0, min=0, max=99999, update=_upd_water_shape,
                                      description="A different shoreline for this pond (same size)")


# --- Active Rock: read/written straight from the object's own data, so every rock (the waterfall's too) is editable
def _rock_info(ob):
    info = list(ob.get("hrp_rock", [1.0, 0, 0.65, 0]))
    return info + [0] * (4 - len(info))


def _get_rsize(self):
    return float(self.id_data.get("hrp_rsize", 1.0))


def _set_rsize(self, v):
    ob = self.id_data
    k = v / max(1e-4, float(ob.get("hrp_rsize", 1.0)))
    ob.scale = tuple(x * k for x in ob.scale)
    ob["hrp_rsize"] = float(v)


def _get_rflat(self):
    return float(_rock_info(self.id_data)[2])


def _set_rflat(self, v):
    rocks.edit_rock(self.id_data, flat=v)


def _get_rseed(self):
    return int(_rock_info(self.id_data)[1])


def _set_rseed(self, v):
    rocks.edit_rock(self.id_data, seed=v)


def _get_rmoss(self):
    return 1.0 - float(self.id_data.get("hrp_nomoss", 0.0))


def _set_rmoss(self, v):
    ob = self.id_data
    ob["hrp_nomoss"] = 1.0 - float(v)
    ob.update_tag()


class HRP_RockSettings(bpy.types.PropertyGroup):
    size: bpy.props.FloatProperty(name="Rock Size", min=0.05, max=20.0, get=_get_rsize, set=_set_rsize,
                                  description="Scale this rock")
    flat: bpy.props.FloatProperty(name="Flatness", min=0.2, max=1.5, get=_get_rflat, set=_set_rflat,
                                  description="Low and flat (small) or tall and round (large)")
    seed: bpy.props.IntProperty(name="Seed", min=0, max=99999, get=_get_rseed, set=_set_rseed,
                                description="A different shape for this rock")
    moss: bpy.props.FloatProperty(name="Moss", min=0.0, max=1.0, get=_get_rmoss, set=_set_rmoss,
                                  description="Moss on this rock (the colour and overall amount are in Colours)")


# --- Active Waterfall: Flow changes live; Height, Width and Seed rebuild it a moment after you stop dragging
_wf_pending = {}


def _wf_args(fall):
    return list(fall.get("hrp_wf_args", [0, 0, 0, 0, 1, 2.4, 1.1, 0]))


def _wf_rebuild():
    if not _wf_pending:
        return None
    tag, vals = next(iter(_wf_pending.items()))
    _wf_pending.clear()
    context = bpy.context
    fall = waterfall.fall_of(context, tag)
    if fall is None:
        return None
    new = waterfall.rebuild_waterfall(context, fall, **vals)
    try:
        _select(context, new)
        bpy.ops.ed.undo_push(message="Edit Waterfall")
    except Exception:
        pass
    return None


def _wf_getter(i, key, cast=float):
    def get(self):
        ob = self.id_data
        p = _wf_pending.get(ob.get("hrp_waterfall"), {})
        return cast(p.get(key, _wf_args(ob)[i]))
    return get


def _wf_setter(key, cast):
    def set_(self, v):
        ob = self.id_data
        tag = ob.get("hrp_waterfall")
        if tag is None:
            return
        _wf_pending.setdefault(tag, {})[key] = cast(v)
        if bpy.app.timers.is_registered(_wf_rebuild):
            bpy.app.timers.unregister(_wf_rebuild)
        bpy.app.timers.register(_wf_rebuild, first_interval=0.5)
    return set_


def _get_flow(self):
    return float(self.id_data.get("hrp_wf_flow", 1.0))


def _set_flow(self, v):
    waterfall.set_flow(self.id_data, v)


class HRP_FallSettings(bpy.types.PropertyGroup):
    height: bpy.props.FloatProperty(name="Height", min=0.5, max=50.0, subtype="DISTANCE",
                                    get=_wf_getter(5, "height"), set=_wf_setter("height", float),
                                    description="Height of the fall (rebuilds the waterfall's rocks and trees)")
    width: bpy.props.FloatProperty(name="Width", min=0.2, max=20.0, subtype="DISTANCE",
                                   get=_wf_getter(6, "width"), set=_wf_setter("width", float),
                                   description="Width of the falling water (rebuilds the waterfall's rocks and trees)")
    seed: bpy.props.IntProperty(name="Seed", min=0, max=99999, get=_wf_getter(7, "seed", int), set=_wf_setter("seed", int),
                                description="Another arrangement of rocks and trees (rebuilds the waterfall)")
    flow: bpy.props.FloatProperty(name="Flow", min=0.0, max=2.0, get=_get_flow, set=_set_flow,
                                  description="How much water comes over the lip")


class HRP_OT_set_water_enum(bpy.types.Operator):
    bl_idname = "harappa.set_water_enum"
    bl_label = "Set"
    bl_description = "Choose this option"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    value: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        ob = context.active_object
        if water.is_water(ob):
            ob.harappa_water.kind = self.value
        return {"FINISHED"}


def _need_meadow(op, context):
    ensure_shading(context)
    if not water.meadows(context.scene):
        op.report({"WARNING"}, report("Make a meadow first: water carves its bed into the meadow"))
        return False
    return True


def _select(context, ob):
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob


class HRP_OT_add_pond(bpy.types.Operator):
    bl_idname = "harappa.add_pond"
    bl_label = "Add Pond"
    bl_description = ("A toon pond at the 3D cursor. It digs its own bed into the meadow and the grass steps back "
                      "from the bank. Edit the curve to reshape it")
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(name="Radius", default=2.5, min=0.2, max=200.0, subtype="DISTANCE",
                                    description="Rough radius of the pond")
    depth: bpy.props.FloatProperty(name="Depth", default=0.7, min=0.02, max=50.0, subtype="DISTANCE",
                                   description="Deepest point below the water line")
    seed: bpy.props.IntProperty(name="Seed", default=0, min=0, description="Shape of the shoreline")

    def execute(self, context):
        if not _need_meadow(self, context):
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        ob = water.add_pond(context, context.scene.cursor.location, self.radius, self.seed, self.depth)
        _busy["on"] = True
        ob.harappa_water.shape_seed = self.seed
        _busy["on"] = False
        _select(context, ob)
        water.clear_trees(context)
        self.report({"INFO"}, report("Pond added"))
        return {"FINISHED"}


class HRP_OT_add_stream(bpy.types.Operator):
    bl_idname = "harappa.add_stream"
    bl_label = "Add Stream"
    bl_description = ("A winding toon stream starting at the 3D cursor and running away from the camera. It "
                      "follows the meadow downhill and carves its own channel. Edit the curve, then Drop Onto "
                      "Meadow")
    bl_options = {"REGISTER", "UNDO"}

    length: bpy.props.FloatProperty(name="Length", default=12.0, min=1.0, max=2000.0, subtype="DISTANCE",
                                    description="Length of the new stream")
    width: bpy.props.FloatProperty(name="Width", default=1.4, min=0.05, max=100.0, subtype="DISTANCE",
                                   description="Stream width in metres")
    depth: bpy.props.FloatProperty(name="Depth", default=0.45, min=0.02, max=50.0, subtype="DISTANCE",
                                   description="Deepest point below the water line")

    def execute(self, context):
        if not _need_meadow(self, context):
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        c = context.scene.cursor.location
        cam = context.scene.camera
        fwd = Vector((0.0, 1.0, 0.0))
        if cam is not None:
            f = cam.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
            f.z = 0.0
            if f.length > 1e-4:
                fwd = f.normalized()
        side = Vector((-fwd.y, fwd.x, 0.0))
        pts = []
        for i in range(6):
            u = i / 5
            p = c + fwd * (self.length * u) + side * (math.sin(u * math.pi * 1.6) * self.length * 0.1)
            pts.append((p.x, p.y, p.z))
        ob = water.add_stream(context, pts, self.width, self.depth)
        _select(context, ob)
        water.clear_trees(context)
        self.report({"INFO"}, report("Stream added"))
        return {"FINISHED"}


class HRP_OT_make_water(bpy.types.Operator):
    bl_idname = "harappa.make_water"
    bl_label = "Make Water from Curves"
    bl_description = ("Turn the selected curves into water: closed curves become ponds, open curves become streams "
                      "(drawn from upstream to downstream)")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if not _need_meadow(self, context):
            return {"CANCELLED"}
        curves = [o for o in context.selected_objects if o.type == "CURVE"]
        if not curves:
            self.report({"WARNING"}, report("Select one or more curves"))
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for ob in curves:
            if not any(sp.use_cyclic_u for sp in ob.data.splines):
                water.snap_stream(context, ob)
            water.make_water(context, ob)
        water.settle(context)                                    # spill levels, streams meeting ponds
        water.clear_trees(context)
        water.refreeze(context)
        self.report({"INFO"}, report(f"Water from {len(curves)} curve(s)"))
        return {"FINISHED"}


class HRP_OT_drop_stream(bpy.types.Operator):
    bl_idname = "harappa.drop_stream"
    bl_label = "Drop Onto Meadow"
    bl_description = ("Lay the active stream back onto the meadow after editing it (running downhill only), or re-level an "
                      "edited pond to its lowest rim; streams nearby join it again")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return water.is_water(context.active_object)

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if not any(sp.use_cyclic_u for sp in context.active_object.data.splines):   # (a pond: just re-level it)
            water.snap_stream(context, context.active_object)
        water.settle(context)
        water.clear_trees(context)
        water.refreeze(context)
        return {"FINISHED"}


class HRP_OT_add_rock(bpy.types.Operator):
    bl_idname = "harappa.add_rock"
    bl_label = "Add Rock"
    bl_description = ("A painted rock with moss on top at the 3D cursor; grass and flowers grow around it. "
                      "Press again for another shape")
    bl_options = {"REGISTER", "UNDO"}

    size: bpy.props.FloatProperty(name="Size", default=1.0, min=0.05, max=100.0, subtype="DISTANCE",
                                  description="Rough size of the rock")
    flat: bpy.props.FloatProperty(name="Flatness", default=0.65, min=0.2, max=1.5,
                                  description="Low and flat (small) or tall and round (large)")
    seed: bpy.props.IntProperty(name="Seed", default=-1, min=-1, max=99999, description="Shape seed (-1 = random)")

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        ensure_shading(context)
        seed = self.seed if self.seed >= 0 else random.randint(0, 99999)
        loc = context.scene.cursor.location.copy()
        hit = _ground_hit(context, loc, through_water=True)            # on the bed, not floating on a pond
        gz = None if hit is None else hit.z
        if gz is not None:                                              # on a slope: seat it on the low side
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                h2 = _ground_hit(context, loc + Vector((dx, dy, 0)) * 0.38 * self.size, through_water=True)
                if h2 is not None:
                    gz = min(gz, h2.z)
        ob = rocks.add_rock(context, loc, self.size, seed, self.flat, gz)
        _select(context, ob)
        return {"FINISHED"}


class HRP_OT_add_waterfall(bpy.types.Operator):
    bl_idname = "harappa.add_waterfall"
    bl_label = "Add Waterfall"
    bl_description = ("A waterfall whose plunge pool is at the 3D cursor: a raised terrace behind it, a stream "
                      "across the top, a rock ledge it drops from, rock walls on both sides and foam at the foot. "
                      "It faces the camera")
    bl_options = {"REGISTER", "UNDO"}

    height: bpy.props.FloatProperty(name="Height", default=2.4, min=0.5, max=50.0, subtype="DISTANCE",
                                    description="Height of the fall")
    width: bpy.props.FloatProperty(name="Width", default=1.4, min=0.2, max=20.0, subtype="DISTANCE",
                                   description="Width of the water at the lip")
    seed: bpy.props.IntProperty(name="Seed", default=-1, min=-1, max=99999, description="Shape seed (-1 = random)")

    def execute(self, context):
        if not _need_meadow(self, context):
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        sc = context.scene
        c = sc.cursor.location.copy()
        fwd = Vector((0.0, 1.0, 0.0))
        if sc.camera is not None:
            f = sc.camera.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
            f.z = 0.0
            if f.length > 1e-4:
                fwd = f.normalized()
        seed = self.seed if self.seed >= 0 else random.randint(0, 99999)
        ob = waterfall.add_waterfall(context, c, fwd, self.height, self.width, seed)
        water.clear_trees(context)
        water.refreeze(context)
        _select(context, ob)
        return {"FINISHED"}


class HRP_OT_remove_waterfall(bpy.types.Operator):
    bl_idname = "harappa.remove_waterfall"
    bl_label = "Remove Waterfall"
    bl_description = "Delete the whole waterfall the active object belongs to (terrace, stream, rocks, pool, sheet)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.get("hrp_waterfall") is not None

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        waterfall.remove_waterfall(context, context.active_object["hrp_waterfall"])
        water.settle(context)
        water.clear_trees(context)
        water.refreeze(context)
        return {"FINISHED"}


class HRP_OT_add_fish(bpy.types.Operator):
    bl_idname = "harappa.add_fish"
    bl_label = "Add Koi"
    bl_description = "Koi swimming slow loops in the deep water of the active pond"
    bl_options = {"REGISTER", "UNDO"}

    count: bpy.props.IntProperty(name="Count", default=6, min=1, max=200, description="How many koi")

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return water.is_water(ob) and any(sp.use_cyclic_u for sp in ob.data.splines)

    def execute(self, context):
        ensure_shading(context)
        fauna.add_fish(context, context.active_object, self.count)
        return {"FINISHED"}


class HRP_OT_add_boat(bpy.types.Operator):
    bl_idname = "harappa.add_boat"
    bl_label = "Add Boat"
    bl_description = ("A small wooden rowboat floating on the active pond (at the 3D cursor when it is on the "
                      "water). Draft, bob and rock live on its Harappa Float modifier")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return water.is_water(ob) and any(sp.use_cyclic_u for sp in ob.data.splines)

    def execute(self, context):
        ensure_shading(context)
        pond = context.active_object
        c = context.scene.cursor.location
        at = c if water.in_water(context, c.x, c.y, 0.0) else None
        boat = fauna.add_boat(context, pond, at=at)
        _select(context, boat)
        return {"FINISHED"}


class HRP_OT_stepping_stones(bpy.types.Operator):
    bl_idname = "harappa.stepping_stones"
    bl_label = "Add Stepping Stones"
    bl_description = ("A row of flat stones across the active stream where it passes closest to the 3D cursor, "
                      "their tops just above the water")
    bl_options = {"REGISTER", "UNDO"}

    count: bpy.props.IntProperty(name="Stones", default=0, min=0, max=30,
                                 description="How many stones (0 = enough to cross)")

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return water.is_water(ob) and not any(sp.use_cyclic_u for sp in ob.data.splines)

    def execute(self, context):
        ensure_shading(context)
        made = water.stepping_stones(context, context.active_object, context.scene.cursor.location, self.count)
        if not made:
            self.report({"WARNING"}, report("Could not find the stream near the 3D cursor"))
            return {"CANCELLED"}
        self.report({"INFO"}, report(f"{len(made)} stepping stones"))
        return {"FINISHED"}


class HRP_OT_rain_here(bpy.types.Operator):
    bl_idname = "harappa.rain_here"
    bl_label = "Rain Here"
    bl_description = ("Make it rain only around the 3D cursor (inside the Rain Area circle); ponds outside stay "
                      "calm. Turns Follow Camera off")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ensure_shading(context)
        s = context.scene.harappa
        if s.weather not in ("RAIN", "STORM"):
            s.weather = "RAIN"
        c = context.scene.cursor.location
        weather.ensure_rain(context, at=(c.x, c.y), amount=max(0.01, min(1.0, s.rain_amount / 0.6 *
                            weather.WEATHERS[s.weather][5])), radius=s.rain_radius)
        _busy["on"] = True
        try:
            s.rain_follow = False
        finally:
            _busy["on"] = False
        water.drive_rain_zone()
        return {"FINISHED"}


class HRP_OT_freeze_banks(bpy.types.Operator):
    bl_idname = "harappa.freeze_banks"
    bl_label = "Freeze Banks"
    bl_description = ("Bake the dug banks of every meadow into the file so playback is fast. Harappa re-bakes after "
                      "its own water tools; after editing a curve by hand press Update Banks")
    bl_options = {"REGISTER", "UNDO"}

    on: bpy.props.BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for gnd in water.meadows(context.scene):
            if self.on and gnd.get("hrp_banks_frozen"):
                water.freeze_banks(context, gnd, False)
            water.freeze_banks(context, gnd, self.on)
        return {"FINISHED"}


class HRP_OT_remove_water(bpy.types.Operator):
    bl_idname = "harappa.remove_water"
    bl_label = "Remove Water"
    bl_description = "Delete the active pond or stream; the meadow fills back in"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return water.is_water(context.active_object)

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        water.remove_water(context, context.active_object)
        return {"FINISHED"}


CLASSES = (
    HRP_Settings, HRP_TreeSettings, HRP_OT_make_meadow, HRP_OT_add_tree, HRP_OT_plant_trees,
    HRP_OT_rebuild_tree, HRP_OT_set_tree_enum, HRP_OT_edit_canopy,
    HRP_OT_make_foliage, HRP_OT_add_clouds, HRP_OT_setup_scene, HRP_OT_paint_mask, HRP_OT_shuffle, HRP_OT_reset,
    HRP_OT_revert, HRP_OT_set_enum,
    HRP_WaterSettings, HRP_RockSettings, HRP_FallSettings, HRP_OT_set_water_enum, HRP_OT_add_pond, HRP_OT_add_stream, HRP_OT_add_rock,
    HRP_OT_add_waterfall, HRP_OT_remove_waterfall, HRP_OT_add_fish, HRP_OT_add_boat, HRP_OT_stepping_stones, HRP_OT_rain_here, HRP_OT_freeze_banks, HRP_OT_make_water, HRP_OT_drop_stream, HRP_OT_remove_water,
)


def register():
    i18n.register()
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.harappa = bpy.props.PointerProperty(type=HRP_Settings)
    bpy.types.Object.harappa_tree = bpy.props.PointerProperty(type=HRP_TreeSettings)
    bpy.types.Object.harappa_water = bpy.props.PointerProperty(type=HRP_WaterSettings)
    bpy.types.Object.harappa_rock = bpy.props.PointerProperty(type=HRP_RockSettings)
    bpy.types.Object.harappa_fall = bpy.props.PointerProperty(type=HRP_FallSettings)
    ui.register()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    bpy.app.timers.register(lambda: (_on_load(None), None)[1], first_interval=0.2)   # updated while a file is open


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    ui.unregister()
    del bpy.types.Object.harappa_water
    del bpy.types.Object.harappa_rock
    del bpy.types.Object.harappa_fall
    if bpy.app.timers.is_registered(_wf_rebuild):
        bpy.app.timers.unregister(_wf_rebuild)
    del bpy.types.Object.harappa_tree
    del bpy.types.Scene.harappa
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    i18n.unregister()
