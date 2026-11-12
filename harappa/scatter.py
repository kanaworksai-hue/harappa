# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry Nodes groups.

HRP Wind     two-layer wind (slow travelling wave + fast flutter), shared by everything that moves
HRP Grass    tufts scattered on a ground by a paintable mask, kept as instances (light), with the
             ground normal / mask / wind wave stored per instance for the shader
HRP Flowers  camera-facing flower cards sitting in the grass tops, in colour clusters
HRP Foliage  camera-facing leaf / blossom cards on a canopy mesh, with canopy normal + depth

Brush layers: point colour attributes on the ground, each one "no change" when it is missing (see layers.py).
hrp_grass (white = grass), hrp_flowers (0.5 = the natural patches, 1 = flowers everywhere, 0 = none),
hrp_height (0.5 = x1, 1 = x2, 0 = flat) and hrp_tint (painted colour, alpha = amount; read by the materials).
"""
import math

import bpy

from .util import G, fresh_group, iface, stamp

GN_VER = 29
WIND = "HRP Wind"
GRASS = "HRP Grass"
FLOWERS = "HRP Flowers"
FOLIAGE = "HRP Foliage"
MASK_ATTR = "hrp_grass"
FLOWERS_ATTR = "hrp_flowers"
HEIGHT_ATTR = "hrp_height"
TINT_ATTR = "hrp_tint"


def _store(g, x, y, geo_sock, name, value_sock, dtype="FLOAT", domain="POINT"):
    st = g.n("GeometryNodeStoreNamedAttribute", x, y, data_type=dtype, domain=domain)
    g.links.new(geo_sock, st.inputs["Geometry"])
    st.inputs["Name"].default_value = name
    kind = {"FLOAT": "VALUE", "FLOAT_VECTOR": "VECTOR", "INT": "INT"}[dtype]
    g.links.new(value_sock, g.inp(st, "Value", kind))
    return g.out(st)


def _rand(g, x, y, lo, hi, seed_sock=None, seed_off=0):
    r = g.n("FunctionNodeRandomValue", x, y, data_type="FLOAT")
    g.set(r, "Min", lo, "VALUE")
    g.set(r, "Max", hi, "VALUE")
    if seed_sock is not None:
        add = g.n("FunctionNodeIntegerMath", x - 160, y - 120) if hasattr(bpy.types, "FunctionNodeIntegerMath") else None
        if add is not None:
            add.operation = "ADD"
            g.link(seed_sock, None, add, ("Value", 0))
            g.set(add, ("Value", 1), seed_off)
            g.links.new(g.out(add), r.inputs["Seed"])
        else:
            g.links.new(seed_sock, r.inputs["Seed"])
    else:
        r.inputs["Seed"].default_value = seed_off
    return g.out(r, "Value", "VALUE")


def _mask(g, gi, x, y):
    """Painted mask (named attribute, 1 when missing), its edge broken up by noise so paths look worn."""
    na = g.n("GeometryNodeInputNamedAttribute", x, y, data_type="FLOAT")
    g.link(gi, "Mask Attribute", na, "Name")
    sw = g.n("GeometryNodeSwitch", x + 180, y, input_type="FLOAT")
    g.link(na, "Exists", sw, "Switch")
    sw.inputs["False"].default_value = 1.0
    g.link(na, "Attribute", sw, "True")
    pos = g.n("GeometryNodeInputPosition", x, y - 200)
    nz = g.n("ShaderNodeTexNoise", x + 180, y - 200, noise_dimensions="2D")
    g.set(nz, "Scale", 1.6)
    g.set(nz, "Detail", 3.0)
    g.link(pos, 0, nz, "Vector")
    edge = g.math("MULTIPLY", x + 360, y - 100, g.out(sw), g.out(g.math("SUBTRACT", x + 200, y - 50, 1.0,
                  g.out(sw))))
    wob = g.math("SUBTRACT", x + 360, y - 250, g.out(nz, "Fac"), 0.5)
    amt = g.math("MULTIPLY", x + 520, y - 200, g.out(wob), g.out(edge))
    out = g.math("MULTIPLY_ADD", x + 680, y - 100, g.out(amt), 3.0, g.out(sw), clamp=True)
    return g.out(out)


def _layer(g, x, y, name, default):
    """A painted brush layer as a number (the colour's grey), or the default when the ground has no such layer."""
    na = g.n("GeometryNodeInputNamedAttribute", x, y, data_type="FLOAT")
    na.inputs["Name"].default_value = name
    sw = g.n("GeometryNodeSwitch", x + 180, y, input_type="FLOAT")
    g.link(na, "Exists", sw, "Switch")
    sw.inputs["False"].default_value = default
    g.link(na, "Attribute", sw, "True")
    return g.out(sw)


def _height_layer(g, x, y):
    """Height multiplier from the Height layer: 0.5 (and no layer) = x1, white = x2, black = flat."""
    return g.out(g.math("MULTIPLY", x + 380, y, _layer(g, x, y, HEIGHT_ATTR, 0.5), 2.0))


def _preview(g, gi, x, y):
    """Preview Factor in the viewport only (lighter grass while painting), 1 in renders."""
    vp = g.n("GeometryNodeIsViewport", x, y)
    sw = g.n("GeometryNodeSwitch", x + 180, y, input_type="FLOAT")
    g.link(vp, 0, sw, "Switch")
    sw.inputs["False"].default_value = 1.0
    g.link(gi, "Preview Factor", sw, "True")
    return g.out(sw)


# ----------------------------------------------------------------------------------------------
def wind_group():
    ng, rebuilt = fresh_group(WIND, "GeometryNodeTree", GN_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Position", "INPUT", "NodeSocketVector")
    iface(ng, "Strength", "INPUT", "NodeSocketFloat", 0.25)
    iface(ng, "Speed", "INPUT", "NodeSocketFloat", 1.2)
    iface(ng, "Scale", "INPUT", "NodeSocketFloat", 5.0)
    iface(ng, "Direction", "INPUT", "NodeSocketFloat", 0.6, subtype="ANGLE")
    iface(ng, "Flutter", "INPUT", "NodeSocketFloat", 0.35)
    iface(ng, "Angle", "OUTPUT", "NodeSocketFloat")
    iface(ng, "Axis", "OUTPUT", "NodeSocketVector")
    iface(ng, "Dir", "OUTPUT", "NodeSocketVector")
    iface(ng, "Wave", "OUTPUT", "NodeSocketFloat")
    gi = g.n("NodeGroupInput", -1200, 0)
    go = g.n("NodeGroupOutput", 1000, 0)
    t = g.n("GeometryNodeInputSceneTime", -1200, -300)
    cs = g.math("COSINE", -1000, 300, g.out(gi, "Direction"))
    sn = g.math("SINE", -1000, 150, g.out(gi, "Direction"))
    d = g.n("ShaderNodeCombineXYZ", -800, 250)
    g.link(cs, 0, d, "X")
    g.link(sn, 0, d, "Y")
    nsn = g.math("MULTIPLY", -800, 50, g.out(sn), -1.0)
    ax = g.n("ShaderNodeCombineXYZ", -600, 50)
    g.link(nsn, 0, ax, "X")
    g.link(cs, 0, ax, "Y")
    # travelling wave: sample noise at P - dir * t * speed
    ts = g.math("MULTIPLY", -800, -300, g.out(t, "Seconds"), g.out(gi, "Speed"))
    sh = g.vmath("SCALE", -600, -200, g.out(d), scale=g.out(ts))
    p2 = g.vmath("SUBTRACT", -400, -100, g.out(gi, "Position"), g.out(sh))
    p3 = g.vmath("DIVIDE", -200, -100, g.out(p2))
    sc = g.n("ShaderNodeCombineXYZ", -400, -300)
    for c in "XYZ":
        g.link(gi, "Scale", sc, c)
    g.link(sc, 0, p3, ("Vector", 1))
    wv = g.n("ShaderNodeTexNoise", 0, -100, noise_dimensions="2D")
    g.set(wv, "Scale", 1.0)
    g.set(wv, "Detail", 1.5)
    g.link(p3, 0, wv, "Vector")
    wave = g.maprange(200, -100, g.out(wv, "Fac"), 0.3, 0.72)
    # fast flutter: 4D noise at 4x the frequency
    fl = g.n("ShaderNodeTexNoise", 0, -400, noise_dimensions="4D")
    g.set(fl, "Scale", 4.0)
    g.set(fl, "Detail", 0.0)                 # one smooth octave: neighbours move together (no shimmering)
    g.link(p3, 0, fl, "Vector")
    tw = g.math("MULTIPLY", -200, -500, g.out(ts), 0.9)
    g.link(tw, 0, fl, "W")
    flc = g.math("SUBTRACT", 200, -400, g.out(fl, "Fac"), 0.5)
    flm = g.math("MULTIPLY", 380, -400, g.out(flc), g.out(gi, "Flutter"))
    # angle = strength * (0.25 + 1.5 * wave + 3 * flutter)
    a1 = g.math("MULTIPLY_ADD", 400, -100, g.out(wave, "Result"), 1.5, 0.25)
    a2 = g.math("MULTIPLY_ADD", 580, -250, g.out(flm), 3.0, g.out(a1))
    ang = g.math("MULTIPLY", 760, -100, g.out(a2), g.out(gi, "Strength"))
    g.link(ang, 0, go, "Angle")
    g.link(ax, 0, go, "Axis")
    g.link(d, 0, go, "Dir")
    g.link(wave, "Result", go, "Wave")
    stamp(ng, GN_VER)
    return ng


def _wind_node(g, gi, x, y, pos_sock, flutter=False):
    w = g.n("GeometryNodeGroup", x, y)
    w.node_tree = wind_group()
    g.links.new(pos_sock, w.inputs["Position"])
    for k in ("Strength", "Speed", "Scale", "Direction"):
        g.link(gi, "Wind " + k, w, k)
    if flutter:
        g.link(gi, "Wind Flutter", w, "Flutter")
    return w


def _wind_inputs(ng, strength):
    iface(ng, "Wind Strength", "INPUT", "NodeSocketFloat", strength, 0.0, 2.0,
          desc="How far the wind bends things")
    iface(ng, "Wind Speed", "INPUT", "NodeSocketFloat", 1.2, 0.0, 20.0, desc="Metres per second the gusts travel")
    iface(ng, "Wind Scale", "INPUT", "NodeSocketFloat", 5.0, 0.05, 1000.0, desc="Size of the gusts in metres")
    iface(ng, "Wind Direction", "INPUT", "NodeSocketFloat", 0.6, desc="Direction the wind blows towards",
          subtype="ANGLE")


def _avoid_inputs(ng):
    iface(ng, "Avoid", "INPUT", "NodeSocketCollection",
          desc="Objects the grass grows around but never through (characters, rocks, houses)")
    iface(ng, "Avoid Margin", "INPUT", "NodeSocketFloat", 0.16, 0.0, 10.0, subtype="DISTANCE",
          desc="Grass gets shorter within this distance of the avoided objects")
    iface(ng, "Avoid Floor", "INPUT", "NodeSocketFloat", 0.3, 0.0, 1.0, subtype="FACTOR",
          desc="Height of the grass right against an avoided object (it also leans away from it)")
    iface(ng, "Avoid Box", "INPUT", "NodeSocketBool", False,
          desc="Faster: treat each avoided object as its bounding box (heavy models, crowds)")
    iface(ng, "Avoid Reach", "INPUT", "NodeSocketFloat", 100.0, 0.0, 100000.0, subtype="DISTANCE",
          desc="How far above a root an avoided object still clears the grass under it")
    iface(ng, "Preview Factor", "INPUT", "NodeSocketFloat", 1.0, 0.0, 1.0, subtype="FACTOR",
          desc="Share of the grass drawn in the viewport (lowered while painting); renders always draw all of it")


def _avoid(g, gi, x, y, pts, reach, keep_gap=0.04):
    """Delete points under / against the 'Avoid' objects and return (points, factor field 0..1).

    Under = a ray straight up from the root hits the object (so nothing grows inside or below it). Next to it, the
    distance to the object's surface scales the blade: short right against it, full height past the margin.
    With an empty collection nothing changes (factor 1)."""
    ci = g.n("GeometryNodeCollectionInfo", x, y, transform_space="RELATIVE")
    g.link(gi, "Avoid", ci, "Collection")
    g.set(ci, "Separate Children", True)                 # one instance per object: one box per object
    rz0 = g.n("GeometryNodeRealizeInstances", x + 180, y)
    g.link(ci, 0, rz0, "Geometry")
    # Box mode: each object's bounding box (a For Each zone over the instances; the Bounding Box node alone would
    # give one box around all of them). The switch only evaluates the side it uses.
    zi = g.n("GeometryNodeForeachGeometryElementInput", x, y + 400)
    zo = g.n("GeometryNodeForeachGeometryElementOutput", x + 540, y + 400)
    zi.pair_with_output(zo)
    zo.domain = "INSTANCE"
    g.link(ci, 0, zi, "Geometry")
    zr = g.n("GeometryNodeRealizeInstances", x + 180, y + 400)
    g.link(zi, "Element", zr, "Geometry")
    bb = g.n("GeometryNodeBoundBox", x + 360, y + 400)
    g.link(zr, 0, bb, "Geometry")
    g.link(bb, "Bounding Box", zo, "Geometry")
    rz = g.n("GeometryNodeSwitch", x + 720, y + 200, input_type="GEOMETRY")
    g.link(gi, "Avoid Box", rz, "Switch")
    g.link(rz0, 0, rz, "False")
    g.link(zo, ("Geometry", 1), rz, "True")              # the zone's generated geometry, not its main output
    cnt = g.n("GeometryNodeAttributeDomainSize", x + 360, y + 200, component="MESH")
    g.link(rz, 0, cnt, "Geometry")
    has = g.math("GREATER_THAN", x + 540, y + 200, g.out(cnt, "Face Count"), 0.5)
    rc = g.n("GeometryNodeRaycast", x + 360, y - 100)
    g.link(rz, 0, rc, "Target Geometry")
    rc.inputs["Ray Direction"].default_value = (0.0, 0.0, 1.0)
    g.link(gi, "Avoid Reach", rc, "Ray Length")            # "under" = anything above the root (also inside big objects)
    px = g.n("GeometryNodeProximity", x + 360, y - 400, target_element="FACES")
    g.link(rz, 0, px, "Geometry")
    # roots inside a sunken object (e.g. the hollow of an ear lying in the ground) see it right below them
    rcd = g.n("GeometryNodeRaycast", x + 360, y - 250)
    g.link(rz, 0, rcd, "Target Geometry")
    rcd.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0)
    rcd.inputs["Ray Length"].default_value = 0.15
    under_any = g.math("MAXIMUM", x + 700, y - 200, g.out(rc, "Is Hit"), g.out(rcd, "Is Hit"))
    kill = g.math("MULTIPLY", x + 860, y - 200, g.out(under_any), g.out(has))
    dl = g.n("GeometryNodeDeleteGeometry", x + 1000, y, domain="POINT")
    g.links.new(pts, dl.inputs["Geometry"])
    g.link(kill, 0, dl, "Selection")
    # continuous: zero height right at the surface, full height past the margin (no popping as things move)
    near = g.maprange(x + 700, y - 500, g.out(px, "Distance"), keep_gap * 0.25, g.out(gi, "Avoid Margin"), 1.0, 0.0,
                      smooth=True)                              # 1 at the surface .. 0 past the margin
    nearh = g.math("MULTIPLY", x + 860, y - 450, g.out(near, "Result"), g.out(has))
    drop = g.math("SUBTRACT", x + 860, y - 550, 1.0, g.out(gi, "Avoid Floor"))
    cut = g.math("MULTIPLY", x + 1000, y - 500, g.out(nearh), g.out(drop))
    f = g.math("SUBTRACT", x + 1140, y - 500, 1.0, g.out(cut))    # never below the floor (no mown ring)
    nohas_s = g.math("SUBTRACT", x + 700, y - 1150, 1.0, g.out(has))
    # lean away from the object: axis = up x (root - nearest point), angle up to 25 degrees right against it
    pos = g.n("GeometryNodeInputPosition", x + 360, y - 700)
    away = g.vmath("SUBTRACT", x + 540, y - 750, g.out(pos), g.out(px, "Position"))
    up = g.n("FunctionNodeInputVector", x + 540, y - 900)
    up.vector = (0.0, 0.0, 1.0)
    ax = g.vmath("CROSS_PRODUCT", x + 700, y - 800, g.out(up), g.out(away))
    axn = g.vmath("NORMALIZE", x + 860, y - 800, g.out(ax))
    ang = g.math("MULTIPLY", x + 1000, y - 700, g.out(nearh), math.radians(25))
    lean = g.n("FunctionNodeAxisAngleToRotation", x + 1140, y - 750)
    g.link(axn, 0, lean, "Axis")
    g.link(ang, 0, lean, "Angle")
    # distance cone: a blade may be at most 1.5 x its root's distance to the object tall, so its tip can never
    # reach it whatever the tilt; at the object's edge the height goes to 0. Continuous everywhere, so blades never
    # pop when an object moves (a breathing character) - the upward-ray kill only happens where this is ~0 already.
    cone = g.math("MULTIPLY", x + 700, y - 1000, g.out(px, "Distance"), 1.5)
    cone_any = g.math("MAXIMUM", x + 860, y - 1000, g.out(cone), g.out(g.math("MULTIPLY", x + 760, y - 1100, g.out(nohas_s),
                                                                              1e6)))
    return g.out(dl), g.out(f), g.out(rz), g.out(has), g.out(lean), g.out(cone_any)


# ----------------------------------------------------------------------------------------------
def grass_group():
    ng, rebuilt = fresh_group(GRASS, "GeometryNodeTree", GN_VER)
    if not rebuilt:
        return ng
    ng.is_modifier = True
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Tuft", "INPUT", "NodeSocketObject", desc="Object whose mesh is used as one grass tuft")
    iface(ng, "Density", "INPUT", "NodeSocketFloat", 40.0, 0.0, 5000.0, desc="Tufts per square metre")
    iface(ng, "Height", "INPUT", "NodeSocketFloat", 0.35, 0.0, 100.0, desc="Grass height in metres",
          subtype="DISTANCE")
    iface(ng, "Height Random", "INPUT", "NodeSocketFloat", 0.35, 0.0, 1.0)
    iface(ng, "Width", "INPUT", "NodeSocketFloat", 1.0, 0.05, 10.0, desc="Tuft width relative to height")
    iface(ng, "Mask Attribute", "INPUT", "NodeSocketString", "hrp_grass",
          desc="Colour attribute painted white where grass grows")
    iface(ng, "Edge Shrink", "INPUT", "NodeSocketFloat", 0.45, 0.0, 1.0,
          desc="Height of grass at the edge of the painted area")
    _wind_inputs(ng, 0.22)
    iface(ng, "Edge Wind", "INPUT", "NodeSocketFloat", 0.15, 0.0, 1.0,
          desc="How much grass at the edge of the painted area moves")
    iface(ng, "LOD Distance", "INPUT", "NodeSocketFloat", 25.0, 0.0, 100000.0,
          desc="Beyond this camera distance grass thins out and grows wider to stay fast", subtype="DISTANCE")
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Detail", "INPUT", "NodeSocketFloat", 1.0, 0.05, 4.0,
          desc="Set by the Detail Level: fewer, wider tufts below 1, more and finer ones above")
    iface(ng, "Show Ground", "INPUT", "NodeSocketBool", True)
    _avoid_inputs(ng)
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -2200, 0)
    go = g.n("NodeGroupOutput", 1800, 0)
    pos = g.n("GeometryNodeInputPosition", -2200, -500)
    mask = _mask(g, gi, -2000, -300)

    cam = g.n("GeometryNodeInputActiveCamera", -2200, -800)
    ci = g.n("GeometryNodeObjectInfo", -2000, -800)
    g.link(cam, 0, ci, "Object")
    dist = g.vmath("DISTANCE", -1800, -700, g.out(pos), g.out(ci, "Location"))
    lod_hi = g.math("MULTIPLY", -1800, -900, g.out(gi, "LOD Distance"), 4.0)
    lod = g.maprange(-1600, -750, g.out(dist, "Value"), g.out(gi, "LOD Distance"), g.out(lod_hi), 1.0, 0.2)
    lod_off = g.math("LESS_THAN", -1600, -950, g.out(gi, "LOD Distance"), 0.001)
    lodf = g.math("MAXIMUM", -1400, -800, g.out(lod, "Result"), g.out(lod_off))
    edge = g.maprange(-1600, -400, mask, 0.05, 0.25)
    near_edge = g.maprange(-1800, -1100, mask, 0.3, 0.75, 1.0, 0.0)
    cn = g.n("ShaderNodeTexNoise", -1800, -1300, noise_dimensions="2D")
    g.set(cn, "Scale", 2.5)
    g.link(pos, 0, cn, "Vector")
    clus = g.maprange(-1600, -1300, g.out(cn, "Fac"), 0.5, 0.6)
    cmix = g.n("ShaderNodeMix", -1400, -1200, data_type="FLOAT")
    g.link(near_edge, "Result", cmix, "Factor", bkind="VALUE")
    g.inp(cmix, "A", "VALUE").default_value = 1.0
    g.link(clus, "Result", cmix, "B", bkind="VALUE")
    dfac0 = g.math("MULTIPLY", -1400, -450, g.out(edge, "Result"), g.out(lodf))
    dfac = g.math("MULTIPLY", -1250, -500, g.out(dfac0), g.mixout(cmix))
    near = g.math("MULTIPLY", -1600, -1000, g.out(gi, "Height"), 0.6)
    far_ok = g.math("GREATER_THAN", -1450, -1000, g.out(dist, "Value"), g.out(near))
    sel0 = g.math("GREATER_THAN", -1400, -250, mask, 0.3)
    sel = g.math("MULTIPLY", -1250, -250, g.out(sel0), g.out(far_ok))

    dp = g.n("GeometryNodeDistributePointsOnFaces", -1200, 0, distribute_method="RANDOM")
    g.link(gi, "Geometry", dp, "Mesh")
    g.link(sel, 0, dp, "Selection")
    dens = g.math("MULTIPLY", -1300, -150, g.out(gi, "Density"), g.out(dfac))
    dens = g.math("MULTIPLY", -1150, -150, g.out(dens), g.out(gi, "Detail"))
    dens = g.math("MULTIPLY", -1100, -100, g.out(dens), _preview(g, gi, -1500, 150))
    g.link(dens, 0, dp, "Density")      # Random mode ignores Density Factor: multiply instead
    g.link(gi, "Seed", dp, "Seed")
    pts = g.out(dp, "Points")
    pts = _store(g, -1000, 0, pts, "hrp_gn", g.out(dp, "Normal"), "FLOAT_VECTOR")
    pts = _store(g, -800, 0, pts, "hrp_mask", mask)
    rnd = _rand(g, -800, -300, 0.0, 1.0, g.out(gi, "Seed"), 11)
    pts = _store(g, -600, 0, pts, "hrp_rand", rnd)

    wind = _wind_node(g, gi, -800, -600, g.out(pos))
    pts = _store(g, -400, 0, pts, "hrp_wind", g.out(wind, "Wave"))
    reach = g.math("MULTIPLY", -400, 400, g.out(gi, "Height"), 1.6)
    pts, avf, avt, avh, avlean, avcone = _avoid(g, gi, -400, 700, pts, g.out(reach))

    # rotation: random spin, half-aligned to the ground normal, then bent by the wind
    spin = _rand(g, -800, -1000, 0.0, math.tau, g.out(gi, "Seed"), 23)
    eul = g.n("ShaderNodeCombineXYZ", -600, -1000)
    g.links.new(spin, eul.inputs["Z"])
    e2r = g.n("FunctionNodeEulerToRotation", -450, -1000)
    g.link(eul, 0, e2r, "Euler")
    al = g.n("FunctionNodeAlignRotationToVector", -300, -1000, axis="Z", pivot_axis="AUTO")
    g.link(e2r, 0, al, "Rotation")
    al.inputs["Factor"].default_value = 0.5
    g.link(dp, "Normal", al, "Vector")
    em = g.maprange(-450, -1300, mask, 0.3, 0.8, g.out(gi, "Edge Wind"), 1.0, smooth=True)
    wa0 = g.math("MULTIPLY", -300, -1300, g.out(wind, "Angle"), g.out(em, "Result"))
    wa = g.math("MULTIPLY", -300, -1400, g.out(wa0), avf)          # calm right against avoided objects
    aa = g.n("FunctionNodeAxisAngleToRotation", -150, -1250)
    g.link(wind, "Axis", aa, "Axis")
    g.link(wa, 0, aa, "Angle")
    rr0 = g.n("FunctionNodeRotateRotation", 0, -1100, rotation_space="GLOBAL")
    g.link(al, 0, rr0, "Rotation")
    g.link(aa, 0, rr0, "Rotate By")
    rr = g.n("FunctionNodeRotateRotation", 150, -1150, rotation_space="GLOBAL")
    g.link(rr0, 0, rr, "Rotation")
    g.links.new(avlean, rr.inputs["Rotate By"])

    # scale: height x random x edge shrink x LOD compensation
    hr0 = g.math("SUBTRACT", -800, -1600, 1.0, g.out(gi, "Height Random"))
    hr1 = g.math("ADD", -800, -1750, 1.0, g.out(gi, "Height Random"))
    hrn = _rand(g, -600, -1650, 0.0, 1.0, g.out(gi, "Seed"), 37)
    hrl = g.n("ShaderNodeMix", -450, -1650, data_type="FLOAT")
    g.links.new(hrn, g.inp(hrl, "Factor", "VALUE"))
    g.link(hr0, 0, hrl, "A", bkind="VALUE")
    g.link(hr1, 0, hrl, "B", bkind="VALUE")
    es = g.maprange(-450, -1850, mask, 0.25, 0.8, g.out(gi, "Edge Shrink"), 1.0, smooth=True)
    lods = g.math("POWER", -450, -2000, g.out(lodf), -0.5)
    s1 = g.math("MULTIPLY", -250, -1650, g.out(gi, "Height"), g.mixout(hrl))
    s2 = g.math("MULTIPLY", -100, -1750, g.out(s1), g.out(es, "Result"))
    s3h = g.math("MULTIPLY", -20, -1800, g.out(s2), _height_layer(g, -500, -2200))      # painted Height layer
    s3a = g.math("MULTIPLY", 50, -1850, g.out(s3h), g.out(lods))
    s3b = g.math("MULTIPLY", 120, -1950, g.out(s3a), avf)
    s3 = g.math("MINIMUM", 300, -2000, g.out(s3b), avcone)
    wider = g.math("POWER", 60, -1650, g.out(gi, "Detail"), -0.5)        # fewer tufts cover the same ground
    sw = g.math("MULTIPLY", 200, -1750, g.out(s3), g.out(g.math("MULTIPLY", 130, -1650, g.out(gi, "Width"), g.out(wider))))
    sv = g.n("ShaderNodeCombineXYZ", 350, -1750)
    g.link(sw, 0, sv, "X")
    g.link(sw, 0, sv, "Y")
    g.link(s3, 0, sv, "Z")

    tuft = g.n("GeometryNodeObjectInfo", 0, -400)
    g.link(gi, "Tuft", tuft, "Object")
    iop = g.n("GeometryNodeInstanceOnPoints", 600, 0)
    g.links.new(pts, iop.inputs["Points"])
    g.link(tuft, "Geometry", iop, "Instance")
    g.link(rr, 0, iop, "Rotation")
    g.link(sv, 0, iop, "Scale")

    ground = g.n("GeometryNodeSwitch", 600, 300, input_type="GEOMETRY")
    g.link(gi, "Show Ground", ground, "Switch")
    g.link(gi, "Geometry", ground, "True")
    join = g.n("GeometryNodeJoinGeometry", 1200, 0)
    g.link(iop, 0, join, "Geometry")
    g.link(ground, 0, join, "Geometry")
    g.link(join, 0, go, "Geometry")
    stamp(ng, GN_VER)
    return ng


