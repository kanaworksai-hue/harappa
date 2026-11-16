# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Toon water: ponds (closed curves) and streams (open curves) that carve their own bed into the meadow.

* Each water body is a curve object with the "Harappa Water" modifier (HRP Water Surface): it turns the curve
  into a flat pond surface or a ribbon that follows the stream, and stores what the shader and the carve need
  (distance to the shore, normalised depth, flow coordinates, scene time).
* Every meadow gets "Harappa Water Carve" (HRP Water Carve) as its FIRST modifier. It reads the whole
  "Harappa Water" collection, digs a smooth bed under each water body, raises a low bank where the ground is
  lower than the water (so a pond on a slope still holds water) and fades the grass mask out over the bank, so
  grass, flowers and the dirt colour of the ground all step back from the water by themselves.
* Water never reads the ground (the depth is a profile, not a raycast), so there is no dependency cycle.
* Everything moves with Scene Time: scrub the timeline, render any frame, no simulation cache.
"""
import math
import random

import bpy

from .util import G, fresh_group, iface, menu, mod_input, only, sock
from . import shading

WATER_VER = 72
SURFACE = "HRP Water Surface"
CARVE = "HRP Water Carve"
MAT_WATER = "HRP Water"
SURFACE_MOD = "Harappa Water"
CARVE_MOD = "Harappa Water Carve"
COLLECTION = "Harappa Water"
STREAMS = "Harappa Water Streams"          # child of COLLECTION: ponds read it to clear their foam at stream mouths
TIME = "HRP Water Time"
MASK_ATTR = "hrp_grass"


# what is in the water decides its colour: clear deep water is blue, glacier flour makes it milky turquoise,
# algae green, tannin from leaves tea-brown.  (name, description, hue shift, saturation, brightness, clarity)
WATER_TYPES = {
    # name, description, clarity, (shallow, mid, deep) or None = the season's own water colours
    "SEASON": ("Season Colours", "The water colours of the current season", 0.0, None),
    "CLEAR": ("Clear Blue Lake", "Clear, deep blue water with a bright sandy shelf", 0.6,
              ("#D6E2A8", "#2C9FD6", "#24609A")),
    "LOTUS": ("Lotus Pond", "Calm green water, a little cloudy: lily pads love it", -0.35,
              ("#B6D68E", "#6FA25A", "#3D6C46")),
    "GLACIER": ("Glacier Lake", "Milky turquoise water full of fine rock flour", -0.25,
                ("#C4F0EA", "#7FD3D6", "#4FAFC0")),
    "STREAM": ("Mountain Stream", "Cold, glass-clear water: you see the bottom", 0.9,
               ("#DAF4DE", "#86D0BE", "#3F8E96")),
    "TEA": ("Tea-Brown Marsh", "Water stained brown by fallen leaves", -0.3, ("#E0B878", "#B07E3C", "#6E4622")),
}
LILY_COVER = {"SEASON": 0.6, "CLEAR": 0.4, "LOTUS": 1.0, "GLACIER": 0.0, "STREAM": 0.0, "TEA": 0.6}
SUMMER_MID = "#3A97B8"                    # type colours are relative to this, so seasons and night still apply
WATER_KEYS = ("hrp_hue", "hrp_sat", "hrp_val", "hrp_clarity")


# ----------------------------------------------------------------------------------------------
# small GN helpers
# ----------------------------------------------------------------------------------------------
def _named(g, x, y, name, dtype="FLOAT"):
    n = g.n("GeometryNodeInputNamedAttribute", x, y, data_type=dtype)
    n.inputs["Name"].default_value = name
    return n


def _store(g, x, y, geo, name, value, dtype="FLOAT", domain="POINT"):
    st = g.n("GeometryNodeStoreNamedAttribute", x, y, data_type=dtype, domain=domain)
    g.links.new(geo, st.inputs["Geometry"])
    st.inputs["Name"].default_value = name
    kind = {"FLOAT": "VALUE", "FLOAT_VECTOR": "VECTOR", "INT": "INT", "FLOAT_COLOR": "RGBA"}[dtype]
    sock = g.inp(st, "Value", kind)
    if isinstance(value, bpy.types.NodeSocket):
        g.links.new(value, sock)
    else:
        sock.default_value = value
    return only(st.outputs)


def _top_only(realize):
    """Realize the water objects themselves, not what they carry (lily pads, reeds, koi stay instances and are left
    out): the carve and the stream mouths only need the surfaces, and realizing every pad each frame is slow."""
    sock(realize.inputs, "Realize All").default_value = False
    sock(realize.inputs, "Depth").default_value = 2                   # the collection, its objects' surfaces


def _xyz(g, x, y, vec):
    sep = g.n("ShaderNodeSeparateXYZ", x, y)
    g.links.new(vec, sock(sep.inputs, "Vector"))
    return sep


def _flat(g, x, y, vec):
    """(x, y, 0) of a vector field."""
    sep = _xyz(g, x, y, vec)
    c = g.n("ShaderNodeCombineXYZ", x + 160, y)
    g.link(sep, "X", c, "X")
    g.link(sep, "Y", c, "Y")
    return only(c.outputs)


def _smooth(g, x, y, v, a, b, lo=0.0, hi=1.0):
    return g.out(g.maprange(x, y, v, a, b, lo, hi, smooth=True), "Result")


def _switch(g, x, y, kind, cond, a_false, b_true):
    sw = g.n("GeometryNodeSwitch", x, y, input_type=kind)
    g.links.new(cond, sw.inputs["Switch"])
    for name, v in (("False", a_false), ("True", b_true)):
        s = sw.inputs[name]
        if isinstance(v, bpy.types.NodeSocket):
            g.links.new(v, s)
        else:
            s.default_value = v
    return only(sw.outputs)


# ----------------------------------------------------------------------------------------------
# water surface: curve -> pond / stream mesh
# ----------------------------------------------------------------------------------------------
def surface_group():
    ng, rebuilt = fresh_group(SURFACE, "GeometryNodeTree", WATER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Width", "INPUT", "NodeSocketFloat", 1.4, 0.05, 100.0, "Stream width in metres", "DISTANCE")
    iface(ng, "Depth", "INPUT", "NodeSocketFloat", 0.6, 0.02, 50.0, "Deepest point below the water line",
          "DISTANCE")
    iface(ng, "Shelf", "INPUT", "NodeSocketFloat", 0.9, 0.05, 50.0,
          "How far from the shore the bed reaches full depth", "DISTANCE")
    iface(ng, "Flow Speed", "INPUT", "NodeSocketFloat", 0.6, 0.0, 20.0, "Streams: metres per second")
    iface(ng, "Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Streams", "INPUT", "NodeSocketCollection", desc="Streams that may flow into this pond")
    iface(ng, "Outlet", "INPUT", "NodeSocketFloat", 0.0, 0.0, 1.0,
          "1 = the stream leaves a pond: a funnel, wide at the pond, narrowing into the channel (0 = a spring)",
          "FACTOR")
    iface(ng, "Mouth", "INPUT", "NodeSocketFloat", 0.0, 0.0, 1.0, "1 = the stream runs into a pond: its mouth opens out",
          "FACTOR")
    iface(ng, "Obstacles", "INPUT", "NodeSocketCollection",
          desc="Rocks standing in the water get a foam collar (Harappa Props)")
    iface(ng, "Outflow Point", "INPUT", "NodeSocketVector",
          desc="Where the stream leaves its pond (object space, set by Drop Onto Meadow)")
    iface(ng, "Inflow Point", "INPUT", "NodeSocketVector",
          desc="Where the stream runs into a pond (object space, set by Drop Onto Meadow)")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1800, 0)
    go = g.n("NodeGroupOutput", 2200, 0)

    res = g.n("GeometryNodeResampleCurve", -1600, 0)
    menu(res.inputs["Mode"], "Length")
    rlen = g.math("MAXIMUM", -1750, 100, only(g.math("DIVIDE", -1850, 100, g.out(g.n("GeometryNodeSplineLength", -2000, 100),
                  "Length"), 400.0).outputs), 0.12)        # 12 cm, coarser only on very long curves (fast big ponds)
    g.link(rlen, 0, res, "Length")
    g.link(gi, "Geometry", res, "Curve")
    cyc = g.n("GeometryNodeInputSplineCyclic", -1600, -250)
    sep = g.n("GeometryNodeSeparateGeometry", -1400, 0, domain="CURVE")
    g.link(res, 0, sep, "Geometry")
    g.link(cyc, 0, sep, "Selection")
    pond_c, stream_c = g.out(sep, "Selection"), g.out(sep, "Inverted")

    # ---- pond: flat at the mean height of its outline
    pos = g.n("GeometryNodeInputPosition", -1400, -400)
    pz = _xyz(g, -1250, -400, only(pos.outputs))
    st = g.n("GeometryNodeAttributeStatistic", -1050, -300, data_type="FLOAT", domain="POINT")
    g.links.new(pond_c, st.inputs["Geometry"])
    g.link(pz, "Z", st, "Attribute")
    lvl = g.out(st, "Mean")
    flatp = g.n("ShaderNodeCombineXYZ", -850, -450)
    g.link(pz, "X", flatp, "X")
    g.link(pz, "Y", flatp, "Y")
    g.links.new(lvl, flatp.inputs["Z"])
    sp = g.n("GeometryNodeSetPosition", -850, -250)
    g.links.new(pond_c, sp.inputs["Geometry"])
    g.link(flatp, 0, sp, "Position")
    fill = g.n("GeometryNodeFillCurve", -650, -250)
    g.link(sp, 0, fill, "Curve")
    menu(fill.inputs["Mode"], "Triangles")
    lift = g.n("GeometryNodeSetPosition", -550, -150)                # Fill Curve drops Z: put it back on the level
    g.link(fill, 0, lift, "Geometry")
    lofs = g.n("ShaderNodeCombineXYZ", -700, -50)
    g.links.new(lvl, lofs.inputs["Z"])
    g.link(lofs, 0, lift, "Offset")
    sub = g.n("GeometryNodeSubdivideMesh", -450, -250)
    g.link(lift, 0, sub, "Mesh")
    per = g.n("GeometryNodeAttributeStatistic", -650, -650, data_type="FLOAT", domain="CURVE")   # pond outline length
    g.links.new(pond_c, per.inputs["Geometry"])
    g.link(g.n("GeometryNodeSplineLength", -800, -700), "Length", per, "Attribute")
    lvl_ = g.math("SUBTRACT", -500, -650, 3.0, only(g.math("ADD", -560, -700, only(g.math("GREATER_THAN", -620, -680,
                  g.out(per, "Sum"), 45.0).outputs), only(g.math("GREATER_THAN", -620, -740, g.out(per, "Sum"),
                  100.0).outputs)).outputs))          # level 3 for garden ponds, 2 and 1 for lakes
    g.link(lvl_, 0, sub, "Level")
    outline = g.n("GeometryNodeCurveToMesh", -650, -500)
    g.link(sp, 0, outline, "Curve")
    prox = g.n("GeometryNodeProximity", -250, -450, target_element="EDGES")
    g.link(outline, 0, prox, "Geometry")
    pshore = _store(g, -50, -250, g.out(sub, 0), "hrp_shore", g.out(prox, "Distance"))
    pflow = _store(g, 150, -250, pshore, "hrp_flow", 0.0)
    pflow = _store(g, 250, -250, pflow, "hrp_end", 999.0)
    # stream mouths: no shore foam where a stream ribbon runs into the pond
    sci = g.n("GeometryNodeCollectionInfo", -650, -800, transform_space="RELATIVE")
    g.link(gi, "Streams", sci, "Collection")
    sreal0 = g.n("GeometryNodeRealizeInstances", -550, -800)
    _top_only(sreal0)
    g.link(sci, 0, sreal0, "Geometry")
    sreal = g.n("GeometryNodeSeparateGeometry", -450, -800, domain="FACE")
    g.link(sreal0, 0, sreal, "Geometry")
    g.link(_named(g, -600, -900, "hrp_carve", "FLOAT_VECTOR"), "Exists", sreal, "Selection")
    spos = g.n("GeometryNodeInputPosition", -450, -950)
    sflat = g.n("GeometryNodeSetPosition", -300, -800)
    g.link(sreal, "Selection", sflat, "Geometry")
    g.links.new(_flat(g, -400, -1050, only(spos.outputs)), sflat.inputs["Position"])
    ssize = g.n("GeometryNodeAttributeDomainSize", -150, -950, component="MESH")
    g.link(sflat, 0, ssize, "Geometry")
    shas = g.n("FunctionNodeCompare", 0, -950, data_type="INT", operation="GREATER_THAN")
    g.link(ssize, "Face Count", shas, "A", bkind="INT")
    g.inp(shas, "B", "INT").default_value = 0
    ppos = g.n("GeometryNodeInputPosition", -150, -1150)
    mprox = g.n("GeometryNodeProximity", 0, -800, target_element="FACES")
    g.link(sflat, 0, mprox, "Geometry")
    g.links.new(_flat(g, -100, -1250, only(ppos.outputs)), mprox.inputs["Sample Position"])
    mfade = _smooth(g, 150, -800, g.out(mprox, "Distance"), 0.15, 2.4)     # (pads keep clear of the inflow too)
    mfade = _switch(g, 300, -850, "FLOAT", g.out(shas, 0), 1.0, mfade)
    pflow = _store(g, 400, -250, pflow, "hrp_mouth", mfade)

    # ---- stream: a flat ribbon along the curve, U = metres along, V = 0..1 across
    nrm = g.n("GeometryNodeSetCurveNormal", -1200, 300)
    g.links.new(stream_c, nrm.inputs["Curve"])
    menu(nrm.inputs["Mode"], "Z Up", "Minimum Twist")
    spl = g.n("GeometryNodeSplineParameter", -1200, 450)
    su = _store(g, -1000, 300, only(nrm.outputs), "hrp_u", g.out(spl, "Length"))
    slen = g.n("GeometryNodeSplineLength", -1200, 900)
    to_end = g.math("SUBTRACT", -1050, 900, g.out(slen, "Length"), g.out(spl, "Length"))
    su = _store(g, -900, 300, su, "hrp_end", g.out(to_end, 0))
    # where the ribbon crosses the shores (found by Settle): the funnel, the mouth and the colour hand-over are measured
    # from there, so they sit on the shore however far into the pond the curve starts or ends
    cpts = g.n("GeometryNodeCurveToPoints", -1550, 1600)             # (Sample Nearest takes points, not curves)
    menu(cpts.inputs["Mode"], "Evaluated") if "Mode" in cpts.inputs else setattr(cpts, "mode", "EVALUATED")
    g.links.new(su, cpts.inputs["Curve"])
    cflat = g.n("GeometryNodeSetPosition", -1450, 1600)             # matched in plan only: the stream's height
    g.link(cpts, "Points", cflat, "Geometry")                          # changes after Settle measured the shore
    g.links.new(_flat(g, -1600, 1450, g.out(g.n("GeometryNodeInputPosition", -1750, 1450), 0)),
                cflat.inputs["Position"])
    def cross_u(sock_name, x, y, fallback):
        sn = g.n("GeometryNodeSampleNearest", x, y, domain="POINT")
        g.link(cflat, 0, sn, "Geometry")
        g.links.new(_flat(g, x - 200, y - 100, g.out(gi, sock_name)), sn.inputs["Sample Position"])
        si = g.n("GeometryNodeSampleIndex", x + 150, y, data_type="FLOAT", domain="POINT")
        g.link(cpts, "Points", si, "Geometry")
        g.link(_named(g, x, y - 150, "hrp_u"), "Attribute", si, "Value")
        g.link(sn, "Index", si, "Index")
        on = g.math("GREATER_THAN", x + 150, y - 150, g.out(gi, "Outlet" if sock_name == "Outflow Point" else "Mouth"), 0.5)
        return _switch(g, x + 300, y, "FLOAT", g.out(on, 0), fallback, g.out(si, "Value", "VALUE"))
    exit_u = cross_u("Outflow Point", -1400, 1500, 0.0)
    entry_u = cross_u("Inflow Point", -1400, 1750, g.out(slen, "Length"))
    from_exit = only(g.math("SUBTRACT", -1250, 1500, g.out(spl, "Length"), exit_u).outputs)
    to_entry = only(g.math("SUBTRACT", -1250, 1750, entry_u, g.out(spl, "Length")).outputs)
    # the hand-overs scale with how much stream shows between the shores: a short link between two ponds still flows
    vis = only(g.math("MAXIMUM", -1250, 1900, only(g.math("SUBTRACT", -1350, 1900, entry_u, exit_u).outputs), 0.5).outputs)
    def fit(k, cap):
        return only(g.math("MINIMUM", -1150, 1950, only(g.math("MULTIPLY", -1250, 1950, vis, k).outputs), cap).outputs)
    su = _store(g, -880, 300, su, "hrp_fx", from_exit)
    su = _store(g, -860, 300, su, "hrp_te", to_entry)
    # width: a narrow source widening over two widths, then a slow natural swell and pinch
    w2 = g.math("MULTIPLY", -1200, 1100, g.out(gi, "Width"), 2.0)
    taper = _smooth(g, -1050, 1100, g.out(spl, "Length"), 0.0, g.out(w2, 0), 0.35, 1.0)       # a spring: narrow start
    # out of a pond the water converges on the outlet: a funnel, wide at the pond, narrowing into the channel
    w25 = g.math("MULTIPLY", -1200, 1200, g.out(gi, "Width"), 2.5)
    flare = _smooth(g, -1050, 1200, from_exit, 0.0, fit(0.55, g.out(w25, 0)), 1.4, 1.0)
    taper = g.mixout(g.mix(-950, 1150, "MIX", "FLOAT", fac=g.out(gi, "Outlet"), a=taper, b=flare))
    # ...and where it runs into a pond its mouth opens out
    mo_ = _smooth(g, -1050, 1000, to_entry, 0.0, fit(0.45, g.out(w2, 0)), 1.3, 1.0)
    mo_ = g.math("MULTIPLY_ADD", -900, 1000, only(g.math("SUBTRACT", -950, 950, mo_, 1.0).outputs), g.out(gi, "Mouth"), 1.0)
    taper = only(g.math("MULTIPLY", -850, 1100, taper, g.out(mo_, 0)).outputs)
    wv = g.n("ShaderNodeCombineXYZ", -1050, 1300)
    g.link(g.math("MULTIPLY", -1200, 1300, g.out(spl, "Length"), 0.16), 0, wv, "X")
    wn_ = g.n("ShaderNodeTexNoise", -900, 1300, noise_dimensions="2D")
    g.set(wn_, "Detail", 1.0)
    g.set(wn_, "Scale", 1.5)                                         # a 4-5 m swell, not a pinch every metre
    g.link(wv, 0, wn_, "Vector")
    swell = g.out(g.maprange(-750, 1300, g.out(wn_, "Fac"), 0.3, 0.7, 0.75, 1.25), "Result")
    ws = g.math("MULTIPLY", -600, 1150, taper, swell)
    su = _store(g, -750, 300, su, "hrp_ws", g.out(ws, 0))
    hw = g.math("MULTIPLY", -1200, 650, g.out(gi, "Width"), 0.5)
    nhw = g.math("MULTIPLY", -1050, 650, g.out(gi, "Width"), -0.5)
    a = g.n("ShaderNodeCombineXYZ", -900, 700)
    g.link(nhw, 0, a, "X")
    b = g.n("ShaderNodeCombineXYZ", -900, 600)
    g.link(hw, 0, b, "X")
    line = g.n("GeometryNodeCurvePrimitiveLine", -750, 650)
    g.link(a, 0, line, "Start")
    g.link(b, 0, line, "End")
    lres = g.n("GeometryNodeResampleCurve", -600, 650)
    menu(lres.inputs["Mode"], "Count")
    lres.inputs["Count"].default_value = 9
    g.link(line, 0, lres, "Curve")
    spl2 = g.n("GeometryNodeSplineParameter", -600, 800)
    sv = _store(g, -450, 650, only(lres.outputs), "hrp_v", g.out(spl2, "Factor"))
    c2m = g.n("GeometryNodeCurveToMesh", -250, 400)
    tan = g.n("GeometryNodeInputTangent", -700, 150)
    side = g.vmath("CROSS_PRODUCT", -550, 150, g.out(tan, 0), (0.0, 0.0, 1.0))
    side = g.vmath("NORMALIZE", -450, 150, only(side.outputs))
    wv2 = g.n("ShaderNodeCombineXYZ", -700, 0)
    g.link(_named(g, -850, 0, "hrp_u"), "Attribute", wv2, "X")
    wv2.inputs["Y"].default_value = 3.7
    wn2 = g.n("ShaderNodeTexNoise", -550, 0, noise_dimensions="2D")
    g.set(wn2, "Scale", 0.13)
    g.set(wn2, "Detail", 1.0)
    g.link(wv2, 0, wn2, "Vector")
    wob2 = g.math("MULTIPLY_ADD", -400, 0, g.out(wn2, "Fac"), 2.0, -1.0)
    amp = g.math("MULTIPLY", -400, -100, g.out(gi, "Width"), 0.22)
    wob2 = g.math("MULTIPLY", -300, 0, g.out(wob2, 0), g.out(amp, 0))
    wob2 = g.math("MULTIPLY", -250, -50, g.out(wob2, 0), g.out(_named(g, -400, -200, "hrp_ws"), "Attribute"))
    offs = g.vmath("SCALE", -200, 100, only(side.outputs), scale=g.out(wob2, 0))
    wander = g.n("GeometryNodeSetPosition", -150, 300)
    g.links.new(su, wander.inputs["Geometry"])
    g.link(offs, 0, wander, "Offset")
    su = only(wander.outputs)
    g.links.new(su, c2m.inputs["Curve"])
    g.links.new(sv, c2m.inputs["Profile Curve"])
    g.link(_named(g, -450, 450, "hrp_ws"), "Attribute", c2m, "Scale")
    vv = _named(g, -250, 650, "hrp_v")
    d05 = g.math("SUBTRACT", -100, 650, g.out(vv, "Attribute"), 0.5)
    ab = g.math("ABSOLUTE", 50, 650, g.out(d05, 0))
    edge = g.math("SUBTRACT", 200, 650, 0.5, g.out(ab, 0))
    sdist = g.math("MULTIPLY", 350, 650, g.out(edge, 0), g.out(gi, "Width"))
    sdist = g.math("MULTIPLY", 450, 750, g.out(sdist, 0), g.out(_named(g, 300, 850, "hrp_ws"), "Attribute"))
    # past the shore the ribbon only has to tuck under the pond a little: further in it would show through it
    tuck = g.math("MINIMUM", -100, 300, g.out(_named(g, -250, 250, "hrp_fx"), "Attribute"),
                  g.out(_named(g, -250, 200, "hrp_te"), "Attribute"))
    cut = g.n("GeometryNodeDeleteGeometry", -50, 400, domain="FACE")
    g.link(c2m, 0, cut, "Geometry")
    g.link(g.math("LESS_THAN", 0, 300, g.out(tuck, 0), -0.5), 0, cut, "Selection")
    sshore = _store(g, 0, 400, g.out(cut, 0), "hrp_shore", g.out(sdist, 0))
    sflow = _store(g, 200, 400, sshore, "hrp_flow", 1.0)
    # a stream that leaves a pond: its first metres are the pond's water turning into a stream (no hard start)
    ostart = _smooth(g, 150, 550, g.out(_named(g, 0, 550, "hrp_fx"), "Attribute"), 0.0, fit(0.22, 1.8))
    ostart = g.math("MULTIPLY_ADD", 250, 550, only(g.math("SUBTRACT", 200, 500, ostart, 1.0).outputs), g.out(gi, "Outlet"),
                    1.0)
    # ...and one that runs into a pond turns into the pond's water over its last metres (same depth colour, its
    # lines and foam fading), so the two bodies share one surface at the join
    oend = _smooth(g, 150, 700, g.out(_named(g, 0, 700, "hrp_te"), "Attribute"), 0.0, fit(0.25, 2.2))
    oend = g.math("MULTIPLY_ADD", 250, 700, only(g.math("SUBTRACT", 200, 650, oend, 1.0).outputs), g.out(gi, "Mouth"), 1.0)
    ostart = g.math("MINIMUM", 300, 600, g.out(ostart, 0), g.out(oend, 0))
    sflow = _store(g, 300, 400, sflow, "hrp_mouth", g.out(ostart, 0))

    # ---- both: level, depth (profile), carve parameters, time; material
    join = g.n("GeometryNodeJoinGeometry", 400, 0)
    g.links.new(sflow, sock(join.inputs, "Geometry"))
    g.links.new(pflow, sock(join.inputs, "Geometry"))
    pos2 = g.n("GeometryNodeInputPosition", 400, -300)
    z2 = _xyz(g, 550, -300, only(pos2.outputs))
    geo = only(join.outputs)
    shore = _named(g, 600, -500, "hrp_shore")
    # the shelf is wide here (a sandy beach), steep there (a deep bank): no even "pool step" all round
    shn = g.n("ShaderNodeTexNoise", 450, -650, noise_dimensions="2D")
    g.set(shn, "Scale", 0.32)
    g.set(shn, "Detail", 1.0)
    g.links.new(only(pos2.outputs), shn.inputs["Vector"])
    shk = g.maprange(600, -650, g.out(shn, "Fac"), 0.32, 0.68, 0.35, 2.1, smooth=True)
    shelf_v = only(g.math("MULTIPLY", 750, -650, g.out(gi, "Shelf"), g.out(shk, "Result")).outputs)
    dn = _smooth(g, 800, -500, g.out(shore, "Attribute"), 0.0, shelf_v)
    # where water bodies meet (a stream entering / leaving a pond) the deep water runs on as a tongue across the
    # shallows, so pond and stream share their colours at the join instead of meeting along a hard line
    mth = _named(g, 650, -700, "hrp_mouth")
    mth_p = _smooth(g, 600, -650, g.out(mth, "Attribute"), 0.0, 0.3)          # a pond's colour tongue is the near part
    mth_v = g.mixout(g.mix(650, -650, "MIX", "FLOAT", fac=g.out(_named(g, 500, -650, "hrp_flow"), "Attribute"),
                           a=mth_p, b=g.out(mth, "Attribute")))
    tongue = g.math("MULTIPLY", 750, -700, only(g.math("SUBTRACT", 700, -750, 1.0, mth_v).outputs), 0.85)
    # on a stream the tongue keeps clear of its own banks (a thin shallow edge stays where the ribbon meets land)
    tb = g.math("MAXIMUM", 700, -850, only(g.math("SUBTRACT", 600, -850, 1.0, g.out(_named(g, 500, -850, "hrp_flow"),
                "Attribute")).outputs), _smooth(g, 600, -900, g.out(shore, "Attribute"), 0.0, 0.3))
    tb = g.math("MAXIMUM", 750, -900, g.out(tb, 0),                    # ...until it is in the pond: no pale edges there
                only(g.math("SUBTRACT", 700, -950, 1.0, _smooth(g, 600, -950, g.out(mth, "Attribute"), 0.0, 0.6)).outputs))
    tongue = g.math("MULTIPLY", 800, -750, g.out(tongue, 0), g.out(tb, 0))
    dn = only(g.math("MAXIMUM", 800, -600, dn, g.out(tongue, 0)).outputs)
    geo = _store(g, 800, 0, geo, "hrp_dn", dn)
    pack = g.n("ShaderNodeCombineXYZ", 900, -300)                   # what the carve needs, in one lookup
    g.link(z2, "Z", pack, "X")
    g.link(gi, "Depth", pack, "Y")
    g.links.new(shelf_v, pack.inputs["Z"])
    geo = _store(g, 1000, 0, geo, "hrp_carve", only(pack.outputs), "FLOAT_VECTOR")
    geo = _store(g, 1600, 0, geo, "hrp_speed", g.out(gi, "Flow Speed"))   # (time lives in the shader: no rebuild per frame)
    # the shader reads three packed vectors (Metal allows only ~31 buffers per material)
    def pack3(geo_in, name, a, b, c, x):
        cv = g.n("ShaderNodeCombineXYZ", x, -600)
        for sock_, nm in zip(("X", "Y", "Z"), (a, b, c)):
            if nm:
                g.link(_named(g, x - 150, -700, nm), "Attribute", cv, sock_)
        return _store(g, x + 80, 0, geo_in, name, only(cv.outputs), "FLOAT_VECTOR")
    geo = pack3(geo, "hrp_a", "hrp_dn", "hrp_shore", "hrp_flow", 1650)
    geo = pack3(geo, "hrp_b", "hrp_u", "hrp_v", "hrp_speed", 1700)
    # distance to anything standing in the water (rocks): the shader draws a foam collar and a lapping ring
    oci = g.n("GeometryNodeCollectionInfo", 1400, -900, transform_space="RELATIVE")
    g.link(gi, "Obstacles", oci, "Collection")
    ore0 = g.n("GeometryNodeRealizeInstances", 1450, -900)
    g.link(oci, 0, ore0, "Geometry")
    ore = g.n("GeometryNodeSeparateGeometry", 1500, -900, domain="POINT")      # rocks only (not the boat)
    g.link(ore0, 0, ore, "Geometry")
    g.link(g.math("LESS_THAN", 1400, -1000, g.out(_named(g, 1300, -1000, "hrp_noobst"), "Attribute"), 0.5), 0, ore,
           "Selection")
    osz = g.n("GeometryNodeAttributeDomainSize", 1600, -1000, component="MESH")
    g.link(ore, "Selection", osz, "Geometry")
    ohas = g.math("GREATER_THAN", 1700, -1000, g.out(osz, "Face Count"), 0.5)
    opx = g.n("GeometryNodeProximity", 1600, -900, target_element="FACES")
    g.link(ore, "Selection", opx, "Geometry")
    od = _switch(g, 1700, -900, "FLOAT", g.out(ohas, 0), 99.0, g.out(opx, "Distance"))
    geo = _store(g, 1720, 0, geo, "hrp_obst", od)
    # distance to a floating boat: screen-space reflections under a hull have nothing to find (a pale smear)
    bsel = g.n("GeometryNodeSeparateGeometry", 1500, -1150, domain="POINT")
    g.link(ore0, 0, bsel, "Geometry")
    g.link(g.math("GREATER_THAN", 1400, -1200, g.out(_named(g, 1300, -1200, "hrp_noobst"), "Attribute"), 0.5), 0, bsel,
           "Selection")
    bsz = g.n("GeometryNodeAttributeDomainSize", 1600, -1250, component="MESH")
    g.link(bsel, "Selection", bsz, "Geometry")
    bpx = g.n("GeometryNodeProximity", 1600, -1150, target_element="FACES")
    g.link(bsel, "Selection", bpx, "Geometry")
    bd = _switch(g, 1700, -1150, "FLOAT", only(g.math("GREATER_THAN", 1650, -1300, g.out(bsz, "Face Count"), 0.5).outputs),
                 99.0, g.out(bpx, "Distance"))
    geo = _store(g, 1730, 0, geo, "hrp_boatd", bd)
    geo = pack3(geo, "hrp_c", "hrp_end", "hrp_mouth", "hrp_obst", 1750)
    sm = g.n("GeometryNodeSetMaterial", 1800, 0)
    g.links.new(geo, sm.inputs["Geometry"])
    g.link(gi, "Material", sm, "Material")
    smooth = g.n("GeometryNodeSetShadeSmooth", 2000, 0)
    g.link(sm, 0, smooth, "Geometry")
    g.link(smooth, 0, go, "Geometry")
    return ng


# ----------------------------------------------------------------------------------------------
# terrace: a closed curve that raises the meadow to its height (waterfall tops, plateaus)
# ----------------------------------------------------------------------------------------------
TERRACE = "HRP Terrace"
TERRACE_MOD = "Harappa Terrace"
TERRAIN = "Harappa Terrain"


def terrace_group():
    ng, rebuilt = fresh_group(TERRACE, "GeometryNodeTree", WATER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Cliff", "INPUT", "NodeSocketFloat", 0.9, 0.05, 50.0, "How far in from the edge the top is reached",
          "DISTANCE")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1200, 0)
    go = g.n("NodeGroupOutput", 800, 0)
    res = g.n("GeometryNodeResampleCurve", -1000, 0)
    menu(res.inputs["Mode"], "Length")
    res.inputs["Length"].default_value = 0.2
    g.link(gi, "Geometry", res, "Curve")
    pos = g.n("GeometryNodeInputPosition", -1000, -250)
    pz = _xyz(g, -850, -250, only(pos.outputs))
    st = g.n("GeometryNodeAttributeStatistic", -700, -200, data_type="FLOAT", domain="POINT")
    g.link(res, 0, st, "Geometry")
    g.link(pz, "Z", st, "Attribute")
    fill = g.n("GeometryNodeFillCurve", -700, 0)
    g.link(res, 0, fill, "Curve")
    menu(fill.inputs["Mode"], "Triangles")
    lift = g.n("GeometryNodeSetPosition", -500, 0)
    g.link(fill, 0, lift, "Geometry")
    lo = g.n("ShaderNodeCombineXYZ", -600, -150)
    g.link(st, "Mean", lo, "Z")
    g.link(lo, 0, lift, "Offset")
    sub = g.n("GeometryNodeSubdivideMesh", -350, 0)
    g.link(lift, 0, sub, "Mesh")
    sub.inputs["Level"].default_value = 3
    crad = g.n("GeometryNodeInputRadius", -650, -500)
    res_c = _store(g, -600, -400, g.out(res, 0), "hrp_cliff", g.out(crad, 0))
    edge = g.n("GeometryNodeCurveToMesh", -500, -400)
    g.links.new(res_c, edge.inputs["Curve"])
    eflat = g.n("GeometryNodeSetPosition", -350, -400)
    g.link(edge, 0, eflat, "Geometry")
    eo = g.n("ShaderNodeCombineXYZ", -450, -550)
    eo.inputs["Z"].default_value = 0.0
    g.link(pz, "X", eo, "X")
    g.link(pz, "Y", eo, "Y")
    g.link(st, "Mean", eo, "Z")
    g.link(eo, 0, eflat, "Position")
    prox = g.n("GeometryNodeProximity", -150, -300, target_element="EDGES")
    g.link(eflat, 0, prox, "Geometry")
    near = g.n("GeometryNodeSampleNearest", -150, -550, domain="POINT")
    g.link(eflat, 0, near, "Geometry")
    rad = g.n("GeometryNodeSampleIndex", 0, -550, data_type="FLOAT", domain="POINT")
    g.link(eflat, 0, rad, "Geometry")
    g.link(_named(g, -150, -700, "hrp_cliff"), "Attribute", rad, "Value")
    g.link(near, "Index", rad, "Index")
    cl = g.math("MULTIPLY", 100, -450, g.out(rad, "Value", "VALUE"), g.out(gi, "Cliff"))
    pack = g.n("ShaderNodeCombineXYZ", 50, -300)
    g.link(st, "Mean", pack, "X")
    g.link(prox, "Distance", pack, "Y")
    g.link(cl, 0, pack, "Z")
    out = _store(g, 250, 0, g.out(sub, 0), "hrp_terr", only(pack.outputs), "FLOAT_VECTOR")
    g.links.new(out, sock(go.inputs, "Geometry"))
    return ng


def terrain_collection(scene):
    coll = bpy.data.collections.get(TERRAIN)
    if coll is None:
        coll = bpy.data.collections.new(TERRAIN)
    if coll.name not in scene.collection.children and not any(
            coll.name in c.children for c in bpy.data.collections):
        scene.collection.children.link(coll)
    return coll


def make_terrace(context, ob, cliff=0.9):
    """A closed curve becomes a raised terrace (hidden in renders: only the meadow moves)."""
    scene = context.scene
    coll = terrain_collection(scene)
    if ob.name not in coll.objects:
        coll.objects.link(ob)
    mod = ob.modifiers.get(TERRACE_MOD)
    if mod is None:
        mod = ob.modifiers.new(TERRACE_MOD, "NODES")
    mod.node_group = terrace_group()
    mod_input(mod, "Cliff", cliff)
    ob.hide_render = True
    ob.display_type = "BOUNDS"                                      # a light box, not a dense black wireframe
    for attr in ("visible_camera", "visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter"):                         # never drawn, not even in a rendered viewport
        if hasattr(ob, attr):
            setattr(ob, attr, False)
    ob["hrp_terrace"] = True
    for gnd in meadows(scene):
        attach_carve(scene, gnd)
    return mod


# ----------------------------------------------------------------------------------------------
# carve: lower the meadow under the water, raise a bank where needed, clear the grass
# ----------------------------------------------------------------------------------------------
def carve_group():
    ng, rebuilt = fresh_group(CARVE, "GeometryNodeTree", WATER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Water", "INPUT", "NodeSocketCollection", desc="The Harappa Water collection")
    iface(ng, "Streams", "INPUT", "NodeSocketCollection", desc="The streams (a child collection of Harappa Water)")
    iface(ng, "Bank", "INPUT", "NodeSocketFloat", 0.32, 0.0, 50.0, "Width of the bare bank beside the water",
          "DISTANCE")
    iface(ng, "Bank Height", "INPUT", "NodeSocketFloat", 0.03, 0.0, 5.0,
          "How far the shore stands above the water line", "DISTANCE")
    iface(ng, "Bank Slope", "INPUT", "NodeSocketFloat", 0.45, 0.02, 5.0, "Steepness of the banks (rise per metre)")
    iface(ng, "Terrain", "INPUT", "NodeSocketCollection", desc="Raised terraces (waterfall tops, plateaus)")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -2000, 0)
    go = g.n("NodeGroupOutput", 2400, 0)

    ci = g.n("GeometryNodeCollectionInfo", -1800, -300, transform_space="RELATIVE")
    g.link(gi, "Water", ci, "Collection")
    ci.inputs["Separate Children"].default_value = False
    ci.inputs["Reset Children"].default_value = False
    real = g.n("GeometryNodeRealizeInstances", -1600, -300)
    _top_only(real)
    g.link(ci, 0, real, "Geometry")
    sci_ = g.n("GeometryNodeCollectionInfo", -1800, -450, transform_space="RELATIVE")   # streams sit one level deeper
    g.link(gi, "Streams", sci_, "Collection")
    sreal_ = g.n("GeometryNodeRealizeInstances", -1600, -450)
    _top_only(sreal_)
    g.link(sci_, 0, sreal_, "Geometry")
    wjoin = g.n("GeometryNodeJoinGeometry", -1550, -350)
    g.link(sreal_, 0, wjoin, "Geometry")
    g.link(real, 0, wjoin, "Geometry")
    wsurf = g.n("GeometryNodeSeparateGeometry", -1500, -200, domain="FACE")    # water surfaces, not pads or reeds
    g.link(wjoin, 0, wsurf, "Geometry")
    # real water surfaces only: after Realize, an attribute "exists" on every face of the joined mesh (a waterfall
    # sheet included), so select by value: only ponds and streams have a depth > 0 in hrp_carve
    cvsel = _xyz(g, -1650, -50, g.out(_named(g, -1800, -50, "hrp_carve", "FLOAT_VECTOR"), "Attribute", "VECTOR"))
    g.link(g.math("GREATER_THAN", -1550, -100, g.out(cvsel, "Y"), 0.001), 0, wsurf, "Selection")
    wpos = g.n("GeometryNodeInputPosition", -1600, -500)
    wsp = g.n("GeometryNodeSetPosition", -1400, -300)
    g.link(wsurf, "Selection", wsp, "Geometry")
    g.links.new(_flat(g, -1500, -600, only(wpos.outputs)), wsp.inputs["Position"])
    W = only(wsp.outputs)
    size = g.n("GeometryNodeAttributeDomainSize", -1400, -100, component="MESH")
    g.links.new(W, sock(size.inputs, "Geometry"))
    has = g.n("FunctionNodeCompare", -1200, -100, data_type="INT", operation="GREATER_THAN")
    g.link(size, "Face Count", has, "A", bkind="INT")
    g.inp(has, "B", "INT").default_value = 0

    pos = g.n("GeometryNodeInputPosition", -1600, 300)
    pxy = _flat(g, -1450, 300, only(pos.outputs))
    prox = g.n("GeometryNodeProximity", -1100, -300, target_element="FACES")
    g.links.new(W, sock(prox.inputs, "Geometry"))
    g.links.new(pxy, prox.inputs["Sample Position"])
    d = g.out(prox, "Distance")

    def sample(name, x, y):
        sn = g.n("GeometryNodeSampleNearestSurface", x, y, data_type="FLOAT")
        g.links.new(W, sn.inputs["Mesh"])
        g.link(_named(g, x - 180, y - 80, name), "Attribute", sn, "Value")
        g.links.new(pxy, sn.inputs["Sample Position"])
        return g.out(sn, "Value")

    shore = sample("hrp_shore", -1100, -550)
    ce = g.n("GeometryNodeSampleNearestSurface", -1100, -1450, data_type="FLOAT_VECTOR")
    g.links.new(W, ce.inputs["Mesh"])
    g.link(_named(g, -1300, -1500, "hrp_c", "FLOAT_VECTOR"), "Attribute", ce, "Value")
    g.links.new(pxy, ce.inputs["Sample Position"])
    endd = g.out(_xyz(g, -900, -1450, g.out(ce, "Value", "VECTOR")), "X")      # distance to a stream's end
    sv_ = g.n("GeometryNodeSampleNearestSurface", -1100, -800, data_type="FLOAT_VECTOR")
    g.links.new(W, sv_.inputs["Mesh"])
    g.link(_named(g, -1300, -880, "hrp_carve", "FLOAT_VECTOR"), "Attribute", sv_, "Value")
    g.links.new(pxy, sv_.inputs["Sample Position"])
    cv = _xyz(g, -900, -800, g.out(sv_, "Value", "VECTOR"))
    level, dmax, shelf = g.out(cv, "X"), g.out(cv, "Y"), g.out(cv, "Z")
    # bank width wanders between 0.3x and 1.5x along the shore
    bwn = g.n("ShaderNodeTexNoise", -1100, -1300, noise_dimensions="2D")
    g.set(bwn, "Scale", 0.22)
    g.set(bwn, "Detail", 1.0)
    g.links.new(pxy, bwn.inputs["Vector"])
    bfac = g.out(g.maprange(-950, -1300, g.out(bwn, "Fac"), 0.3, 0.7, 0.3, 1.5), "Result")
    bankw = only(g.math("MULTIPLY", -800, -1300, g.out(gi, "Bank"), bfac).outputs)

    inside = g.math("LESS_THAN", -800, -300, d, 0.002)
    neg = g.math("MULTIPLY", -800, -500, shore, -1.0)
    s = g.mix(-600, -400, "MIX", "FLOAT", fac=g.out(inside, 0), a=d, b=g.out(neg, 0))
    s = g.mixout(s)                                                   # signed distance to the shore (<0 = water)

    lip = g.math("ADD", -400, -800, level, g.out(gi, "Bank Height"))
    # inside: level + lip -> level - depth across the shelf
    ins = g.math("MULTIPLY", -400, -600, s, -1.0)
    xs = g.math("DIVIDE", -300, -600, g.out(ins, 0), shelf, clamp=True)
    fall = only(g.math("MULTIPLY", -150, -600, g.out(xs, 0),
                  only(g.math("SUBTRACT", -250, -500, 2.0, g.out(xs, 0)).outputs)).outputs)   # steep at the shore
    dl = g.math("ADD", -250, -900, dmax, g.out(gi, "Bank Height"))
    drop = g.math("MULTIPLY", -100, -700, fall, g.out(dl, 0))
    f_in = g.math("SUBTRACT", 50, -700, g.out(lip, 0), g.out(drop, 0))
    # outside: a bank that rises with the slope
    rise = g.math("MULTIPLY", -250, -1000, s, g.out(gi, "Bank Slope"))
    f_out = g.math("ADD", 50, -1000, g.out(lip, 0), g.out(rise, 0))
    f = g.mixout(g.mix(250, -800, "MIX", "FLOAT", fac=g.out(inside, 0), a=g.out(f_out, 0), b=g.out(f_in, 0)))

    pz = _xyz(g, -1450, 500, only(pos.outputs))
    # terraces first: raise the meadow to each terrace top, easing up over its cliff width
    tci = g.n("GeometryNodeCollectionInfo", -1800, 900, transform_space="RELATIVE")
    g.link(gi, "Terrain", tci, "Collection")
    treal = g.n("GeometryNodeRealizeInstances", -1650, 900)
    g.link(tci, 0, treal, "Geometry")
    tpos = g.n("GeometryNodeInputPosition", -1650, 1050)
    tflat = g.n("GeometryNodeSetPosition", -1500, 900)
    g.link(treal, 0, tflat, "Geometry")
    g.links.new(_flat(g, -1600, 1150, only(tpos.outputs)), tflat.inputs["Position"])
    tsize = g.n("GeometryNodeAttributeDomainSize", -1350, 1050, component="MESH")
    g.link(tflat, 0, tsize, "Geometry")
    thas = g.n("FunctionNodeCompare", -1200, 1050, data_type="INT", operation="GREATER_THAN")
    g.link(tsize, "Face Count", thas, "A", bkind="INT")
    g.inp(thas, "B", "INT").default_value = 0
    tprox = g.n("GeometryNodeProximity", -1200, 900, target_element="FACES")
    g.link(tflat, 0, tprox, "Geometry")
    g.links.new(pxy, tprox.inputs["Sample Position"])
    tin_s = g.n("GeometryNodeSampleNearestSurface", -1200, 700, data_type="FLOAT_VECTOR")
    g.link(tflat, 0, tin_s, "Mesh")
    g.link(_named(g, -1350, 650, "hrp_terr", "FLOAT_VECTOR"), "Attribute", tin_s, "Value")
    g.links.new(pxy, tin_s.inputs["Sample Position"])
    tv = _xyz(g, -1050, 700, g.out(tin_s, "Value", "VECTOR"))          # (top height, distance to edge, cliff)
    tinside = g.math("LESS_THAN", -1050, 900, g.out(tprox, "Distance"), 0.002)
    ramp = g.maprange(-900, 750, g.out(tv, "Y"), 0.0, g.out(tv, "Z"), smooth=True)
    ramp = g.math("MULTIPLY", -750, 800, g.out(ramp, "Result"), g.out(tinside, 0))
    zt = g.mixout(g.mix(-600, 700, "MIX", "FLOAT", fac=g.out(ramp, 0), a=g.out(pz, "Z"), b=g.out(tv, "X")))
    zt = g.math("MAXIMUM", -450, 700, zt, g.out(pz, "Z"))
    zr = _switch(g, -300, 700, "FLOAT", g.out(thas, 0), g.out(pz, "Z"), g.out(zt, 0))
    cliffm = g.math("MULTIPLY", -300, 550, g.out(ramp, 0), only(g.math("SUBTRACT", -400, 500, 1.0, g.out(ramp, 0))
                    .outputs))                                       # 1 on the steep terrace face
    cliffm = g.maprange(-150, 550, g.out(cliffm, 0), 0.03, 0.12, 1.0, 0.0, smooth=True)
    z1 = g.math("MINIMUM", 450, -700, zr, f)
    # a low dam where the meadow is lower than the shore (pond on a slope), easing back over the bank
    away = _smooth(g, 450, -1000, s, 0.0, bankw)
    berm = g.mixout(g.mix(650, -900, "MIX", "FLOAT", fac=away, a=g.out(lip, 0), b=g.out(z1, 0)))
    z2 = g.math("MAXIMUM", 850, -800, g.out(z1, 0), berm)
    z3 = g.mixout(g.mix(1050, -700, "MIX", "FLOAT", fac=g.out(inside, 0), a=g.out(z2, 0), b=g.out(z1, 0)))
    znew = _switch(g, 1250, -600, "FLOAT", g.out(has, 0), zr, z3)
    np_ = g.n("ShaderNodeCombineXYZ", 1450, -400)
    g.link(pz, "X", np_, "X")
    g.link(pz, "Y", np_, "Y")
    g.links.new(znew, np_.inputs["Z"])
    # work only near water and terraces (fields are evaluated on the selection only): far meadow is free
    jb = g.n("GeometryNodeJoinGeometry", 900, 1300)
    g.links.new(W, sock(jb.inputs, "Geometry"))
    g.link(tflat, 0, jb, "Geometry")
    bb = g.n("GeometryNodeBoundBox", 1050, 1300)
    g.link(jb, 0, bb, "Geometry")
    cen = g.vmath("ADD", 1200, 1350, g.out(bb, "Min"), g.out(bb, "Max"))
    cen = g.vmath("SCALE", 1300, 1350, only(cen.outputs), scale=0.5)
    half = g.vmath("SUBTRACT", 1200, 1200, g.out(bb, "Max"), g.out(bb, "Min"))
    half = g.vmath("SCALE", 1300, 1200, only(half.outputs), scale=0.5)
    half = g.vmath("ADD", 1400, 1200, only(half.outputs), (6.0, 6.0, 1e6))
    dd = g.vmath("ABSOLUTE", 1450, 1350, only(g.vmath("SUBTRACT", 1400, 1350, only(pos.outputs), only(cen.outputs)).outputs))
    ins = g.vmath("SUBTRACT", 1550, 1300, only(half.outputs), only(dd.outputs))
    insx = _xyz(g, 1650, 1300, only(ins.outputs))
    near = g.math("MINIMUM", 1750, 1300, g.out(insx, "X"), g.out(insx, "Y"))
    near = g.math("GREATER_THAN", 1850, 1300, g.out(near, 0), 0.0)
    # remember the meadow's own slope (before the carve) for planting rules
    nrm0 = g.n("GeometryNodeInputNormal", 1450, 150)
    geo0 = _store(g, 1550, 100, g.out(gi, "Geometry"), "hrp_flat", g.out(_xyz(g, 1500, 200, sock(nrm0.outputs, "Normal")), "Z"))
    geo0 = _store(g, 1600, 50, geo0, "hrp_sd", 99.0)
    setp = g.n("GeometryNodeSetPosition", 1650, 0)
    g.links.new(geo0, setp.inputs["Geometry"])
    g.link(np_, 0, setp, "Position")
    g.link(near, 0, setp, "Selection")

    # grass mask: keep what was painted, fade it out over the bank
    m0 = _named(g, 1450, 400, MASK_ATTR)
    msw = _switch(g, 1600, 400, "FLOAT", g.out(m0, "Exists"), 1.0, g.out(m0, "Attribute"))
    bn = g.n("ShaderNodeTexNoise", 1300, 800, noise_dimensions="2D")
    g.set(bn, "Scale", 0.9)
    g.set(bn, "Detail", 3.0)
    g.links.new(pxy, bn.inputs["Vector"])
    bjit = g.math("MULTIPLY_ADD", 1450, 800, g.out(bn, "Fac"), 0.9, -0.5)
    bjit = g.math("MULTIPLY", 1600, 800, g.out(bjit, 0), bankw)
    hfn = g.n("ShaderNodeTexNoise", 1300, 1000, noise_dimensions="2D")
    g.set(hfn, "Scale", 5.0)
    g.set(hfn, "Detail", 1.0)
    g.links.new(pxy, hfn.inputs["Vector"])
    hfj = g.math("MULTIPLY_ADD", 1450, 1000, g.out(hfn, "Fac"), 0.6, -0.3)
    hfj = g.math("MULTIPLY", 1550, 1000, g.out(hfj, 0), bankw)
    bank_in = g.math("ADD", 1450, 600, s, g.out(bjit, 0))
    bank_in = g.math("ADD", 1550, 650, g.out(bank_in, 0), g.out(hfj, 0))
    keep = _smooth(g, 1600, 600, g.out(bank_in, 0), -0.06, bankw)            # tufts reach into the shallows
    hgt = g.math("SUBTRACT", 1450, 1200, znew, level)                       # a tall cut bank grows grass again
    kh = _smooth(g, 1600, 1200, g.out(hgt, 0), 0.15, 0.32)
    keep = only(g.math("MAXIMUM", 1700, 700, keep, kh).outputs)
    nrm_ = g.n("GeometryNodeInputNormal", 1650, 900)                       # evaluated on the moved ground
    nzz_ = _xyz(g, 1750, 900, sock(nrm_.outputs, "Normal"))
    blur = g.n("GeometryNodeBlurAttribute", 1850, 1000, data_type="FLOAT")    # no triangle teeth on the edge
    g.link(nzz_, "Z", blur, "Value")
    blur.inputs["Iterations"].default_value = 2
    steep = g.maprange(1900, 900, g.out(blur, 0), 0.72, 0.84, smooth=True)          # steep faces are bare rock
    keep = only(g.math("MULTIPLY", 1800, 750, keep, g.out(steep, "Result")).outputs)
    keep2 = _switch(g, 1750, 600, "FLOAT", g.out(has, 0), g.out(steep, "Result"), keep)
    m = g.math("MULTIPLY", 1900, 400, msw, keep2)
    col = g.n("FunctionNodeCombineColor", 2050, 400)
    for c in ("Red", "Green", "Blue"):
        g.link(m, 0, col, c)
    out = _store(g, 2100, 0, only(setp.outputs), MASK_ATTR, only(col.outputs), "FLOAT_COLOR")
    st_nodes = [out.node]
    wet = g.math("SUBTRACT", 1900, 700, 1.0, keep2)
    out = _store(g, 2250, 0, out, "hrp_wet", g.out(wet, 0))
    st_nodes.append(out.node)
    sdo = _switch(g, 2250, 300, "FLOAT", g.out(has, 0), 99.0, s)
    out = _store(g, 2350, 0, out, "hrp_sd", sdo)                            # signed distance to the shore
    st_nodes.append(out.node)
    out = _store(g, 2450, 0, out, "hrp_endd", endd)                         # (no reeds at a waterfall's lip)
    st_nodes.append(out.node)
    above = g.math("SUBTRACT", 2350, 400, znew, level)
    out = _store(g, 2500, 0, out, "hrp_above", g.out(above, 0))             # height above the nearest water
    st_nodes.append(out.node)
    for stn in st_nodes:                                                    # far away: painted mask untouched
        g.link(near, 0, stn, "Selection")
    bake = g.n("GeometryNodeBake", 2550, 0, label="Banks")              # Freeze Banks: skip the carve when baked
    if not len(bake.bake_items):
        bake.bake_items.new("GEOMETRY", "Geometry")
    g.links.new(out, bake.inputs["Geometry"])
    g.links.new(bake.outputs["Geometry"], go.inputs["Geometry"])
    return ng


def freeze_banks(context, ground, on=True):
    """Bake the carve of this meadow into the .blend (playback no longer re-runs it), or go back to live."""
    mod = ground.modifiers.get(CARVE_MOD)
    if mod is None or not mod.bakes:
        return False
    b = mod.bakes[0]
    with context.temp_override(object=ground, active_object=ground):
        if on:
            b.bake_mode = "STILL"
            try:
                mod.bake_target = "PACKED"
            except (TypeError, AttributeError):
                pass
            bpy.ops.object.geometry_node_bake_single(session_uid=ground.session_uid, modifier_name=mod.name,
                                                     bake_id=b.bake_id)
        else:
            bpy.ops.object.geometry_node_bake_delete_single(session_uid=ground.session_uid, modifier_name=mod.name,
                                                            bake_id=b.bake_id)
    ground["hrp_banks_frozen"] = bool(on)
    return True


def refreeze(context):
    """After Harappa changed water or terraces: re-bake meadows whose banks are frozen."""
    for gnd in meadows(context.scene):
        if gnd.get("hrp_banks_frozen"):
            freeze_banks(context, gnd, False)
            freeze_banks(context, gnd, True)


# ----------------------------------------------------------------------------------------------
# toon water material
# ----------------------------------------------------------------------------------------------
def _attr(g, name, x, y):
    return g.out(g.n("ShaderNodeAttribute", x, y, attribute_name=name, attribute_type="GEOMETRY"), "Fac")


def type_colours(g, pal, x, y):
    """Shallow / mid / deep: the season's, or this body's water type scaled by the season (so night darkens it)."""
    from .util import srgb
    use = g.out(g.n("ShaderNodeAttribute", x, y, attribute_name="hrp_wuse", attribute_type="OBJECT"), "Fac")
    ref = g.n("ShaderNodeRGB", x, y - 150)
    only(ref.outputs).default_value = (*[max(c, 1e-3) for c in srgb(SUMMER_MID)], 1.0)
    ratio = g.mix(x + 200, y - 100, "DIVIDE", fac=1.0, a=g.out(pal, "water_mid"), b=only(ref.outputs))
    out = []
    for k, (attr, key) in enumerate((("hrp_wcol_s", "water_shallow"), ("hrp_wcol_m", "water_mid"),
                                     ("hrp_wcol_d", "water_deep"))):
        tc = g.n("ShaderNodeAttribute", x, y - 300 - 150 * k, attribute_name=attr, attribute_type="OBJECT")
        sc_ = g.mix(x + 350, y - 300 - 150 * k, "MULTIPLY", fac=1.0, a=g.out(tc, "Color"), b=g.mixout(ratio))
        m = g.mix(x + 500, y - 300 - 150 * k, fac=use, a=g.out(pal, key), b=g.mixout(sc_))
        out.append(g.mixout(m))
    return out


RAIN_ZONE = "HRP Rain Zone"
RAIN_OB = "Harappa Rain"                                              # (weather.RAIN_OB; no import cycle)


def rain_zone_group():
    """Shader group: 1 inside the rain area, 0 outside. The centre and radius are driven from the Harappa Rain object,
    so moving it (or the camera it follows) moves the raindrop rings with it."""
    ng, rebuilt = fresh_group(RAIN_ZONE, "ShaderNodeTree", 2)
    if rebuilt:
        g = G(ng)
        iface(ng, "Position", "INPUT", "NodeSocketVector")
        iface(ng, "Zone", "OUTPUT", "NodeSocketFloat")
        gi = g.n("NodeGroupInput", -800, 0)
        go = g.n("NodeGroupOutput", 400, 0)
        vals = {}
        for i, (k, d) in enumerate((("X", 0.0), ("Y", 0.0), ("R", 1.0e6))):
            v = g.n("ShaderNodeValue", -800, -200 - 120 * i)
            v.name = v.label = k
            only(v.outputs).default_value = d
            vals[k] = v
        c = g.n("ShaderNodeCombineXYZ", -600, -200)
        g.link(vals["X"], 0, c, "X")
        g.link(vals["Y"], 0, c, "Y")
        p = _flat(g, -600, 0, g.out(gi, "Position"))
        d = g.vmath("DISTANCE", -400, 0, p, g.out(c, 0))
        r0 = g.math("MULTIPLY", -400, -250, g.out(vals["R"], 0), 0.8)
        z = g.n("ShaderNodeMapRange", -200, 0, interpolation_type="SMOOTHSTEP")
        g.links.new(d.outputs["Value"], z.inputs["Value"])
        g.link(vals["R"], 0, z, "From Min")
        g.link(r0, 0, z, "From Max")
        g.link(z, "Result", go, "Zone")
    drive_rain_zone()
    return ng


def drive_rain_zone():
    ng = bpy.data.node_groups.get(RAIN_ZONE)
    if ng is None:
        return
    ob = bpy.data.objects.get(RAIN_OB)
    for k, chan in (("X", "LOC_X"), ("Y", "LOC_Y"), ("R", None)):
        node = ng.nodes.get(k)
        if node is None:
            continue
        sock = only(node.outputs)
        try:
            sock.driver_remove("default_value")
        except TypeError:
            pass
        if ob is None:
            sock.default_value = 1.0e6 if k == "R" else 0.0
            continue
        drv = sock.driver_add("default_value").driver
        drv.type = "SCRIPTED"
        var = drv.variables.new()
        var.name = "v"
        if chan:
            var.type = "TRANSFORMS"
            var.targets[0].id = ob
            var.targets[0].transform_type = chan
            var.targets[0].transform_space = "WORLD_SPACE"
        else:
            var.type = "SINGLE_PROP"
            var.targets[0].id = ob
            var.targets[0].data_path = '["hrp_rain_r"]'
        drv.expression = "v"


def water_material():
    mat, rebuilt = shading._fresh_mat(MAT_WATER)
    if not rebuilt and mat.get("hrp_water_ver") == WATER_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_water_ver"] = WATER_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -2600, 0)
    pal.node_tree = shading.palette_group()
    geo = g.n("ShaderNodeNewGeometry", -2600, 600)
    P = g.out(geo, "Position")
    def vattr(name, x, y):
        return _xyz(g, x + 180, y, g.out(g.n("ShaderNodeAttribute", x, y, attribute_name=name,
                                               attribute_type="GEOMETRY"), "Vector"))
    va = vattr("hrp_a", -2800, 1100)
    vb = vattr("hrp_b", -2800, 1600)
    vc = vattr("hrp_c", -2800, 2100)
    dn, shore, flow = g.out(va, "X"), g.out(va, "Y"), g.out(va, "Z")
    u, v = g.out(vb, "X"), g.out(vb, "Y")
    tg = g.n("ShaderNodeGroup", -2600, 2500)
    tg.node_tree = time_group()
    t = g.out(tg, "Seconds")                                         # frame/fps driver, kept out of the palette
    mouth = g.out(vc, "Y")
    night = g.math("MINIMUM", -2400, 2700, g.out(pal, "water_glow"), 1.0)
    spd = g.out(vb, "Z")
    endd = g.out(vc, "X")
    endf = _smooth(g, -2400, 2300, endd, 0.0, 1.2)                  # stream lines fade out at the mouth

    # --- depth bands, their edges wobbled so they read hand-drawn
    wn = g.n("ShaderNodeTexNoise", -2300, 900, noise_dimensions="3D")
    g.set(wn, "Scale", 1.3)
    g.set(wn, "Detail", 2.0)
    g.links.new(P, wn.inputs["Vector"])
    wob = g.math("MULTIPLY_ADD", -2100, 900, g.out(wn, "Fac"), 0.22, -0.11)
    clar0 = g.out(g.n("ShaderNodeAttribute", -2400, 1050, attribute_name="hrp_clarity", attribute_type="OBJECT"), "Fac")
    dk = g.math("MULTIPLY_ADD", -2250, 1050, clar0, -0.35, 1.0)
    dn_c = g.math("MULTIPLY", -2100, 1050, dn, g.out(dk, 0))
    d2 = g.math("ADD", -1950, 900, g.out(dn_c, 0), g.out(wob, 0))
    on_ = g.n("ShaderNodeTexNoise", -2300, 1300, noise_dimensions="2D")         # shallows that come and go
    g.set(on_, "Scale", 0.28)
    g.set(on_, "Detail", 1.0)
    g.links.new(P, on_.inputs["Vector"])
    d2 = g.math("ADD", -1900, 1000, g.out(d2, 0), only(g.math("MULTIPLY_ADD", -2050, 1250, g.out(on_, "Fac"), 0.6, -0.3)
                .outputs))
    b1 = _smooth(g, -1800, 1000, g.out(d2, 0), 0.21, 0.25)
    b2 = _smooth(g, -1800, 800, g.out(d2, 0), 0.56, 0.6)
    cs, cm, cd = type_colours(g, pal, -2300, 1800)
    cd = g.mixout(g.mix(-1700, 700, fac=0.15, a=cd, b=cm))                      # deep: blue, never navy
    # the bed shows through the shallows: soft sandy / weedy blotches
    bedn = g.n("ShaderNodeTexVoronoi", -2300, 1500, voronoi_dimensions="2D", feature="SMOOTH_F1")
    g.set(bedn, "Scale", 2.6)
    g.links.new(P, bedn.inputs["Vector"])
    bed = _smooth(g, -2100, 1500, g.out(bedn, "Distance"), 0.18, 0.42)
    bedc = g.mixout(g.mix(-1950, 1450, "MULTIPLY", fac=0.5, a=cs, b=(0.86, 0.9, 0.62, 1.0)))
    bshal = _smooth(g, -1950, 1600, g.out(d2, 0), 0.32, 0.04)
    bedf = g.math("MULTIPLY", -1800, 1550, only(g.math("SUBTRACT", -1900, 1500, 1.0, bed).outputs), bshal)
    cs = g.mixout(g.mix(-1750, 1450, fac=only(g.math("MULTIPLY", -1700, 1600, g.out(bedf, 0), 0.6).outputs), a=cs, b=bedc))
    c = g.mixout(g.mix(-1600, 1000, fac=b1, a=cs, b=cm))
    c = g.mixout(g.mix(-1450, 900, fac=b2, a=c, b=cd))
    # per water body: type / tint (object custom properties, neutral when missing)
    def oattr(name, x, y):
        return g.out(g.n("ShaderNodeAttribute", x, y, attribute_name=name, attribute_type="OBJECT"), "Fac")
    hsv = g.n("ShaderNodeHueSaturation", -1300, 1100)
    tint = _xyz(g, -1650, 1150, g.out(g.n("ShaderNodeAttribute", -1850, 1150, attribute_name="hrp_tint",
                                           attribute_type="OBJECT"), "Vector"))
    g.link(g.math("ADD", -1450, 1250, g.out(tint, "X"), 0.5), 0, hsv, "Hue")
    g.link(g.math("ADD", -1450, 1150, g.out(tint, "Y"), 1.0), 0, hsv, "Saturation")
    g.link(g.math("ADD", -1450, 1050, g.out(tint, "Z"), 1.0), 0, hsv, "Value")
    g.links.new(c, hsv.inputs["Color"])
    c = only(hsv.outputs)
    clar = clar0
    # --- caustic net in the shallows (Voronoi cell edges, drifting slowly)
    cw = g.n("ShaderNodeTexNoise", -2500, 300, noise_dimensions="2D")
    g.set(cw, "Scale", 0.6)
    g.links.new(P, cw.inputs["Vector"])
    pw = only(g.vmath("MULTIPLY_ADD", -2400, 350, g.out(cw, "Color"), (0.9, 0.9, 0.0)).outputs)
    pw = only(g.vmath("ADD", -2350, 350, pw, P).outputs)
    cxy = g.n("ShaderNodeCombineXYZ", -2100, 300)
    pxyz = _xyz(g, -2300, 300, P)
    pwx = _xyz(g, -2250, 450, pw)
    g.link(pwx, "X", cxy, "X")
    g.link(pwx, "Y", cxy, "Y")
    g.link(g.math("MULTIPLY", -2250, 150, t, 0.12), 0, cxy, "Z")
    vor = g.n("ShaderNodeTexVoronoi", -1950, 300, voronoi_dimensions="3D", feature="DISTANCE_TO_EDGE")
    g.set(vor, "Scale", 2.4)
    g.link(cxy, 0, vor, "Vector")
    nn = g.n("ShaderNodeTexNoise", -1950, 500, noise_dimensions="2D")
    g.set(nn, "Scale", 2.0)
    g.links.new(P, nn.inputs["Vector"])
    lw_ = g.math("MULTIPLY_ADD", -1900, 600, g.out(cw, "Fac"), 0.03, 0.005)
    net = _smooth(g, -1800, 300, g.out(vor, "Distance"), g.out(lw_, 0), 0.004)
    broken = _smooth(g, -1800, 500, g.out(nn, "Fac"), 0.42, 0.55)
    net = only(g.math("MULTIPLY", -1700, 400, net, broken).outputs)
    shallow = _smooth(g, -1800, 150, dn, 0.42, 0.12)
    netw = g.math("MULTIPLY", -1650, 250, net, shallow)
    netw = g.math("MULTIPLY", -1500, 250, g.out(netw, 0), g.out(pal, "water_caustics"))
    netw = g.math("MULTIPLY", -1400, 250, g.out(netw, 0), 0.2)
    netw = g.math("MULTIPLY", -1380, 230, g.out(netw, 0),
                  only(g.math("ADD", -1480, 180, clar, 1.0, clamp=True).outputs))     # murky water: no caustics
    netw = g.math("MULTIPLY", -1350, 200, g.out(netw, 0),
                  only(g.math("MULTIPLY_ADD", -1450, 100, g.out(night, 0), -0.7, 1.0).outputs))
    c = g.mixout(g.mix(-1300, 700, fac=g.out(netw, 0), a=c, b=g.out(pal, "water_line")))

    # --- flow streaks along streams (stretched noise, panned along U)
    def streak_layer(x, y, speed_k, vy, seed):
        fu = g.n("ShaderNodeCombineXYZ", x, y)
        mv = g.math("MULTIPLY", x - 300, y, t, spd)
        mv = g.math("MULTIPLY", x - 200, y, g.out(mv, 0), speed_k)
        g.link(g.math("MULTIPLY", x - 150, y + 50,
                      only(g.math("SUBTRACT", x - 100, y + 100, u, g.out(mv, 0)).outputs), 0.35), 0, fu, "X")
        g.link(g.math("MULTIPLY", x - 150, y - 100, v, vy), 0, fu, "Y")
        fu.inputs["Z"].default_value = seed
        fn = g.n("ShaderNodeTexNoise", x + 150, y, noise_dimensions="3D")
        g.set(fn, "Scale", 1.6)
        g.set(fn, "Detail", 0.0)
        g.link(fu, 0, fn, "Vector")
        return _smooth(g, x + 300, y, g.out(fn, "Fac"), 0.675, 0.683)
    st1 = streak_layer(-2200, -150, 1.0, 9.0, 0.0)
    st2 = streak_layer(-2200, -400, 1.45, 14.0, 7.3)
    streak = g.math("MAXIMUM", -1700, -250, st1, st2)
    sbn = g.n("ShaderNodeTexNoise", -1900, -550, noise_dimensions="3D")              # lines break and re-form
    sbv = g.n("ShaderNodeCombineXYZ", -2050, -550)
    g.link(pxyz, "X", sbv, "X")
    g.link(pxyz, "Y", sbv, "Y")
    g.link(g.math("MULTIPLY", -2150, -600, t, 0.35), 0, sbv, "Z")
    g.set(sbn, "Scale", 1.4)
    g.link(sbv, 0, sbn, "Vector")
    sbk = _smooth(g, -1750, -550, g.out(sbn, "Fac"), 0.44, 0.52)
    streak = g.math("MULTIPLY", -1700, -300, g.out(streak, 0), sbk)
    # where a stream runs down a slope it turns to white rapids (more and longer streaks, foam between them)
    gnz = _xyz(g, -2100, -750, g.out(geo, "Normal"))
    rap = _smooth(g, -1950, -750, g.out(gnz, "Z"), 0.992, 0.94)
    rap = only(g.math("MULTIPLY", -1850, -750, rap, flow).outputs)
    rfn = g.n("ShaderNodeTexNoise", -1950, -900, noise_dimensions="3D")
    rfv = g.n("ShaderNodeCombineXYZ", -2050, -900)
    g.link(g.math("MULTIPLY", -2150, -850, only(g.math("SUBTRACT", -2250, -850, u, only(g.math("MULTIPLY", -2350, -850, t,
                  only(g.math("MULTIPLY", -2450, -850, spd, 2.0).outputs)).outputs)).outputs), 0.6), 0, rfv, "X")
    g.link(g.math("MULTIPLY", -2150, -950, v, 5.0), 0, rfv, "Y")
    g.set(rfn, "Scale", 1.3)
    g.set(rfn, "Detail", 2.0)
    g.link(rfv, 0, rfn, "Vector")
    rfoam = _smooth(g, -1800, -900, g.out(rfn, "Fac"), 0.47, 0.5)
    rfoam = only(g.math("MULTIPLY", -1700, -850, rfoam, rap).outputs)
    streak = g.math("MAXIMUM", -1650, -300, g.out(streak, 0), rfoam)
    streak2 = g.math("MULTIPLY", -1650, -150, g.out(streak, 0), flow)
    streak2 = g.math("MULTIPLY", -1600, -100, g.out(streak2, 0), endf)
    streak2 = g.math("MULTIPLY", -1550, -50, g.out(streak2, 0), mouth)              # ...and fade in at an outlet
    c = g.mixout(g.mix(-1150, 500, fac=g.out(streak2, 0), a=c, b=g.out(pal, "water_line")))

    # --- shore foam: a contact line and a second line that breathes in and out (Wind Waker style)
    fnz = g.n("ShaderNodeTexNoise", -2300, -600, noise_dimensions="2D")
    g.set(fnz, "Scale", 3.5)
    g.links.new(P, fnz.inputs["Vector"])
    jit = g.math("MULTIPLY_ADD", -2100, -600, g.out(fnz, "Fac"), 0.06, -0.03)
    sh2 = g.math("ADD", -1950, -600, shore, g.out(jit, 0))
    cwn = g.n("ShaderNodeTexNoise", -2300, -450, noise_dimensions="2D")
    g.set(cwn, "Scale", 0.5)
    g.links.new(P, cwn.inputs["Vector"])
    cwid = g.out(g.maprange(-2100, -450, g.out(cwn, "Fac"), 0.3, 0.7, 0.045, 0.12), "Result")
    cin = g.math("MULTIPLY", -1950, -450, cwid, 0.7)
    contact = _smooth(g, -1800, -600, g.out(sh2, 0), cwid, g.out(cin, 0))
    breathe = g.math("SINE", -2100, -800, only(g.math("MULTIPLY", -2250, -800, t, 1.7).outputs))
    off = g.math("MULTIPLY_ADD", -1950, -800, g.out(breathe, 0), 0.04, 0.24)
    gap = g.math("ABSOLUTE", -1800, -800, only(g.math("SUBTRACT", -1950, -950, g.out(sh2, 0), g.out(off, 0)).outputs))
    ring2 = _smooth(g, -1650, -800, g.out(gap, 0), 0.016, 0.009)
    dsn = g.n("ShaderNodeTexNoise", -1900, -1050, noise_dimensions="2D")             # a few arcs, not a lane line
    g.set(dsn, "Scale", 0.9)
    g.links.new(P, dsn.inputs["Vector"])
    dash = _smooth(g, -1650, -950, g.out(dsn, "Fac"), 0.56, 0.62)
    ring2 = g.math("MULTIPLY", -1500, -800, ring2, dash)
    pond_only = g.math("SUBTRACT", -1500, -950, 1.0, flow)
    ring2 = g.math("MULTIPLY", -1400, -850, g.out(ring2, 0), g.out(pond_only, 0))
    ring2 = g.math("MULTIPLY", -1350, -900, g.out(ring2, 0),
                   only(g.math("MULTIPLY_ADD", -1450, -1000, g.out(night, 0), -0.5, 1.0).outputs))
    obst = g.out(vc, "Z")
    collar = _smooth(g, -1800, -1150, only(g.math("ADD", -1900, -1150, obst, g.out(jit, 0)).outputs), 0.07, 0.045)
    lap = g.math("MULTIPLY_ADD", -2000, -1250, g.out(breathe, 0), 0.03, 0.17)
    lapg = g.math("ABSOLUTE", -1900, -1250, only(g.math("SUBTRACT", -2000, -1300, obst, g.out(lap, 0)).outputs))
    lapr = _smooth(g, -1800, -1250, g.out(lapg, 0), 0.014, 0.008)
    lapr = g.math("MULTIPLY", -1700, -1250, lapr, only(g.math("MAXIMUM", -1800, -1350, dash, 0.4).outputs))
    collar = g.math("MAXIMUM", -1600, -1200, collar, g.out(lapr, 0))
    contact = only(g.math("MAXIMUM", -1500, -650, contact, g.out(collar, 0)).outputs)
    foam = g.math("MAXIMUM", -1350, -700, contact, g.out(ring2, 0))
    foam = g.math("MULTIPLY", -1250, -700, g.out(foam, 0), endf)
    foam = g.math("MULTIPLY", -1200, -650, g.out(foam, 0), mouth)
    rzf = _xyz(g, -1400, -500, g.out(g.n("ShaderNodeTexCoord", -1550, -500), "Reflection"))
    farf = g.maprange(-1250, -500, g.out(rzf, "Z"), 0.5, 0.25, 0.35, 1.0, smooth=True)    # lit far bank, dark near
    brk = _smooth(g, -1250, -400, g.out(fnz, "Fac"), 0.36, 0.42)
    farf = g.math("MULTIPLY", -1100, -450, g.out(farf, "Result"), only(g.math("MAXIMUM", -1150, -350, brk, 0.5).outputs))
    foam = g.math("MULTIPLY", -1050, -600, g.out(foam, 0), g.out(farf, 0))

    # --- rain ripples: one ring per Voronoi cell, each cell on its own clock
    rv = g.n("ShaderNodeTexVoronoi", -2300, -1300, voronoi_dimensions="2D", feature="F1")
    g.set(rv, "Scale", 2.4)
    g.set(rv, "Randomness", 0.8)
    g.links.new(P, rv.inputs["Vector"])
    rc = g.n("ShaderNodeSeparateColor", -2100, -1350)
    g.link(rv, "Color", rc, "Color")
    ph = g.math("MULTIPLY_ADD", -1950, -1300, t, 0.85, g.out(rc, "Red"))
    ph = g.math("FRACT", -1800, -1300, g.out(ph, 0))
    rad = g.math("MULTIPLY", -1650, -1400, g.out(ph, 0), 0.30)
    rg = g.math("ABSOLUTE", -1500, -1300, only(g.math("SUBTRACT", -1650, -1250, g.out(rv, "Distance"),
                                                  g.out(rad, 0)).outputs))
    ring = _smooth(g, -1350, -1300, g.out(rg, 0), 0.010, 0.004)
    fade = g.math("SUBTRACT", -1350, -1450, 1.0, g.out(ph, 0))
    rz = g.n("ShaderNodeGroup", -1700, -1650)
    rz.node_tree = rain_zone_group()
    g.links.new(P, rz.inputs["Position"])
    live = g.math("LESS_THAN", -1350, -1550, g.out(rc, "Green"),
                  only(g.math("MULTIPLY", -1500, -1650, g.out(pal, "water_rain"), g.out(rz, "Zone")).outputs))
    ring = g.math("MULTIPLY", -1200, -1300, ring, g.out(fade, 0))
    ring = g.math("MULTIPLY", -1050, -1300, g.out(ring, 0), g.out(live, 0))
    ring = g.math("GREATER_THAN", -900, -1300, g.out(ring, 0), 0.25)

    # --- glints: a few sparkles that blink
    gx = g.n("ShaderNodeCombineXYZ", -2100, -1750)
    g.link(pxyz, "X", gx, "X")
    g.link(pxyz, "Y", gx, "Y")
    g.link(g.math("MULTIPLY", -2250, -1850, t, 0.9), 0, gx, "Z")
    gv = g.n("ShaderNodeTexVoronoi", -1950, -1750, voronoi_dimensions="3D", feature="F1")
    g.set(gv, "Scale", 9.0)
    g.link(gx, 0, gv, "Vector")
    gs = g.n("ShaderNodeSeparateColor", -1800, -1850)
    g.link(gv, "Color", gs, "Color")
    gdot = _smooth(g, -1650, -1750, g.out(gv, "Distance"), 0.05, 0.03)
    gsel = g.math("GREATER_THAN", -1650, -1900, g.out(gs, "Red"), 0.86)
    glint = g.math("MULTIPLY", -1500, -1800, gdot, g.out(gsel, 0))
    glint = g.math("MULTIPLY", -1350, -1800, g.out(glint, 0), g.out(pal, "water_glints"))
    gls = g.n("ShaderNodeBsdfGlossy", -1800, -2100)
    g.set(gls, "Roughness", 0.25)
    gs2 = g.n("ShaderNodeShaderToRGB", -1650, -2100)
    g.link(gls, 0, gs2, "Shader")
    gbw = g.n("ShaderNodeRGBToBW", -1500, -2100)
    g.link(gs2, "Color", gbw, "Color")
    sunm = _smooth(g, -1350, -2100, g.out(gbw, 0), 0.25, 0.6)
    glint = g.math("MULTIPLY", -1200, -1900, g.out(glint, 0), sunm)

    # moonlight at night: a broken column of horizontal dashes where the moon (the night's sun) is mirrored
    win2 = _xyz(g, -1700, -2300, g.out(g.n("ShaderNodeTexCoord", -1850, -2300), "Window"))
    mdv = g.n("ShaderNodeCombineXYZ", -1550, -2300)
    g.link(g.math("MULTIPLY", -1650, -2250, g.out(win2, "X"), 4.0), 0, mdv, "X")
    g.link(g.math("MULTIPLY", -1650, -2350, g.out(win2, "Y"), 90.0), 0, mdv, "Y")
    g.link(g.math("MULTIPLY", -1650, -2400, t, 0.6), 0, mdv, "Z")
    mdn = g.n("ShaderNodeTexNoise", -1400, -2300, noise_dimensions="3D")
    g.set(mdn, "Scale", 1.0)
    g.link(mdv, 0, mdn, "Vector")
    mdash = _smooth(g, -1250, -2300, g.out(mdn, "Fac"), 0.56, 0.6)                  # broken into dashes
    # the anime cheat: a column on the water in the direction of the moon, whatever its height
    ml = g.n("ShaderNodeCombineXYZ", -1700, -2550)
    for k, ax in enumerate(("X", "Y")):
        vn = g.n("ShaderNodeValue", -1850, -2500 - 100 * k)
        vn.name = vn.label = "Moon" + ax
        g.link(vn, 0, ml, ax)
    mln = g.vmath("NORMALIZE", -1550, -2550, only(ml.outputs))
    rfl = g.out(g.n("ShaderNodeTexCoord", -1850, -2700), "Reflection")
    rxy = g.vmath("NORMALIZE", -1550, -2700, _flat(g, -1700, -2700, rfl))
    mdot = g.vmath("DOT_PRODUCT", -1400, -2600, only(mln.outputs), only(rxy.outputs))
    mcol = _smooth(g, -1250, -2150, mdot.outputs["Value"], 0.992, 0.998)           # a narrow path of light
    mcol = only(g.math("MULTIPLY", -1150, -2100, mcol, _smooth(g, -1250, -2050, dn, 0.12, 0.3)).outputs)   # open water
    moon = g.math("MULTIPLY", -1100, -2200, mdash, mcol)
    moon = g.math("MULTIPLY", -1050, -2250, g.out(moon, 0), 0.75)                      # silver, not a white bar
    moon = g.math("MULTIPLY", -1000, -2200, g.out(moon, 0), only(g.math("MINIMUM", -1100, -2350, g.out(pal, "water_glow"),
                  1.0).outputs))
    lines = g.math("MAXIMUM", -1100, -1000, g.out(foam, 0), g.out(ring, 0))
    lines = g.math("MAXIMUM", -1050, -1050, g.out(lines, 0), g.out(moon, 0))
    lines = g.math("MAXIMUM", -950, -1100, g.out(lines, 0), g.out(glint, 0))

    # --- sky reflection at grazing angles
    tc = g.n("ShaderNodeTexCoord", -1500, 1300)
    rz = _xyz(g, -1350, 1300, g.out(tc, "Reflection"))
    win = _xyz(g, -1500, 1500, g.out(tc, "Window"))
    wst = g.n("ShaderNodeCombineXYZ", -1350, 1500)
    g.link(g.math("MULTIPLY", -1450, 1600, g.out(win, "X"), 3.0), 0, wst, "X")
    g.link(g.math("MULTIPLY", -1450, 1450, g.out(win, "Y"), 45.0), 0, wst, "Y")
    rn = g.n("ShaderNodeTexNoise", -1200, 1500, noise_dimensions="2D")
    g.set(rn, "Detail", 0.0)
    g.link(wst, 0, rn, "Vector")
    fj = g.math("MULTIPLY_ADD", -1100, 1450, g.out(rn, "Fac"), 0.05, g.out(rz, "Z"))
    fr = _smooth(g, -1000, 1300, g.out(fj, 0), 0.155, 0.15, 0.0, 0.35)          # painted streaks of sky, far shore

    # the water takes a little of the sky's colour (peach at golden hour, grey under a storm)
    c = g.mixout(g.mix(-850, 750, fac=0.07, a=c, b=g.out(pal, "water_sky")))
    # --- cel: tree shadows fall on the water too (flat normal)
    sh = g.mix(-750, 700, "MULTIPLY", fac=0.5, a=c, b=g.out(pal, "water_shade"))      # gentle, like the grass shadow
    dp = g.mix(-750, 550, "MULTIPLY", fac=0.6, a=g.mixout(sh), b=g.out(pal, "water_shade"))
    cel = shading._cel_node(g, pal, -500, 700, g.out(geo, "Normal"), c, g.mixout(sh), g.mixout(dp))
    # flat water must not fall into the shadow band just because the sun is low (golden hour):
    # lit wherever any direct light arrives, shaded only under real cast shadows
    for k, v_ in (("Threshold", 0.035), ("Deep Threshold", -1.0)):      # shaded water: shadow colour, never the deep one
        for lk in list(cel.inputs[k].links):
            mat.node_tree.links.remove(lk)
        cel.inputs[k].default_value = v_
    col = g.out(cel, "Color")
    # the sky is mirrored whether or not the sun reaches the water: added after the light/shadow split
    col = g.mixout(g.mix(-300, 700, fac=fr, a=col, b=g.out(pal, "water_sky")))
    # and the far bank is mirrored as a dark green band along the shore seen at a glancing angle
    # (which half of a pond is "far": the side away from the camera, from the pond's centre)
    oi = g.n("ShaderNodeObjectInfo", -900, 1250)
    rel = g.vmath("SUBTRACT", -750, 1250, _flat(g, -900, 1350, P), _flat(g, -900, 1150, g.out(oi, "Location")))
    rel = g.vmath("NORMALIZE", -600, 1250, only(rel.outputs))
    away = g.vmath("SCALE", -750, 1100, _flat(g, -900, 1050, g.out(geo, "Incoming")), scale=-1.0)
    away = g.vmath("NORMALIZE", -600, 1100, only(away.outputs))
    side_ = g.vmath("DOT_PRODUCT", -450, 1200, only(rel.outputs), only(away.outputs))
    farh = g.maprange(-300, 1200, side_.outputs["Value"], 0.05, 0.45, smooth=True)
    nearh = g.maprange(-300, 1350, side_.outputs["Value"], -0.1, -0.5, smooth=True)
    bw = g.math("MULTIPLY_ADD", -450, 1000, g.out(rn, "Fac"), 0.25, 0.25)              # band width wanders
    inb = g.math("LESS_THAN", -300, 1000, shore, g.out(bw, 0))
    pond_ = g.math("SUBTRACT", -300, 900, 1.0, flow)
    bank = g.math("MULTIPLY", -150, 1050, g.out(farh, "Result"), g.out(inb, 0))
    bank = g.math("MULTIPLY", -100, 950, g.out(bank, 0), g.out(pond_, 0))
    bank = g.math("MULTIPLY", -50, 950, g.out(bank, 0), 0.0)                    # (real reflections do this now)
    bcol = g.mix(-150, 850, "MULTIPLY", fac=1.0, a=g.out(pal, "grass_deep"), b=(0.55, 0.62, 0.5, 1.0))
    col = g.mixout(g.mix(-50, 750, fac=g.out(bank, 0), a=col, b=g.mixout(bcol)))
    # near bank: the shallows are seen from above, so they read darker (no sky in them)
    nsh = g.maprange(-150, 1300, shore, 1.2, 0.2, smooth=True)
    nb = g.math("MULTIPLY", -50, 1300, g.out(nearh, "Result"), g.out(nsh, "Result"))
    nb = g.math("MULTIPLY", 0, 1250, g.out(nb, 0), g.out(pond_, 0))
    ncol = g.mix(0, 1150, "MULTIPLY", fac=1.0, a=col, b=(0.62, 0.78, 0.76, 1.0))
    col = g.mixout(g.mix(100, 800, fac=only(g.math("MULTIPLY", 50, 1200, g.out(nb, 0), 0.25).outputs), a=col,
                         b=g.mixout(ncol)))
    # lines on top, unshaded; at night they glow (strength > 1 feeds the bloom)
    glow = g.math("MULTIPLY_ADD", -500, -900, g.out(pal, "water_glow"), 0.25, 1.0)
    gl =g.n("ShaderNodeCombineColor", -450, -1200)
    for ch in ("Red", "Green", "Blue"):
        g.link(glow, 0, gl, ch)
    fl = g.mix(-300, -1100, "MULTIPLY", fac=1.0, a=g.out(pal, "water_foam"), b=only(gl.outputs))
    out = g.mix(-100, 400, fac=g.out(lines, 0), a=col, b=g.mixout(fl))
    # base glow at night: the water itself gives off a little light
    bg = g.math("MULTIPLY_ADD", -300, 200, g.out(pal, "water_glow"), 0.0, 1.0)
    bgc = g.n("ShaderNodeCombineColor", -150, 200)
    for ch in ("Red", "Green", "Blue"):
        g.link(bg, 0, bgc, ch)
    out = g.mix(100, 400, "MULTIPLY", fac=1.0, a=g.mixout(out), b=only(bgc.outputs))
    mo = shading._emit_out(g, g.mixout(out), 700, 400, pal=pal, haze=1.0)
    # real reflections (EEVEE ray tracing): the trees, rocks, clouds of THIS scene in the water, strongest at a
    # glancing angle, broken by small ripples; the painted toon colour stays underneath
    em_out = mo.inputs["Surface"].links[0].from_socket
    rn2 = g.n("ShaderNodeTexNoise", 500, 900, noise_dimensions="3D")
    g.set(rn2, "Scale", 5.0)
    g.set(rn2, "Detail", 2.0)
    rp = g.n("ShaderNodeCombineXYZ", 350, 900)
    g.link(pxyz, "X", rp, "X")
    g.link(g.math("MULTIPLY", 250, 850, pxyz.outputs["Y"], 1.6), 0, rp, "Y")
    g.link(g.math("MULTIPLY", 250, 800, t, 0.25), 0, rp, "Z")
    g.link(rp, 0, rn2, "Vector")
    bump = g.n("ShaderNodeBump", 650, 900)
    g.set(bump, "Strength", 0.025)
    g.set(bump, "Distance", 0.02)
    g.link(rn2, "Fac", bump, "Height")
    gl = g.n("ShaderNodeBsdfGlossy", 800, 900)
    g.set(gl, "Roughness", 0.03)
    g.link(bump, 0, gl, "Normal")
    lw = g.n("ShaderNodeLayerWeight", 650, 1100)
    g.set(lw, "Blend", 0.4)
    g.link(bump, 0, lw, "Normal")
    ramt = g.out(g.n("ShaderNodeAttribute", 650, 1250, attribute_name="hrp_refl", attribute_type="OBJECT"), "Fac")
    ramt = g.math("ADD", 750, 1250, ramt, 1.0)                                   # per body, neutral when missing
    rf = g.math("MULTIPLY", 800, 1100, g.out(lw, "Fresnel"), g.out(ramt, 0))
    rf = g.math("MULTIPLY_ADD", 900, 1100, g.out(rf, 0), 0.9, 0.06, clamp=True)
    rf = g.math("MULTIPLY", 950, 1050, g.out(rf, 0), only(g.math("SUBTRACT", 900, 1000, 1.0, rap).outputs))
    bdist = g.out(g.n("ShaderNodeAttribute", 700, 1350, attribute_name="hrp_boatd", attribute_type="GEOMETRY"), "Fac")
    bnear = _smooth(g, 850, 1350, bdist, 0.3, 2.2)                      # no mirror right round a hull
    bex = g.n("ShaderNodeAttribute", 700, 1450, attribute_name="hrp_boatd", attribute_type="GEOMETRY")
    bnear = g.math("MAXIMUM", 900, 1400, bnear, only(g.math("LESS_THAN", 800, 1450, g.out(bex, "Fac"), 0.0001).outputs))
    rf = g.math("MULTIPLY", 1000, 1100, g.out(rf, 0), g.out(bnear, 0))
    ms = g.n("ShaderNodeMixShader", 1000, 700)
    g.link(rf, 0, ms, "Factor")
    g.links.new(em_out, sock(ms.inputs, ("Shader", 0)))
    g.link(gl, 0, ms, ("Shader", 1))
    g.link(ms, 0, mo, "Surface")
    mat["hrp_kind"] = "water"
    drive_time(bpy.context.scene)
    drive_moon(mat)
    shading._done(mat, "water_material")
    return mat


def drive_moon(mat=None):
    """The water's Moon X/Y follow the moon painted in the Harappa sky (its 'moon dir')."""
    from .scene import WORLD
    mat = mat or bpy.data.materials.get(MAT_WATER)
    w = bpy.data.worlds.get(WORLD)
    if mat is None or w is None or not w.node_tree:
        return
    md = w.node_tree.nodes.get("moon dir")
    if md is None:
        return
    for k, ax in enumerate(("X", "Y")):
        nd = mat.node_tree.nodes.get("Moon" + ax)
        if nd is None:
            continue
        try:
            only(nd.outputs).driver_remove("default_value")
        except TypeError:
            pass
        only(nd.outputs).default_value = md.inputs[k].default_value


