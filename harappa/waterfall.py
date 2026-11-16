# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""A waterfall built the way real ones form: a stream runs across a raised terrace, drops off the edge of a hard
caprock that overhangs a scooped-out alcove, between two rock walls, into a plunge pool.

Add Waterfall makes all of it at once (each part stays editable):
  terrace (raises the meadow) · stream on top (its own channel) · caprock + bank rocks + walls + alcove ·
  the falling sheet (this module) · a plunge pool (a pond) · foam at the foot.
The sheet uses the three-slice idea: the lip and the foot keep their size in metres, only the middle scrolls."""
import math
import random

import bpy
from mathutils import Matrix, Vector

from . import rocks, shading, water
from .util import G, fresh_group, iface, mod_input, only, sock, stamp

FALL_VER = 46
FALL = "HRP Waterfall"
FALL_MOD = "Harappa Waterfall"
MAT_FALL = "HRP Waterfall"
MAT_FOAM = "HRP Foam"
MAT_SPLASH = "HRP Splash"
MAT_SKIRT = "HRP White Water"
G_ACC = 9.8


# ----------------------------------------------------------------------------------------------
# sheet: lip at the origin, falls along local -Y
# ----------------------------------------------------------------------------------------------
def crown_geo(g, x, y, secs, rx, ry, height, open_front=False, life=None):
    """GN: a crown splash wall round the origin (ellipse rx x ry), height `height` (x a slow breathing pulse unless
    `life` is given: then life 0..1 scales it), rim drawn into fingers. Stores hrp_cv / hrp_spk / hrp_ang for
    splash_material(). open_front: zero height towards local -Y (a horseshoe round a falling sheet)."""
    cgrid = g.n("GeometryNodeMeshGrid", x, y)
    cgrid.inputs["Size X"].default_value = 1.0
    cgrid.inputs["Size Y"].default_value = 1.0
    cgrid.inputs["Vertices X"].default_value = 121
    cgrid.inputs["Vertices Y"].default_value = 12
    cgp = _sep(g, x + 150, y - 150, only(g.n("GeometryNodeInputPosition", x, y - 150).outputs))
    U = g.math("MULTIPLY", x + 300, y - 150, only(g.math("ADD", x + 250, y - 150, g.out(cgp, "X"), 0.5).outputs), 6.2832)
    V = g.math("ADD", x + 300, y - 250, g.out(cgp, "Y"), 0.5)
    tl = g.math("MULTIPLY", x + 300, y - 350, secs, 1.4)
    if life is None:
        pulse = only(g.math("MULTIPLY_ADD", x + 450, y - 350, only(g.math("SINE", x + 400, y - 400, only(g.math("MULTIPLY", x + 350,
                       y - 400, g.out(tl, 0), 2.2).outputs)).outputs), 0.5, 0.5).outputs)
        hk = only(g.math("MULTIPLY_ADD", x + 550, y - 400, pulse, 0.3, 0.85).outputs)
    else:
        pulse, hk = life, life
    nsp = 14.0
    spk0 = g.math("MULTIPLY_ADD", x + 450, y - 150, only(g.math("COSINE", x + 400, y - 150, only(g.math("MULTIPLY_ADD", x + 350,
                  y - 150, g.out(U, 0), nsp, only(g.math("MULTIPLY", x + 300, y - 200, g.out(tl, 0), 0.6).outputs))
                  .outputs)).outputs), 0.5, 0.5)
    jitc = g.math("MULTIPLY_ADD", x + 500, y - 250, only(g.math("SINE", x + 450, y - 250, only(g.math("MULTIPLY_ADD", x + 400,
                  y - 250, g.out(U, 0), nsp * 0.37, 2.3).outputs)).outputs), 0.35, 1.0)
    jit2 = g.math("MULTIPLY_ADD", x + 550, y - 300, only(g.math("SINE", x + 500, y - 300, only(g.math("MULTIPLY_ADD", x + 450,
                  y - 300, g.out(U, 0), nsp * 1.13, 0.7).outputs)).outputs), 0.25, 1.0)      # uneven fingers
    jitc = g.math("MULTIPLY", x + 600, y - 250, g.out(jitc, 0), g.out(jit2, 0))
    spk = g.math("MULTIPLY", x + 650, y - 150, only(g.math("POWER", x + 550, y - 150, g.out(spk0, 0), 5.0).outputs),
                 g.out(jitc, 0))
    rimh = g.math("MULTIPLY_ADD", x + 750, y - 150, g.out(spk, 0), 0.5, 0.6)
    v3 = g.math("POWER", x + 650, y - 300, g.out(V, 0), 3.0)
    zc = g.math("MULTIPLY", x + 900, y - 200, g.out(V, 0), only(g.math("MULTIPLY_ADD", x + 800, y - 250, g.out(v3, 0),
                only(g.math("SUBTRACT", x + 750, y - 300, g.out(rimh, 0), 1.0).outputs), 1.0).outputs))
    Hc = g.math("MULTIPLY", x + 800, y - 400, height, hk)
    sinU = g.math("SINE", x + 450, y - 600, g.out(U, 0))
    cosU = g.math("COSINE", x + 450, y - 700, g.out(U, 0))
    if open_front:
        front = g.maprange(x + 600, y - 600, only(g.math("MULTIPLY", x + 550, y - 600, g.out(sinU, 0), -1.0).outputs),
                           0.25, 0.8, smooth=True)
        Hc = g.math("MULTIPLY", x + 950, y - 350, g.out(Hc, 0), only(g.math("MULTIPLY_ADD", x + 850, y - 650,
                    g.out(front, "Result"), -1.0, 1.0).outputs))
    if open_front:                                                   # the two sides never mirror each other
        sideb = g.math("GREATER_THAN", x + 600, y - 500, g.out(cosU, 0), 0.0)
        sph = g.math("MULTIPLY_ADD", x + 700, y - 500, g.out(sideb, 0), 2.6, only(g.math("MULTIPLY", x + 600, y - 550,
                     secs, 1.3).outputs))
        samp = g.math("MULTIPLY_ADD", x + 850, y - 500, only(g.math("SINE", x + 800, y - 500, g.out(sph, 0)).outputs),
                      0.3, only(g.math("MULTIPLY_ADD", x + 750, y - 450, g.out(sideb, 0), -0.3, 1.0).outputs))
        Hc = g.math("MULTIPLY", x + 950, y - 450, g.out(Hc, 0), g.out(samp, 0))
    zc = g.math("MULTIPLY", x + 1050, y - 200, g.out(zc, 0), g.out(Hc, 0))
    flare = g.math("MULTIPLY_ADD", x + 600, y - 800, pulse, 0.5, 0.65)
    rr = g.math("MULTIPLY_ADD", x + 800, y - 800, g.out(flare, 0), only(g.math("POWER", x + 700, y - 850, g.out(V, 0), 1.4)
                .outputs), 1.0)
    rr = g.math("MULTIPLY", x + 900, y - 800, g.out(rr, 0), only(g.math("MULTIPLY_ADD", x + 800, y - 900, only(g.math(
        "SINE", x + 700, y - 950, only(g.math("MULTIPLY", x + 600, y - 950, g.out(U, 0), 5.0).outputs)).outputs),
        0.05, 1.0).outputs))
    rr = g.math("ADD", x + 1000, y - 800, g.out(rr, 0), only(g.math("MULTIPLY", x + 900, y - 1000, only(g.math(
        "MULTIPLY", x + 800, y - 1000, g.out(spk, 0), only(g.math("POWER", x + 700, y - 1050, g.out(V, 0), 4.0).outputs))
        .outputs), only(g.math("MULTIPLY", x + 800, y - 1100, pulse, 0.25).outputs)).outputs))
    cpv = g.n("ShaderNodeCombineXYZ", x + 1200, y - 700)
    g.link(g.math("MULTIPLY", x + 1100, y - 650, only(g.math("MULTIPLY", x + 1000, y - 650, g.out(rr, 0), g.out(cosU, 0))
                  .outputs), rx), 0, cpv, "X")
    g.link(g.math("MULTIPLY", x + 1100, y - 750, only(g.math("MULTIPLY", x + 1000, y - 750, g.out(rr, 0), g.out(sinU, 0))
                  .outputs), ry), 0, cpv, "Y")
    g.link(zc, 0, cpv, "Z")
    cst = sock(cgrid.outputs, "Mesh")
    for nm_, val in (("hrp_cv", g.out(V, 0)), ("hrp_spk", g.out(spk, 0)),
                     ("hrp_ang", only(g.math("DIVIDE", x + 400, y - 1100, g.out(U, 0), 6.2832).outputs))):
        st_ = g.n("GeometryNodeStoreNamedAttribute", x + 300, y, data_type="FLOAT", domain="POINT")
        g.links.new(cst, st_.inputs["Geometry"])
        st_.inputs["Name"].default_value = nm_
        g.links.new(val, st_.inputs["Value"])
        cst = only(st_.outputs)
    cmv = g.n("GeometryNodeSetPosition", x + 1300, y)
    g.links.new(cst, cmv.inputs["Geometry"])
    g.link(cpv, 0, cmv, "Position")
    sm_ = g.n("GeometryNodeSetShadeSmooth", x + 1400, y + 50)
    g.link(cmv, 0, sm_, "Geometry")
    return only(sm_.outputs)


def fall_group():
    ng, rebuilt = fresh_group(FALL, "GeometryNodeTree", FALL_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Width", "INPUT", "NodeSocketFloat", 1.0, 0.05, 100.0, "Width at the lip", "DISTANCE")
    iface(ng, "Drop", "INPUT", "NodeSocketFloat", 2.5, 0.1, 500.0, "Height of the fall", "DISTANCE")
    iface(ng, "Throw", "INPUT", "NodeSocketFloat", 0.9, 0.0, 20.0, "Speed the water leaves the lip (m/s)")
    iface(ng, "Sheet Spread", "INPUT", "NodeSocketFloat", 0.25, 0.0, 3.0, "How much wider the sheet gets as it falls")
    iface(ng, "Foam", "INPUT", "NodeSocketFloat", 1.0, 0.0, 3.0, "Size of the foam at the foot")
    iface(ng, "Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Foam Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Spray Mist", "INPUT", "NodeSocketFloat", 0.8, 0.0, 3.0, "Spray mist rising at the foot")
    iface(ng, "Mist Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Splash Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Skirt Material", "INPUT", "NodeSocketMaterial")
    for it in ng.interface.items_tree:                           # older waterfalls get the new looks by default
        if getattr(it, "name", "") == "Mist Material":
            it.default_value = mist_material()
        if getattr(it, "name", "") == "Splash Material":
            it.default_value = splash_material()
        if getattr(it, "name", "") == "Skirt Material":
            it.default_value = skirt_material()
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1800, 0)
    go = g.n("NodeGroupOutput", 1800, 0)
    grid = g.n("GeometryNodeMeshGrid", -1600, 0)
    grid.inputs["Size X"].default_value = 1.0
    grid.inputs["Size Y"].default_value = 1.0
    grid.inputs["Vertices X"].default_value = 24
    grid.inputs["Vertices Y"].default_value = 90
    pos = g.n("GeometryNodeInputPosition", -1600, -300)
    p = g.n("ShaderNodeSeparateXYZ", -1450, -300)
    g.link(pos, 0, p, "Vector")
    u = g.math("ADD", -1300, -250, g.out(p, "X"), 0.5)                     # 0..1 across
    sv = g.math("SUBTRACT", -1300, -400, 0.5, g.out(p, "Y"))                # 0 lip .. 1 foot
    tmax = g.math("SQRT", -1300, -550, only(g.math("DIVIDE", -1450, -550, only(g.math("MULTIPLY", -1600, -550,
                  g.out(gi, "Drop"), 2.0).outputs), G_ACC).outputs))
    t = g.math("MULTIPLY", -1150, -450, g.out(sv, 0), g.out(tmax, 0))
    wid = g.math("MULTIPLY", -1150, -250, only(g.math("MULTIPLY_ADD", -1250, -150, g.out(sv, 0),
                 g.out(gi, "Sheet Spread"), 1.0).outputs), g.out(gi, "Width"))
    x = g.math("MULTIPLY", -1000, -250, only(g.math("SUBTRACT", -1100, -200, g.out(u, 0), 0.5).outputs), g.out(wid, 0))
    y = g.math("MULTIPLY", -1000, -400, g.out(t, 0), g.out(gi, "Throw"))
    y = g.math("MULTIPLY", -900, -400, g.out(y, 0), -1.0)
    z = g.math("MULTIPLY", -1000, -550, only(g.math("MULTIPLY", -1100, -550, g.out(t, 0), g.out(t, 0)).outputs),
               -0.5 * G_ACC)
    # a soft forward bulge in the middle of the sheet
    bul = g.math("SUBTRACT", -1000, -700, 1.0, only(g.math("POWER", -1100, -700, only(g.math("MULTIPLY_ADD", -1200, -700,
                 g.out(u, 0), 2.0, -1.0).outputs), 2.0).outputs))
    bul = g.math("MULTIPLY", -850, -700, g.out(bul, 0), only(g.math("MULTIPLY_ADD", -1000, -800, g.out(sv, 0), 0.06,
                 0.02).outputs))
    y = g.math("SUBTRACT", -750, -450, g.out(y, 0), g.out(bul, 0))
    crest = g.math("MULTIPLY", -850, -650, only(g.math("SUBTRACT", -950, -650, 1.0, only(g.math("POWER", -1050, -650,
                   only(g.math("MULTIPLY_ADD", -1150, -650, g.out(u, 0), 2.0, -1.0).outputs), 2.0).outputs)).outputs),
                   only(g.math("MULTIPLY", -950, -750, g.out(gi, "Width"), 0.045).outputs))
    crest = g.math("MULTIPLY", -750, -650, g.out(crest, 0), g.out(g.maprange(-850, -800, g.out(sv, 0), 0.12, 0.0,
                   smooth=True), "Result"))
    z = g.math("ADD", -650, -600, g.out(z, 0), g.out(crest, 0))
    np_ = g.n("ShaderNodeCombineXYZ", -600, -300)
    g.link(x, 0, np_, "X")
    g.link(y, 0, np_, "Y")
    g.link(z, 0, np_, "Z")
    sp = g.n("GeometryNodeSetPosition", -400, 0)
    g.link(np_, 0, sp, "Position")
    # distance travelled from the lip (chord) and to the foot: the shader's fixed-size lip and foot
    yz = g.n("ShaderNodeCombineXYZ", -600, -600)
    g.link(y, 0, yz, "Y")
    g.link(z, 0, yz, "Z")
    arc = g.vmath("LENGTH", -450, -600, only(yz.outputs))
    endv = g.n("ShaderNodeCombineXYZ", -600, -800)
    g.link(g.math("MULTIPLY", -750, -850, only(g.math("MULTIPLY", -850, -850, g.out(tmax, 0), g.out(gi, "Throw"))
                  .outputs), -1.0), 0, endv, "Y")
    g.link(g.math("MULTIPLY", -750, -950, g.out(gi, "Drop"), -1.0), 0, endv, "Z")
    total = g.vmath("LENGTH", -450, -800, only(endv.outputs))
    to_end = g.math("ADD", -300, -700, g.out(gi, "Drop"), g.out(z, 0))          # height left to the foot
    pack = g.n("ShaderNodeCombineXYZ", -150, -500)
    g.link(u, 0, pack, "X")
    g.link(arc, "Value", pack, "Y")
    g.link(to_end, 0, pack, "Z")
    st = g.n("GeometryNodeStoreNamedAttribute", -150, 0, data_type="FLOAT_VECTOR", domain="POINT")
    g.link(grid, "Mesh", st, "Geometry")                                # stored from the flat grid, then moved
    st.inputs["Name"].default_value = "hrp_wf"
    g.link(pack, 0, st, "Value", bkind="VECTOR")
    g.link(st, 0, sp, "Geometry")
    bk = g.n("GeometryNodeTransform", -250, 200)                    # a darker sheet behind: the fall has depth
    g.link(sp, 0, bk, "Geometry")
    bk.inputs["Translation"].default_value = (0.0, 0.07, -0.02)
    bk.inputs["Scale"].default_value = (0.86, 1.0, 1.0)
    bks = g.n("GeometryNodeStoreNamedAttribute", -100, 200, data_type="FLOAT", domain="POINT")
    g.link(bk, 0, bks, "Geometry")
    bks.inputs["Name"].default_value = "hrp_back"
    bks.inputs["Value"].default_value = 1.0
    bj = g.n("GeometryNodeJoinGeometry", -50, 0)
    g.link(sp, 0, bj, "Geometry")
    g.link(bks, 0, bj, "Geometry")
    sm = g.n("GeometryNodeSetMaterial", 50, 0)
    g.link(bj, 0, sm, "Geometry")
    g.link(gi, "Material", sm, "Material")
    # foam: a ring of soft white blobs where the sheet hits the pool, bobbing
    footy = g.math("MULTIPLY", -600, -1100, g.out(tmax, 0), g.out(gi, "Throw"))
    ring = g.n("GeometryNodeMeshCircle", -600, -1300)
    ring.inputs["Vertices"].default_value = 14
    g.link(g.math("MULTIPLY", -750, -1300, g.out(gi, "Width"), 0.62), 0, ring, "Radius")
    rel_ = g.n("GeometryNodeTransform", -520, -1250)                    # an ellipse along the impact line
    g.link(ring, 0, rel_, "Geometry")
    rel_.inputs["Scale"].default_value = (1.0, 0.5, 1.0)
    pts = g.n("GeometryNodeMeshToPoints", -450, -1300)
    g.link(rel_, 0, pts, "Mesh")
    jit = g.n("FunctionNodeRandomValue", -450, -1500, data_type="FLOAT_VECTOR")
    jit.inputs["Min"].default_value = (-0.1, -0.1, -0.05)
    jit.inputs["Max"].default_value = (0.1, 0.1, -0.01)
    tm = g.n("GeometryNodeInputSceneTime", -600, -1700)
    idx = g.n("GeometryNodeInputIndex", -600, -1800)
    hph = g.n("FunctionNodeRandomValue", -600, -1950, data_type="FLOAT")      # hashed phase: no visible wave
    g.set(hph, "Max", 6.283, "VALUE")
    ph = g.math("MULTIPLY_ADD", -450, -1750, g.out(tm, "Seconds"), 5.0, g.out(hph, "Value", "VALUE"))
    bob = g.math("MULTIPLY", -300, -1750, only(g.math("SINE", -350, -1750, g.out(ph, 0)).outputs), 0.035)
    off = g.n("ShaderNodeCombineXYZ", -150, -1500)
    g.link(g.math("MULTIPLY", -300, -1600, g.out(footy, 0), -1.0), 0, off, "Y")
    g.link(g.math("SUBTRACT", -300, -1900, g.out(bob, 0), g.out(gi, "Drop")), 0, off, "Z")
    fpos = g.vmath("ADD", 0, -1400, g.out(jit, "Value", "VECTOR"), only(off.outputs))
    fsp = g.n("GeometryNodeSetPosition", 150, -1300)
    g.link(pts, 0, fsp, "Geometry")
    g.link(fpos, 0, fsp, "Offset")
    blob = g.n("GeometryNodeMeshIcoSphere", 150, -1600)
    blob.inputs["Subdivisions"].default_value = 3
    blob.inputs["Radius"].default_value = 1.0
    bs = g.n("FunctionNodeRandomValue", 150, -1800, data_type="FLOAT")
    g.set(bs, "Min", 0.08, "VALUE")
    g.set(bs, "Max", 0.16, "VALUE")
    bsc = g.math("MULTIPLY", 300, -1800, g.out(bs, "Value", "VALUE"), g.out(gi, "Foam"))
    bsc = g.math("MULTIPLY", 400, -1800, g.out(bsc, 0), only(g.math("MULTIPLY_ADD", 300, -1950, g.out(gi, "Width"), 0.4,
                 0.6).outputs))
    lump = g.n("FunctionNodeRandomValue", 250, -2050, data_type="FLOAT_VECTOR")
    lump.inputs["Min"].default_value = (1.0, 0.9, 0.7)
    lump.inputs["Max"].default_value = (1.5, 1.3, 0.95)
    lsc = g.vmath("SCALE", 400, -1950, g.out(lump, "Value", "VECTOR"), scale=g.out(bsc, 0))
    inst = g.n("GeometryNodeInstanceOnPoints", 400, -1300)
    g.link(fsp, 0, inst, "Points")
    blob_s = g.n("GeometryNodeSetShadeSmooth", 250, -1650)
    g.link(blob, "Mesh", blob_s, "Geometry")
    g.link(blob_s, 0, inst, "Instance")
    g.link(lsc, 0, inst, "Scale")
    fm = g.n("GeometryNodeSetMaterial", 600, -1300)
    g.link(inst, 0, fm, "Geometry")
    g.link(gi, "Foam Material", fm, "Material")
    # a big flattened mound right where the water lands
    mound = g.n("GeometryNodeMeshIcoSphere", 400, -1600)
    mound.inputs["Subdivisions"].default_value = 3
    mound.inputs["Radius"].default_value = 1.0
    msc = g.n("ShaderNodeCombineXYZ", 550, -1650)
    mw_ = g.math("MULTIPLY", 450, -1700, g.out(gi, "Width"), 0.42)
    mw_ = g.math("MULTIPLY", 500, -1750, g.out(mw_, 0), g.out(gi, "Foam"))
    g.link(mw_, 0, msc, "X")
    g.link(g.math("MULTIPLY", 550, -1800, g.out(mw_, 0), 0.6), 0, msc, "Y")
    g.link(g.math("MULTIPLY", 550, -1850, g.out(mw_, 0), 0.22), 0, msc, "Z")
    mxf = g.n("GeometryNodeTransform", 700, -1600)
    g.link(mound, "Mesh", mxf, "Geometry")
    g.link(msc, 0, mxf, "Scale")
    mt = g.n("ShaderNodeCombineXYZ", 650, -1450)
    g.link(g.math("MULTIPLY", 550, -1450, g.out(footy, 0), -1.0), 0, mt, "Y")
    g.link(g.math("SUBTRACT", 550, -1500, only(g.math("MULTIPLY", 450, -1500, only(g.math("SINE", 350, -1500,
           only(g.math("MULTIPLY", 250, -1500, g.out(tm, "Seconds"), 3.1).outputs)).outputs), 0.02).outputs),
           g.out(gi, "Drop")), 0, mt, "Z")
    g.link(mt, 0, mxf, "Translation")
    mm = g.n("GeometryNodeSetMaterial", 850, -1600)
    g.link(mxf, 0, mm, "Geometry")
    g.link(gi, "Foam Material", mm, "Material")
    # splash crown: one continuous wall of thrown-up water round the landing point (ellipse along the impact line),
    # its rim drawn out into fingers, breathing and turning slowly; open in the front so it never hides the curtain
    Hc = g.math("MULTIPLY", 1800, -1700, only(g.math("MULTIPLY", 1700, -1750, g.out(gi, "Width"), 0.26).outputs),
                g.out(gi, "Foam"))
    Rx = g.math("MULTIPLY", 1900, -2500, g.out(gi, "Width"), 0.52)
    Ry = g.math("MULTIPLY", 1900, -2600, g.out(gi, "Width"), 0.32)
    cgeo = crown_geo(g, 1000, -1300, g.out(tm, "Seconds"), g.out(Rx, 0), g.out(Ry, 0), g.out(Hc, 0), True)
    cmv0 = g.n("GeometryNodeTransform", 2500, -1250)
    g.links.new(cgeo, cmv0.inputs["Geometry"])
    ctv = g.n("ShaderNodeCombineXYZ", 2400, -1400)
    g.link(g.math("MULTIPLY", 2300, -1400, g.out(footy, 0), -1.0), 0, ctv, "Y")
    g.link(g.math("SUBTRACT", 2300, -1450, -0.03, g.out(gi, "Drop")), 0, ctv, "Z")
    g.link(ctv, 0, cmv0, "Translation")
    cin = cmv0
    # droplets: thrown up and out from the landing point, falling back (ballistic, looping)
    dpt = g.n("GeometryNodePoints", 1000, -3100)
    dpt.inputs["Count"].default_value = 26
    dr = g.n("FunctionNodeRandomValue", 1000, -3250, data_type="FLOAT_VECTOR")
    dr.inputs["Min"].default_value = (0.0, 0.5, 1.6)
    dr.inputs["Max"].default_value = (6.283, 1.6, 3.0)
    drs = _sep(g, 1150, -3250, g.out(dr, "Value", "VECTOR"))
    dph = g.n("FunctionNodeRandomValue", 1000, -3400, data_type="FLOAT")
    g.set(dph, "Max", 1.0, "VALUE")
    dph.inputs["Seed"].default_value = 9
    tau = g.math("MULTIPLY", 1300, -3400, only(g.math("FRACT", 1200, -3400, only(g.math("MULTIPLY_ADD", 1100, -3450,
                 g.out(tm, "Seconds"), 1.3, g.out(dph, "Value", "VALUE")).outputs)).outputs), 0.75)
    hv = g.math("MULTIPLY", 1450, -3250, g.out(drs, "Y"), only(g.math("MULTIPLY_ADD", 1350, -3150, g.out(gi, "Foam"), 0.5,
                0.5).outputs))
    dxy = g.math("MULTIPLY", 1550, -3250, g.out(hv, 0), g.out(tau, 0))
    dz = g.math("SUBTRACT", 1550, -3400, only(g.math("MULTIPLY", 1450, -3400, g.out(drs, "Z"), g.out(tau, 0)).outputs),
                only(g.math("MULTIPLY", 1450, -3500, only(g.math("MULTIPLY", 1350, -3500, g.out(tau, 0), g.out(tau, 0))
                       .outputs), 0.5 * G_ACC).outputs))
    dp_ = g.n("ShaderNodeCombineXYZ", 1750, -3250)
    r0 = g.math("MULTIPLY", 1550, -3100, g.out(gi, "Width"), 0.3)
    rr_ = g.math("ADD", 1650, -3150, g.out(dxy, 0), g.out(r0, 0))
    g.link(g.math("MULTIPLY", 1700, -3100, only(g.math("COSINE", 1600, -3050, g.out(drs, "X")).outputs), g.out(rr_, 0)),
           0, dp_, "X")
    g.link(g.math("SUBTRACT", 1750, -3150, only(g.math("MULTIPLY", 1700, -3200, only(g.math("SINE", 1600, -3200,
           g.out(drs, "X")).outputs), g.out(rr_, 0)).outputs), g.out(footy, 0)), 0, dp_, "Y")
    g.link(g.math("SUBTRACT", 1700, -3400, g.out(dz, 0), g.out(gi, "Drop")), 0, dp_, "Z")
    dsp = g.n("GeometryNodeSetPosition", 1900, -3100)
    g.link(dpt, 0, dsp, "Geometry")
    g.link(dp_, 0, dsp, "Position")
    dalive = g.math("GREATER_THAN", 1750, -3550, g.out(dz, 0), -0.02)
    drad = g.math("MULTIPLY", 1900, -3500, g.out(dalive, 0), only(g.math("MULTIPLY_ADD", 1800, -3450, g.out(tau, 0), -0.9,
                  1.0).outputs))
    drad = g.math("MULTIPLY", 2000, -3500, g.out(drad, 0), only(g.math("MULTIPLY", 1900, -3600, g.out(gi, "Foam"),
                  0.03).outputs))
    dball = g.n("GeometryNodeMeshIcoSphere", 1900, -3700)
    dball.inputs["Subdivisions"].default_value = 2
    dball.inputs["Radius"].default_value = 1.0
    din = g.n("GeometryNodeInstanceOnPoints", 2150, -3100)
    g.link(dsp, 0, din, "Points")
    dball_s = g.n("GeometryNodeSetShadeSmooth", 2000, -3700)
    g.link(dball, "Mesh", dball_s, "Geometry")
    g.link(dball_s, 0, din, "Instance")
    g.link(drad, 0, din, "Scale")
    real_ = g.n("GeometryNodeRealizeInstances", 2400, -1300)              # hrp_sz reaches the shader
    g.link(cin, 0, real_, "Geometry")
    splm0 = g.n("GeometryNodeSetMaterial", 2500, -1300)
    g.link(real_, 0, splm0, "Geometry")
    g.link(gi, "Splash Material", splm0, "Material")
    dm = g.n("GeometryNodeSetMaterial", 2300, -3100)
    g.link(din, 0, dm, "Geometry")
    g.link(gi, "Foam Material", dm, "Material")
    # white water: a ragged sheet of foam on the pool round the landing point, churning
    skd = g.n("GeometryNodeMeshCircle", 1000, -2700, fill_type="TRIANGLE_FAN")
    skd.inputs["Vertices"].default_value = 48
    skd.inputs["Radius"].default_value = 1.0
    sks = g.n("GeometryNodeSubdivideMesh", 1150, -2700)
    g.link(skd, 0, sks, "Mesh")
    sks.inputs["Level"].default_value = 3
    skp = g.n("GeometryNodeInputPosition", 1000, -2850)
    skr = g.vmath("LENGTH", 1150, -2850, only(skp.outputs))
    skst = g.n("GeometryNodeStoreNamedAttribute", 1300, -2700, data_type="FLOAT", domain="POINT")
    g.link(sks, 0, skst, "Geometry")
    skst.inputs["Name"].default_value = "hrp_r"
    g.link(skr, "Value", skst, "Value", bkind="VALUE")
    skx = g.n("GeometryNodeTransform", 1450, -2700)
    g.link(skst, 0, skx, "Geometry")
    skw = g.math("MULTIPLY", 1300, -2900, g.out(gi, "Width"), only(g.math("MULTIPLY_ADD", 1200, -2950, g.out(gi, "Foam"),
                 0.7, 0.7).outputs))
    sksc = g.n("ShaderNodeCombineXYZ", 1450, -2900)
    g.link(skw, 0, sksc, "X")
    g.link(g.math("MULTIPLY", 1350, -3000, g.out(skw, 0), 0.75), 0, sksc, "Y")
    sksc.inputs["Z"].default_value = 1.0
    g.link(sksc, 0, skx, "Scale")
    skt = g.n("ShaderNodeCombineXYZ", 1450, -2550)
    g.link(g.math("MULTIPLY", 1350, -2500, g.out(footy, 0), -1.0), 0, skt, "Y")
    g.link(g.math("SUBTRACT", 1350, -2600, 0.012, g.out(gi, "Drop")), 0, skt, "Z")
    g.link(skt, 0, skx, "Translation")
    skm = g.n("GeometryNodeSetMaterial", 1600, -2700)
    g.link(skx, 0, skm, "Geometry")
    g.link(gi, "Skirt Material", skm, "Material")
    spl_ = g.n("GeometryNodeJoinGeometry", 2650, -1300)
    g.link(splm0, 0, spl_, "Geometry")
    g.link(dm, 0, spl_, "Geometry")
    g.link(skm, 0, spl_, "Geometry")
    splm = spl_
    # spray mist: a few soft puffs drifting up from the foot, each on its own clock
    mpts = g.n("GeometryNodePoints", 400, -2300)
    mpts.inputs["Count"].default_value = 7
    mr = g.n("FunctionNodeRandomValue", 250, -2450, data_type="FLOAT_VECTOR")
    mr.inputs["Min"].default_value = (-0.75, -0.5, 0.0)
    mr.inputs["Max"].default_value = (0.75, 0.6, 1.0)
    mrs = _sep(g, 400, -2450, g.out(mr, "Value", "VECTOR"))
    mph = g.math("FRACT", 550, -2550, only(g.math("MULTIPLY_ADD", 450, -2550, g.out(tm, "Seconds"), 0.12,
                 g.out(mrs, "Z")).outputs))
    mpos = g.n("ShaderNodeCombineXYZ", 700, -2400)
    g.link(g.math("MULTIPLY", 550, -2350, g.out(mrs, "X"), g.out(gi, "Width")), 0, mpos, "X")
    g.link(g.math("SUBTRACT", 550, -2400, g.out(mrs, "Y"), g.out(footy, 0)), 0, mpos, "Y")
    g.link(g.math("SUBTRACT", 600, -2500, only(g.math("MULTIPLY_ADD", 500, -2500, g.out(mph, 0), 1.4, 0.15).outputs),
           g.out(gi, "Drop")), 0, mpos, "Z")
    msp = g.n("GeometryNodeSetPosition", 850, -2300)
    g.link(mpts, 0, msp, "Geometry")
    g.link(mpos, 0, msp, "Position")
    puff = g.n("GeometryNodeMeshIcoSphere", 850, -2550)
    puff.inputs["Subdivisions"].default_value = 3
    puff.inputs["Radius"].default_value = 1.0
    psz = g.math("MULTIPLY", 850, -2700, only(g.math("MULTIPLY_ADD", 750, -2700, g.out(mph, 0), 0.35, 0.25).outputs),
                 only(g.math("MULTIPLY", 700, -2800, g.out(gi, "Width"), g.out(gi, "Spray Mist")).outputs))
    mins = g.n("GeometryNodeInstanceOnPoints", 1000, -2300)
    g.link(msp, 0, mins, "Points")
    g.link(puff, "Mesh", mins, "Instance")
    g.link(psz, 0, mins, "Scale")
    mfade = g.n("GeometryNodeStoreNamedAttribute", 1150, -2300, data_type="FLOAT", domain="INSTANCE")
    g.link(mins, 0, mfade, "Geometry")
    mfade.inputs["Name"].default_value = "hrp_mist"
    fade_ = g.math("MULTIPLY", 1000, -2500, g.out(g.maprange(850, -2550, g.out(mph, 0), 0.0, 0.25, smooth=True), "Result"),
                   g.out(g.maprange(850, -2650, g.out(mph, 0), 1.0, 0.55, smooth=True), "Result"))
    g.link(fade_, 0, mfade, "Value", bkind="VALUE")
    mmat = g.n("GeometryNodeSetMaterial", 1300, -2300)
    g.link(mfade, 0, mmat, "Geometry")
    g.link(gi, "Mist Material", mmat, "Material")
    msw = g.n("GeometryNodeSwitch", 1350, -2100, input_type="GEOMETRY")
    g.link(g.math("GREATER_THAN", 1200, -2100, g.out(gi, "Spray Mist"), 0.01), 0, msw, "Switch")
    g.link(mmat, 0, msw, "True")
    join = g.n("GeometryNodeJoinGeometry", 1400, 0)
    g.link(sm, 0, join, "Geometry")
    # (the big dome read as a pale bubble: the lumps and the white water replace it)
    g.link(msw, 0, join, "Geometry")
    lumps = g.n("GeometryNodeSetMaterial", 750, -1300)                  # flattened churning lumps round the foot
    g.link(inst, 0, lumps, "Geometry")
    g.link(gi, "Foam Material", lumps, "Material")
    g.link(lumps, 0, join, "Geometry")
    g.link(splm, 0, join, "Geometry")
    g.link(join, 0, go, "Geometry")
    stamp(ng, FALL_VER)                                   # built: not rebuilt on every use
    return ng


# ----------------------------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------------------------
def fall_material():
    mat, rebuilt = shading._fresh_mat(MAT_FALL)
    if not rebuilt and mat.get("hrp_fall_ver") == FALL_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fall_ver"] = FALL_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1600, 0)
    pal.node_tree = shading.palette_group()
    tg = g.n("ShaderNodeGroup", -1600, 300)
    tg.node_tree = water.time_group()
    t = g.out(tg, "Seconds")
    at = g.n("ShaderNodeAttribute", -1600, 600, attribute_name="hrp_wf", attribute_type="GEOMETRY")
    wf = g.n("ShaderNodeSeparateXYZ", -1400, 600)
    g.link(at, "Vector", wf, "Vector")
    u, v, to_end = g.out(wf, "X"), g.out(wf, "Y"), g.out(wf, "Z")
    # middle slice: streaks scroll down
    vs = g.math("SUBTRACT", -1200, 500, v, only(g.math("MULTIPLY", -1300, 400, t, 1.6).outputs))
    sc = g.n("ShaderNodeCombineXYZ", -1050, 500)
    g.link(g.math("MULTIPLY", -1150, 600, u, 15.0), 0, sc, "X")
    g.link(g.math("MULTIPLY", -1150, 450, g.out(vs, 0), 0.55), 0, sc, "Y")
    g.link(g.math("MULTIPLY", -1150, 350, t, 0.15), 0, sc, "Z")
    nz = g.n("ShaderNodeTexNoise", -900, 500, noise_dimensions="3D")
    g.set(nz, "Scale", 1.0)
    g.set(nz, "Detail", 3.0)
    g.set(nz, "Roughness", 0.55)
    g.link(sc, 0, nz, "Vector")
    st = g.out(nz, "Fac")
    # a second, faster and finer layer of strands over the first (water does not fall at one speed)
    vs2 = g.math("SUBTRACT", -1200, 750, v, only(g.math("MULTIPLY", -1300, 750, t, 2.6).outputs))
    sc2 = g.n("ShaderNodeCombineXYZ", -1050, 750)
    g.link(g.math("MULTIPLY", -1150, 850, u, 26.0), 0, sc2, "X")
    g.link(g.math("MULTIPLY", -1150, 800, g.out(vs2, 0), 0.8), 0, sc2, "Y")
    sc2.inputs["Z"].default_value = 3.7
    nz2_ = g.n("ShaderNodeTexNoise", -900, 750, noise_dimensions="3D")
    g.set(nz2_, "Scale", 1.0)
    g.set(nz2_, "Detail", 1.0)
    g.link(sc2, 0, nz2_, "Vector")
    st = only(g.math("MAXIMUM", -750, 700, st, only(g.math("SUBTRACT", -850, 750, g.out(nz2_, "Fac"), 0.06).outputs)).outputs)
    rhy = g.n("ShaderNodeTexNoise", -900, 950, noise_dimensions="2D")
    g.set(rhy, "Scale", 2.5)
    g.set(rhy, "Detail", 0.0)
    rhv = g.n("ShaderNodeCombineXYZ", -1000, 950)
    g.link(u, 0, rhv, "X")
    rhv.inputs["Y"].default_value = 3.3
    g.link(rhv, 0, rhy, "Vector")
    st = only(g.math("ADD", -750, 900, st, only(g.math("MULTIPLY_ADD", -800, 950, g.out(rhy, "Fac"), 0.14, -0.07).outputs)
                ).outputs)
    k1 = g.maprange(-700, 650, st, 0.40, 0.43, smooth=True)
    k2 = g.maprange(-700, 500, st, 0.53, 0.56, smooth=True)
    k3 = g.maprange(-700, 350, st, 0.64, 0.665, smooth=True)
    ws, wm, wd = water.type_colours(g, pal, -1600, 1200)                # same water type as the stream
    # toon steps, all opaque: darker blue streaks / pale cyan body / white highlights
    pale = g.mix(-650, 750, fac=0.3, a=ws, b=g.out(pal, "water_line"))             # keeps its water colour at dusk
    dstreak = g.mix(-650, 850, fac=0.35, a=wm, b=wd)
    col = g.mix(-500, 600, fac=g.out(k1, "Result"), a=g.mixout(dstreak), b=g.mixout(pale))
    col = g.mix(-350, 550, fac=g.out(k2, "Result"), a=g.mixout(col), b=g.out(pal, "water_line"))
    col = g.mix(-200, 500, fac=g.out(k3, "Result"), a=g.mixout(col), b=g.out(pal, "water_foam"))
    edge_d = g.math("SUBTRACT", -900, 200, 0.5, only(g.math("ABSOLUTE", -1000, 200, only(g.math("SUBTRACT", -1100, 200, u,
                    0.5).outputs)).outputs))
    dark = g.maprange(-700, 200, g.out(edge_d, 0), 0.10, 0.02, smooth=True)
    col = g.mix(-50, 450, fac=only(g.math("MULTIPLY", -150, 350, g.out(dark, "Result"), 0.35).outputs), a=g.mixout(col),
                b=wd)
    # top slice: a bright curl in the first 0.3 m after the lip
    ln_ = g.n("ShaderNodeTexNoise", -900, 100, noise_dimensions="2D")
    g.set(ln_, "Scale", 1.0)
    lnv = g.n("ShaderNodeCombineXYZ", -1000, 100)
    g.link(g.math("MULTIPLY", -1100, 100, u, 6.0), 0, lnv, "X")
    g.link(g.math("MULTIPLY", -1100, 50, t, 0.4), 0, lnv, "Y")
    g.link(lnv, 0, ln_, "Vector")
    lipd = g.math("MULTIPLY_ADD", -800, 50, g.out(ln_, "Fac"), 0.16, 0.12)              # 0.2 .. 0.36 m, ragged
    lipband = g.maprange(-700, 0, only(g.math("SUBTRACT", -750, 0, v, g.out(lipd, 0)).outputs), 0.012, 0.0, smooth=True)
    lipline = g.maprange(-700, -150, only(g.math("ABSOLUTE", -850, -150, only(g.math("SUBTRACT", -950, -150, v, 0.04)
                         .outputs)).outputs), 0.03, 0.012, smooth=True)
    col = g.mix(100, 400, fac=only(g.math("MULTIPLY", -500, 0, g.out(lipband, "Result"), 0.9).outputs),
                a=g.mixout(col), b=g.out(pal, "water_foam"))
    col = g.mix(250, 350, fac=only(g.math("MULTIPLY", 150, 300, g.out(lipline, "Result"), 0.7).outputs),
                a=g.mixout(col), b=g.out(pal, "water_foam"))                    # a soft curl, not a ruled line
    # bottom slice: churning white foam in the last 0.4 m
    fn = g.n("ShaderNodeTexNoise", -900, -400)
    g.set(fn, "Scale", 5.0)
    fc = g.n("ShaderNodeCombineXYZ", -1050, -400)
    g.link(g.math("MULTIPLY", -1150, -350, u, 3.0), 0, fc, "X")
    g.link(g.math("MULTIPLY_ADD", -1150, -450, t, 0.9, to_end), 0, fc, "Y")
    g.link(fc, 0, fn, "Vector")
    foot = g.math("ADD", -700, -400, only(g.math("SUBTRACT", -800, -500, 0.14, to_end).outputs),
                  only(g.math("MULTIPLY_ADD", -800, -350, g.out(fn, "Fac"), 0.24, -0.12).outputs))
    foot = g.maprange(-550, -400, g.out(foot, 0), 0.0, 0.03, smooth=True)
    col = g.mix(400, 300, fac=g.out(foot, "Result"), a=g.mixout(col), b=g.out(pal, "water_foam"))
    # eroded side edges and a soft start at the lip -> alpha
    en = g.n("ShaderNodeTexNoise", -900, -700)
    g.set(en, "Scale", 4.0)
    ec = g.n("ShaderNodeCombineXYZ", -1050, -700)
    g.link(g.math("MULTIPLY", -1150, -650, u, 2.0), 0, ec, "X")
    g.link(g.math("MULTIPLY", -1150, -750, g.out(vs, 0), 1.5), 0, ec, "Y")
    g.link(ec, 0, en, "Vector")
    er = g.math("ADD", -700, -700, g.out(edge_d, 0), only(g.math("MULTIPLY_ADD", -800, -800, g.out(en, "Fac"), 0.3,
                -0.15).outputs))
    alpha = g.maprange(-550, -700, g.out(er, 0), 0.02, 0.035, smooth=True)
    # the side edges break into a few separate strands below the lip
    sn = g.n("ShaderNodeTexNoise", -900, -950, noise_dimensions="2D")
    g.set(sn, "Scale", 1.0)
    g.set(sn, "Detail", 0.0)
    scn = g.n("ShaderNodeCombineXYZ", -1050, -950)
    g.link(g.math("MULTIPLY", -1150, -900, u, 16.0), 0, scn, "X")
    g.link(g.math("MULTIPLY", -1150, -1000, g.out(vs, 0), 0.12), 0, scn, "Y")
    g.link(scn, 0, sn, "Vector")
    gap = g.maprange(-750, -950, g.out(sn, "Fac"), 0.5, 0.56, smooth=True)
    zone = g.maprange(-750, -1100, g.out(edge_d, 0), 0.2, 0.1, smooth=True)
    below = g.maprange(-750, -1250, v, 0.05, 0.35, smooth=True)
    cut = g.math("MULTIPLY", -600, -1000, g.out(gap, "Result"), g.out(zone, "Result"))
    cut = g.math("MULTIPLY", -500, -1050, g.out(cut, 0), g.out(below, "Result"))
    alpha = g.math("MULTIPLY", -400, -800, g.out(alpha, "Result"), only(g.math("SUBTRACT", -450, -1000, 1.0, g.out(cut, 0))
                   .outputs))
    rn = g.n("ShaderNodeTexNoise", -900, -1350, noise_dimensions="2D")                 # ropes in the lower part
    rnv = g.n("ShaderNodeCombineXYZ", -1050, -1350)
    g.link(g.math("MULTIPLY", -1150, -1300, u, 7.0), 0, rnv, "X")
    g.link(g.math("MULTIPLY", -1150, -1400, g.out(vs, 0), 0.25), 0, rnv, "Y")
    g.set(rn, "Scale", 1.0)
    g.set(rn, "Detail", 0.0)
    g.link(rnv, 0, rn, "Vector")
    low = g.maprange(-750, -1450, to_end, 1.2, 0.45, smooth=True)
    thr = g.math("MULTIPLY_ADD", -650, -1400, g.out(low, "Result"), 0.16, 0.36)
    gaps = g.maprange(-550, -1350, only(g.math("SUBTRACT", -650, -1300, g.out(rn, "Fac"), g.out(thr, 0)).outputs),
                      -0.02, 0.0, 0.0, 1.0, smooth=True)
    gaps = g.math("MAXIMUM", -450, -1350, g.out(gaps, "Result"), g.out(foot, "Result"))
    alpha = g.math("MULTIPLY", -400, -1250, g.out(alpha, 0), only(g.math("MAXIMUM", -500, -1250,
                   g.out(gaps, 0), only(g.math("SUBTRACT", -600, -1200, 1.0, g.out(low, "Result")).outputs)).outputs))
    core = g.math("MULTIPLY_ADD", -300, -900, g.out(k2, "Result"), 0.0, 1.0)         # opaque toon water
    core = g.math("MAXIMUM", -200, -900, g.out(core, 0), g.out(foot, "Result"))
    core = g.math("MAXIMUM", -150, -950, g.out(core, 0), g.out(lipband, "Result"))
    alpha = g.math("MULTIPLY", -100, -850, g.out(alpha, 0), g.out(core, 0))
    # night: moonlit, not self-lit - less saturated and darker
    nhs = g.n("ShaderNodeHueSaturation", 300, 600)
    ng_ = g.math("MINIMUM", 150, 650, g.out(pal, "water_glow"), 1.0)
    g.link(g.math("MULTIPLY_ADD", 200, 700, g.out(ng_, 0), 0.0, 1.0), 0, nhs, "Saturation")
    g.link(g.math("MULTIPLY_ADD", 200, 600, g.out(ng_, 0), -0.12, 1.0), 0, nhs, "Value")
    g.links.new(g.mixout(col), nhs.inputs["Color"])
    col = g.mix(320, 560, fac=1.0, a=g.mixout(col), b=only(nhs.outputs))
    back = g.out(g.n("ShaderNodeAttribute", 200, -400, attribute_name="hrp_back", attribute_type="GEOMETRY"), "Fac")
    col = g.mix(350, 350, fac=only(g.math("MULTIPLY", 250, -350, back, 0.7).outputs), a=g.mixout(col), b=wd)
    alpha = g.mix(350, -500, "MIX", "FLOAT", fac=back, a=g.out(alpha, 0),
                  b=only(g.math("MULTIPLY", 250, -550, g.out(er, 0), 30.0, clamp=True).outputs))
    alpha = g.mixout(alpha)
    glow = g.math("MULTIPLY_ADD", 400, -200, g.out(pal, "water_glow"), 0.1, 1.0)
    gc = g.n("ShaderNodeCombineColor", 550, -200)
    for ch in ("Red", "Green", "Blue"):
        g.link(glow, 0, gc, ch)
    col = g.mix(600, 300, "MULTIPLY", fac=1.0, a=g.mixout(col), b=only(gc.outputs))
    shading._emit_out(g, g.mixout(col), 1000, 300, alpha=alpha, shadow_off=True, pal=pal, soft=True)
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    mat["hrp_kind"] = "waterfall"
    shading._done(mat, "fall_material")
    return mat


def _sep(g, x, y, vec):
    sep = g.n("ShaderNodeSeparateXYZ", x, y)
    g.links.new(vec, sock(sep.inputs, "Vector"))
    return sep


MAT_MIST = "HRP Mist"


def mist_material():
    """Soft white spray: transparent at the rim, a little denser in the middle, fading in and out per puff."""
    mat, rebuilt = shading._fresh_mat(MAT_MIST)
    if not rebuilt and mat.get("hrp_fall_ver") == FALL_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fall_ver"] = FALL_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -800, 0)
    pal.node_tree = shading.palette_group()
    lw = g.n("ShaderNodeLayerWeight", -800, 300)
    g.set(lw, "Blend", 0.5)
    core = g.math("POWER", -600, 300, only(g.math("SUBTRACT", -700, 300, 1.0, g.out(lw, "Facing")).outputs), 3.5)
    fd = g.n("ShaderNodeAttribute", -800, 500, attribute_name="hrp_mist", attribute_type="INSTANCER")
    a = g.math("MULTIPLY", -450, 350, g.out(core, 0), g.out(fd, "Fac"))
    a = g.math("MULTIPLY", -350, 350, g.out(a, 0), 0.07)
    shading._emit_out(g, g.out(pal, "water_foam"), 0, 200, pal=pal, alpha=g.out(a, 0), shadow_off=True, soft=True)
    mat.surface_render_method = "BLENDED"
    shading._done(mat, "mist_material")
    return mat


def splash_material():
    """The crown: toon bands up the wall (cyan to white), darker inside, a bright band, streaks, fingers at the rim
    and an eroded, breaking edge."""
    mat, rebuilt = shading._fresh_mat(MAT_SPLASH)
    if not rebuilt and mat.get("hrp_fall_ver") == FALL_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fall_ver"] = FALL_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1200, 0)
    pal.node_tree = shading.palette_group()
    tg = g.n("ShaderNodeGroup", -1200, 300)
    tg.node_tree = water.time_group()
    t = g.out(tg, "Seconds")
    def at(nm, y):
        return g.out(g.n("ShaderNodeAttribute", -1200, y, attribute_name=nm, attribute_type="GEOMETRY"), "Fac")
    cv, spk, ang = at("hrp_cv", 600), at("hrp_spk", 750), at("hrp_ang", 900)
    geo = g.n("ShaderNodeNewGeometry", -1200, 1100)
    back = g.out(geo, "Backfacing")
    b1 = g.maprange(-900, 600, cv, 0.3, 0.34, smooth=True)
    b2 = g.maprange(-900, 450, cv, 0.7, 0.74, smooth=True)
    wht = g.mix(-900, 900, fac=0.75, a=g.out(pal, "water_foam"), b=(1.0, 1.0, 1.0, 1.0))         # never peach
    low = g.mix(-750, 700, fac=0.3, a=(0.85, 0.95, 1.0, 1.0), b=g.out(pal, "water_mid"))
    col = g.mix(-600, 600, fac=g.out(b1, "Result"), a=g.mixout(low), b=g.mixout(wht))
    col = g.mix(-450, 550, fac=g.out(b2, "Result"), a=g.mixout(col), b=g.mixout(wht))
    cool = g.mix(-450, 400, fac=0.25, a=(1.0, 1.0, 1.0, 1.0), b=g.out(pal, "water_mid"))           # one cool step
    col = g.mix(-300, 500, fac=only(g.math("MULTIPLY", -400, 400, back, 0.8).outputs), a=g.mixout(col),
                b=g.mixout(cool))
    # a curved white highlight band and fine vertical streaks: a sheet of water, not a shell
    wave = g.math("MULTIPLY_ADD", -900, 200, only(g.math("SINE", -1000, 200, only(g.math("MULTIPLY", -1100, 200, ang,
                  18.85).outputs)).outputs), 0.05, 0.56)
    hb = g.maprange(-700, 200, only(g.math("ABSOLUTE", -800, 200, only(g.math("SUBTRACT", -850, 250, cv, g.out(wave, 0))
                    .outputs)).outputs), 0.045, 0.02, smooth=True)
    hbf = g.math("MULTIPLY", -550, 200, g.out(hb, "Result"), only(g.math("SUBTRACT", -650, 150, 1.0, back).outputs))
    col = g.mix(-150, 450, fac=g.out(hbf, 0), a=g.mixout(col), b=g.mixout(wht))
    sv = g.n("ShaderNodeCombineXYZ", -1000, -100)
    g.link(g.math("MULTIPLY", -1100, -50, ang, 40.0), 0, sv, "X")
    g.link(g.math("MULTIPLY", -1100, -100, cv, 0.6), 0, sv, "Y")
    g.link(g.math("MULTIPLY", -1100, -150, t, 0.3), 0, sv, "Z")
    stn = g.n("ShaderNodeTexNoise", -850, -100, noise_dimensions="3D")
    g.set(stn, "Scale", 1.0)
    g.link(sv, 0, stn, "Vector")
    streak = g.math("MULTIPLY", -650, -100, g.out(g.maprange(-750, -100, g.out(stn, "Fac"), 0.58, 0.64, smooth=True),
                    "Result"), 0.45)
    col = g.mix(0, 400, fac=g.out(streak, 0), a=g.mixout(col), b=g.out(pal, "water_line"))
    # alpha: fingers at the rim, an eroding edge that crawls, the sheet more solid up top
    ev = g.n("ShaderNodeCombineXYZ", -1000, -400)
    g.link(g.math("MULTIPLY", -1100, -350, ang, 9.0), 0, ev, "X")
    g.link(g.math("MULTIPLY", -1100, -400, cv, 2.2), 0, ev, "Y")
    g.link(g.math("MULTIPLY", -1100, -450, t, 0.7), 0, ev, "Z")
    enz = g.n("ShaderNodeTexNoise", -850, -400, noise_dimensions="3D")
    g.set(enz, "Scale", 1.0)
    g.set(enz, "Detail", 2.0)
    g.link(ev, 0, enz, "Vector")
    keep = g.math("ADD", -650, -400, g.out(enz, "Fac"), only(g.math("MULTIPLY", -750, -500, only(g.math("SUBTRACT", -850, -500,
                  1.0, cv).outputs), 0.45).outputs))
    a1 = g.maprange(-500, -400, g.out(keep, 0), 0.3, 0.34, smooth=True)
    fing = g.maprange(-500, -600, only(g.math("ADD", -600, -600, spk, only(g.math("MULTIPLY", -700, -650, only(g.math(
        "SUBTRACT", -800, -650, 1.0, only(g.math("POWER", -900, -650, cv, 3.0).outputs)).outputs), 1.6).outputs))
        .outputs), 0.18, 0.24, smooth=True)
    lwe = g.n("ShaderNodeLayerWeight", -700, -900)
    g.set(lwe, "Blend", 0.5)
    edgeon = g.maprange(-550, -900, g.out(lwe, "Facing"), 0.93, 0.85, smooth=True)    # never a glass fan edge-on
    alpha = g.math("MULTIPLY", -300, -500, only(g.math("MULTIPLY", -400, -500, g.out(a1, "Result"), g.out(fing, "Result"))
                   .outputs), g.out(edgeon, "Result"))
    shading._emit_out(g, g.mixout(col), 300, 300, pal=pal, alpha=g.out(alpha, 0), shadow_off=True, soft=True)
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    mat["hrp_kind"] = "splash"
    shading._done(mat, "splash_material")
    return mat


def skirt_material():
    """Churning white water on the pool round the foot: dense in the middle, breaking into patches and specks."""
    mat, rebuilt = shading._fresh_mat(MAT_SKIRT)
    if not rebuilt and mat.get("hrp_fall_ver") == FALL_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fall_ver"] = FALL_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -900, 0)
    pal.node_tree = shading.palette_group()
    tg = g.n("ShaderNodeGroup", -900, 300)
    tg.node_tree = water.time_group()
    t = g.out(tg, "Seconds")
    r = g.out(g.n("ShaderNodeAttribute", -900, 600, attribute_name="hrp_r", attribute_type="GEOMETRY"), "Fac")
    geo = g.n("ShaderNodeNewGeometry", -900, 800)
    pv = g.n("ShaderNodeCombineXYZ", -700, 800)
    ps = g.n("ShaderNodeSeparateXYZ", -800, 900)
    g.link(geo, "Position", ps, "Vector")
    g.link(ps, "X", pv, "X")
    g.link(ps, "Y", pv, "Y")
    g.link(g.math("MULTIPLY", -800, 700, t, 0.8), 0, pv, "Z")
    pvs = g.vmath("MULTIPLY", -650, 850, only(pv.outputs), (1.0, 0.33, 1.0))            # streaks run with the flow
    nz = g.n("ShaderNodeTexNoise", -550, 800, noise_dimensions="3D")
    g.set(nz, "Scale", 3.2)
    g.set(nz, "Detail", 1.0)
    g.links.new(only(pvs.outputs), nz.inputs["Vector"])
    f = g.math("ADD", -400, 700, only(g.math("SUBTRACT", -500, 600, 1.0, r).outputs),
               only(g.math("MULTIPLY_ADD", -500, 750, g.out(nz, "Fac"), 0.9, -0.45).outputs))
    dense = g.maprange(-250, 700, g.out(f, 0), 0.4, 0.415, smooth=True)
    edge = g.maprange(-250, 550, g.out(f, 0), 0.24, 0.255, smooth=True)
    a = g.math("MAXIMUM", -100, 650, g.out(dense, "Result"), only(g.math("MULTIPLY", -150, 550, g.out(edge, "Result"), 0.6)
               .outputs))
    # impact rings: two thin rings running outwards past the foam, fading
    for k, ph in enumerate((0.0, 0.5)):
        fr_ = g.math("FRACT", -500, 300 - 150 * k, only(g.math("MULTIPLY_ADD", -600, 300 - 150 * k, t, 0.55, ph).outputs))
        rr = g.math("MULTIPLY_ADD", -400, 300 - 150 * k, g.out(fr_, 0), 0.55, 0.45)
        gap_ = g.math("ABSOLUTE", -300, 300 - 150 * k, only(g.math("SUBTRACT", -350, 250 - 150 * k, r, g.out(rr, 0))
                      .outputs))
        ring_ = g.maprange(-200, 300 - 150 * k, g.out(gap_, 0), 0.018, 0.01, smooth=True)
        ring_ = g.math("MULTIPLY", -100, 300 - 150 * k, g.out(ring_, "Result"),
                       only(g.math("SUBTRACT", -200, 200 - 150 * k, 1.0, g.out(fr_, 0)).outputs))
        ring_ = g.math("MULTIPLY", 0, 400 - 100 * k, g.out(ring_, 0), only(g.math("SUBTRACT", -100, 350 - 100 * k, 1.0,
                       g.out(dense, "Result")).outputs))                  # rings only on open water
        a = g.math("MAXIMUM", 0, 500 - 100 * k, g.out(a, 0), g.out(ring_, 0))
    wfo = g.mix(-250, 350, fac=0.75, a=g.out(pal, "water_foam"), b=(1.0, 1.0, 1.0, 1.0))
    wed = g.mix(-250, 250, fac=0.5, a=g.mixout(wfo), b=(0.82, 0.93, 1.0, 1.0))
    col = g.mix(-100, 300, fac=g.out(dense, "Result"), a=g.mixout(wed), b=g.mixout(wfo))
    glow = g.math("MULTIPLY_ADD", -300, -100, g.out(pal, "water_glow"), 0.0, 1.0)
    gc = g.n("ShaderNodeCombineColor", -150, -100)
    for ch in ("Red", "Green", "Blue"):
        g.link(glow, 0, gc, ch)
    col = g.mix(50, 250, "MULTIPLY", fac=1.0, a=g.mixout(col), b=only(gc.outputs))
    shading._emit_out(g, g.mixout(col), 250, 250, pal=pal, alpha=g.out(a, 0), shadow_off=True, soft=True)
    mat.surface_render_method = "BLENDED"
    shading._done(mat, "skirt_material")
    return mat


def foam_material():
    mat, rebuilt = shading._fresh_mat(MAT_FOAM)
    if not rebuilt and mat.get("hrp_fall_ver") == FALL_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fall_ver"] = FALL_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -800, 0)
    pal.node_tree = shading.palette_group()
    geo = g.n("ShaderNodeNewGeometry", -800, 300)
    icy = g.mix(-650, -100, fac=0.6, a=g.out(pal, "water_shade"), b=(0.8, 0.9, 1.0, 1.0))
    sh = g.mix(-500, 0, fac=0.3, a=g.out(pal, "water_foam"), b=g.mixout(icy))                  # bright, icy
    wlit = g.mix(-500, 200, fac=0.75, a=g.out(pal, "water_foam"), b=(1.0, 1.0, 1.0, 1.0))         # never peach
    cel = shading._cel_node(g, pal, -200, 200, g.out(geo, "Normal"), g.mixout(wlit), g.mixout(sh),
                            g.mixout(sh))
    shading._emit_out(g, g.out(cel, "Color"), 200, 200, pal=pal)
    shading._done(mat, "foam_material")
    return mat


# ----------------------------------------------------------------------------------------------
# one-click waterfall
# ----------------------------------------------------------------------------------------------
def _fall_object(context, name="Harappa Waterfall"):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0, 0, 0)], [], [])
    ob = bpy.data.objects.new(name, me)
    water.water_collection(context.scene).objects.link(ob)
    mod = ob.modifiers.new(FALL_MOD, "NODES")
    mod.node_group = fall_group()
    mod_input(mod, "Material", fall_material())
    mod_input(mod, "Foam Material", foam_material())
    mod_input(mod, "Mist Material", mist_material())
    mod_input(mod, "Splash Material", splash_material())
    mod_input(mod, "Skirt Material", skirt_material())
    ob.visible_shadow = False
    return ob, mod


def _rock(context, loc, size, seed, flat, rot=0.0, tag=None, block=False, tilt=(0.0, 0.0), kind="ROUND"):
    """size = wanted dimensions in metres (x across, y depth, z height)."""
    ob = rocks.add_rock(context, loc, 1.0, seed, flat, ground_z=loc[2], block=block, kind=kind)
    me = ob.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    dims = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    ob.scale = tuple(t / max(d, 1e-4) for t, d in zip(size, dims))
    ob.rotation_euler = (tilt[0], tilt[1], rot)
    if tag:
        ob["hrp_waterfall"] = tag
    return ob


def set_flow(fall, flow):
    """How much water: the throw off the lip, the spread and the foam all follow it."""
    mod = fall.modifiers.get(FALL_MOD)
    if mod is None:
        return
    fall["hrp_wf_flow"] = float(flow)
    mod_input(mod, "Throw", 0.45 + 0.5 * flow)
    mod_input(mod, "Sheet Spread", 0.3 + 0.35 * flow)
    mod_input(mod, "Foam", 0.4 + 0.6 * flow)
    fall.update_tag()


def fall_of(context, tag):
    return next((o for o in context.scene.objects if o.get("hrp_waterfall") == tag and o.modifiers.get(FALL_MOD)),
                None)


def rebuild_waterfall(context, fall, height=None, width=None, seed=None):
    """Remove and rebuild a waterfall in the same place with new settings; returns the new sheet."""
    a = list(fall.get("hrp_wf_args", ()))
    if len(a) < 8:
        return fall
    pc, fwd = list(a[0:3]), a[3:5]
    lip = fall.get("hrp_wf_lip")
    if lip is not None:                                           # follow the sheet if the user moved it
        pc[0] += fall.location.x - lip[0]
        pc[1] += fall.location.y - lip[1]
    h, w, sd = a[5] if height is None else height, a[6] if width is None else width, \
        int(a[7] if seed is None else seed)
    flow = float(fall.get("hrp_wf_flow", 1.0))
    remove_waterfall(context, fall["hrp_waterfall"])
    new = add_waterfall(context, pc, fwd, h, w, sd, flow=flow)
    water.refreeze(context)
    return new


def add_waterfall(context, pool_center, forward, height=2.4, width=1.4, seed=0, flow=1.0, trees=True):
    """pool_center: world point where the water lands; forward: horizontal direction from the camera into
    the scene (the cliff stands behind the pool, the water falls towards the camera)."""
    scene = context.scene
    rs = random.Random(seed * 31 + 5)
    f = Vector((forward[0], forward[1], 0.0)).normalized()
    side = Vector((-f.y, f.x, 0.0))
    yaw = math.atan2(f.y, f.x) - math.pi / 2                      # local +Y = forward
    tag = f"wf{seed}_{rs.randint(0, 99999)}"
    grounds = water._ground_bvhs(water.meadows(scene))
    pc = Vector(pool_center)
    gz = water._ground_z(grounds, pc.x, pc.y)                    # the meadow itself, not an earlier terrace
    base = (gz if gz is not None else pc.z)
    throw = 0.9
    tmax = math.sqrt(2 * height / G_ACC)
    lip_xy = pc + f * (throw * tmax + 0.1)
    # the plunge pool is dug into the slope down to its lowest rim (worked out exactly once it exists); the whole
    # fall sits that much lower, so the drop is still the height asked for
    prad = max(2.0, width * 1.8)
    pcc = pc + f * (prad * 0.2)
    rim0 = []
    for k in range(24):
        a = k / 24 * math.tau
        dv = Vector((math.cos(a), math.sin(a), 0.0))
        if dv.dot(f) < 0.3:
            q = pcc + dv * prad * 0.9
            zq = water._ground_z(grounds, q.x, q.y)
            if zq is not None:
                rim0.append(zq)
    lvl0 = min(base, max(base - 0.9, min(rim0) - 0.06)) if rim0 else base
    water_top = lvl0 + height                                    # the stream surface at the lip
    top = water_top + 0.16                                       # terrace top: grass right down to the water
    drop = top - base
    # 1. terrace: a full flat top (half-width hw x back) behind the lip; the side and back slopes lie OUTSIDE it,
    #    each as wide as 3x its local rise, so the top stays flat and the stream has real banks
    hw, back = width * 0.5 + 2.4, 7.0
    cliff = 0.3

    def slope_w(x, y):
        gz_c = water._ground_z(grounds, x, y)
        return max(0.6, 3.0 * max(0.2, top - (gz_c if gz_c is not None else base)))

    corners, radii = [], []
    n = 48
    ph1, ph2 = rs.uniform(0, 6.28), rs.uniform(0, 6.28)
    for i in range(n):
        a = 2 * math.pi * i / n
        cx, cy = math.cos(a), math.sin(a)
        sx = math.copysign(abs(cx) ** 0.5, cx) * hw
        sy = (math.copysign(abs(cy) ** 0.35, cy) * 0.5 + 0.5) * (back - 0.15) + 0.15     # flat top outline, its
        #    front just behind the lip: the ground under the falling water is the pool's, not the terrace's
        q = lip_xy + side * sx + f * sy
        fwd = sy
        k = max(0.0, min(1.0, (fwd - 0.4) / 1.2))                    # steep along the front, gentle elsewhere
        k = k * k * (3 - 2 * k)
        lipw = width * 0.5 + 0.6                                     # ...and the front is a cliff only by the
        kf = 0.0 if cy >= 0 else max(0.0, min(1.0, (abs(sx) - lipw) / max(0.1, hw - lipw)))   # fall: its
        kf = kf * kf * (3 - 2 * kf)                                  # corners ease down, no box
        k = max(k, kf)
        wob = 1.0 + (0.1 * math.sin(3 * a + ph1) + 0.06 * math.sin(5 * a + ph2)) * max(k, 0.0)   # not a ruled edge
        q = lip_xy + side * sx * wob + f * sy * (wob if cy > 0 else 1.0)
        if cy < 0 and abs(sx) > width * 0.5 + 0.4:                  # beside the lip: a ragged rim, set back
            q = q + f * (0.35 + 0.3 * math.sin(4.0 * a + ph2)) * min(1.0, (abs(sx) - width * 0.5 - 0.4) / 0.8)
        sw = slope_w(q.x, q.y)
        if cy < 0:
            sw = min(sw, 3.2)                                        # front corners: a short slope, not a ramp
        outward = side * math.copysign(1.0, sx) * abs(cx) ** 0.35 + f * (max(0.0, cy) + min(0.0, cy) * kf)
        if outward.length > 1e-4:
            outward = outward.normalized()
        q = q + outward * sw * k                                     # push the edge out by its slope width
        corners.append(q)
        radii.append(1.0 + (sw / cliff - 1.0) * k)
    cu = bpy.data.curves.new("Harappa Terrace", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(corners) - 1)
    for p, c, r in zip(sp.points, corners, radii):
        p.co = (c.x, c.y, top, 1.0)
        p.radius = r
    sp.use_cyclic_u = True
    terr = bpy.data.objects.new("Harappa Terrace", cu)
    terr["hrp_waterfall"] = tag
    water.terrain_collection(scene).objects.link(terr)
    context.view_layer.update()
    water.make_terrace(context, terr, cliff=cliff)
    terrs = water._terraces(scene)

    def hill_z(q):
        z = water._ground_z(grounds, q.x, q.y, terrs)
        return base if z is None else z
    # 2. the plunge pool, centred where the water lands; its back cuts an alcove under the lip
    # (prad, pcc: the pool reaches in under the lip, the water lands IN it)
    pool = water.add_pond(context, (pcc.x, pcc.y, base), radius=prad, seed=seed, depth=0.9, use_terrain=False)
    pool["hrp_waterfall"] = tag
    # ...but stops at the cliff: its back is cut flat along the face, short of the lip (seen from above the pool and
    # the stream on the terrace must not overlap, or the bank under the lip is read as the high stream's)
    mw, inv = pool.matrix_world, pool.matrix_world.inverted()
    for sp_ in pool.data.splines:
        for p_ in (sp_.bezier_points if sp_.type == "BEZIER" else sp_.points):
            w = mw @ p_.co.to_3d()
            d = (w - lip_xy.to_3d()).to_2d().dot(f.to_2d()) + 0.08
            if d > 0:
                nw = inv @ (w - f * d)
                if sp_.type == "BEZIER":
                    p_.co = nw
                else:
                    p_.co = (nw.x, nw.y, nw.z, p_.co[3])
        if sp_.type == "BEZIER":                                   # smooth again round the new straight back
            for p_ in sp_.bezier_points:
                p_.handle_left_type = p_.handle_right_type = "AUTO"
    # ...and it is scoured INTO the slope, not set on it: water stands at the lowest point of its rim, where it spills
    # over (fill and spill). Ground is higher than the water everywhere else; the carve cuts the uphill banks.
    rim = []
    for sp_ in pool.data.splines:
        for p_ in (sp_.bezier_points if sp_.type == "BEZIER" else sp_.points):
            w = mw @ p_.co.to_3d()
            if (w - lip_xy.to_3d()).to_2d().dot(f.to_2d()) < -0.4:           # (the cliff side is rock, not a rim)
                rim.append((hill_z(w), w))
    low_z, notch = min(rim, key=lambda t: t[0]) if rim else (base, pcc - f * prad)
    lvl = min(base, max(base - 0.9, low_z - 0.06))
    water._set_level(pool, lvl)
    od = (notch - pcc).to_2d()
    od = od.normalized() if od.length > 1e-4 else -f.to_2d()
    wout = max(0.7, width * 0.8)
    nperp = Vector((-od.y, od.x))
    if low_z - 0.06 < lvl - 0.01:                                      # a slope too steep to dig into: a boulder bar
        for zr, w in rim:                                              # holds the water on the low side
            if zr < lvl + 0.05 and (w.to_2d() - notch.to_2d()).length > wout * 0.8:
                bs = rs.uniform(0.45, 0.7)
                _rock(context, (w.x, w.y, lvl - bs * 0.45), (bs * 1.3, bs, bs * 0.9), rs.randint(0, 9999), 0.6,
                      rs.uniform(0, 6.28), tag)
    for sgn in (-1, 1):                                                # the spill notch: a stone each side
        q = notch.to_2d() + nperp * sgn * (wout * 0.5 + 0.2) - od * 0.1
        bs = rs.uniform(0.4, 0.55)
        _rock(context, (q.x, q.y, lvl - bs * 0.35), (bs * 1.4, bs, bs * 0.8), rs.randint(0, 9999), 0.7,
              math.atan2(od.y, od.x), tag, kind="SLAB")
    life = pool.modifiers.get("Harappa Pond Life")                # no lilies in churning water
    if life is not None:
        mod_input(life, "Lily Pads", 0.0)
    # 3. the stream across the flat top, its surface exactly at the lip height
    run = back - 1.6                                              # well inside the flat top
    pts = []
    ph = rs.uniform(0, 3)
    for k in range(5):
        tt = k / 4
        wob = math.sin(tt * math.pi * 1.3 + ph) * 0.6 * (1 - tt)
        q = lip_xy + f * run * (1 - tt) + side * wob
        pts.append((q.x, q.y, water_top))
    src = Vector(pts[0][:2])                                       # the spring: water wells up between rocks
    for k in range(3):
        a = rs.uniform(0, math.tau) if k else math.atan2(f.y, f.x)
        q = src + Vector((math.cos(a), math.sin(a))) * rs.uniform(0.55, 0.8)
        bs = rs.uniform(0.5, 0.8)
        _rock(context, (q.x, q.y, top - 0.15), (bs * 1.3, bs, bs * 0.8), rs.randint(0, 9999), 0.7,
              rs.uniform(0, 6.28), tag)
    stream = water.add_stream(context, pts, width=width, depth=0.22, feeds_fall=True, fixed_z=water_top)
    stream["hrp_waterfall"] = tag
    # 4. the sheet (same water look as the stream and the pool)
    fall, fmod = _fall_object(context)
    fall["hrp_waterfall"] = tag
    fall.location = (lip_xy.x, lip_xy.y, water_top)
    fall.rotation_euler = (0.0, 0.0, yaw)                          # local -Y (the fall) points at the camera
    mod_input(fmod, "Width", width)
    mod_input(fmod, "Drop", max(0.2, water_top - water.pond_level(pool)))
    mod_input(fmod, "Throw", throw)
    for o in (pool, fall):
        for k in ("hrp_hue", "hrp_sat", "hrp_val", "hrp_clarity", "hrp_tint", "hrp_wuse", "hrp_wcol_s",
                  "hrp_wcol_m", "hrp_wcol_d", "hrp_wtype"):
            if k in stream:
                o[k] = stream[k]
    # 5. the cliff face: big weathered boulders, not masonry. Each side is a ragged wall of two or three rounded
    #    rocks, the biggest beside the lip, the upper ones set back and resting on the lower; one side taller.
    def ground_at(q):
        z = water._ground_z(grounds, q.x, q.y)
        return base if z is None else z

    tall = rs.choice((-1, 1))
    for sgn in (-1, 1):
        hmul = 1.0 if sgn == tall else rs.uniform(0.7, 0.82)
        back_off = 0.0 if sgn == tall else rs.uniform(0.3, 0.6)
        d = width * 0.5 + 0.15
        first = True
        while d < hw + 0.3:
            wdt = rs.uniform(1.5, 2.4) if first else rs.uniform(1.1, 2.0)
            mid = d + wdt * 0.42
            end_f = max(0.0, (mid - (hw - 1.4)) / 1.6)
            front = lip_xy + side * sgn * mid - f * (rs.uniform(-0.1, 0.5) - back_off)
            dep = rs.uniform(1.3, 1.9)
            foot = [front + side * dx + f * dy for dx in (-wdt * 0.4, wdt * 0.4) for dy in (-dep * 0.3, dep * 0.3)]
            z0 = min(min(ground_at(q), hill_z(q)) for q in foot) - 0.25      # on the slope where the hill eases
            zhill = hill_z(front + f * (dep * 0.9))                         # down: no drawers sticking out
            #    (the height of the hill right behind the rock: what it leans on)
            face_h = max(0.5, (top - z0) * (1.0 - 0.6 * end_f) * hmul + rs.uniform(-0.15, 0.2))
            face_h = min(face_h, max(0.5, zhill - z0 + 0.6))                  # never above the slope it leans on
            stack = 1 if face_h < 1.3 else 2
            zc = z0
            for li in range(stack):
                if stack == 1:
                    hgt = face_h + 0.1
                else:                                                # a low boulder in front, a wide one in the hill
                    hgt = min(face_h * 0.55, 1.3) if li == 0 else face_h - min(face_h * 0.55, 1.3) * 0.7 + 0.15
                ww = max(wdt * (1.0 if li == 0 else rs.uniform(1.05, 1.25)), hgt * 1.15)
                q = front + f * (0.7 * li) + side * sgn * rs.uniform(0.0, 0.3) * li
                rk = _rock(context, (q.x, q.y, zc), (ww, dep * (1.0 if li == 0 else 1.2), hgt + 0.15),
                           rs.randint(0, 9999), rs.uniform(0.7, 0.85), yaw + rs.uniform(-0.3, 0.3), tag,
                           tilt=(rs.uniform(-0.06, 0.06), rs.uniform(-0.08, 0.08)),
                           kind="ANGULAR" if rs.random() < 0.6 else "ROUND")
                if li < stack - 1:
                    rk["hrp_nomoss"] = 0.6
                zc += hgt * 0.7                                      # sunk into the slope, not stacked eggs
            d += wdt * rs.uniform(0.62, 0.78)                         # overlapping: no gaps, no joints in a row
            first = False
        for k in range(3):                                             # fallen boulders at the foot
            q2 = lip_xy + side * sgn * rs.uniform(width * 0.5 + 0.9, hw) - f * rs.uniform(1.0, 2.2)
            bs = rs.uniform(0.35, 0.7) if k else rs.uniform(0.75, 1.05)
            _rock(context, (q2.x, q2.y, ground_at(q2) - 0.15), (bs * 1.3, bs * 1.1, bs), rs.randint(0, 9999), 0.75,
                  rs.uniform(0, 6.28), tag)
        q = lip_xy + side * sgn * (width * 0.5 + 0.25) + f * 0.25       # the bank rocks that frame the lip
        _rock(context, (q.x, q.y, water_top - 0.25), (0.75, 1.0, 0.5), rs.randint(0, 9999), 0.75, yaw, tag)
        dx = width * 0.5 + 1.2
        while dx < hw + 1.2:                                           # rim stones along the whole front edge
            q = lip_xy + side * sgn * dx + f * rs.uniform(0.3, 1.3)
            bs = rs.uniform(0.4, 1.2)
            dx += rs.uniform(0.6, 1.1)
            _rock(context, (q.x, q.y, hill_z(q) - bs * 0.35), (bs * 1.3, bs * 1.1, bs), rs.randint(0, 9999),
                  rs.uniform(0.6, 0.85), rs.uniform(0, 6.28), tag, kind=rs.choice(("ROUND", "ANGULAR")))
        sh_ = 1.0 if sgn == tall else rs.uniform(0.6, 0.8)              # shoulders: the cliff top beside the lip
        q = lip_xy + side * sgn * (width * 0.5 + rs.uniform(0.8, 1.1)) + f * rs.uniform(0.6, 0.9)   # is rock
        _rock(context, (q.x, q.y, top - 0.75 * sh_), (rs.uniform(1.3, 1.7), rs.uniform(1.3, 1.6), 0.95 * sh_),
              rs.randint(0, 9999), 0.6, yaw + rs.uniform(-0.25, 0.25), tag, tilt=(rs.uniform(-0.05, 0.05), 0.0),
              kind="SLAB")
    _rock(context, (lip_xy + f * 0.5).to_3d() + Vector((0, 0, water_top - 0.34)), (width + 1.0, 1.2, 0.36),
          rs.randint(0, 9999), 0.4, yaw, tag)                       # the ledge the water pours over
    recess = max(0.3, prad - (throw * tmax + 0.1))
    q = lip_xy + f * 0.45                                          # right behind the falling sheet
    alc = _rock(context, (q.x, q.y, base - 0.5), (width + 1.2, 0.7, water_top - base + 0.2), rs.randint(0, 9999),
                1.0, yaw, tag, block=True)                         # a solid dark back wall behind the sheet
    alc["hrp_dark"] = 1.0
    # 6. the hill reads as a hill: rock outcrops along the front slopes, and trees on the top
    for sgn in (-1, 1):
        for k in range(3):
            q = lip_xy + side * sgn * (hw + rs.uniform(0.6, 3.2)) + f * rs.uniform(-0.6, 2.5)
            zq = hill_z(q)
            if zq - base < 0.35:
                continue
            bs = rs.uniform(0.5, 1.0)
            _rock(context, (q.x, q.y, zq - bs * 0.45), (bs * 1.5, bs * 1.2, bs), rs.randint(0, 9999), 0.6,
                  rs.uniform(0, 6.28), tag, tilt=(rs.uniform(-0.2, 0.2), rs.uniform(-0.2, 0.2)))
    if trees:
        from . import tree as htree
        for sgn, fw, shape, ht in ((tall, rs.uniform(4.5, 6.0), "ROUND", rs.uniform(3.8, 4.8)),
                                   (-tall, rs.uniform(2.0, 3.0), "BUSH", rs.uniform(1.3, 1.8))):
            q = lip_xy + side * sgn * rs.uniform(1.8, hw - 0.4) + f * fw     # off-centre: not a gate
            root = htree.add_tree(context, shape, ht, rs.randint(0, 9999), (q.x, q.y, hill_z(q) - 0.05))
            if root is not None:
                root["hrp_waterfall"] = tag
    # 7. the pool spills through its notch and the water takes the steepest way down the meadow (into a pond if it
    #    meets one); steep stretches turn into step-pools (snap_stream), each drop framed by stones
    out_pts = _descent_path(scene, hill_z, pcc.to_2d() + od * prad * 0.3, notch.to_2d(), od, pool)
    outflow = None
    try:
        outflow = water.add_stream(context, [(q.x, q.y, lvl) for q in out_pts], width=wout, depth=0.3)
        outflow["hrp_waterfall"] = tag
    except Exception:                                                  # off the meadow: no outflow
        pass
    fall["hrp_wf_args"] = [pc.x, pc.y, pc.z, f.x, f.y, float(height), float(width), int(seed)]
    fall["hrp_wf_lip"] = [fall.location.x, fall.location.y]
    set_flow(fall, flow)
    scene.cursor.location = pc
    water.settle(context)
    if outflow is not None:
        _step_stones(context, outflow, wout, rs, tag)
    return fall


def _descent_path(scene, hill_z, start, notch, od, pool, step=0.5, max_len=18.0):
    """From the pool's notch, follow the steepest way down (within +-60 deg of the current heading, so it bends
    smoothly) until the water meets a pond, settles in a dip, or has run max_len."""
    ponds = water._ponds(scene, skip=pool)
    path = [start, notch]
    cur, head = notch.copy(), od.copy()
    zc = hill_z(cur.to_3d())
    flat = 0
    for _ in range(int(max_len / step)):
        best = None
        for a in range(-60, 61, 15):
            r = math.radians(a)
            dv = Vector((head.x * math.cos(r) - head.y * math.sin(r), head.x * math.sin(r) + head.y * math.cos(r)))
            q = cur + dv * step
            z = hill_z(q.to_3d())
            score = z + abs(a) / 60.0 * 0.012                         # prefer going straight on near-flat ground
            if best is None or score < best[0]:
                best = (score, q, dv, z)
        _sc, q, dv, z = best
        if z > zc + 0.02:                                              # a dip: the water would pool here
            break
        flat = flat + 1 if z > zc - 0.005 else 0
        if flat > 10:
            break
        head = (head * 0.55 + dv * 0.45).normalized()
        cur, zc = q, min(zc, z)
        path.append(cur.copy())
        if any(water._inside(poly, cur.x, cur.y) for poly, _l, _p in ponds):
            for _k in range(3):                                        # run on under the pond a little
                cur = cur + head * step
                path.append(cur.copy())
            break
    out = [path[0], path[1]]                                           # light smoothing, ends kept
    for i in range(2, len(path) - 1):
        out.append((path[i - 1] + path[i] * 2 + path[i + 1]) / 4)
    out.append(path[-1])
    return out


def _step_stones(context, stream, width, rs, tag):
    """A stone on each side of every drop of a stepped stream (the step's lip), like a garden cascade."""
    mw = stream.matrix_world
    for sp in stream.data.splines:
        pts = [mw @ p.co.to_3d() for p in (sp.bezier_points if sp.type == "BEZIER" else sp.points)]
        for a, b in zip(pts, pts[1:]):
            if a.z - b.z < 0.12:
                continue
            t = (b - a).to_2d()
            if t.length < 1e-4:
                continue
            t.normalize()
            nrm = Vector((-t.y, t.x))
            for sgn in (-1, 1):
                q = a.to_2d() + nrm * sgn * (width * 0.5 + rs.uniform(0.05, 0.2)) + t * rs.uniform(0.0, 0.2)
                bs = rs.uniform(0.35, 0.55)
                _rock(context, (q.x, q.y, a.z - bs * 0.3), (bs * 1.3, bs, bs * 0.85), rs.randint(0, 9999), 0.6,
                      math.atan2(t.y, t.x), tag, kind="ANGULAR")


def remove_waterfall(context, tag):
    for o in [o for o in context.scene.objects if o.get("hrp_waterfall") == tag]:
        for ch in list(o.children):                              # e.g. the pool's fish
            bpy.data.objects.remove(ch)
        data = o.data
        bpy.data.objects.remove(o)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