# ----------------------------------------------------------------------------------------------
def _camera_facing(g, x, y, seed_sock, seed_off):
    """Rotation of the active camera with a random roll around the view axis."""
    cam = g.n("GeometryNodeInputActiveCamera", x, y)
    ci = g.n("GeometryNodeObjectInfo", x + 160, y)
    g.link(cam, 0, ci, "Object")
    roll = _rand(g, x + 160, y - 250, 0.0, math.tau, seed_sock, seed_off)
    aa = g.n("FunctionNodeAxisAngleToRotation", x + 360, y - 200)
    aa.inputs["Axis"].default_value = (0, 0, 1)
    g.links.new(roll, aa.inputs["Angle"])
    rr = g.n("FunctionNodeRotateRotation", x + 540, y, rotation_space="LOCAL")
    g.link(ci, "Rotation", rr, "Rotation")
    g.link(aa, 0, rr, "Rotate By")
    return g.out(rr), ci


def flowers_group():
    ng, rebuilt = fresh_group(FLOWERS, "GeometryNodeTree", GN_VER)
    if not rebuilt:
        return ng
    ng.is_modifier = True
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Card", "INPUT", "NodeSocketObject", desc="Object whose mesh is used as the flower card")
    iface(ng, "Density", "INPUT", "NodeSocketFloat", 45.0, 0.0, 2000.0, desc="Flowers per square metre inside patches")
    iface(ng, "Patch Size", "INPUT", "NodeSocketFloat", 2.5, 0.01, 1000.0, desc="Size of the flower patches in metres",
          subtype="DISTANCE")
    iface(ng, "Patch Amount", "INPUT", "NodeSocketFloat", 0.5, 0.0, 1.0, desc="Share of the meadow covered by patches")
    iface(ng, "Size", "INPUT", "NodeSocketFloat", 0.07, 0.0, 10.0, desc="Flower size in metres", subtype="DISTANCE")
    iface(ng, "Size Random", "INPUT", "NodeSocketFloat", 0.35, 0.0, 1.0)
    iface(ng, "Height", "INPUT", "NodeSocketFloat", 0.3, 0.0, 100.0, desc="Height of the flower heads",
          subtype="DISTANCE")
    iface(ng, "Mask Attribute", "INPUT", "NodeSocketString", "hrp_grass")
    _wind_inputs(ng, 0.22)
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Detail", "INPUT", "NodeSocketFloat", 1.0, 0.05, 4.0, desc="Set by the Detail Level: fewer or more flowers")
    _avoid_inputs(ng)
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -2000, 0)
    go = g.n("NodeGroupOutput", 1600, 0)
    pos = g.n("GeometryNodeInputPosition", -2000, -500)
    mask = _mask(g, gi, -1800, -300)
    # patches: low-frequency noise above a threshold
    pd = g.vmath("DIVIDE", -1800, -600, g.out(pos))
    psz = g.n("ShaderNodeCombineXYZ", -2000, -700)
    for c in "XYZ":
        g.link(gi, "Patch Size", psz, c)
    g.link(psz, 0, pd, ("Vector", 1))
    pn = g.n("ShaderNodeTexNoise", -1600, -600, noise_dimensions="3D")
    g.set(pn, "Scale", 1.0)
    g.set(pn, "Detail", 2.0)
    g.link(pd, 0, pn, "Vector")
    th = g.maprange(-1400, -800, g.out(gi, "Patch Amount"), 0.0, 1.0, 0.72, 0.3)
    th2 = g.math("ADD", -1200, -800, g.out(th, "Result"), 0.08)
    pf = g.maprange(-1200, -600, g.out(pn, "Fac"), g.out(th, "Result"), g.out(th2), smooth=True)
    mk = g.maprange(-1400, -400, mask, 0.5, 0.8)
    # painted Flowers layer f: below 0.5 thins the natural patches out (0 = none), above 0.5 fills the gaps
    # between them (1 = flowers everywhere); 0.5 and no layer = the patches as they are. Continuous everywhere.
    fl = _layer(g, -1600, -1000, FLOWERS_ATTR, 0.5)
    f2 = g.math("MULTIPLY", -1400, -1000, fl, 2.0)
    lo = g.math("MINIMUM", -1250, -950, g.out(f2), 1.0)
    hi = g.math("MAXIMUM", -1250, -1050, g.out(g.math("SUBTRACT", -1350, -1100, g.out(f2), 1.0)), 0.0)
    pf1 = g.math("MULTIPLY", -1100, -900, g.out(pf, "Result"), g.out(lo))
    gap = g.math("SUBTRACT", -1100, -1050, 1.0, g.out(pf, "Result"))
    pf2 = g.math("MULTIPLY_ADD", -950, -1000, g.out(gap), g.out(hi), g.out(pf1))
    dfac = g.math("MULTIPLY", -1000, -500, g.out(pf2), g.out(mk, "Result"))
    dp = g.n("GeometryNodeDistributePointsOnFaces", -800, 0, distribute_method="RANDOM")
    g.link(gi, "Geometry", dp, "Mesh")
    dens = g.math("MULTIPLY", -900, -150, g.out(gi, "Density"), g.out(dfac))
    dens = g.math("MULTIPLY", -750, -150, g.out(dens), g.out(gi, "Detail"))
    dens = g.math("MULTIPLY", -700, -100, g.out(dens), _preview(g, gi, -1000, 150))
    g.link(dens, 0, dp, "Density")
    sd = g.math("ADD", -1000, -200, g.out(gi, "Seed"), 101)
    g.link(sd, 0, dp, "Seed")
    pts = g.out(dp, "Points")
    pts = _store(g, -600, 0, pts, "hrp_gn", g.out(dp, "Normal"), "FLOAT_VECTOR")
    rnd = _rand(g, -600, -300, 0.0, 1.0, g.out(gi, "Seed"), 51)
    pts = _store(g, -400, 0, pts, "hrp_rand", rnd)
    # colour index 0..3, clustered by Voronoi cells a bit smaller than the patches
    vc = g.n("ShaderNodeTexVoronoi", -800, -900, voronoi_dimensions="3D")
    g.link(pd, 0, vc, "Vector")
    g.set(vc, "Scale", 1.3)
    sep = g.n("FunctionNodeSeparateColor", -600, -900)
    g.link(vc, "Color", sep, "Color")
    rmix = _rand(g, -600, -1100, 0.0, 1.0, g.out(gi, "Seed"), 61)
    pick = g.n("GeometryNodeSwitch", -400, -1000, input_type="FLOAT")
    gt = g.math("GREATER_THAN", -400, -1200, rmix, 0.94)
    g.link(gt, 0, pick, "Switch")
    g.link(sep, "Red", pick, "False")
    r2 = _rand(g, -600, -1300, 0.0, 1.0, g.out(gi, "Seed"), 71)
    g.links.new(r2, pick.inputs["True"])
    bias = g.math("POWER", -350, -1000, g.out(pick), 1.6)          # colours 1 and 2 dominate
    idx = g.math("FLOOR", -200, -1000, g.out(g.math("MULTIPLY", -300, -1100, g.out(bias), 3.999)))
    pts = _store(g, -200, 0, pts, "hrp_col", g.out(idx))
    reach = g.math("MULTIPLY", -200, 400, g.out(gi, "Height"), 1.6)
    pts, avf, _avt, _avh, _lean, _cone = _avoid(g, gi, -200, 700, pts, g.out(reach), keep_gap=0.12)
    # lift to the grass tops, sway with the wind
    lift = _rand(g, -400, -1500, 0.45, 0.95, g.out(gi, "Seed"), 81)
    lh0 = g.math("MULTIPLY", -200, -1500, lift, g.out(gi, "Height"))
    lh1 = g.math("MULTIPLY", -150, -1550, g.out(lh0), _height_layer(g, -700, -1700))  # painted Height layer
    lh = g.math("MULTIPLY", -100, -1600, g.out(lh1), avf)
    up = g.vmath("SCALE", 0, -1500, g.out(dp, "Normal"), scale=g.out(lh))
    wind = _wind_node(g, gi, -200, -1800, g.out(pos))
    sway = g.math("MULTIPLY", 0, -1800, g.out(wind, "Angle"), g.out(lh))
    sv = g.vmath("SCALE", 200, -1800, g.out(wind, "Dir"), scale=g.out(sway))
    off = g.vmath("ADD", 400, -1600, g.out(up), g.out(sv))
    spos = g.n("GeometryNodeSetPosition", 0, 0)
    g.links.new(pts, spos.inputs["Geometry"])
    g.link(off, 0, spos, "Offset")
    rot, _ci = _camera_facing(g, 200, -300, g.out(gi, "Seed"), 91)
    sz = _rand(g, 400, -700, 0.0, 1.0, g.out(gi, "Seed"), 97)
    s0 = g.math("SUBTRACT", 400, -900, 1.0, g.out(gi, "Size Random"))
    smix = g.n("ShaderNodeMix", 600, -800, data_type="FLOAT")
    g.links.new(sz, g.inp(smix, "Factor", "VALUE"))
    g.link(s0, 0, smix, "A", bkind="VALUE")
    g.inp(smix, "B", "VALUE").default_value = 1.0
    ss = g.math("MULTIPLY", 800, -800, g.mixout(smix), g.out(gi, "Size"))
    card = g.n("GeometryNodeObjectInfo", 400, 300)
    g.link(gi, "Card", card, "Object")
    iop = g.n("GeometryNodeInstanceOnPoints", 1000, 0)
    g.link(spos, 0, iop, "Points")
    g.link(card, "Geometry", iop, "Instance")
    g.links.new(rot, iop.inputs["Rotation"])
    g.link(ss, 0, iop, "Scale")
    join = g.n("GeometryNodeJoinGeometry", 1300, 0)
    g.link(iop, 0, join, "Geometry")
    g.link(gi, "Geometry", join, "Geometry")
    g.link(join, 0, go, "Geometry")
    stamp(ng, GN_VER)
    return ng