def time_group():
    """A one-value group 'Seconds' (driven) used only by the water: a changing frame doesn't touch the palette."""
    ng, rebuilt = fresh_group(TIME, "ShaderNodeTree", WATER_VER)
    if rebuilt:
        g = G(ng)
        iface(ng, "Seconds", "OUTPUT", "NodeSocketFloat")
        v = g.n("ShaderNodeValue", 0, 0, label="seconds")
        out = g.n("NodeGroupOutput", 200, 0)
        g.links.new(only(v.outputs), sock(out.inputs, "Seconds"))
    return ng


def drive_time(scene):
    """Seconds = frame / fps as a driver (a simple expression: works without auto-run scripts)."""
    ng = time_group()
    node = ng.nodes.get("seconds")
    if node is None or scene is None:
        return
    sock = only(node.outputs)
    try:
        sock.driver_remove("default_value")
    except TypeError:
        pass
    d = sock.driver_add("default_value").driver
    d.type = "SCRIPTED"
    for name, path in (("fps", "render.fps"), ("fb", "render.fps_base")):
        var = d.variables.new()
        var.name = name
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "SCENE"
        var.targets[0].id = scene
        var.targets[0].data_path = path
    d.expression = "frame * fb / fps"


# ----------------------------------------------------------------------------------------------
# objects
# ----------------------------------------------------------------------------------------------
def water_collection(scene):
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION)
    if coll.name not in scene.collection.children and not any(
            coll.name in c.children for c in bpy.data.collections):
        scene.collection.children.link(coll)
    return coll


