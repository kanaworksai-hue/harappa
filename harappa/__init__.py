# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Harappa (原っぱ) — one-click anime grass, trees and flowers for Blender (EEVEE).

by KanaWorks_AI · Tokyo AI Visuals LLC · https://x.com/KanaWorks_AI
Redistribution or modification must keep the attribution in NOTICE.md (GPLv3 section 7(b)).
"""
import colorsys
import json
import math
import os
import random

import bmesh
import bpy
from mathutils import Vector, noise

from . import (avoid, blend, build, clouds, cumulus, fauna, i18n, layers, look, looks, pondlife, presets, quality,
               ridges, rocks, scatter, scene as hscene, shading, tree, ui, water, waterfall, weather)
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
    ("leaf_break", "Broken Leaf Edges", 0.0, 1.0, "Breaks the edges of the leaf dabs into ragged brush marks"),
    ("cloud_jitter", "Cloud Brushiness", 0.0, 4.0, "How broken and brushy the edge between a cloud's light and shade is"),
    ("cloud_rim_amount", "Cloud Rim Glow", 0.0, 1.0, "Bright edge on clouds that have the sun behind them"),
    ("cloud_threshold", "Cloud Light / Shadow Split", 0.0, 1.0, "How much of each cloud is in shade"),
    ("tint_amount", "Painted Colour Strength", 0.0, 1.0, "How strongly colours painted on the meadow show through"),
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


def bl_info_version():
    """The add-on version from blender_manifest.toml (written into saved looks)."""
    try:
        with open(os.path.join(os.path.dirname(__file__), "blender_manifest.toml"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


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
    self.look_name = ""                                   # the season's colours replace a look's
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
def after_look(context):
    """A look was written into the settings (looks.apply): bring the scene up to it in one go."""
    sc = context.scene
    s = sc.harappa
    se = presets.SEASONS[s.season]
    sun = bpy.data.objects.get(hscene.SUN)
    if sun is not None:
        hscene.key_sun(sc, sc.camera, s.sun_elevation, s.sun_side, se["sun"]["colour"], se["sun"]["strength"])
    _season_blossom(sc, se.get("blossom", 0.0))
    w = bpy.data.worlds.get(hscene.WORLD)
    if w is not None:
        st, mo = se.get("night", (0.0, 0.0))
        hscene.set_night(w, st, mo, sc.camera)
    _style_leaves(sc)
    quality.apply(sc)
    _refresh_all(s, context)


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


def _style_leaves(sc, obs=None):
    """The paint style also sets the size of the leaf dabs (Crisp: big blocks, Painterly: small broken dabs), with
    the density turned the other way (by area) so a crown stays as full. Each crown keeps its own base values, so a style
    change is lossless and a value the user typed is taken as the new base."""
    m0 = float(presets.STYLES[sc.harappa.style]["keys"].get("leaf_scale", 1.0))
    for ob in (obs if obs is not None else sc.objects):
        if not ob.get("hrp_canopy") or ob.get("hrp_clouds"):
            continue
        # needle pads stay solid: an evergreen only takes the bigger dabs, never smaller ones
        m = max(m0, 1.0) if ob.get("hrp_evergreen") else m0
        mod = ob.modifiers.get("Harappa Foliage")
        if mod is None or mod.node_group is None:
            continue
        try:
            cs, cd = float(mod_input(mod, "Leaf Size")), float(mod_input(mod, "Density"))
        except KeyError:
            continue
        prev = float(ob.get("hrp_leaf_mult", 1.0))
        base = ob.get("hrp_leaf_base")
        if base is None or abs(cs - base[0] * prev) > 1e-5 * max(1.0, cs) \
                or abs(cd - base[1] / prev ** 2) > 1e-4 * max(1.0, cd):
            base = (cs / prev, cd * prev ** 2)                 # new, rebuilt or edited by hand
        ob["hrp_leaf_base"] = list(base)
        ob["hrp_leaf_mult"] = m
        mod_input(mod, "Leaf Size", base[0] * m)
        mod_input(mod, "Density", base[1] / m ** 2)            # by area: a crown stays as full
        ob.update_tag()


def apply_style(self, context):
    if _busy["on"]:
        return
    _apply_values(self, None, presets.STYLES[self.style]["keys"])
    _style_leaves(context.scene)
    quality.apply(context.scene)                          # the clouds' grid follows the style too
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
            look.compose(ob)                               # the user's own colour for this tree stays
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
                                            get=g_seed, set=s_seed, options=set(),
                                            description="Pick another shape for this cloud (it stays where it is)"),
        "cloud_tower": bpy.props.FloatProperty(name="Tower", min=0.0, max=1.0, get=g_tower, set=s_tower, options=set(),
                                               description="How high the cloud piles up: flat cumulus at 0, a "
                                                           "towering summer cloud at 1"),
        "cloud_width": bpy.props.FloatProperty(name="Cloud Width", min=0.01, max=1e6, get=g_width, set=s_width,
                                               options=set(),
                                               subtype="DISTANCE", description="Width of this cloud"),
    }


PAINT_LAYERS = [
    ("GRASS", "Grass", "Paint where grass grows. Erase to make bare paths and clearings"),
    ("FLOWERS", "Flowers", "Paint where flowers bloom. Erase to keep an area plain grass"),
    ("HEIGHT", "Grass Height", "Paint taller grass. Erase to make it shorter, like a mown lawn"),
    ("COLOUR", "Colour", "Paint a colour onto the grass and ground: sunlit patches, dry spots, flower beds"),
]
_BRUSHES = "brushes/essentials_brushes-mesh_vertex.blend/Brush/"


def _upd_paint_colour(self, context):
    """The Colour layer paints a colour at full brightness: the field shows exactly what will be painted."""
    if _busy["on"]:
        return
    fv = layers.full_value(tuple(self.paint_colour))
    if max(abs(a - b) for a, b in zip(fv, self.paint_colour)) > 1e-4:
        _busy["on"] = True
        self.paint_colour = fv
        _busy["on"] = False
    _upd_brush(self, context)


def _upd_brush(self, context):
    if not _busy["on"] and context.mode == "PAINT_VERTEX" and meadow_of(context.active_object) is not None:
        apply_brush(context)                    # never on the user's own mesh they are vertex painting


def apply_brush(context):
    """Point Blender's vertex paint brush at the chosen layer, mode, strength and colour. Every step is optional:
    brushes are assets that differ between versions, so whatever cannot be set is left to the user."""
    s = context.scene.harappa
    ob = context.active_object
    if ob is None or ob.type != "MESH":
        return False
    me = ob.data
    at = layers.ensure(me, s.paint_layer)
    try:
        me.color_attributes.active_color = at
    except (AttributeError, TypeError):
        pass
    ts = context.tool_settings
    vp = ts.vertex_paint
    brush = getattr(vp, "brush", None)
    want_blur = s.paint_mode == "SMOOTH"
    is_blur = getattr(brush, "vertex_brush_type", "DRAW") in ("BLUR", "AVERAGE", "SMEAR")
    if brush is None or want_blur != is_blur:
        try:
            bpy.ops.brush.asset_activate(asset_library_type="ESSENTIALS",
                                         relative_asset_identifier=_BRUSHES + ("Blur" if want_blur else "Paint Hard"))
        except (RuntimeError, TypeError, AttributeError):
            pass
        brush = getattr(vp, "brush", None)
    if brush is None:
        return False
    rgba, blend = layers.target(s.paint_layer, s.paint_mode, tuple(s.paint_colour))
    ok = True
    for holder in (getattr(vp, "unified_paint_settings", None), brush):    # 5.2 reads the first, 5.3 the brush
        if holder is None:
            continue
        for attr, val in (("color", rgba[:3]), ("strength", s.paint_strength)):
            try:
                setattr(holder, attr, val)
            except (AttributeError, TypeError):
                ok = ok and holder is not brush
    try:
        if not want_blur:
            brush.blend = blend
    except (AttributeError, TypeError):
        ok = False
    return ok


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
                                        description="How light and shadow are painted, how big the leaf dabs are and "
                                                    "how blocky the clouds are", update=apply_style),
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
        "paint_layer": bpy.props.EnumProperty(name="Brush Layer", items=PAINT_LAYERS, default="GRASS",
                                              description="What the brush paints on the meadow", update=_upd_brush),
        "paint_mode": bpy.props.EnumProperty(
            name="Brush", default="PAINT", update=_upd_brush, description="What a brush stroke does",
            items=[("PAINT", "Paint", "Add with the brush"),
                   ("ERASE", "Erase", "Remove with the brush"),
                   ("SMOOTH", "Smooth", "Soften the edges of what you painted")]),
        "paint_strength": bpy.props.FloatProperty(name="Brush Strength", default=0.6, min=0.0, max=1.0, subtype="FACTOR",
                                                  update=_upd_brush,
                                                  description="How much each stroke changes. Lower for soft edges"),
        "paint_colour": bpy.props.FloatVectorProperty(
            name="Paint Colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=layers.full_value(srgb("#F2D25C")),
            update=_upd_paint_colour,
            description="Pick a paint colour. It is painted at full brightness; light and shade still fall on it. "
                        "The swatches match the current season"),
        "look_name": bpy.props.StringProperty(name="Look", default="",
                                              description="The look last put on this scene"),
    }
    ann.update(_cloud_props())
    ann.update(look.props())
    ann.update(avoid.props())
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


SMALL_GROUND = 10.0          # metres: a meadow on less than this shows only a patch of grass from the camera
HILL_SIZE = 40.0


def _ground_size(ob):
    return max(ob.dimensions.x, ob.dimensions.y)


def _is_small_plane(ob):
    """A plain plane (Blender's Add > Plane, maybe scaled) too small for a meadow: 4 corners, one face, flat, no
    modifiers, under SMALL_GROUND. Make Anime Meadow turns it into the rolling hill instead of a 2 m lawn."""
    return (ob.type == "MESH" and len(ob.data.vertices) == 4 and len(ob.data.polygons) == 1 and not ob.modifiers
            and ob.dimensions.z < 1e-4 and _ground_size(ob) < SMALL_GROUND and not ob.get("hrp_ground"))


def _hill_mesh(size=HILL_SIZE, seed=0):
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
    return me


def _make_hill(context, size=HILL_SIZE, seed=0):
    ob = bpy.data.objects.new("Meadow", _hill_mesh(size, seed))
    ob["hrp_hill"] = True                     # Harappa's own hill: already fine enough to paint on
    ob.location = context.scene.cursor.location
    (context.collection or context.scene.collection).objects.link(ob)
    return ob


def _plane_to_hill(ob, seed=0):
    """The small plane becomes the hill where it stands (same object, name and place; Ctrl+Z brings it back)."""
    old = ob.data
    ob.data = _hill_mesh(HILL_SIZE, seed)
    for m in old.materials:
        ob.data.materials.append(m)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    ob.rotation_euler = (0.0, 0.0, ob.rotation_euler.z)
    ob.scale = (1.0, 1.0, 1.0)
    ob["hrp_hill"] = True
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
    plane_to_hill: bpy.props.BoolProperty(
        name="Small Plane to Hill", default=True,
        description="A plain plane smaller than 10 m becomes a 40 m rolling hill: a meadow needs room. "
                    "Off: grass only on the plane")

    def execute(self, context):
        sc = context.scene
        targets = [o for o in context.selected_objects if o.type == "MESH" and tree_root(o) is None
                   and not o.get("hrp_canopy") and not _is_default_cube(o)]
        created = False
        grown = None
        if not targets:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            _hide_startup_objects(sc)
            targets = [_make_hill(context, seed=sc.harappa.variation)]
            created = True
        elif self.plane_to_hill and len(targets) == 1 and _is_small_plane(targets[0]):
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            _hide_startup_objects(sc)
            grown = _ground_size(targets[0])
            _plane_to_hill(targets[0], seed=sc.harappa.variation)
            context.view_layer.update()
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
        if avoid.current(sc) is not None:                      # a new meadow avoids what the others avoid
            avoid.assign(sc, avoid.current(sc))
        if created:
            for o in context.selected_objects:
                o.select_set(False)
            targets[0].select_set(True)
            context.view_layer.objects.active = targets[0]
        small = [o for o in targets if _ground_size(o) < SMALL_GROUND]
        if grown is not None:
            self.report({"INFO"}, report(f"The {grown:.1f} m plane became a {HILL_SIZE:.0f} m hill: a meadow needs room"))
        elif small:
            self.report({"WARNING"}, report(f"Small ground ({_ground_size(small[0]):.1f} m): the meadow is only that "
                                            f"big. Scale it to 30 m or more, or click with nothing selected for a hill"))
        else:
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
        if water.in_water(context, loc.x, loc.y, margin=self.height * 0.08, z=hit.z if hit is not None else loc.z):
            self.report({"WARNING"}, report("Trees don't grow in water: put the 3D cursor on dry ground"))
            return {"CANCELLED"}
        if hit is not None:
            loc.z = hit.z - 0.02 * self.height
        root = tree.add_tree(context, self.shape, self.height, seed, loc, blossom=bl)
        init_tree_settings(root, self.shape, self.height, seed, tree.SHAPES[self.shape]["style"])
        _style_leaves(sc, root.children)
        if not _scene_ready(sc):
            setup_scene(context)
        for o in context.selected_objects:
            o.select_set(False)
        root.select_set(True)
        context.view_layer.objects.active = root
        self.report({"INFO"}, report(f"Tree added (seed {seed})"))
        return {"FINISHED"}


def _refit_clouds(sc):
    """Trees were planted after the clouds were laid out: the layout's own clouds that a new crown would cover step
    aside. The others, and clouds the user moved or shaped, stay where they are."""
    cumulus.clear_trees(bpy.context)


def _onto_third(sc, cam, ground, co, h, others, mask):
    """Slide the focal tree sideways onto the nearer third of the frame, onto the ground, if there is room."""
    from bpy_extras.object_utils import world_to_camera_view
    q = world_to_camera_view(sc, cam, co)
    target = 1 / 3 if q.x < 0.5 else 2 / 3
    tr, _br, _bl, tl = cam.data.view_frame(scene=sc)
    half = abs(tr.x - tl.x) * 0.5 / max(abs(tr.z), 1e-6)      # half the frame width per metre of depth
    right = cam.matrix_world.to_quaternion() @ Vector((1, 0, 0))
    right.z = 0.0
    if right.length < 1e-6:
        return co
    p = co + right.normalized() * (target - q.x) * 2.0 * half * q.z
    inv = ground.matrix_world.inverted()
    hit, loc, _n, idx = ground.ray_cast(inv @ (p + Vector((0, 0, 1000.0))),
                                         (inv.to_3x3() @ Vector((0, 0, -1))).normalized())
    if not hit:
        return co
    p = ground.matrix_world @ loc
    if mask is not None:
        poly = ground.data.polygons[idx]
        if min(mask.data[v].color[0] for v in poly.vertices) < 0.7:   # not onto a painted path
            return co
    if any((p - o).length < h * 0.9 for o in others):
        return co
    if (p - cam.matrix_world.translation).length < h * 3.0:     # the same 'not too close' rule as the others
        return co
    return p


class HRP_OT_plant_trees(bpy.types.Operator):
    bl_idname = "harappa.plant_trees"
    bl_label = "Plant Trees"
    bl_description = ("Scatter anime trees over the active meadow, keeping off painted paths. Clouds that the new "
                      "trees would cover step aside")
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
        _style_leaves(sc)
        _refit_clouds(sc)
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
        look.compose(canopy)
        if mod is not None:
            mod_input(mod, "Leaf Size", sp["leaf"] * height)
            mod_input(mod, "Density", float(sp["dens"]) * (5.0 / max(height, 0.1)) ** 2)
            mod_input(mod, "Inflate", 0.025 * height)
            mod_input(mod, "Roundness", sp["roundness"])
            mod_input(mod, "Blossom Scale", 0.16 * height)
            mod_input(mod, "Card", tree.card_object(context.scene, "leaf", style))
            for k in ("hrp_leaf_base", "hrp_leaf_mult"):
                if k in canopy:
                    del canopy[k]
            _style_leaves(context.scene, [canopy])


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
            for k in ("hrp_leaf_base", "hrp_leaf_mult"):          # fresh values: not a hand edit under this style
                if k in ob:
                    del ob[k]
            mod = ob.modifiers.get("Harappa Foliage") or ob.modifiers.new("Harappa Foliage", "NODES")
            mod.node_group = scatter.foliage_group()
            mod_input(mod, "Card", tree.card_object(context.scene, "leaf", "ROUND"))
            sc_ = ob.matrix_world.to_scale()                     # the mesh itself, not the leaves on it
            vs = [v.co for v in ob.data.vertices] if ob.type == "MESH" and len(ob.data.vertices) else None
            size = (max((max(c[i] for c in vs) - min(c[i] for c in vs)) * abs(sc_[i]) for i in range(3))
                    if vs else max(ob.dimensions)) or 1.0
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
            look.compose(ob)
        if not _scene_ready(context.scene):
            setup_scene(context)
        _style_leaves(context.scene, obs)
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
                ob["hrp_value"] = float(ob.get("hrp_value_base", 0.0))
                look.compose(ob)                           # each object's own colour is the user's: it stays
        s.look_name = ""
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


# ---------------------------------------------------------------------------------------------
# brush layers
# ---------------------------------------------------------------------------------------------
def _painting_target(context):
    """The meadow being painted right now, else None."""
    if context.mode != "PAINT_VERTEX":
        return None
    return meadow_of(context.active_object)


def _paint_target(context):
    """The meadow to paint on: the active object when it is one, else the only meadow of the scene."""
    ob = meadow_of(context.active_object)
    if ob is not None:
        return ob
    ms = avoid.meadows(context.scene)
    return ms[0] if len(ms) == 1 else None


class HRP_OT_paint_layer(bpy.types.Operator):
    bl_idname = "harappa.paint_layer"
    bl_label = "Paint Layer"
    bl_description = "Paint this layer on the meadow with the brush (click again to stop painting)"
    bl_options = {"REGISTER", "UNDO"}
    layer: bpy.props.EnumProperty(items=PAINT_LAYERS, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        it = next((i for i in PAINT_LAYERS if i[0] == props.layer), None)
        return i18n.t(it[2]) if it else ""

    @classmethod
    def poll(cls, context):
        if _paint_target(context) is not None:
            return True
        cls.poll_message_set(i18n.t("Select a meadow to paint on"))
        return False

    def execute(self, context):
        s = context.scene.harappa
        ob = _paint_target(context)
        if context.mode == "PAINT_VERTEX" and context.active_object == ob and s.paint_layer == self.layer:
            return bpy.ops.harappa.paint_done()                     # the same button again: done
        scatter.grass_group()                                       # an older file: bring the nodes up first
        scatter.flowers_group()
        if context.mode == "PAINT_VERTEX":                          # keep a strength set with Shift+F
            br = getattr(context.tool_settings.vertex_paint, "brush", None)
            if br is not None and abs(br.strength - s.paint_strength) > 1e-4:
                _busy["on"] = True
                s.paint_strength = br.strength
                _busy["on"] = False
        if context.mode != "OBJECT" and context.active_object != ob:
            bpy.ops.object.mode_set(mode="OBJECT")
        if context.active_object != ob:
            for o in context.selected_objects:
                o.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
        fresh = layers.attr_name(self.layer) not in ob.data.color_attributes or not layers.painted(ob)
        layers.ensure(ob.data, self.layer)
        _busy["on"] = True
        if s.paint_layer != self.layer or context.mode != "PAINT_VERTEX":
            s.paint_mode = "PAINT"                  # a new layer starts with its Paint action (More Flowers, Taller...)
        s.paint_layer = self.layer
        if s.paint_mode == "SMOOTH":
            s.paint_mode = "PAINT"
        if self.layer == "GRASS" and fresh and "GRASS" not in layers.painted(ob):
            s.paint_mode = "ERASE"                  # grass is everywhere at first: the first thing to paint is a path
        _busy["on"] = False
        if self.layer == "COLOUR":                  # show the strokes at once, even before anything is painted
            ob["hrp_painting_colour"] = True
        elif "hrp_painting_colour" in ob:
            del ob["hrp_painting_colour"]
        build.refresh_custom(ob)
        if context.mode != "PAINT_VERTEX":
            bpy.ops.object.mode_set(mode="VERTEX_PAINT")
        layers.set_preview(ob, True)
        _painting.add(ob.name)
        _outline_off(context)
        if not apply_brush(context):
            self.report({"WARNING"}, report("Pick the brush colour by hand: this Blender's brush can't be set"))
        return {"FINISHED"}


class HRP_OT_paint_done(bpy.types.Operator):
    bl_idname = "harappa.paint_done"
    bl_label = "Done Painting"
    bl_description = "Leave paint mode and go back to moving objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        layers.end_previews(context.scene)
        _painting.clear()
        _outline_back()
        _end_colour(context.scene)
        return {"FINISHED"}


class HRP_OT_paint_fill(bpy.types.Operator):
    bl_idname = "harappa.paint_fill"
    bl_label = "Fill Layer"
    bl_description = ("Fill the whole layer with what the brush paints (grass everywhere / flowers everywhere / "
                      "tallest / one colour; with Erase: the opposite)")
    bl_options = {"REGISTER", "UNDO"}
    clear: bpy.props.BoolProperty(name="Clear", default=False, options={"SKIP_SAVE"},
                                  description="Reset the layer to its starting state instead")

    @classmethod
    def description(cls, context, props):
        if props.clear:
            return i18n.t("Reset this layer to its starting state. Other layers are not touched")
        return i18n.t(cls.bl_description)

    @classmethod
    def poll(cls, context):
        return _paint_target(context) is not None

    def execute(self, context):
        s = context.scene.harappa
        ob = _paint_target(context)
        m = "PAINT" if s.paint_mode == "SMOOTH" else s.paint_mode
        if context.mode == "PAINT_VERTEX" and context.active_object == ob:
            # while painting, Blender's own Fill: it goes onto the paint undo stack, so Ctrl+Z takes it back
            # (data written from Python in paint mode would not be undoable)
            layers.ensure(ob.data, s.paint_layer)
            rgb = layers.fill_colour(s.paint_layer, m, tuple(s.paint_colour), self.clear)
            vp = context.tool_settings.vertex_paint
            for holder in (getattr(vp, "unified_paint_settings", None), getattr(vp, "brush", None)):
                try:
                    holder.color = rgb
                except (AttributeError, TypeError):
                    pass
            try:
                bpy.ops.paint.vertex_color_set()
            finally:
                apply_brush(context)                            # the brush back to what it paints
            ob.data.update()
            return {"FINISHED"}
        if self.clear:
            layers.clear(ob, s.paint_layer)
        else:
            layers.fill(ob, s.paint_layer, layers.target(s.paint_layer, m, tuple(s.paint_colour))[0])
        return {"FINISHED"}


class HRP_OT_paint_swatch(bpy.types.Operator):
    bl_idname = "harappa.paint_swatch"
    bl_label = "Use Colour"
    bl_description = "Paint with this colour of the current season"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    key: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        name = ui.SWATCH_NAMES.get(props.key)
        return (i18n.t(name) + ": " if name else "") + i18n.t(cls.bl_description)

    def execute(self, context):
        s = context.scene.harappa
        if hasattr(s, self.key):
            s.paint_colour = tuple(getattr(s, self.key))
            s.paint_mode = "PAINT"
        return {"FINISHED"}


SWATCHES = ("grass_tip", "grass_lit2", "flower_b", "flower_c", "flower_d")


class HRP_OT_ground_finer(bpy.types.Operator):
    bl_idname = "harappa.ground_finer"
    bl_label = "Make Ground Finer"
    bl_description = "Adds more points to the ground so strokes get smooth edges. Your painting is kept"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = meadow_of(context.active_object)
        return ob is not None and not ob.get("hrp_hill")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        ob = meadow_of(context.active_object)
        now, after = len(ob.data.vertices), layers.finer_count(ob)
        col = self.layout.column(align=True)
        layers._spacing.pop(ob.name, None)
        col.label(text=i18n.report(f"Ground points: {now:,} (about {layers.spacing(ob):.2f} m apart)"),
                  translate=False)
        col.label(text=i18n.report(f"After: {after:,} points"), translate=False)
        if after > layers.HEAVY:
            col.label(text=i18n.t("This ground is very large. Painting may be slow"), icon="ERROR", translate=False)

    def execute(self, context):
        ob = meadow_of(context.active_object)
        mode = context.mode
        if mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        n = layers.make_finer(ob)
        if mode == "PAINT_VERTEX":
            bpy.ops.object.mode_set(mode="VERTEX_PAINT")
            apply_brush(context)
        self.report({"WARNING"} if n > layers.HEAVY else {"INFO"}, report(f"Ground now has {n:,} points"))
        return {"FINISHED"}


_painting = set()                      # meadows drawn lighter while they are painted


def _end_colour(scene):
    """Painting is over: a meadow keeps the custom grass material only if it really has a painted colour now."""
    for ob in scene.objects:
        if ob.get("hrp_painting_colour"):
            del ob["hrp_painting_colour"]
            build.refresh_custom(ob)
_outlines = {}                         # 3D views whose selection outline is hidden while painting: pointer -> old value


def _outline_off(context):
    """Every grass blade of the selected meadow gets Blender's orange selection outline, which turns the whole meadow
    orange while it is painted. Hide the outline in this view while painting; Done Painting puts it back."""
    sp = context.space_data
    if sp is None or sp.type != "VIEW_3D":
        return
    if sp.as_pointer() not in _outlines:
        _outlines[sp.as_pointer()] = sp.overlay.show_outline_selected
    sp.overlay.show_outline_selected = False


def _outline_back():
    if not _outlines:
        return
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                for sp in area.spaces:
                    if sp.type == "VIEW_3D" and sp.as_pointer() in _outlines:
                        sp.overlay.show_outline_selected = _outlines[sp.as_pointer()]
    except (AttributeError, ReferenceError):
        pass
    _outlines.clear()


# ---------------------------------------------------------------------------------------------
# avoid objects
# ---------------------------------------------------------------------------------------------
class HRP_OT_avoid_add(bpy.types.Operator):
    bl_idname = "harappa.avoid_add"
    bl_label = "Avoid Selected"
    bl_description = "Grass and flowers will make room for the selected objects (characters, props, buildings)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not avoid.meadows(context.scene):
            cls.poll_message_set(i18n.t("Make a meadow first"))
            return False
        if not context.selected_objects:
            cls.poll_message_set(i18n.t("Select the objects the grass should avoid"))
            return False
        return True

    def execute(self, context):
        scatter.grass_group()                                   # an older file: bring the nodes up first
        scatter.flowers_group()
        added, skipped, heavy = avoid.add(context, list(context.selected_objects))
        col = avoid.current(context.scene)
        msg = report(f"Grass now avoids {len(col.objects) if col else 0} object(s)")
        notes = [f"{name}: {i18n.t(why)}" for name, why in skipped[:2]]
        if heavy and not context.scene.harappa.avoid_box:
            notes.append(i18n.t('This model is heavy. Turn on "Use Simple Box" if the viewport gets slow'))
        # one message: Blender's status bar only shows the last one (the panel keeps the reasons too)
        self.report({"WARNING"} if notes else {"INFO"}, " · ".join([msg] + notes))
        return {"FINISHED"} if added or not skipped else {"CANCELLED"}


class HRP_OT_avoid_remove(bpy.types.Operator):
    bl_idname = "harappa.avoid_remove"
    bl_label = "Stop Avoiding"
    bl_description = "Let grass grow through the selected objects again"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        return i18n.t("Stop avoiding this object") if props.name else i18n.t(cls.bl_description)

    def execute(self, context):
        obs = [bpy.data.objects.get(self.name)] if self.name else list(context.selected_objects)
        n = avoid.remove(context, [o for o in obs if o is not None])
        col = avoid.current(context.scene)
        self.report({"INFO"}, report(f"Grass now avoids {len(col.objects) if col else 0} object(s)"))
        return {"FINISHED"} if n else {"CANCELLED"}


class HRP_OT_avoid_select(bpy.types.Operator):
    bl_idname = "harappa.avoid_select"
    bl_label = "Select"
    bl_description = "Select this object"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        if ob is None:
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------
# blend the user's own models into the meadow
# ---------------------------------------------------------------------------------------------
class HRP_OT_blend_in(bpy.types.Operator):
    bl_idname = "harappa.blend_in"
    bl_label = "Blend Into Meadow"
    bl_description = ("Paint the selected models like the meadow: no black shadows, shadow colours follow the season "
                      "and Look. Their own materials are kept and come back with Original Look")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not blend.targets(context.selected_objects):
            cls.poll_message_set(i18n.t("Select your own models (characters, props, buildings)"))
            return False
        return True

    def execute(self, context):
        done, already = blend.apply(list(context.selected_objects))
        if not done:
            self.report({"INFO"}, report(f"Already blended: {len(already)} object(s)"))
            return {"CANCELLED"}
        self.report({"INFO"}, report(f"Blended {len(done)} object(s) into the meadow"))
        return {"FINISHED"}


class HRP_OT_blend_out(bpy.types.Operator):
    bl_idname = "harappa.blend_out"
    bl_label = "Original Look"
    bl_description = "Give the selected models their own materials back"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(blend.blended(o) or o.get(blend.ADDED) for o in blend.targets(context.selected_objects))

    def execute(self, context):
        done = blend.restore(list(context.selected_objects))
        self.report({"INFO"}, report(f"Restored {len(done)} object(s)"))
        return {"FINISHED"} if done else {"CANCELLED"}


# ---------------------------------------------------------------------------------------------
# this object's colour
# ---------------------------------------------------------------------------------------------
class HRP_OT_tint_reset(bpy.types.Operator):
    bl_idname = "harappa.tint_reset"
    bl_label = "Back to Scene Colours"
    bl_description = "Give the selected objects back the scene's colours (their own colour and shifts are removed)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return look.is_harappa(context.active_object)

    def execute(self, context):
        done = set()
        for ob in {*context.selected_objects, context.active_object}:
            for o in look.targets(ob):
                if o not in done:
                    look.reset(o)
                    done.add(o)
        return {"FINISHED"}


class HRP_OT_tint_copy(bpy.types.Operator):
    bl_idname = "harappa.tint_copy"
    bl_label = "Copy to Selected"
    bl_description = "Give the other selected Harappa objects this object's colour settings"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if look.is_harappa(context.active_object) and len(context.selected_objects) > 1:
            return True
        cls.poll_message_set(i18n.t("Select the other objects too, then this one last"))
        return False

    def execute(self, context):
        src = look.targets(context.active_object)[-1]
        h, s_, v, col, amt = look.user(src)
        n = 0
        for ob in context.selected_objects:
            if ob == context.active_object or not look.is_harappa(ob):
                continue
            for o in look.targets(ob):
                look.set_user(o, h, s_, v, col, amt)
            n += 1
        self.report({"INFO"}, report(f"Colour copied to {n} object(s)"))
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------
# my looks
# ---------------------------------------------------------------------------------------------
def _look_report(op, name, n):
    s = bpy.context.scene.harappa
    se = next(i.name for i in s.bl_rna.properties["season"].enum_items if i.identifier == s.season)
    st = next(i.name for i in s.bl_rna.properties["style"].enum_items if i.identifier == s.style)
    op.report({"INFO"}, report(f"Look applied: {name}") + f" ({i18n.t(se)}, {i18n.t(st)})")
    if n["missing"]:
        op.report({"INFO"}, report(f"{n['missing']} setting(s) not in the look kept their value"))
    if n["unknown"] or n["bad"] or n["clamped"]:
        op.report({"WARNING"}, report(f"Ignored {n['unknown']} unknown and {n['bad']} unreadable setting(s), "
                                      f"limited {n['clamped']} to their range"))


class HRP_OT_look_save(bpy.types.Operator):
    bl_idname = "harappa.look_save"
    bl_label = "Save Look"
    bl_description = "Save the colours, light, sky and paint style of this scene as a look you can use anywhere"
    bl_options = {"REGISTER"}
    name: bpy.props.StringProperty(name="Name", default="My Look", description="Name of the look")
    grass: bpy.props.BoolProperty(name="Grass and Wind Settings", default=False,
                                  description="Also keep the grass, flower and wind settings of the meadow")

    def invoke(self, context, event):
        if not self.properties.is_property_set("name"):
            self.name = context.scene.harappa.look_name or i18n.t("My Look")
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "name", text=i18n.t("Name"), translate=False)
        col.label(text=i18n.t("Colours, light, sky and paint style"), icon="CHECKMARK", translate=False)
        col.prop(self, "grass", text=i18n.t("Grass and Wind Settings"), translate=False)
        col.label(text=i18n.t("Not saved: painting, each object's own colour,"), icon="INFO", translate=False)
        col.label(text=i18n.t("avoided objects"), icon="BLANK1", translate=False)
        if os.path.exists(looks.path_of(self.name.strip() or "Look")):
            col.label(text=i18n.report(f'Replaces the look "{self.name.strip()}"'), icon="ERROR", translate=False)

    def execute(self, context):
        name = self.name.strip()
        if not name:
            self.report({"WARNING"}, report("Give the look a name"))
            return {"CANCELLED"}
        try:
            looks.save(context, name, grass=self.grass)
        except OSError as e:
            self.report({"ERROR"}, f"{e}")
            return {"CANCELLED"}
        context.scene.harappa.look_name = name
        context.scene["hrp_look_fp"] = looks.fingerprint(context)
        self.report({"INFO"}, report(f"Look saved: {name}"))
        return {"FINISHED"}


class HRP_OT_look_apply(bpy.types.Operator):
    bl_idname = "harappa.look_apply"
    bl_label = "Apply Look"
    bl_description = "Put this look on the scene: colours, light, sky and paint style"
    bl_options = {"REGISTER", "UNDO"}
    filepath: bpy.props.StringProperty(subtype="FILE_PATH", options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        try:
            data = looks.read(self.filepath)
        except ValueError as e:
            self.report({"ERROR"}, report(f"Not a look: {e}"))
            return {"CANCELLED"}
        n = looks.apply(context, data)
        _look_report(self, context.scene.harappa.look_name, n)
        return {"FINISHED"}


class HRP_OT_look_season(bpy.types.Operator):
    bl_idname = "harappa.look_season"
    bl_label = "Season Default"
    bl_description = "Back to the colours of the current season and paint style"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.harappa
        _busy["on"] = True
        s.variation = 0
        _busy["on"] = False
        if "hrp_base" in context.scene:
            del context.scene["hrp_base"]
        apply_season(s, context)
        apply_style(s, context)
        return {"FINISHED"}


class HRP_OT_look_delete(bpy.types.Operator):
    bl_idname = "harappa.look_delete"
    bl_label = "Delete Look"
    bl_description = "Delete a saved look. This can't be undone"
    bl_options = {"REGISTER"}
    filepath: bpy.props.StringProperty(subtype="FILE_PATH", options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        name = next((n for n, p in looks.all_looks() if p == self.filepath), os.path.basename(self.filepath))
        try:
            return context.window_manager.invoke_confirm(
                self, event, title=i18n.t("Delete Look"),
                message=i18n.report(f'Delete the look "{name}"? This can\'t be undone'), confirm_text=i18n.t("Delete"))
        except TypeError:
            return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        folder = os.path.realpath(looks.folder())
        p = os.path.realpath(self.filepath)
        if os.path.dirname(p) != folder or not p.endswith(looks.EXT) or not os.path.isfile(p):
            return {"CANCELLED"}
        os.remove(p)
        self.report({"INFO"}, report("Look deleted"))
        return {"FINISHED"}


class HRP_OT_look_import(bpy.types.Operator):
    bl_idname = "harappa.look_import"
    bl_label = "Import Look"
    bl_description = "Add look files someone shared with you to My Looks"
    bl_options = {"REGISTER"}
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    directory: bpy.props.StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        paths = [os.path.join(self.directory, f.name) for f in self.files if f.name] or [self.filepath]
        ok, bad = 0, 0
        for p in paths:
            try:
                data = looks.read(p)
            except ValueError:
                bad += 1
                continue
            name = str(data.get("name") or os.path.basename(p).split(".")[0])[:64]
            if os.path.dirname(os.path.realpath(p)) == os.path.realpath(looks.folder()):
                ok += 1                                      # already in My Looks
                continue
            name = looks.free_name(name)                     # never overwrite a saved look: 'Name (2)'
            data["name"] = name
            with open(looks.path_of(name), "w", encoding="utf-8") as fo:
                json.dump(data, fo, indent=1, ensure_ascii=False)
            ok += 1
        self.report({"WARNING"} if bad else {"INFO"}, report(f"Imported {ok} look(s), skipped {bad}"))
        return {"FINISHED"} if ok else {"CANCELLED"}


class HRP_OT_look_export(bpy.types.Operator):
    bl_idname = "harappa.look_export"
    bl_label = "Export Look"
    bl_description = "Save the scene's look as a file to share"
    bl_options = {"REGISTER"}
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    check_existing: bpy.props.BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        name = context.scene.harappa.look_name or "My Look"
        self.filepath = looks.file_name(name)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        p = self.filepath
        if not p.endswith(".json"):
            p += looks.EXT
        name = context.scene.harappa.look_name or os.path.basename(p).split(".")[0]
        looks.save(context, name, path=p)
        self.report({"INFO"}, report(f"Look saved: {name}"))
        return {"FINISHED"}


class HRP_OT_look_folder(bpy.types.Operator):
    bl_idname = "harappa.look_folder"
    bl_label = "Open Looks Folder"
    bl_description = "Show the folder the looks are kept in (drop shared look files here)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=looks.folder())
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
    HRP_OT_make_foliage, HRP_OT_add_clouds, HRP_OT_add_ridges, HRP_OT_setup_scene, HRP_OT_paint_mask, HRP_OT_shuffle, HRP_OT_reset,
    HRP_OT_revert, HRP_OT_set_enum, HRP_OT_set_detail, HRP_OT_cloud_give_back, HRP_OT_cloud_new_shape,
    HRP_OT_paint_layer, HRP_OT_paint_done, HRP_OT_paint_fill, HRP_OT_paint_swatch, HRP_OT_ground_finer,
    HRP_OT_avoid_add, HRP_OT_avoid_remove, HRP_OT_avoid_select, HRP_OT_blend_in, HRP_OT_blend_out, HRP_OT_tint_reset, HRP_OT_tint_copy,
    HRP_OT_look_save, HRP_OT_look_apply, HRP_OT_look_season, HRP_OT_look_delete, HRP_OT_look_import,
    HRP_OT_look_export, HRP_OT_look_folder,
    HRP_WaterSettings, HRP_RockSettings, HRP_FallSettings, HRP_OT_set_water_enum, HRP_OT_add_pond, HRP_OT_add_stream,
    HRP_OT_add_rock, HRP_OT_add_waterfall, HRP_OT_remove_waterfall, HRP_OT_add_fish, HRP_OT_add_boat,
    HRP_OT_stepping_stones, HRP_OT_rain_here, HRP_OT_freeze_banks, HRP_OT_make_water, HRP_OT_drop_stream,
    HRP_OT_remove_water,
)


_sky_seen = {}


@bpy.app.handlers.persistent
def _follow_camera(scene, _depsgraph=None):
    """Keep the sky gradient fitted to the camera when the user moves it, changes the lens or the format."""
    _paint_watch()
    try:
        avoid.prune(scene)
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    try:
        hscene.aim_view(scene, _depsgraph)                 # the clouds' painter's light, whatever the world
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
    """A newly opened file has its own cameras: fit its skies afresh. Bring its objects' colours up to date and
    give back the full grass of a meadow that was saved while it was being painted."""
    _sky_seen.clear()
    _painting.clear()
    try:
        upgrade_groups()
        look.migrate()
        layers.end_previews()
    except (AttributeError, ReferenceError, RuntimeError):
        pass


def upgrade_groups():
    """Bring the file's Geometry Nodes groups up to this version as soon as it is opened, so an older meadow can be
    painted and avoid things right away (the rebuild keeps every value a user set, new inputs get their defaults)."""
    names = {scatter.GRASS, scatter.FLOWERS, scatter.FOLIAGE, scatter.WIND}
    if any(ng.name in names and ng.get("hrp_ver") != scatter.GN_VER for ng in bpy.data.node_groups):
        scatter.wind_group()
        for name, make in ((scatter.GRASS, scatter.grass_group), (scatter.FLOWERS, scatter.flowers_group),
                           (scatter.FOLIAGE, scatter.foliage_group)):
            if bpy.data.node_groups.get(name) is not None:
                make()


def _paint_watch():
    """Painting ended some other way than Done Painting (Tab, the mode menu): give the grass back."""
    if not _painting:
        return
    try:
        if bpy.context.mode == "PAINT_VERTEX":
            return
    except AttributeError:
        return
    names = list(_painting)
    _painting.clear()
    _outline_back()
    try:
        _end_colour(bpy.context.scene)
    except AttributeError:
        pass
    for name in names:
        ob = bpy.data.objects.get(name)
        if ob is not None:
            layers.set_preview(ob, False)


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
    for h in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        if _follow_camera in h:
            h.remove(_follow_camera)
    if _forget_cameras in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_forget_cameras)
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
