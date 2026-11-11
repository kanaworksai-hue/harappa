# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn objects into an anime meadow: grass + flowers on a ground mesh."""
import bpy

from . import scatter, shading, tree
from .util import mod_input

GRASS_MOD = "Harappa Grass"
FLOWER_MOD = "Harappa Flowers"


def ensure_mask(me, name=scatter.MASK_ATTR, value=1.0):
    """Point colour attribute, white = grass. Created full so grass grows everywhere at first."""
    attr = me.color_attributes.get(name)
    if attr is None:
        attr = me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
        vals = [value, value, value, 1.0] * len(me.vertices)
        attr.data.foreach_set("color", vals)
    try:
        me.color_attributes.active_color = attr
    except (AttributeError, TypeError):
        pass
    return attr


def ground_area(ob):
    me = ob.data
    s = ob.matrix_world.to_scale()
    k = abs(s.x * s.y)
    return sum(p.area for p in me.polygons) * k


def make_meadow(context, ob, density=40.0, height=0.35, flowers=True, max_tufts=250000, seed=0):
    scene = context.scene
    me = ob.data
    ensure_mask(me)
    gm = shading.ground_material()
    if not me.materials:
        me.materials.append(gm)
    else:
        if "hrp_prev_mats" not in ob:
            ob["hrp_prev_mats"] = [m.name if m else "" for m in me.materials]
        for i in range(len(me.materials)):
            me.materials[i] = gm
    area = max(ground_area(ob), 1e-4)
    dens = min(density, max_tufts / area)
    tuft = tree.tuft_object(scene)
    mod = ob.modifiers.get(GRASS_MOD)
    if mod is None:
        mod = ob.modifiers.new(GRASS_MOD, "NODES")
    mod.node_group = scatter.grass_group()
    mod_input(mod, "Tuft", tuft)
    mod_input(mod, "Density", dens)
    mod_input(mod, "Height", height)
    mod_input(mod, "Seed", seed)
    if flowers:
        card = tree.card_object(scene, "flower")
        fm = ob.modifiers.get(FLOWER_MOD)
        if fm is None:
            fm = ob.modifiers.new(FLOWER_MOD, "NODES")
        fm.node_group = scatter.flowers_group()
        mod_input(fm, "Card", card)
        mod_input(fm, "Height", height * 0.85)
        mod_input(fm, "Size", height * 0.26)
        mod_input(fm, "Seed", seed)
    # the ground (and its grass instances) receive shadows but don't cast them: faster, cleaner
    ob.visible_shadow = False
    ob["hrp_ground"] = True
    ob["hrp_size"] = float(max(ob.dimensions.x, ob.dimensions.y, 1.0))     # the cloud shadows' scale
    return mod