def streams_collection(scene):
    parent = water_collection(scene)
    coll = bpy.data.collections.get(STREAMS)
    if coll is None:
        coll = bpy.data.collections.new(STREAMS)
    if coll.name not in parent.children:
        parent.children.link(coll)
    return coll


def is_water(ob):
    return ob is not None and ob.type == "CURVE" and ob.modifiers.get(SURFACE_MOD) is not None


def meadows(scene):
    return [o for o in scene.objects if o.type == "MESH" and o.get("hrp_ground") and not o.get("hrp_far_hills")]


def attach_carve(scene, ground):
    """Put the carve FIRST on a meadow (before grass and flowers) so they see the lowered ground and mask."""
    coll = water_collection(scene)
    mod = ground.modifiers.get(CARVE_MOD)
    if mod is None:
        mod = ground.modifiers.new(CARVE_MOD, "NODES")
    mod.node_group = carve_group()
    mod_input(mod, "Water", coll)
    mod_input(mod, "Streams", streams_collection(scene))
    mod_input(mod, "Terrain", terrain_collection(scene))
    idx = list(ground.modifiers).index(mod)
    if idx != 0:
        ground.modifiers.move(idx, 0)
    return mod


def _bake_transform(ob):
    """Water lies level in the world: a rotation or scale of the curve object (a circle added in front view, a curve
    squashed flat) goes into the curve itself, so the object keeps only its location."""
    from mathutils import Matrix, Quaternion, Vector
    _loc, rot, sca = ob.matrix_basis.decompose()
    if rot == Quaternion() and (sca - Vector((1.0, 1.0, 1.0))).length < 1e-6:
        return
    ob.data.transform(Matrix.LocRotScale(None, rot, sca))
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    ob.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def make_water(context, ob, width=1.4, depth=0.6, shelf=None, speed=0.6):
    """Turn a curve object into a pond (closed curve) or stream (open curve)."""
    scene = context.scene
    if ob.data.users == 1:
        _bake_transform(ob)
    coll = water_collection(scene)
    is_pond = any(sp.use_cyclic_u for sp in ob.data.splines)
    target = coll if is_pond else streams_collection(scene)
    for c in (coll, bpy.data.collections.get(STREAMS)):             # (the user's own collections are kept)
        if c is not None and c is not target and ob.name in c.objects:
            c.objects.unlink(ob)
    if ob.name not in target.objects:
        target.objects.link(ob)
    mod = ob.modifiers.get(SURFACE_MOD)
    if mod is None:
        mod = ob.modifiers.new(SURFACE_MOD, "NODES")
    mod.node_group = surface_group()
    mod_input(mod, "Width", width)
    mod_input(mod, "Depth", depth)
    mod_input(mod, "Shelf", shelf if shelf is not None else max(0.3, min(1.5, depth * 1.5)))
    mod_input(mod, "Flow Speed", speed)
    mod_input(mod, "Outlet", float(ob.get("hrp_outlet", 0.0)))
    mod_input(mod, "Mouth", float(ob.get("hrp_mouth", 0.0)))
    _pass_crossings(mod, ob)
    mod_input(mod, "Material", water_material())
    mod_input(mod, "Streams", streams_collection(scene) if is_pond else None)
    from . import rocks as _rk
    mod_input(mod, "Obstacles", _rk.props_collection(scene))
    ob.data.bevel_depth = 0.0
    ob.data.extrude = 0.0
    ob.visible_shadow = False
    ob["hrp_water"] = True
    from . import pondlife, rocks
    if is_pond and ob.modifiers.get(pondlife.LIFE_MOD) is None:
        pondlife.attach_life(ob)
    for gnd in meadows(scene):
        attach_carve(scene, gnd)
        if gnd.modifiers.get(rocks.SHORE_MOD) is None:
            rocks.attach_shore(scene, gnd)
    settle(context)
    refreeze(context)
    return mod


