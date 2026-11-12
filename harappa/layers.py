# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Brush layers: what the user paints on a meadow, one point colour attribute per layer.

The panel paints them with Blender's own Vertex Paint; the agent CLI and the Fill / Clear buttons write them with
the functions here. Both mean the same: Paint moves a layer towards its 'paint' value, Erase towards its 'erase'
value (the Colour layer erases its alpha, i.e. its amount). A layer that does not exist changes nothing, so a
meadow made before the layers existed looks the same; Make Meadow, seasons, Shuffle and Reset never write them.
"""
import bmesh
import bpy
import numpy as np

from . import scatter

# key: (attribute, starting value, paint value, erase value). Values are linear RGBA.
LAYERS = {
    "GRASS": (scatter.MASK_ATTR, (1.0, 1.0, 1.0, 1.0), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0)),
    "FLOWERS": (scatter.FLOWERS_ATTR, (0.5, 0.5, 0.5, 1.0), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0)),
    "HEIGHT": (scatter.HEIGHT_ATTR, (0.5, 0.5, 0.5, 1.0), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0)),
    "COLOUR": (scatter.TINT_ATTR, (1.0, 1.0, 1.0, 0.0), None, None),     # paint = the chosen colour, alpha 1
}
PREVIEW = 0.3                 # share of the grass drawn in the viewport while painting
HEAVY = 1_000_000             # ground points above which painting gets slow
MIN_TINT = 0.002


def attr_name(layer):
    return LAYERS[layer][0]


def ensure(me, layer):
    """The layer's attribute, created at its starting value (= no change) when missing."""
    name, start = LAYERS[layer][:2]
    at = me.color_attributes.get(name)
    if at is not None and (at.domain != "POINT" or at.data_type != "FLOAT_COLOR"):
        me.color_attributes.remove(at)                   # a stray attribute of that name the layer cannot use
        at = None
    if at is None:
        at = me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
        at.data.foreach_set("color", list(start) * len(me.vertices))
    return at


def target(layer, mode, colour=(1.0, 1.0, 1.0)):
    """(RGBA the brush moves towards, blend mode) for Paint / Erase on a layer."""
    if layer == "COLOUR":
        colour = tuple(min(max(c, MIN_TINT), 1.0 - MIN_TINT) for c in colour[:3])   # pure black / white = none
        if mode == "ERASE":
            return (*colour, 0.0), "ERASE_ALPHA"
        return (*colour, 1.0), "MIX"
    _n, _s, paint, erase = LAYERS[layer]
    return (paint if mode != "ERASE" else erase), "MIX"


def _read(at, n):
    vals = np.empty(n * 4, dtype=np.float32)
    at.data.foreach_get("color", vals)
    return vals.reshape(n, 4)


def fill(ob, layer, rgba):
    me = ob.data
    at = ensure(me, layer)
    n = len(me.vertices)
    if layer == "COLOUR" and rgba[3] <= 0.0:              # erase everything = keep the colour, amount 0
        vals = _read(at, n)
        vals[:, 3] = 0.0
    else:
        vals = np.tile(np.asarray(rgba, dtype=np.float32), (n, 1))
    at.data.foreach_set("color", vals.ravel())
    me.update()
    ob.update_tag()


def clear(ob, layer):
    fill(ob, layer, LAYERS[layer][1])


def fill_colour(layer, mode, colour=(1.0, 1.0, 1.0), clear_=False):
    """The RGB Blender's own Fill (paint.vertex_color_set, always alpha 1) needs for a Fill or Clear of a layer.
    The Colour layer's 'none' is pure white, so clearing it that way equals its starting state."""
    if clear_:
        return LAYERS[layer][1][:3]
    if layer == "COLOUR" and mode == "ERASE":
        return (1.0, 1.0, 1.0)
    return target(layer, mode, colour)[0][:3]