# ----------------------------------------------------------------------------------------------
def foliage_group():
    ng, rebuilt = fresh_group(FOLIAGE, "GeometryNodeTree", GN_VER)
    if not rebuilt:
        return ng
    ng.is_modifier = True
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Card", "INPUT", "NodeSocketObject", desc="Object whose mesh is used as the leaf card")
    iface(ng, "Density", "INPUT", "NodeSocketFloat", 45.0, 0.0, 5000.0, desc="Leaf cards per square metre of canopy")
    iface(ng, "Leaf Size", "INPUT", "NodeSocketFloat", 0.42, 0.0, 100.0, desc="Size of one leaf dab in metres",
          subtype="DISTANCE")
    iface(ng, "Size Random", "INPUT", "NodeSocketFloat", 0.4, 0.0, 1.0)
    iface(ng, "Inflate", "INPUT", "NodeSocketFloat", 0.12, 0.0, 100.0,
          desc="Push leaves out along the canopy normal for a fluffier outline", subtype="DISTANCE")
    iface(ng, "Roundness", "INPUT", "NodeSocketFloat", 0.4, 0.0, 1.0,
          desc="0 = every clump shades on its own, 1 = the whole canopy shades like one ball")
    iface(ng, "Blossom", "INPUT", "NodeSocketFloat", 0.0, 0.0, 1.0, desc="Share of cards that are blossoms")
    iface(ng, "Blossom Scale", "INPUT", "NodeSocketFloat", 1.2, 0.01, 1000.0, desc="Size of blossom clusters",
          subtype="DISTANCE")
    _wind_inputs(ng, 0.05)
    iface(ng, "Wind Flutter", "INPUT", "NodeSocketFloat", 0.06, 0.0, 1.0,
          desc="Fast leaf flutter on top of the slow sway (keep low: high values make close-ups shimmer)")
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Fill Inside", "INPUT", "NodeSocketBool", False,
          desc="Render the canopy mesh in the shadow colour behind the leaves (no see-through gaps)")
    iface(ng, "Fill Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -2200, 0)
    go = g.n("NodeGroupOutput", 1800, 0)
    pos = g.n("GeometryNodeInputPosition", -2200, -600)

    bb = g.n("GeometryNodeBoundBox", -2000, 400)
    g.link(gi, "Geometry", bb, "Geometry")
    sumv = g.vmath("ADD", -1800, 400, g.out(bb, "Min"), g.out(bb, "Max"))
    ctr = g.vmath("SCALE", -1650, 400, g.out(sumv), scale=0.5)
    half = g.vmath("SUBTRACT", -1650, 250, g.out(bb, "Max"), g.out(ctr))
    halfm = g.vmath("MAXIMUM", -1500, 250, g.out(half), (0.01, 0.01, 0.01))

    dp = g.n("GeometryNodeDistributePointsOnFaces", -1600, 0, distribute_method="RANDOM")
    g.link(gi, "Geometry", dp, "Mesh")
    g.link(gi, "Density", dp, "Density")
    g.link(gi, "Seed", dp, "Seed")
    pts = g.out(dp, "Points")
    # canopy-level normal: ellipsoid around the bounding box
    rel = g.vmath("SUBTRACT", -1400, -600, g.out(pos), g.out(ctr))
    ell = g.vmath("DIVIDE", -1250, -600, g.out(rel), g.out(halfm))
    en = g.vmath("NORMALIZE", -1100, -600, g.out(ell))
    elen = g.vmath("LENGTH", -1100, -800, g.out(ell))
    mixn = g.n("ShaderNodeMix", -900, -500, data_type="VECTOR")
    g.link(gi, "Roundness", mixn, "Factor", bkind="VALUE")
    g.link(dp, "Normal", mixn, "A", bkind="VECTOR")
    g.link(en, 0, mixn, "B", bkind="VECTOR")
    nn = g.vmath("NORMALIZE", -700, -500, g.mixout(mixn))
    pts = _store(g, -1300, 0, pts, "hrp_n", g.out(nn), "FLOAT_VECTOR")
    dep = g.maprange(-900, -800, g.out(elen, "Value"), 0.35, 0.95)
    pts = _store(g, -1100, 0, pts, "hrp_depth", g.out(dep, "Result"))
    rnd = _rand(g, -1100, -300, 0.0, 1.0, g.out(gi, "Seed"), 13)
    pts = _store(g, -900, 0, pts, "hrp_rand", rnd)
    # blossoms: whole Voronoi cells (bunches) chosen by the cell's random value, rounded inside each cell
    bd = g.vmath("DIVIDE", -1100, -1100, g.out(pos))
    bsz = g.n("ShaderNodeCombineXYZ", -1300, -1200)
    for c in "XYZ":
        g.link(gi, "Blossom Scale", bsz, c)
    g.link(bsz, 0, bd, ("Vector", 1))
    bv = g.n("ShaderNodeTexVoronoi", -900, -1100, voronoi_dimensions="3D")
    g.set(bv, "Scale", 1.0)
    g.link(bd, 0, bv, "Vector")
    bvc = g.n("FunctionNodeSeparateColor", -700, -1250)
    g.link(bv, "Color", bvc, "Color")
    sep = g.n("ShaderNodeSeparateXYZ", -900, -1500)
    g.link(nn, 0, sep, "Vector")
    topb = g.math("MULTIPLY_ADD", -700, -1400, g.out(sep, "Z"), 0.9, 0.85)
    lim0 = g.math("MULTIPLY", -550, -1400, g.out(topb), g.out(gi, "Blossom"))
    lnz = g.math("MULTIPLY_ADD", -550, -1500, g.out(bvc, "Green"), 0.5, -0.25)      # +-0.25 per cell
    lim = g.math("ADD", -450, -1450, g.out(lim0), g.out(g.math("MULTIPLY", -500, -1550, g.out(lnz),
                 g.out(gi, "Blossom"))))
    cell0 = g.math("LESS_THAN", -400, -1300, g.out(bvc, "Red"), g.out(lim))
    upok = g.math("GREATER_THAN", -400, -1450, g.out(sep, "Z"), -0.45)        # never under the crown
    cell = g.math("MULTIPLY", -300, -1350, g.out(cell0), g.out(upok))
    br = _rand(g, -700, -1600, 0.0, 0.2, g.out(gi, "Seed"), 17)
    rad = g.math("ADD", -550, -1600, br, 0.4)
    inside = g.math("LESS_THAN", -400, -1500, g.out(bv, "Distance"), g.out(rad))
    bl = g.math("MULTIPLY", -250, -1300, g.out(cell), g.out(inside))
    pts = _store(g, -700, 0, pts, "hrp_bloom", g.out(bl))
    # inflate along the clump normal, then sway with the wind (more at the top)
    inf = _rand(g, -500, -300, 0.0, 1.0, g.out(gi, "Seed"), 19)
    il0 = g.math("MULTIPLY", -350, -300, inf, g.out(gi, "Inflate"))
    upf = g.math("GREATER_THAN", -500, -500, g.out(sep, "Z"), 0.1)
    bl_up = g.math("MULTIPLY", -450, -450, g.out(bl), g.out(upf))
    bpush = g.math("MULTIPLY", -350, -450, g.out(bl_up), g.out(gi, "Inflate"))
    il = g.math("MULTIPLY_ADD", -250, -350, g.out(bpush), 1.2, g.out(il0))
    io = g.vmath("SCALE", -200, -300, g.out(dp, "Normal"), scale=g.out(il))
    wind = _wind_node(g, gi, -500, -1800, g.out(pos), flutter=True)
    sepr = g.n("ShaderNodeSeparateXYZ", -500, -2000)
    g.link(ell, 0, sepr, "Vector")
    hf = g.maprange(-300, -2000, g.out(sepr, "Z"), -1.0, 1.0, 0.2, 1.0)
    halfz = g.n("ShaderNodeSeparateXYZ", -500, -2200)
    g.link(halfm, 0, halfz, "Vector")
    sw1 = g.math("MULTIPLY", -100, -1900, g.out(wind, "Angle"), g.out(hf, "Result"))
    sw2 = g.math("MULTIPLY", 50, -1900, g.out(sw1), g.out(halfz, "Z"))
    swv = g.vmath("SCALE", 200, -1900, g.out(wind, "Dir"), scale=g.out(sw2))
    off = g.vmath("ADD", 350, -1000, g.out(io), g.out(swv))
    spos = g.n("GeometryNodeSetPosition", -500, 0)
    g.links.new(pts, spos.inputs["Geometry"])
    g.link(off, 0, spos, "Offset")

    rot, _ci = _camera_facing(g, -300, 600, g.out(gi, "Seed"), 29)
    sz = _rand(g, 0, -600, 0.0, 1.0, g.out(gi, "Seed"), 31)
    s0 = g.math("SUBTRACT", 0, -800, 1.0, g.out(gi, "Size Random"))
    smix = g.n("ShaderNodeMix", 200, -700, data_type="FLOAT")
    g.links.new(sz, g.inp(smix, "Factor", "VALUE"))
    g.link(s0, 0, smix, "A", bkind="VALUE")
    g.inp(smix, "B", "VALUE").default_value = 1.0
    bscale = g.maprange(200, -900, g.out(bl), 0.0, 1.0, 1.0, 1.5)
    ss1 = g.math("MULTIPLY", 400, -700, g.mixout(smix), g.out(gi, "Leaf Size"))
    ss = g.math("MULTIPLY", 550, -750, g.out(ss1), g.out(bscale, "Result"))
    card = g.n("GeometryNodeObjectInfo", 300, 300)
    g.link(gi, "Card", card, "Object")
    iop = g.n("GeometryNodeInstanceOnPoints", 800, 0)
    g.link(spos, 0, iop, "Points")
    g.link(card, "Geometry", iop, "Instance")
    g.links.new(rot, iop.inputs["Rotation"])
    g.link(ss, 0, iop, "Scale")
    fill = g.n("GeometryNodeSetMaterial", 600, 400)
    g.link(gi, "Geometry", fill, "Geometry")
    g.link(gi, "Fill Material", fill, "Material")
    shr = g.n("GeometryNodeSetPosition", 700, 500)
    g.link(fill, 0, shr, "Geometry")
    nrm = g.n("GeometryNodeInputNormal", 500, 600)
    shrink = g.vmath("SCALE", 600, 600, g.out(nrm, "Normal"), scale=0.0)
    ish0 = g.math("MULTIPLY", 300, 750, g.out(gi, "Leaf Size"), 0.3)
    ish = g.math("MULTIPLY_ADD", 450, 700, g.out(gi, "Inflate"), -0.5, g.out(g.math("MULTIPLY", 380, 800, g.out(ish0),
                 -1.0)))
    g.link(ish, 0, shrink, "Scale")
    g.link(shrink, 0, shr, "Offset")
    em = g.n("GeometryNodeSwitch", 800, 300, input_type="GEOMETRY")
    g.link(gi, "Fill Inside", em, "Switch")
    g.link(shr, 0, em, "True")
    join = g.n("GeometryNodeJoinGeometry", 1200, 0)
    g.link(iop, 0, join, "Geometry")
    g.link(em, 0, join, "Geometry")
    g.link(join, 0, go, "Geometry")
    stamp(ng, GN_VER)
    return ng