def _ground_bvhs(grounds):
    """BVH trees of the meadows' OWN meshes (before any modifier, so before the carve), in world space."""
    from mathutils.bvhtree import BVHTree
    out = []
    for gnd in grounds:
        me = gnd.data
        mw = gnd.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        out.append(BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in me.polygons]))
    return out


def _terraces(scene):
    """(polygon xy, top height, cliff width) of every terrace curve, world space."""
    out = []
    for o in scene.objects:
        if not o.get("hrp_terrace") or o.type != "CURVE":
            continue
        cliff = 0.9
        m = o.modifiers.get(TERRACE_MOD)
        if m is not None:
            try:
                cliff = float(mod_input(m, "Cliff"))
            except KeyError:
                pass
        for sp in o.data.splines:
            pts = list(sp.bezier_points if sp.type == "BEZIER" else sp.points)
            ws = [o.matrix_world @ p.co.to_3d() for p in pts]
            if len(ws) >= 3:
                out.append(([(w.x, w.y) for w in ws], sum(w.z for w in ws) / len(ws),
                            [cliff * p.radius for p in pts]))
    return out


def _edge_dist(poly, x, y, widths=None):
    """Distance to the polygon outline and (if given) the per-point width interpolated along the nearest edge."""
    best, w = 1e9, 1.0
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        vx, vy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy + 1e-12)))
        d = math.hypot(x - ax - t * vx, y - ay - t * vy)
        if d < best:
            best = d
            if widths is not None:
                w = widths[i] * (1 - t) + widths[(i + 1) % n] * t
    return (best, w) if widths is not None else best