def paint_disc(ob, layer, centre, radius, rgba, strength=1.0, soft=0.35):
    """Paint a round spot (world X, Y and radius) the way one dab of the brush would: the layer moves towards rgba
    by strength, fading out over the outer 'soft' share of the radius. For the Colour layer an rgba alpha of 0
    erases the amount only. Returns the number of points it changed."""
    me = ob.data
    at = ensure(me, layer)
    n = len(me.vertices)
    vals = _read(at, n)
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    mw = np.array(ob.matrix_world, dtype=np.float64)
    wp = co @ mw[:3, :3].T + mw[:3, 3]
    d = np.hypot(wp[:, 0] - centre[0], wp[:, 1] - centre[1])
    inner = radius * (1.0 - soft)
    w = np.clip((radius - d) / max(radius - inner, 1e-9), 0.0, 1.0)
    w = (w * w * (3.0 - 2.0 * w) * strength).astype(np.float32)          # smooth edge
    if layer == "COLOUR" and rgba[3] <= 0.0:
        vals[:, 3] -= vals[:, 3] * w
    else:
        vals += (np.asarray(rgba, dtype=np.float32) - vals) * w[:, None]
    at.data.foreach_set("color", vals.ravel())
    me.update()
    ob.update_tag()
    return int((w > 0).sum())


def painted(ob):
    """Layers on this meadow that hold something else than their starting value."""
    out = []
    me = ob.data
    for key, (name, start, *_r) in LAYERS.items():
        at = me.color_attributes.get(name)
        if at is None or at.domain != "POINT" or at.data_type != "FLOAT_COLOR":
            continue
        vals = _read(at, len(me.vertices))
        if not len(vals):
            continue
        if key == "COLOUR":                     # some amount, on a colour that is not the 'none' white / black
            s = vals[:, :3].sum(axis=1)
            if ((vals[:, 3] > 1e-3) & (s > 1e-3) & (s < 2.9995)).any():
                out.append(key)
        elif np.abs(vals[:, 0] - start[0]).max() > 1e-3:
            out.append(key)
    return out


# --------------------------------------------------------------------------------------------------
# the viewport while painting
# --------------------------------------------------------------------------------------------------
def _meadow_mods(ob):
    from . import build
    return [m for m in ob.modifiers if m.type == "NODES" and m.name in (build.GRASS_MOD, build.FLOWER_MOD)
            and m.node_group is not None]


def set_preview(ob, on):
    """Lighter grass and flowers in the viewport (never in renders) while this meadow is painted."""
    from .util import mod_input
    for m in _meadow_mods(ob):
        try:
            if abs(float(mod_input(m, "Preview Factor")) - (PREVIEW if on else 1.0)) > 1e-6:
                mod_input(m, "Preview Factor", PREVIEW if on else 1.0)
        except KeyError:
            continue                                    # a meadow from before this input existed
    if on:
        ob["hrp_preview"] = True
    elif "hrp_preview" in ob:
        del ob["hrp_preview"]
    ob.update_tag()


def end_previews(scene=None):
    """Give every meadow its full grass back (after painting, or a file saved while painting)."""
    obs = scene.objects if scene is not None else bpy.data.objects
    for ob in obs:
        if ob.get("hrp_preview"):
            set_preview(ob, False)


# --------------------------------------------------------------------------------------------------
# ground resolution
# --------------------------------------------------------------------------------------------------
_spacing = {}


def spacing(ob):
    """Average edge length in metres (world scale), cached per mesh state (the panel asks on every redraw)."""
    me = ob.data
    key = (me.as_pointer(), len(me.vertices), len(me.edges), tuple(round(x, 4) for x in ob.matrix_world.to_scale()))
    hit = _spacing.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    if not me.edges:
        return 0.0
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    ev = np.empty(len(me.edges) * 2, dtype=np.int32)
    me.edges.foreach_get("vertices", ev)
    co = co.reshape(-1, 3) * np.array(ob.matrix_world.to_scale(), dtype=np.float32)
    ev = ev.reshape(-1, 2)
    val = float(np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1).mean())
    _spacing[ob.name] = (key, val)
    return val


def finer_count(ob):
    """Points after one subdivision (each edge split once, quads get a centre point)."""
    me = ob.data
    quads = sum(1 for p in me.polygons if len(p.vertices) == 4)
    ngons = sum(1 for p in me.polygons if len(p.vertices) > 4)
    return len(me.vertices) + len(me.edges) + quads + ngons


def make_finer(ob):
    """Subdivide the ground once without changing its shape; every painted layer is carried over."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True, smooth=0.0)
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob.update_tag()
    return len(me.vertices)