def _ground_z(bvhs, x, y, terr=None):
    """Height of the meadow below x, y before the water carve (terraces included), or None.
    Repeated calls give the same answer."""
    from mathutils import Vector
    best = None
    for bvh in bvhs:
        hit = bvh.ray_cast(Vector((x, y, 1e5)), Vector((0.0, 0.0, -1.0)))
        if hit[0] is not None:
            z = hit[0].z
            best = z if best is None else max(best, z)
    if best is not None:
        for poly, top, cliffs in (terr or ()):
            if _inside(poly, x, y):
                d, cliff = _edge_dist(poly, x, y, cliffs)
                r = max(0.0, min(1.0, d / max(cliff, 1e-3)))
                r = r * r * (3 - 2 * r)
                best = max(best, best + (top - best) * r)
    return best


def pond_level(pond):
    """World height of a pond's water surface (its outline's mean height)."""
    pts = []
    for sp in pond.data.splines:
        pts += [pond.matrix_world @ p.co.to_3d() for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points)]
    return sum(p.z for p in pts) / max(1, len(pts))


def add_pond(context, center, radius=3.0, seed=0, depth=0.7, use_terrain=True):
    """A slightly irregular closed curve at the meadow height around center (world)."""
    import random
    scene = context.scene
    grounds = _ground_bvhs(meadows(scene))
    pts = [(center[0] + x, center[1] + y) for x, y in pond_outline(radius, seed)]
    terr = _terraces(scene) if use_terrain else None
    zs = [z for z in (_ground_z(grounds, x, y, terr) for x, y in pts) if z is not None]
    zc = _ground_z(grounds, center[0], center[1], terr)
    level = (sorted(zs)[len(zs) // 2] if zs else (zc if zc is not None else center[2])) - 0.06
    if zs:                                                       # fill and spill (see spill_level)
        level = min(level, max(level - 0.74, min(zs) - 0.06))
    cu = bpy.data.curves.new("Harappa Pond", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, (x, y) in zip(sp.bezier_points, pts):
        bp.co = (x - center[0], y - center[1], level)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.use_cyclic_u = True
    ob = bpy.data.objects.new("Harappa Pond", cu)
    ob.location = (center[0], center[1], 0.0)
    ob["hrp_pond"] = [radius, seed]
    water_collection(scene).objects.link(ob)
    context.view_layer.update()                                  # matrix_world must include the new location
    make_water(context, ob, depth=depth)
    return ob


def pond_outline(radius, seed, n=12):
    """Irregular, slightly oval shoreline (local xy around 0)."""
    import random
    rs = random.Random(seed * 131 + 7)
    ph = [rs.uniform(0, 6.28) for _ in range(4)]
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = radius * (1 + 0.16 * math.sin(2 * a + ph[0]) + 0.12 * math.sin(3 * a + ph[1])
                      + 0.06 * math.sin(5 * a + ph[2]) + 0.04 * math.sin(7 * a + ph[3]))
        out.append((math.cos(a) * r * 1.25, math.sin(a) * r))
    return out


def reshape_pond(context, ob, seed):
    """A new shoreline for a pond made by Add Pond (same size and level)."""
    info = ob.get("hrp_pond")
    if info is None:
        return False
    sp = ob.data.splines[0]
    pts = pond_outline(float(info[0]), seed, len(sp.bezier_points))
    for bp, (x, y) in zip(sp.bezier_points, pts):
        bp.co = (x, y, bp.co.z)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob["hrp_pond"] = [float(info[0]), seed]
    settle(context)
    refreeze(context)
    return True


def resize_pond(context, ob, size):
    """Scale the shoreline points around their centre (object scale stays 1, so pads keep their size)."""
    old = float(ob.get("hrp_size", 1.0))
    k = size / max(old, 1e-4)
    for sp in ob.data.splines:
        pts = list(sp.bezier_points if sp.type == "BEZIER" else sp.points)
        if not pts:
            continue
        cx = sum(p.co.x for p in pts) / len(pts)
        cy = sum(p.co.y for p in pts) / len(pts)
        for p in pts:
            if sp.type == "BEZIER":
                for attr in ("co", "handle_left", "handle_right"):
                    v = getattr(p, attr)
                    setattr(p, attr, (cx + (v.x - cx) * k, cy + (v.y - cy) * k, v.z))
            else:
                p.co = (cx + (p.co.x - cx) * k, cy + (p.co.y - cy) * k, p.co.z, p.co[3])
    ob["hrp_size"] = size
    mw = ob.matrix_world
    centre = mw @ type(mw.translation)((cx, cy, 0.0)) if pts else mw.translation
    for b in [o for o in context.scene.objects if o.get("hrp_boat") == ob.name]:   # boats keep their place
        b.location.x = centre.x + (b.location.x - centre.x) * k
        b.location.y = centre.y + (b.location.y - centre.y) * k
    settle(context)
    refreeze(context)


def set_look(ob, kind=None, **vals):
    """Water type and per-body tint, stored as object custom properties the shader reads."""
    from .util import srgb
    if kind is not None:
        _n, _d, clar, cols = WATER_TYPES[kind]
        vals = dict(vals)
        vals.setdefault("hrp_clarity", clar)                              # the tint the user set is kept
        old = ob.get("hrp_wtype", "SEASON")
        ob["hrp_wtype"] = kind
        life = ob.modifiers.get("Harappa Pond Life")                     # what grows depends on the water,
        if life is not None:                                             # unless the user chose the amount
            cur = float(mod_input(life, "Lily Pads"))
            if abs(cur - LILY_COVER.get(old, 0.6)) < 1e-3:
                mod_input(life, "Lily Pads", LILY_COVER[kind])
        ob["hrp_wuse"] = 0.0 if cols is None else 1.0
        for key, hx in zip(("hrp_wcol_s", "hrp_wcol_m", "hrp_wcol_d"), cols or ("#000000",) * 3):
            ob[key] = list(srgb(hx))
    for k, v in vals.items():
        ob[k] = float(v)
    ob["hrp_tint"] = [float(ob.get("hrp_hue", 0.0)), float(ob.get("hrp_sat", 0.0)), float(ob.get("hrp_val", 0.0))]
    ob.update_tag()


def water_bvhs(context):
    """[(BVH, (xmin, ymin, xmax, ymax))] of every evaluated water surface, world space: build once, test many points."""
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    out = []
    for o in context.scene.objects:
        if not is_water(o):
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        vs = [mw @ v.co for v in me.vertices]
        if vs:
            out.append((BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons]),
                        (min(v.x for v in vs), min(v.y for v in vs), max(v.x for v in vs), max(v.y for v in vs))))
        ev.to_mesh_clear()
    return out


def in_water(context, x, y, margin=0.35, z=None, above=0.8, bvhs=None):
    """True when x, y (world) is on a pond or stream, or within margin of one. With z, only when that height is at
    the water (no more than `above` over its surface): a tree on a rock, a roof or a cliff above the water is fine."""
    from mathutils import Vector
    for bvh, (x0, y0, x1, y1) in (bvhs if bvhs is not None else water_bvhs(context)):
        if x < x0 - margin or x > x1 + margin or y < y0 - margin or y > y1 + margin:
            continue
        for dx, dy in ((0, 0), (margin, 0), (-margin, 0), (0, margin), (0, -margin)):
            h = bvh.ray_cast(Vector((x + dx, y + dy, 1e4)), Vector((0, 0, -1)))[0]
            if h is not None and (z is None or z <= h.z + above):
                return True
    return False


def stepping_stones(context, stream, near, count=0):
    """Flat stones across the stream at the point nearest to `near`, tops just clear of the water."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from . import rocks
    dg = context.evaluated_depsgraph_get()
    ev = stream.evaluated_get(dg)
    me = ev.to_mesh()
    mw = stream.matrix_world
    vs = [mw @ v.co for v in me.vertices]
    bvh = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons])
    ev.to_mesh_clear()
    sp = stream.data.splines[0]
    pts = [mw @ p.co for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points)]
    pts = [Vector((p.x, p.y, p.z)) for p in pts]
    q = Vector((near[0], near[1]))
    best = None
    for a, b in zip(pts, pts[1:]):                                # nearest point on the centre line
        ab = (b - a).to_2d()
        t = max(0.0, min(1.0, (q - a.to_2d()).dot(ab) / max(ab.length_squared, 1e-9)))
        c = a.to_2d() + ab * t
        d = (q - c).length
        if best is None or d < best[0]:
            best = (d, c, ab.normalized())
    if best is None:
        return []
    _d, c, tang = best
    side = Vector((-tang.y, tang.x))
    hit = bvh.ray_cast(Vector((c.x, c.y, 1e4)), Vector((0, 0, -1)))
    if hit[0] is None:
        return []
    wz = hit[0].z
    half = 0.0                                                    # the water's half width here
    for k in range(1, 60):
        p = c + side * (k * 0.1)
        if bvh.ray_cast(Vector((p.x, p.y, 1e4)), Vector((0, 0, -1)))[0] is None:
            break
        half = k * 0.1
    n = count or max(3, int((half * 2 + 0.4) / 0.62) + 1)     # separate stones, water between them
    rs = random.Random(int(abs(c.x * 1000 + c.y * 37)))
    made = []
    for i in range(n):
        u = (i + 0.5) / n * 2 - 1
        p = c + side * (u * (half + 0.25)) + tang * rs.uniform(-0.12, 0.12)
        sz = rs.uniform(0.28, 0.36)
        rk = rocks.add_rock(context, (p.x, p.y, 0.0), sz, rs.randint(0, 9999), 0.45, ground_z=wz - sz * 0.3)
        rk["hrp_stone"] = stream.name
        made.append(rk)
    return made


def clear_trees(context, margin=1.0):
    """Nature's rule for trees that were there first: none left standing in new water or in front of a waterfall.
    Returns how many were removed."""
    sc = context.scene
    falls = [o for o in sc.objects if o.get("hrp_waterfall") is not None and o.get("hrp_wf_args") is not None]
    bvhs = water_bvhs(context)
    gone = 0
    for root in [o for o in sc.objects if o.get("hrp_tree") is not None and o.parent is None
                 and o.get("hrp_waterfall") is None]:
        p = root.matrix_world.translation
        bad = any((p.to_2d() - f.matrix_world.translation.to_2d()).length < f["hrp_wf_args"][6] * 0.5 + 3.5
                  and p.z < f["hrp_wf_args"][2] + f["hrp_wf_args"][5] * 0.5        # at the pool, not up on the hill
                  for f in falls) or in_water(context, p.x, p.y, margin, z=p.z, bvhs=bvhs)
        if bad:
            for o in [root] + list(root.children_recursive):
                bpy.data.objects.remove(o)
            gone += 1
    return gone


def _ponds(scene, skip=None):
    """(polygon xy, level) of every pond curve: its bezier/poly points in world space."""
    out = []
    for o in scene.objects:
        if o is skip or not is_water(o) or abs(o.matrix_world.determinant()) < 1e-12:   # (a squashed curve: no level)
            continue
        for sp in o.data.splines:
            if not sp.use_cyclic_u:
                continue
            pts = sp.bezier_points if sp.type == "BEZIER" else sp.points
            ws = [o.matrix_world @ p.co.to_3d() for p in pts]
            if len(ws) >= 3:
                out.append(([(w.x, w.y) for w in ws], sum(w.z for w in ws) / len(ws), o))
    return out


def _set_level(pond, z):
    """Move every point of a pond curve to world height z."""
    mw = pond.matrix_world
    inv = mw.inverted_safe()
    for sp in pond.data.splines:
        for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points):
            w = mw @ p.co.to_3d()
            new = inv @ type(w)((w.x, w.y, z))
            if sp.type == "BEZIER":
                d = new - p.co
                p.co = new
                p.handle_left = p.handle_left + d
                p.handle_right = p.handle_right + d
            else:
                p.co = (*new, p.co[3])


def _inside(poly, x, y):
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            c = not c
        j = i
    return c


def snap_stream(context, ob, below=0.06):
    """Drop an open curve onto the meadow so it runs downhill only (from its first point). Where it ends in a pond
    the two meet: if the stream arrives lower, the pond settles to its height; otherwise the mouth takes the pond
    level. Repeatable: it measures the meadow before the carve, so pressing it twice changes nothing.
    Returns the ponds it lowered."""
    lowered = []
    grounds = _ground_bvhs(meadows(context.scene))
    ponds = [] if ob.get("hrp_fall_feed") else _ponds(context.scene, skip=ob)   # a waterfall's stream ends at the lip
    mw = ob.matrix_world
    inv = mw.inverted_safe()
    # where the stream crosses into a pond, add a point right on the shore: inside the pond it must lie flat at the
    # pond's level (its slope happens on the bank), or the bed under its last stretch is dug to the pond's depth
    if not ob.get("hrp_fixed_z") and not ob.get("hrp_fall_feed"):
        _downhill_first(ob, grounds, ponds)
    if ponds and not ob.get("hrp_fixed_z"):
        _join_ends(ob, ponds)
        _shore_points(ob, ponds)
    for sp in ob.data.splines:
        pts = list(sp.bezier_points if sp.type == "BEZIER" else sp.points)
        cos = [mw @ p.co.to_3d() for p in pts]
        zs = []
        terr = _terraces(context.scene)
        for co in cos:
            z = _ground_z(grounds, co.x, co.y, terr)
            z = (co.z if z is None else z) - below
            if zs:
                z = min(z, zs[-1])
            zs.append(z)
        locked = set()                                       # points held at a pond's level
        for poly, lvl, pond in ponds:
            inside = [k for k, co in enumerate(cos) if _inside(poly, co.x, co.y)]
            locked.update(inside)
            if not inside:
                continue
            # an outlet (the stream starts in this pond) flows OUT at the pond's level: it never pulls the pond down
            # (a lowered pool left a waterfall's foot hanging above the water)
            head = 0
            while head < len(cos) and head in inside:
                head += 1
            if head:
                for k in range(len(zs)):
                    zs[k] = lvl - 0.015 if k < head else min(zs[k], lvl - 0.015)
                inside = [k for k in inside if k >= head]
                if not inside:
                    continue
            low = max(min(zs[k] for k in inside), lvl - 0.8)
            if low < lvl - 0.015:                            # the stream arrives lower: the pond settles to meet it
                _set_level(pond, low + 0.015)
                lowered.append(pond)
                lvl = low + 0.015
            for k in inside:
                zs[k] = lvl - 0.015
            for k in range(max(inside) + 1, len(zs)):          # a stream running on out of the pond starts at its level
                zs[k] = min(zs[k], lvl - 0.015)
            # ...and it grades down to the mouth gently (it cuts its way into the bank), never a chute at the end
            k0 = min(inside)
            run = 0.0
            for k in range(k0 - 1, -1, -1):
                run += (cos[k + 1] - cos[k]).to_2d().length
                zs[k] = min(zs[k], lvl - 0.015 + 0.12 * run)
        outlet, mouth, exit_p, entry_p = _crossings(cos, ponds)
        ob["hrp_outlet"], ob["hrp_mouth"] = float(outlet), float(mouth)
        ob["hrp_exit"] = list(inv @ exit_p) if exit_p is not None else [0.0, 0.0, 0.0]
        ob["hrp_entry"] = list(inv @ entry_p) if entry_p is not None else [0.0, 0.0, 0.0]
        for k in range(len(zs) - 2, -1, -1):                 # never uphill after the lift
            zs[k] = max(zs[k], zs[k + 1])
        if "hrp_fixed_z" in ob:
            zs = [float(ob["hrp_fixed_z"])] * len(zs)
        else:
            zs = _step_profile(cos, zs, locked, float(ob.get("hrp_width", 1.0)))
        for p, co, z in zip(pts, cos, zs):
            new = inv @ type(co)((co.x, co.y, z))
            if sp.type == "BEZIER":
                d = new - p.co
                p.co = new
                p.handle_left = p.handle_left + d
                p.handle_right = p.handle_right + d
            else:
                p.co = (*new, p.co[3])
        if sp.type == "BEZIER" and "hrp_fixed_z" not in ob and len(pts) > 2:
            _level_handles(sp)
    return lowered


def _step_profile(cos, zs, locked, width):
    """A steep stream is a staircase of calm pools and short drops, never a smooth chute (Montgomery & Buffington
    1997: above ~6 % slope, steps every 1-4 channel widths). Each pool is cut into the slope at the level of its lower
    end, so the water only ever goes down from where it was: it stays under its banks."""
    n = len(zs)
    zs = list(zs)
    d = [0.0]
    for k in range(1, n):
        d.append(d[-1] + (cos[k] - cos[k - 1]).to_2d().length)
    pool = max(0.9, 1.8 * width)
    k = 0
    while k < n - 2:
        if k in locked:
            k += 1
            continue
        j = k + 1
        while j < n - 1 and d[j] - d[k] < pool and (j + 1) not in locked:
            j += 1
        run = max(1e-3, d[j] - d[k])
        if (zs[k] - zs[j]) / run > 0.06 and j - k >= 2:
            for m in range(k + 1, j):
                zs[m] = zs[j]
        k = j
    return zs


def _level_handles(sp):
    """Bezier handles lie flat (the water's level between points): no bump up before a drop, and a step reads as a
    smooth lip and a fall, not an overshoot."""
    bp = sp.bezier_points
    n = len(bp)
    for i, p in enumerate(bp):
        a = bp[max(0, i - 1)].co
        b = bp[min(n - 1, i + 1)].co
        t = (b - a).to_2d()
        if t.length < 1e-6:
            continue
        t.normalize()
        l1 = (p.co - a).to_2d().length / 3.0 if i > 0 else 0.1
        l2 = (b - p.co).to_2d().length / 3.0 if i < n - 1 else 0.1
        # a drop falls right over the lip and runs out below (the ground falls away there too), not a symmetric S
        if i < n - 1 and p.co.z - b.z > 0.05:
            l2 = (b - p.co).to_2d().length * 0.06
        if i > 0 and a.z - p.co.z > 0.05:
            l1 = (p.co - a).to_2d().length * 0.6
        p.handle_left_type = p.handle_right_type = "FREE"
        p.handle_left = (p.co.x - t.x * l1, p.co.y - t.y * l1, p.co.z)
        p.handle_right = (p.co.x + t.x * l2, p.co.y + t.y * l2, p.co.z)


def _crossings(cos, ponds):
    """Along a stream's control points (world): does it leave a pond / run into one, and where it crosses each shore.
    A stream counts as running into a pond when it enters one after starting outside it (its end may lie anywhere
    under the pond)."""
    def bisect(poly, a, b, a_in):
        lo, hi = 0.0, 1.0
        for _ in range(20):
            mid = (lo + hi) / 2
            if _inside(poly, *a.lerp(b, mid).to_2d()) == a_in:
                lo = mid
            else:
                hi = mid
        return a.lerp(b, (lo + hi) / 2)
    exit_p = entry_p = None
    for poly, _l, _p in ponds:
        ins = [_inside(poly, c.x, c.y) for c in cos]
        if ins and ins[0] and exit_p is None:
            k = next((i for i in range(1, len(cos)) if not ins[i]), None)
            if k is not None:
                exit_p = bisect(poly, cos[k - 1], cos[k], True)
        start = next((i for i in range(len(cos)) if not ins[i]), None)
        if start is None:
            continue
        k = next((i for i in range(start + 1, len(cos)) if ins[i] and not ins[i - 1]), None)
        if k is not None and entry_p is None and all(ins[k:]):     # it ends there (one passing through runs on)
            entry_p = bisect(poly, cos[k - 1], cos[k], False)
    return exit_p is not None, entry_p is not None, exit_p, entry_p


def _pass_crossings(mod, ob):
    for key, sock_ in (("hrp_exit", "Outflow Point"), ("hrp_entry", "Inflow Point")):
        try:
            mod_input(mod, sock_, tuple(float(v) for v in ob.get(key, (0.0, 0.0, 0.0))))
        except (KeyError, TypeError):
            pass


def _downhill_first(ob, grounds, ponds=(), rise=0.25):
    """Water runs downhill: a stream drawn from low ground up to high ground is turned round (its first point is its
    spring), instead of digging a trench uphill and pulling the pond at its end down."""
    mw = ob.matrix_world
    for sp in ob.data.splines:
        if sp.type != "BEZIER" or sp.use_cyclic_u or len(sp.bezier_points) < 2:
            continue
        a, b = mw @ sp.bezier_points[0].co, mw @ sp.bezier_points[-1].co
        if any(_inside(poly, a.x, a.y) for poly, _l, _p in ponds):      # it flows out of a pond: that is its source
            continue
        za, zb = _ground_z(grounds, a.x, a.y), _ground_z(grounds, b.x, b.y)
        if za is None or zb is None or zb <= za + rise:
            continue
        pts = [(p.co.copy(), p.handle_left.copy(), p.handle_right.copy(), p.handle_left_type, p.handle_right_type)
               for p in sp.bezier_points]
        for p, (co, hl, hr, tl, tr) in zip(sp.bezier_points, reversed(pts)):
            p.handle_left_type, p.handle_right_type = "FREE", "FREE"
            p.co, p.handle_left, p.handle_right = co, hr, hl
            p.handle_left_type, p.handle_right_type = tr, tl


def _poly_near(poly, x, y):
    """(distance, nearest point) from x, y to a closed polygon's outline."""
    from mathutils import Vector
    p = Vector((x, y))
    best = (1e9, None)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        a, b = Vector(a), Vector(b)
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
        q = a + ab * t
        d = (p - q).length
        if d < best[0]:
            best = (d, q)
    return best


def _join_ends(ob, ponds, reach=1.2, into=0.9):
    """A stream drawn up to a pond (its end within `reach` of the shore) runs into it; one that starts beside a pond
    flows out of it. The end is carried across the shore, so the two always meet (repeatable)."""
    mw = ob.matrix_world
    inv = mw.inverted_safe()
    for sp in ob.data.splines:
        if sp.type != "BEZIER" or sp.use_cyclic_u or len(sp.bezier_points) < 2:
            continue
        for end in (-1, 0):
            pts = [mw @ p.co.to_3d() for p in sp.bezier_points]
            c = pts[end]
            if any(_inside(poly, c.x, c.y) for poly, _l, _p in ponds):
                continue
            near = min((_poly_near(poly, c.x, c.y) + (poly,) for poly, _l, _p in ponds), key=lambda t: t[0])
            if near[0] > reach or near[1] is None:
                continue
            d = (near[1] - c.to_2d())
            d = d.normalized() if d.length > 1e-4 else (c - pts[-2 if end == -1 else 1]).to_2d().normalized()
            q = near[1] + d * into
            if not _inside(near[2], q.x, q.y):
                continue
            new = inv @ type(c)((q.x, q.y, c.z))
            sp.bezier_points.add(1)
            bps = sp.bezier_points
            if end == 0:                                           # shift everything one place to make room
                for i in range(len(bps) - 1, 0, -1):
                    bps[i].co = bps[i - 1].co.copy()
                bps[0].co = new
            else:
                bps[-1].co = new
            for bp in bps:
                bp.handle_left_type = bp.handle_right_type = "AUTO"


def _shore_points(ob, ponds):
    """Insert a control point where an open curve first enters a pond (once; repeatable)."""
    mw = ob.matrix_world
    inv = mw.inverted_safe()
    for sp in ob.data.splines:
        if sp.type != "BEZIER" or sp.use_cyclic_u:
            continue
        pts = [mw @ p.co.to_3d() for p in sp.bezier_points]
        for poly, _lvl, _pond in ponds:
            ins = [_inside(poly, c.x, c.y) for c in pts]
            k = next((i for i in range(1, len(pts)) if ins[i] and not ins[i - 1]), None)
            if k is None:
                continue
            a, b = pts[k - 1], pts[k]
            lo, hi = 0.0, 1.0
            for _ in range(18):
                mid = (lo + hi) / 2
                q = a.lerp(b, mid)
                if _inside(poly, q.x, q.y):
                    hi = mid
                else:
                    lo = mid
            q = a.lerp(b, hi)
            if min((q - a).length, (b - q).length) < 0.25:           # already a point on the shore
                continue
            pts.insert(k, q)
            sp.bezier_points.add(1)
            for bp, c in zip(sp.bezier_points, pts):
                bp.co = inv @ c
                bp.handle_left_type = bp.handle_right_type = "AUTO"
            break


def sync_boats(context):
    """A boat floats at its pond's level, wherever the level ended up (a spill level, a stream lowering it)."""
    for b in context.scene.objects:
        pond = bpy.data.objects.get(b.get("hrp_boat", "")) if b.get("hrp_boat") else None
        if pond is not None and is_water(pond):
            lv = pond_level(pond)
            if abs(b.location.z - lv) > 1e-4:
                b.location.z = lv


def sync_falls(context):
    """A waterfall's sheet ends exactly on its pool's surface, wherever the pool's level ended up."""
    from .util import mod_input as _mi
    try:
        context.view_layer.update()                                  # a fall placed a moment ago: fresh matrices
    except Exception:
        pass
    for o in context.scene.objects:
        m = o.modifiers.get("Harappa Waterfall")
        tag = o.get("hrp_waterfall")
        if m is None or tag is None:
            continue
        pool = next((p for p in context.scene.objects if p.get("hrp_waterfall") == tag and is_water(p)
                     and any(s_.use_cyclic_u for s_ in p.data.splines)), None)
        if pool is not None:
            try:
                _mi(m, "Drop", max(0.2, o.matrix_world.translation.z - pond_level(pool)))
            except KeyError:
                pass


def spill_level(scene, pond, grounds=None, terr=None):
    """Fill and spill: a pond's water stands just under the lowest point of its rim, where it would overflow, never
    above the ground around it (on a slope it is dug into the hill, not held up by a dam). On a very steep slope it
    is dug in at most 0.8 m below its average rim and the rest is held by its bank."""
    grounds = grounds if grounds is not None else _ground_bvhs(meadows(scene))
    terr = terr if terr is not None else _terraces(scene)
    rim = []
    for sp in pond.data.splines:
        if not sp.use_cyclic_u:
            continue
        ws = [pond.matrix_world @ p.co.to_3d() for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points)]
        for a, b in zip(ws, ws[1:] + ws[:1]):
            for k in range(6):
                q = a.lerp(b, k / 6)
                z = _ground_z(grounds, q.x, q.y, terr)
                if z is not None:
                    rim.append(z)
    if not rim:
        return None
    med = sorted(rim)[len(rim) // 2]
    return min(med - 0.06, max(med - 0.8, min(rim) - 0.06))


def _spill_ponds(context):
    grounds = _ground_bvhs(meadows(context.scene))
    terr = _terraces(context.scene)
    for o in context.scene.objects:
        if (not is_water(o) or o.get("hrp_waterfall") or o.get("hrp_level_fixed")
                or not any(sp.use_cyclic_u for sp in o.data.splines)):
            continue                                                 # (a waterfall's pool is dug in by the fall)
        lv = spill_level(context.scene, o, grounds, terr)
        if lv is not None and abs(lv - pond_level(o)) > 1e-4:
            _set_level(o, lv)
    ps = [(poly, o) for poly, _l, o in _ponds(context.scene) if not o.get("hrp_waterfall")]
    for i, (pa, a) in enumerate(ps):                           # ponds that overlap share the lower level
        for pb, b in ps[i + 1:]:
            if any(_inside(pb, *q) for q in pa) or any(_inside(pa, *q) for q in pb):
                lo = min(pond_level(a), pond_level(b))
                for o in (a, b):
                    if abs(pond_level(o) - lo) > 1e-4:
                        _set_level(o, lo)


def settle(context):
    """Make every stream that runs into a pond agree with it, whatever was made first (a lowered pond can pull
    other streams with it, so repeat until nothing changes). Ponds first find their own spill level, so the result
    never depends on the order things were made in."""
    _spill_ponds(context)
    for _ in range(4):
        moved = False
        ponds = _ponds(context.scene)
        for o in list(context.scene.objects):
            if not is_water(o) or o.get("hrp_fall_feed") or any(sp.use_cyclic_u for sp in o.data.splines):
                continue
            mw = o.matrix_world
            touches = any(_inside(poly, (mw @ p.co.to_3d()).x, (mw @ p.co.to_3d()).y)
                          for poly, _l, _p in ponds for sp in o.data.splines
                          for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points))
            touches = touches or any(_poly_near(poly, (mw @ p.co.to_3d()).x, (mw @ p.co.to_3d()).y)[0] < 1.2
                                     for poly, _l, _p in ponds for sp in o.data.splines
                                     for p in ((sp.bezier_points[0], sp.bezier_points[-1]) if sp.type == "BEZIER"
                                               and len(sp.bezier_points) else ()))
            stale = not touches and (o.get("hrp_outlet") or o.get("hrp_mouth"))   # its pond is gone
            if (touches or stale) and snap_stream(context, o):
                moved = True
            m_ = o.modifiers.get(SURFACE_MOD)
            if m_ is not None and (touches or stale):
                try:
                    mod_input(m_, "Outlet", float(o.get("hrp_outlet", 0.0)))
                    mod_input(m_, "Mouth", float(o.get("hrp_mouth", 0.0)))
                    _pass_crossings(m_, o)
                except KeyError:
                    pass
        if not moved:
            break
    sync_falls(context)
    sync_boats(context)


def add_stream(context, points, width=1.4, depth=0.45, feeds_fall=False, fixed_z=None):
    """Open curve through world points (first = upstream), dropped onto the meadow."""
    cu = bpy.data.curves.new("Harappa Stream", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = (p[0], p[1], p[2] if len(p) > 2 else 0.0)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new("Harappa Stream", cu)
    if feeds_fall:
        ob["hrp_fall_feed"] = True
    if fixed_z is not None:
        ob["hrp_fixed_z"] = float(fixed_z)                     # a waterfall's stream: level, on its terrace
    ob["hrp_width"] = float(width)                              # (the step-pools are spaced by it)
    water_collection(context.scene).objects.link(ob)
    snap_stream(context, ob)
    make_water(context, ob, width=width, depth=depth)
    return ob


def remove_water(context, ob):
    coll = bpy.data.collections.get(COLLECTION)
    name = ob.name
    gone = list(ob.children_recursive)                         # its koi...
    for o in list(context.scene.objects):                      # ...and the boats floating on it
        if o.get("hrp_boat") == name or o.get("hrp_fish") == name:
            gone += [o] + list(o.children_recursive)
    for o in {x.name: x for x in gone}.values():
        if o.name in bpy.data.objects and o is not ob:
            bpy.data.objects.remove(o)
    data = ob.data
    bpy.data.objects.remove(ob)
    if data is not None and data.users == 0:
        bpy.data.curves.remove(data)
    tc = bpy.data.collections.get(TERRAIN)
    if coll is not None and not coll.all_objects and (tc is None or not tc.all_objects):
        for gnd in meadows(context.scene):
            m = gnd.modifiers.get(CARVE_MOD)
            if m is not None:
                gnd.modifiers.remove(m)
    settle(context)                                              # streams that ran into it lie back on the meadow
    refreeze(context)
