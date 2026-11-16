# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Life on the water: koi that cruise the deep zone of a pond, and a little rowboat that floats.

* Koi: a procedural cartoon koi (body, tail, fins; hrp_x = 0 nose .. 1 tail). "Harappa Fish" is a separate
  object per pond whose modifier reads the pond (Object Info), so only the fish re-evaluate each frame. Each fish
  swims a slow loop in the deep zone with a travelling body wave; it is drawn at the surface, tinted towards the
  water colour, so it reads as seen through the water (the toon water itself is opaque).
* Boat: a procedural rowboat that bobs and rocks on the water. Draft = how deep it sits (its buoyancy)."""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from . import shading, water
from .util import G, fresh_group, iface, mod_input, only, sock

FAUNA_VER = 22
FISH = "HRP Fish"
FISH_MOD = "Harappa Fish"
MAT_KOI = "HRP Koi"
KOI_OB = "HRP Koi"
FLOAT = "HRP Float"
FLOAT_MOD = "Harappa Float"
MAT_BOAT = "HRP Boat"


# ----------------------------------------------------------------------------------------------
# koi mesh: 1 m long, nose at +x, back at +z
# ----------------------------------------------------------------------------------------------
def koi_mesh(name):
    bm = bmesh.new()
    xs = 26
    rings = []
    hx = []
    for i in range(xs + 1):
        t = i / xs                                            # 0 nose .. 1 tail root
        x = 0.5 - t * 0.78
        w = 0.105 * math.sin(math.pi * min(0.93, 0.08 + t * 1.05)) ** 0.8 * (1 - 0.35 * t)
        h = 0.07 * math.sin(math.pi * min(0.93, 0.06 + t * 1.05)) ** 0.9
        w, h = max(w, 0.024 if t > 0.5 else 0.0), max(h, 0.018 if t > 0.5 else 0.0)   # a real tail stalk
        ring = []
        for j in range(10):
            a = 2 * math.pi * j / 10
            ring.append(bm.verts.new((x, math.cos(a) * w + 1e-4, math.sin(a) * h + 0.01)))
            hx.append((t * 0.78, 0.0))
        rings.append(ring)
    for i in range(xs):
        for j in range(10):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % 10], rings[i + 1][(j + 1) % 10], rings[i + 1][j]))
    nose = bm.verts.new((0.505, 0, 0.01))
    hx.append((0.0, 0.0))
    for j in range(10):
        bm.faces.new((nose, rings[0][(j + 1) % 10], rings[0][j]))
    tailroot = rings[-1]

    def fin(pts, tag):
        vs = []
        for p in pts:
            vs.append(bm.verts.new(p))
            hx.append(((0.5 - p[0]) / 1.0, tag))
        bm.faces.new(vs)

    # tail: two soft lobes
    fin([(-0.25, 0.02, 0.012), (-0.46, 0.13, 0.012), (-0.52, 0.07, 0.012), (-0.44, 0.0, 0.012),
         (-0.52, -0.07, 0.012), (-0.46, -0.13, 0.012), (-0.25, -0.02, 0.012)], 1.0)
    # pectoral fins
    for s in (-1, 1):
        fin([(0.24, s * 0.07, 0.0), (0.12, s * 0.2, -0.005), (0.06, s * 0.17, -0.005), (0.14, s * 0.07, 0.0)], 1.0)
    # low dorsal fin
    fin([(0.12, 0, 0.075), (-0.02, 0, 0.11), (-0.18, 0, 0.07), (-0.18, 0, 0.06), (0.12, 0, 0.065)], 1.0)
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for nm, k in (("hrp_x", 0), ("hrp_fin", 1)):
        at = me.attributes.get(nm) or me.attributes.new(nm, "FLOAT", "POINT")
        vals = [v[k] for v in hx][:len(me.vertices)]
        at.data.foreach_set("value", vals + [0.0] * (len(me.vertices) - len(vals)))
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    return me


def koi_material():
    mat, rebuilt = shading._fresh_mat(MAT_KOI)
    if not rebuilt and mat.get("hrp_fauna_ver") == FAUNA_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fauna_ver"] = FAUNA_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1400, 0)
    pal.node_tree = shading.palette_group()
    tc = g.n("ShaderNodeTexCoord", -1400, 400)
    rnd = g.n("ShaderNodeAttribute", -1400, 200, attribute_name="hrp_koi", attribute_type="GEOMETRY")
    seed = g.n("ShaderNodeSeparateXYZ", -1200, 200)
    g.link(rnd, "Vector", seed, "Vector")
    # patches: kohaku red / showa black / ogon gold, chosen per fish
    pv = only(g.vmath("ADD", -1100, 400, g.out(tc, "Object"), g.out(rnd, "Vector")).outputs)
    pv = only(g.vmath("MULTIPLY", -1000, 400, pv, (1.0, 2.2, 2.2)).outputs)
    nz = g.n("ShaderNodeTexNoise", -850, 400, noise_dimensions="3D")
    g.set(nz, "Scale", 3.2)
    g.set(nz, "Detail", 2.0)
    g.links.new(pv, nz.inputs["Vector"])
    patch = g.maprange(-650, 400, g.out(nz, "Fac"), 0.47, 0.50, smooth=True)          # every fish shows red
    nz2 = g.n("ShaderNodeTexNoise", -850, 150, noise_dimensions="3D")
    g.set(nz2, "Scale", 5.5)
    g.links.new(pv, nz2.inputs["Vector"])
    black = g.maprange(-650, 150, g.out(nz2, "Fac"), 0.60, 0.62, smooth=True)
    showa = g.math("GREATER_THAN", -650, 0, g.out(seed, "Y"), 0.62)
    gold = g.math("GREATER_THAN", -650, -100, g.out(seed, "Y"), 0.86)
    black = g.math("MULTIPLY", -500, 100, g.out(black, "Result"), g.out(showa, 0))
    red = (0.81, 0.12, 0.022, 1.0)                                   # #E8602A
    base = g.mix(-400, 400, fac=g.out(patch, "Result"), a=(0.9, 0.85, 0.78, 1.0), b=red)
    base = g.mix(-250, 400, fac=g.out(black, 0), a=g.mixout(base), b=(0.03, 0.03, 0.04, 1.0))
    base = g.mix(-100, 400, fac=g.out(gold, 0), a=g.mixout(base), b=(1.0, 0.5, 0.05, 1.0))                # bright yamabuki, not tan
    # seen through the water: pulled towards the water colour, fins more than the body
    fin = g.n("ShaderNodeAttribute", -1400, -300, attribute_name="hrp_fin", attribute_type="GEOMETRY")
    sub = g.math("MULTIPLY_ADD", -500, -300, g.out(fin, "Fac"), 0.3, 0.26)          # just under the surface
    air = g.n("ShaderNodeAttribute", -650, -450, attribute_name="hrp_air", attribute_type="GEOMETRY")
    sub = g.math("MULTIPLY", -400, -350, g.out(sub, 0), only(g.math("SUBTRACT", -500, -450, 1.0, g.out(air, "Fac"))
                 .outputs))                                               # ...except a koi leaping in the air
    deep = g.mix(-200, -100, fac=0.6, a=g.out(pal, "water_mid"), b=g.out(pal, "water_deep"))
    col = g.mix(50, 300, fac=g.out(sub, 0), a=g.mixout(base), b=g.mixout(deep))
    lum = g.n("ShaderNodeRGBToBW", -200, -300)                       # dimmed with the water (night, storm)
    g.link(pal, "water_mid", lum, "Color")
    dim = g.math("MINIMUM", 0, -300, only(g.math("MULTIPLY", -100, -300, g.out(lum, 0), 3.2).outputs), 1.0)
    dc = g.n("ShaderNodeCombineColor", 150, -300)
    for ch in ("Red", "Green", "Blue"):
        g.link(dim, 0, dc, ch)
    col = g.mix(250, 300, "MULTIPLY", fac=1.0, a=g.mixout(col), b=only(dc.outputs))
    shading._emit_out(g, g.mixout(col), 400, 300, pal=pal)
    return mat


def koi_object():
    ob = bpy.data.objects.get(KOI_OB)
    if ob is not None and ob.get("hrp_ver") == FAUNA_VER:
        return ob
    me = koi_mesh(KOI_OB)
    me.materials.clear()
    me.materials.append(koi_material())
    if ob is None:
        ob = bpy.data.objects.new(KOI_OB, me)
        from .pondlife import _asset_coll
        _asset_coll().objects.link(ob)
    ob.hide_render = ob.hide_viewport = True
    ob["hrp_ver"] = FAUNA_VER
    return ob


# ----------------------------------------------------------------------------------------------
# fish: loops in the deep zone of a pond, body wave by time
# ----------------------------------------------------------------------------------------------
def fish_group():
    ng, rebuilt = fresh_group(FISH, "GeometryNodeTree", FAUNA_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Pond", "INPUT", "NodeSocketObject")
    iface(ng, "Koi", "INPUT", "NodeSocketObject")
    iface(ng, "Count", "INPUT", "NodeSocketInt", 6, 0, 200)
    iface(ng, "Size", "INPUT", "NodeSocketFloat", 0.5, 0.05, 5.0, "Fish length", "DISTANCE")
    iface(ng, "Speed", "INPUT", "NodeSocketFloat", 0.35, 0.0, 5.0, "Swimming speed (m/s)")
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Leap Every", "INPUT", "NodeSocketFloat", 6.0, 0.0, 120.0,
          "A koi leaps out of the water every this many seconds (0 = never)")
    iface(ng, "Splash Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    for it in ng.interface.items_tree:
        if getattr(it, "name", "") == "Splash Material":
            from . import waterfall as _wf
            it.default_value = _wf.splash_material()
    gi = g.n("NodeGroupInput", -2000, 0)
    go = g.n("NodeGroupOutput", 1800, 0)
    oi = g.n("GeometryNodeObjectInfo", -1800, 0, transform_space="RELATIVE")
    g.link(gi, "Pond", oi, "Object")
    surf = g.n("GeometryNodeSeparateGeometry", -1600, 0, domain="FACE")
    g.link(oi, "Geometry", surf, "Geometry")
    na = g.n("GeometryNodeInputNamedAttribute", -1800, -200, data_type="FLOAT_VECTOR")
    na.inputs["Name"].default_value = "hrp_a"
    g.link(na, "Exists", surf, "Selection")
    sa = g.n("ShaderNodeSeparateXYZ", -1600, -200)
    g.link(na, "Attribute", sa, "Vector")
    deep = g.maprange(-1450, -200, g.out(sa, "X"), 0.5, 0.75, smooth=True)
    pondonly = g.math("SUBTRACT", -1450, -350, 1.0, g.out(sa, "Z"))
    dens = g.math("MULTIPLY", -1300, -250, g.out(deep, "Result"), g.out(pondonly, 0))
    dist = g.n("GeometryNodeDistributePointsOnFaces", -1150, 0, distribute_method="POISSON")
    g.link(surf, "Selection", dist, "Mesh")
    dist.inputs["Distance Min"].default_value = 1.2
    dist.inputs["Density Max"].default_value = 5.0
    g.link(dens, 0, dist, "Density Factor")
    g.link(gi, "Seed", dist, "Seed")
    # Count fish picked at random over the pond (not by face order)
    srt_key = g.n("FunctionNodeRandomValue", -1000, -400, data_type="FLOAT")
    g.link(gi, "Seed", srt_key, "Seed")
    srt = g.n("GeometryNodeSortElements", -900, 0, domain="POINT")
    g.link(dist, "Points", srt, "Geometry")
    g.link(srt_key, "Value", srt, "Sort Weight", akind="VALUE")
    idx = g.n("GeometryNodeInputIndex", -1000, -300)
    keep = g.n("FunctionNodeCompare", -850, -300, data_type="INT", operation="LESS_THAN")
    g.link(idx, 0, keep, "A", bkind="INT")
    g.link(gi, "Count", keep, "B", bkind="INT")
    sel = g.n("GeometryNodeSeparateGeometry", -850, 0, domain="POINT")
    g.link(srt, 0, sel, "Geometry")
    g.link(keep, 0, sel, "Selection")
    # each fish: loop radius from the distance to the shore, phase and direction random
    shore = g.math("MULTIPLY", -850, -500, g.out(sa, "Y"), 0.45)            # evaluated on the source points below
    r_rand = g.n("FunctionNodeRandomValue", -850, -700, data_type="FLOAT")
    g.set(r_rand, "Min", 0.5, "VALUE")
    g.set(r_rand, "Max", 1.4, "VALUE")
    g.link(gi, "Seed", r_rand, "Seed")
    sh_s = g.n("GeometryNodeSampleNearestSurface", -650, -500, data_type="FLOAT")
    g.link(surf, "Selection", sh_s, "Mesh")
    g.link(shore, 0, sh_s, "Value")
    rad = g.math("MINIMUM", -450, -550, g.out(sh_s, "Value", "VALUE"), g.out(r_rand, "Value", "VALUE"))
    rad = g.math("MAXIMUM", -350, -550, g.out(rad, 0), 0.35)
    ph = g.n("FunctionNodeRandomValue", -650, -800, data_type="FLOAT")
    g.set(ph, "Max", 6.283, "VALUE")
    dirn = g.n("FunctionNodeRandomValue", -650, -950, data_type="BOOLEAN")
    dsg = g.math("MULTIPLY_ADD", -450, -950, g.out(dirn, "Value", "BOOLEAN"), 2.0, -1.0)
    tm = g.n("GeometryNodeInputSceneTime", -650, -1100)
    om = g.math("DIVIDE", -450, -1100, g.out(gi, "Speed"), g.out(rad, 0))
    om = g.math("MULTIPLY", -350, -1100, g.out(om, 0), g.out(dsg, 0))
    ang = g.math("MULTIPLY_ADD", -250, -1000, g.out(tm, "Seconds"), g.out(om, 0), g.out(ph, "Value", "VALUE"))
    ang2 = g.math("MULTIPLY", -250, -1200, g.out(ang, 0), 2.0)                   # a lazy figure of eight
    cx = g.math("MULTIPLY", -100, -850, only(g.math("SINE", -150, -850, g.out(ang, 0)).outputs), g.out(rad, 0))
    cy = g.math("MULTIPLY", -100, -1000, only(g.math("SINE", -150, -1000, g.out(ang2, 0)).outputs),
                only(g.math("MULTIPLY", -200, -1100, g.out(rad, 0), 0.55).outputs))
    off = g.n("ShaderNodeCombineXYZ", 50, -900)
    g.link(cx, 0, off, "X")
    g.link(cy, 0, off, "Y")
    off.inputs["Z"].default_value = 0.002
    mv = g.n("GeometryNodeSetPosition", 200, 0)
    g.link(sel, "Selection", mv, "Geometry")
    g.link(off, 0, mv, "Offset")
    # heading: along the loop tangent
    # heading = direction of travel: d/dt (r sin a, 0.55 r sin 2a) ~ (cos a, 1.1 cos 2a) * sign
    vx = g.math("MULTIPLY", -100, -1300, only(g.math("COSINE", -150, -1300, g.out(ang, 0)).outputs), g.out(dsg, 0))
    vy = g.math("MULTIPLY", -100, -1400, only(g.math("MULTIPLY", -150, -1400, only(g.math("COSINE", -200, -1400,
                g.out(ang2, 0)).outputs), 1.1).outputs), g.out(dsg, 0))
    head = g.math("ARCTAN2", 50, -1150, g.out(vy, 0), g.out(vx, 0))
    rot = g.n("ShaderNodeCombineXYZ", 200, -1150)
    g.link(head, 0, rot, "Z")
    kv = g.n("FunctionNodeRandomValue", 200, -1350, data_type="FLOAT_VECTOR")
    st = g.n("GeometryNodeStoreNamedAttribute", 350, 0, data_type="FLOAT_VECTOR", domain="POINT")
    g.link(mv, 0, st, "Geometry")
    st.inputs["Name"].default_value = "hrp_koi"
    g.link(kv, "Value", st, "Value", akind="VECTOR", bkind="VECTOR")
    ko = g.n("GeometryNodeObjectInfo", 350, -400)
    g.link(gi, "Koi", ko, "Object")
    inst = g.n("GeometryNodeInstanceOnPoints", 550, 0)
    g.link(st, 0, inst, "Points")
    g.link(ko, "Geometry", inst, "Instance")
    g.link(rot, 0, inst, "Rotation")
    fsc = g.n("ShaderNodeCombineXYZ", 450, -500)                     # flat: always under the lily pads
    g.link(gi, "Size", fsc, "X")
    g.link(gi, "Size", fsc, "Y")
    g.link(g.math("MULTIPLY", 350, -600, g.out(gi, "Size"), 0.35), 0, fsc, "Z")
    g.link(fsc, 0, inst, "Scale")
    # body wave: realize and bend each fish sideways along its length
    real = g.n("GeometryNodeRealizeInstances", 750, 0)
    g.link(inst, 0, real, "Geometry")
    hx = g.n("GeometryNodeInputNamedAttribute", 750, -300, data_type="FLOAT")
    hx.inputs["Name"].default_value = "hrp_x"
    kk = g.n("GeometryNodeInputNamedAttribute", 750, -450, data_type="FLOAT_VECTOR")
    kk.inputs["Name"].default_value = "hrp_koi"
    kks = g.n("ShaderNodeSeparateXYZ", 900, -450)
    g.link(kk, "Attribute", kks, "Vector")
    wave = g.math("MULTIPLY_ADD", 1050, -350, g.out(hx, "Attribute"), -7.0,
                  only(g.math("MULTIPLY_ADD", 900, -600, g.out(tm, "Seconds"), 7.5,
                         only(g.math("MULTIPLY", 800, -650, g.out(kks, "X"), 30.0).outputs)).outputs))
    amp = g.math("MULTIPLY", 1050, -500, only(g.math("POWER", 950, -500, g.out(hx, "Attribute"), 1.6).outputs),
                 only(g.math("MULTIPLY", 950, -650, g.out(gi, "Size"), 0.12).outputs))
    side = g.math("MULTIPLY", 1200, -400, only(g.math("SINE", 1150, -350, g.out(wave, 0)).outputs), g.out(amp, 0))
    # sideways in each fish's own frame: perpendicular to its heading (stored on the points as hrp_head)
    hd = g.n("GeometryNodeInputNamedAttribute", 1050, -800, data_type="FLOAT")
    hd.inputs["Name"].default_value = "hrp_head"
    sx = g.math("MULTIPLY", 1300, -700, only(g.math("SINE", 1200, -700, g.out(hd, "Attribute")).outputs), -1.0)
    sy = g.math("COSINE", 1200, -850, g.out(hd, "Attribute"))
    bo = g.n("ShaderNodeCombineXYZ", 1400, -600)
    g.link(g.math("MULTIPLY", 1350, -650, g.out(sx, 0), g.out(side, 0)), 0, bo, "X")
    g.link(g.math("MULTIPLY", 1350, -800, g.out(sy, 0), g.out(side, 0)), 0, bo, "Y")
    bend = g.n("GeometryNodeSetPosition", 1500, 0)
    g.link(real, 0, bend, "Geometry")
    g.link(bo, 0, bend, "Offset")
    # the leaper has its own spot in the deep water (there may be no point left over after the swimmers)
    dist2 = g.n("GeometryNodeDistributePointsOnFaces", -1150, -2400, distribute_method="POISSON")
    g.link(surf, "Selection", dist2, "Mesh")
    dist2.inputs["Distance Min"].default_value = 0.8
    dist2.inputs["Density Max"].default_value = 5.0
    g.link(dens, 0, dist2, "Density Factor")
    g.link(g.math("ADD", -1300, -2500, g.out(gi, "Seed"), 77.0), 0, dist2, "Seed", bkind="INT")
    idx0 = g.n("GeometryNodeInputIndex", -1000, -2500)
    leap = _leaper(g, gi, dist2.outputs["Points"], idx0, tm, ko, g.out(surf, "Selection"))
    fj = g.n("GeometryNodeJoinGeometry", 1650, 0)
    g.link(bend, 0, fj, "Geometry")
    g.link(leap, 0, fj, "Geometry")
    g.link(fj, 0, go, "Geometry")
    # hrp_head on the points before instancing (the heading angle, for the bend direction)
    sth = g.n("GeometryNodeStoreNamedAttribute", 450, 200, data_type="FLOAT", domain="POINT")
    g.link(st, 0, sth, "Geometry")
    sth.inputs["Name"].default_value = "hrp_head"
    g.link(head, 0, sth, "Value", bkind="VALUE")
    g.link(sth, 0, inst, "Points")
    return ng


def _leaper(g, gi, srt, idx, tm, ko, surf=None):
    """Now and then one koi leaps out of the pond in an arc: a crown of splash and a ring where it leaves the water
    and where it dives back in. Returns the geometry (fish + splashes)."""
    from .pondlife import ring_disc
    X, Y = 0, -2600
    one = g.n("FunctionNodeCompare", X, Y, data_type="INT", operation="EQUAL")      # its first point
    g.link(idx, 0, one, "A", bkind="INT")
    g.inp(one, "B", "INT").default_value = 0
    pt = g.n("GeometryNodeSeparateGeometry", X + 150, Y, domain="POINT")
    g.links.new(srt, pt.inputs["Geometry"])
    g.link(one, 0, pt, "Selection")
    on = g.math("GREATER_THAN", X, Y - 150, g.out(gi, "Leap Every"), 0.05)
    P = g.math("MAXIMUM", X, Y - 250, g.out(gi, "Leap Every"), 2.5)
    J = 1.0                                                              # seconds in the air
    tt = g.math("ADD", X + 150, Y - 250, g.out(tm, "Seconds"), 2.0)       # nothing mid-splash on frame 1
    k = g.math("FLOOR", X + 300, Y - 200, only(g.math("DIVIDE", X + 250, Y - 250, g.out(tt, 0), g.out(P, 0)).outputs))
    tin = g.math("SUBTRACT", X + 450, Y - 250, g.out(tt, 0), only(g.math("MULTIPLY", X + 350, Y - 300, g.out(k, 0),
                 g.out(P, 0)).outputs))                              # seconds since this period began
    u = g.math("DIVIDE", X + 550, Y - 250, g.out(tin, 0), J)
    air = g.math("LESS_THAN", X + 650, Y - 300, g.out(u, 0), 1.0)
    uc = g.math("MINIMUM", X + 650, Y - 200, g.out(u, 0), 1.0)
    hr = g.n("FunctionNodeRandomValue", X + 350, Y - 450, data_type="FLOAT")     # a new heading every leap
    g.set(hr, "Max", 6.283, "VALUE")
    g.link(g.math("ADD", X + 250, Y - 500, g.out(k, 0), 0.0), 0, hr, "ID", bkind="INT")
    # always across the pond, towards its middle (takeoff and entry both over open water)
    bbx = g.n("GeometryNodeBoundBox", X + 100, Y - 1200)
    g.links.new(surf, sock(bbx.inputs, "Geometry"))
    bc = g.vmath("SCALE", X + 250, Y - 1200, only(g.vmath("ADD", X + 200, Y - 1250, g.out(bbx, "Min"), g.out(bbx, "Max"))
                 .outputs), scale=0.5)
    tod = g.vmath("SUBTRACT", X + 350, Y - 1200, only(bc.outputs), only(g.n("GeometryNodeInputPosition", X + 250, Y - 1350)
                  .outputs))
    tds = _xyz_s(g, X + 450, Y - 1200, only(tod.outputs))
    hd_ = only(g.math("ADD", X + 600, Y - 1150, only(g.math("ARCTAN2", X + 550, Y - 1200, g.out(tds, "Y"), g.out(tds, "X"))
                 .outputs), only(g.math("MULTIPLY_ADD", X + 500, Y - 1300, g.out(hr, "Value", "VALUE"), 0.2, -0.63)
                 .outputs)).outputs)
    S = g.out(gi, "Size")
    D = g.math("MULTIPLY", X + 450, Y - 600, S, 2.2)                       # horizontal reach
    H = g.math("MULTIPLY", X + 450, Y - 700, S, 1.9)                       # height of the arc
    dx = g.math("MULTIPLY", X + 800, Y - 500, only(g.math("SUBTRACT", X + 700, Y - 500, g.out(uc, 0), 0.5).outputs),
                g.out(D, 0))
    zz = g.math("SUBTRACT", X + 900, Y - 650, only(g.math("MULTIPLY", X + 800, Y - 650, only(g.math("MULTIPLY", X + 700, Y - 650,
                g.out(uc, 0), only(g.math("SUBTRACT", X + 600, Y - 700, 1.0, g.out(uc, 0)).outputs)).outputs),
                only(g.math("MULTIPLY", X + 700, Y - 750, g.out(H, 0), 4.0).outputs)).outputs),
                only(g.math("MULTIPLY", X + 800, Y - 800, S, 0.15).outputs))
    cs, sn = g.math("COSINE", X + 800, Y - 900, hd_), g.math("SINE", X + 800, Y - 1000, hd_)
    off = g.n("ShaderNodeCombineXYZ", X + 1000, Y - 600)
    g.link(g.math("MULTIPLY", X + 900, Y - 550, g.out(dx, 0), g.out(cs, 0)), 0, off, "X")
    g.link(g.math("MULTIPLY", X + 900, Y - 600, g.out(dx, 0), g.out(sn, 0)), 0, off, "Y")
    g.link(zz, 0, off, "Z")
    fp = g.n("GeometryNodeSetPosition", X + 1100, Y)
    g.link(pt, "Selection", fp, "Geometry")
    g.link(off, 0, fp, "Offset")
    pitch = g.math("ARCTAN2", X + 1000, Y - 800, only(g.math("MULTIPLY", X + 900, Y - 850, only(g.math("MULTIPLY", X + 800,
                   Y - 850, g.out(H, 0), 4.0).outputs), only(g.math("SUBTRACT", X + 800, Y - 900, 1.0,
                   only(g.math("MULTIPLY", X + 700, Y - 900, g.out(uc, 0), 2.0).outputs)).outputs)).outputs),
                   g.out(D, 0))
    rot = g.n("ShaderNodeCombineXYZ", X + 1150, Y - 800)
    g.link(g.math("MULTIPLY", X + 1050, Y - 750, g.out(pitch, 0), -1.0), 0, rot, "Y")
    g.links.new(hd_, rot.inputs["Z"])
    vis = g.math("MULTIPLY", X + 1150, Y - 300, g.out(air, 0), g.out(on, 0))
    fsc = g.n("ShaderNodeCombineXYZ", X + 1250, Y - 400)
    sv_ = g.math("MULTIPLY", X + 1150, Y - 400, only(g.math("MULTIPLY", X + 1050, Y - 450, S, 1.25).outputs),
                 g.out(vis, 0))
    g.link(sv_, 0, fsc, "X")
    g.link(sv_, 0, fsc, "Y")
    g.link(g.math("MULTIPLY", X + 1150, Y - 450, g.out(sv_, 0), 0.85), 0, fsc, "Z")
    kv = g.n("FunctionNodeRandomValue", X + 1100, Y - 150, data_type="FLOAT_VECTOR")
    kv.inputs["Seed"].default_value = 5
    kv.inputs["Min"].default_value = (0.0, 0.0, 0.0)                         # the leaper is always a red-and-white
    kv.inputs["Max"].default_value = (1.0, 0.55, 1.0)                        # kohaku: it is the hero of the shot
    airs = g.n("GeometryNodeStoreNamedAttribute", X + 1200, Y + 100, data_type="FLOAT", domain="POINT")
    g.link(fp, 0, airs, "Geometry")
    airs.inputs["Name"].default_value = "hrp_air"
    airs.inputs["Value"].default_value = 1.0
    fp = airs
    kst = g.n("GeometryNodeStoreNamedAttribute", X + 1250, Y, data_type="FLOAT_VECTOR", domain="POINT")
    g.link(fp, 0, kst, "Geometry")
    kst.inputs["Name"].default_value = "hrp_koi"
    g.link(kv, "Value", kst, "Value", akind="VECTOR", bkind="VECTOR")
    ust = g.n("GeometryNodeStoreNamedAttribute", X + 1320, Y, data_type="FLOAT", domain="POINT")
    g.link(kst, 0, ust, "Geometry")
    ust.inputs["Name"].default_value = "hrp_leapu"
    g.link(uc, 0, ust, "Value", bkind="VALUE")
    fi0 = g.n("GeometryNodeInstanceOnPoints", X + 1400, Y)
    g.link(ust, 0, fi0, "Points")
    g.link(ko, "Geometry", fi0, "Instance")
    g.link(rot, 0, fi0, "Rotation")
    g.link(fsc, 0, fi0, "Scale")
    fre = g.n("GeometryNodeRealizeInstances", X + 1500, Y)                      # bend the body along the arc
    g.link(fi0, 0, fre, "Geometry")
    bx = g.n("GeometryNodeInputNamedAttribute", X + 1400, Y + 200, data_type="FLOAT")
    bx.inputs["Name"].default_value = "hrp_x"
    bu = g.n("GeometryNodeInputNamedAttribute", X + 1400, Y + 300, data_type="FLOAT")
    bu.inputs["Name"].default_value = "hrp_leapu"
    bend = g.math("MULTIPLY", X + 1600, Y + 250, only(g.math("POWER", X + 1500, Y + 200, g.out(bx, "Attribute"), 1.8)
                  .outputs), only(g.math("MULTIPLY", X + 1500, Y + 300, only(g.math("MULTIPLY_ADD", X + 1400, Y + 350,
                  g.out(bu, "Attribute"), 2.0, -1.0).outputs), only(g.math("MULTIPLY", X + 1400, Y + 450, S, 0.28)
                  .outputs)).outputs))
    bo = g.n("ShaderNodeCombineXYZ", X + 1700, Y + 250)
    g.link(bend, 0, bo, "Z")
    fi = g.n("GeometryNodeSetPosition", X + 1650, Y)
    g.link(fre, 0, fi, "Geometry")
    g.link(bo, 0, fi, "Offset")
    # splashes: where it leaves the water (age from 0) and where it dives back in (age from J)
    parts = []
    for e, sign in ((0.0, -1.0), (J, 1.0)):
        age = g.math("SUBTRACT", X, Y - 1300, g.out(tin, 0), e)
        live = g.math("MULTIPLY", X + 100, Y - 1300, only(g.math("GREATER_THAN", X, Y - 1400, g.out(age, 0), 0.0).outputs),
                      only(g.math("LESS_THAN", X, Y - 1450, g.out(age, 0), 0.9).outputs))
        live = g.math("MULTIPLY", X + 200, Y - 1300, g.out(live, 0), g.out(on, 0))
        sp_ = g.n("ShaderNodeCombineXYZ", X + 300, Y - 1200)
        half = g.math("MULTIPLY", X + 200, Y - 1150, g.out(D, 0), 0.5 * sign)
        g.link(g.math("MULTIPLY", X + 250, Y - 1100, g.out(half, 0), g.out(cs, 0)), 0, sp_, "X")
        g.link(g.math("MULTIPLY", X + 250, Y - 1200, g.out(half, 0), g.out(sn, 0)), 0, sp_, "Y")
        sp_.inputs["Z"].default_value = 0.005
        spt = g.n("GeometryNodeSetPosition", X + 450, Y - 1100)
        g.link(pt, "Selection", spt, "Geometry")
        g.link(sp_, 0, spt, "Offset")
        # a ring that spreads
        rd = ring_disc(g, X + 300, Y - 1700)
        rs_ = g.math("MULTIPLY", X + 500, Y - 1500, only(g.math("MULTIPLY_ADD", X + 400, Y - 1500, g.out(age, 0), 1.6, 0.25)
                     .outputs), only(g.math("MULTIPLY", X + 400, Y - 1600, S, g.out(live, 0)).outputs))
        ri = g.n("GeometryNodeInstanceOnPoints", X + 650, Y - 1100)
        g.link(spt, 0, ri, "Points")
        g.links.new(only(rd.outputs), ri.inputs["Instance"])
        g.link(rs_, 0, ri, "Scale")
        parts.append(ri)
        # a crown splash (the waterfall's crown at fish scale) rising and falling over 0.6 s
        from .waterfall import crown_geo
        ctr = g.n("GeometryNodeSampleIndex", X + 450, Y - 2150, data_type="FLOAT_VECTOR", domain="POINT")
        g.link(spt, 0, ctr, "Geometry")
        g.link(g.n("GeometryNodeInputPosition", X + 300, Y - 2200), 0, ctr, "Value")
        lf = g.math("SINE", X + 600, Y - 2300, only(g.math("MULTIPLY", X + 500, Y - 2300, only(g.math("MINIMUM", X + 400, Y - 2300,
                    only(g.math("DIVIDE", X + 300, Y - 2300, g.out(age, 0), 0.6).outputs), 1.0).outputs),
                    3.1416).outputs))
        lf = g.math("MULTIPLY", X + 700, Y - 2300, g.out(lf, 0), g.out(live, 0))
        cr = crown_geo(g, X + 300, Y - 2500, g.out(tm, "Seconds"),
                       only(g.math("MULTIPLY", X + 200, Y - 2450, S, 0.27).outputs),
                       only(g.math("MULTIPLY", X + 200, Y - 2550, S, 0.27).outputs),
                       only(g.math("MULTIPLY", X + 200, Y - 2650, S, 0.65).outputs), False, g.out(lf, 0))
        crx = g.n("GeometryNodeTransform", X + 1500, Y - 2500)
        g.links.new(cr, crx.inputs["Geometry"])
        g.links.new(g.out(ctr, "Value", "VECTOR"), crx.inputs["Translation"])
        on_ = g.math("GREATER_THAN", X + 1400, Y - 2650, g.out(lf, 0), 0.02)        # gone between splashes
        osc = g.n("ShaderNodeCombineXYZ", X + 1450, Y - 2650)
        for ax in ("X", "Y", "Z"):
            g.link(on_, 0, osc, ax)
        g.link(osc, 0, crx, "Scale")
        cm = g.n("GeometryNodeSetMaterial", X + 1650, Y - 2500)
        g.link(crx, 0, cm, "Geometry")
        g.link(gi, "Splash Material", cm, "Material")
        parts.append(cm)
    jn = g.n("GeometryNodeJoinGeometry", X + 1600, Y)
    g.link(fi, 0, jn, "Geometry")
    for pp in parts:
        g.link(pp, 0, jn, "Geometry")
    return jn


def add_fish(context, pond, count=6, size=0.5, speed=0.35):
    """A 'Harappa Fish' object swimming in this pond (re-run to update it)."""
    name = f"{pond.name} Fish"
    ob = bpy.data.objects.get(name)
    if ob is None:
        me = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, me)
        water.water_collection(context.scene).objects.link(ob)
    ob.matrix_world = pond.matrix_world.copy()
    ob.parent = pond
    ob.matrix_parent_inverse = pond.matrix_world.inverted()
    mod = ob.modifiers.get(FISH_MOD) or ob.modifiers.new(FISH_MOD, "NODES")
    mod.node_group = fish_group()
    mod_input(mod, "Pond", pond)
    mod_input(mod, "Koi", koi_object())
    mod_input(mod, "Count", count)
    mod_input(mod, "Size", size)
    mod_input(mod, "Speed", speed)
    from . import waterfall as _wf
    mod_input(mod, "Splash Material", _wf.splash_material())
    ob["hrp_fish"] = pond.name
    ob.visible_shadow = False
    return ob


# ----------------------------------------------------------------------------------------------
# boat
# ----------------------------------------------------------------------------------------------
def boat_mesh(name):
    """A small rowboat, 2.4 m long, keel at z = 0; hrp_wood = plank stripes coordinate."""
    bm = bmesh.new()
    n, m = 16, 9
    rows = []
    for i in range(n + 1):
        t = i / n
        x = (t - 0.5) * 2.4
        half = 0.55 * math.sin(math.pi * t * 0.88) ** 0.6       # pointed bow, a real transom at the stern
        rise = 0.12 * (2 * t - 1) ** 4
        row = []
        for j in range(m + 1):
            s = j / m * 2 - 1                                  # -1 .. 1 across, bottom at 0
            y = s * half
            z = 0.45 * abs(s) ** 1.8 + rise
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for i in range(n):
        for j in range(m):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    rim = [rows[i][0] for i in range(n + 1)] + [rows[i][m] for i in range(n, -1, -1)]
    gun = []                                                   # a gunwale rail along the rim
    for v in rim:
        gun.append(bm.verts.new((v.co.x, v.co.y * 1.04, v.co.z + 0.05)))
    for k in range(len(rim) - 1):
        bm.faces.new((rim[k], rim[k + 1], gun[k + 1], gun[k]))
    stern = [rows[n][j] for j in range(m + 1)]                 # a flat transom closes the stern
    bm.faces.new(stern[::-1])
    # two thwarts (seats)
    for sx in (-0.4, 0.45):
        bmesh.ops.create_cube(bm, size=1.0, matrix=__import__("mathutils").Matrix.LocRotScale(
            Vector((sx, 0, 0.3)), None, Vector((0.22, 0.92, 0.04))))
    zf, prev = 0.165, None                                     # a bilge floor over the whole inside: the pond
    for i in range(n + 1):                                     # surface never shows inside the hull
        t = i / n
        half = 0.55 * math.sin(math.pi * t * 0.88) ** 0.6
        rise = 0.12 * (2 * t - 1) ** 4
        sf = min(1.0, max(0.0, (zf - rise) / 0.45) ** (1 / 1.8))
        x = (t - 0.5) * 2.4
        cur = (bm.verts.new((x, -sf * half * 0.985, zf)), bm.verts.new((x, sf * half * 0.985, zf)))
        if prev is not None and (cur[1].co.y - cur[0].co.y) + (prev[1].co.y - prev[0].co.y) > 1e-4:
            bm.faces.new((prev[0], prev[1], cur[1], cur[0]))
        prev = cur
    for x0, x1, hw_ in ((-0.55, 0.85, 0.21), (-0.95, -0.5, 0.11)):   # floorboards on top
        bmesh.ops.create_cube(bm, size=1.0, matrix=__import__("mathutils").Matrix.LocRotScale(
            Vector(((x0 + x1) / 2, 0, 0.18)), None, Vector((x1 - x0, hw_ * 2, 0.02))))
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
    return me


def _xyz_s(g, x, y, vec):
    sep = g.n("ShaderNodeSeparateXYZ", x, y)
    g.links.new(vec, sock(sep.inputs, "Vector"))
    return sep


def boat_material():
    mat, rebuilt = shading._fresh_mat(MAT_BOAT)
    if not rebuilt and mat.get("hrp_fauna_ver") == FAUNA_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fauna_ver"] = FAUNA_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1200, 0)
    pal.node_tree = shading.palette_group()
    geo = g.n("ShaderNodeNewGeometry", -1200, 400)
    tc = g.n("ShaderNodeTexCoord", -1200, 200)
    sz = g.n("ShaderNodeSeparateXYZ", -1000, 200)
    g.link(tc, "Object", sz, "Vector")
    plank = g.math("FRACT", -800, 200, only(g.math("MULTIPLY", -900, 200, g.out(sz, "Z"), 9.0).outputs))
    seam = g.maprange(-650, 200, g.out(plank, 0), 0.08, 0.02, smooth=True)       # dark plank lines
    up_ = g.vmath("DOT_PRODUCT", -900, 0, g.out(geo, "Normal"), (0.0, 0.0, 1.0))
    inner = g.maprange(-750, 0, g.out(up_, "Value"), 0.2, 0.5, smooth=True)      # the inside faces the sky
    rail = g.maprange(-750, -150, g.out(sz, "Z"), 0.44, 0.47, smooth=True)       # the gunwale
    lit = g.mix(-500, 300, fac=0.35, a=g.out(pal, "bark_lit"), b=g.out(pal, "dirt_lit"))
    lit = g.mix(-450, 250, fac=only(g.math("MULTIPLY", -550, 150, g.out(inner, "Result"), 0.5).outputs),
                a=g.mixout(lit), b=g.out(pal, "dirt_lit"))
    lit = g.mix(-400, 200, fac=g.out(rail, "Result"), a=g.mixout(lit), b=(0.16, 0.39, 0.35, 1.0))  # faded paint #6FA8A0
    lit = g.mix(-350, 300, fac=g.out(seam, "Result"), a=g.mixout(lit), b=g.out(pal, "bark_shadow"))
    sh = g.mix(-250, 50, fac=0.5, a=g.mixout(lit), b=g.out(pal, "bark_shadow"))    # soft shade inside the hull
    cel = shading._cel_node(g, pal, -100, 300, g.out(geo, "Normal"), g.mixout(lit), g.mixout(sh), g.mixout(sh))
    oi = g.n("ShaderNodeObjectInfo", -300, 600)
    wz = g.math("SUBTRACT", -150, 600, g.out(_xyz_s(g, -300, 750, g.out(geo, "Position")), "Z"),
                g.out(_xyz_s(g, -150, 750, g.out(oi, "Location")), "Z"))
    wl = g.maprange(0, 600, g.out(wz, 0), 0.07, 0.02, smooth=True)               # wet, dark at the waterline
    wcol = g.mix(150, 400, fac=only(g.math("MULTIPLY", 50, 500, g.out(wl, "Result"), 0.8).outputs),
                 a=g.out(cel, "Color"), b=(0.018, 0.08, 0.16, 1.0))
    shading._emit_out(g, g.mixout(wcol), 300, 300, pal=pal)
    mat.use_backface_culling = False
    return mat


def float_group():
    ng, rebuilt = fresh_group(FLOAT, "GeometryNodeTree", FAUNA_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Draft", "INPUT", "NodeSocketFloat", 0.12, 0.0, 5.0, "How deep it sits in the water (buoyancy)",
          "DISTANCE")
    iface(ng, "Bob", "INPUT", "NodeSocketFloat", 0.025, 0.0, 1.0, "Up and down on the ripples", "DISTANCE")
    iface(ng, "Sway", "INPUT", "NodeSocketFloat", 0.035, 0.0, 0.5, "Rocking side to side (radians)")
    iface(ng, "Speed", "INPUT", "NodeSocketFloat", 1.0, 0.0, 10.0, "How fast it bobs")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -900, 0)
    go = g.n("NodeGroupOutput", 700, 0)
    tm = g.n("GeometryNodeInputSceneTime", -900, -300)
    t = g.math("MULTIPLY", -750, -300, g.out(tm, "Seconds"), g.out(gi, "Speed"))
    bz = g.math("MULTIPLY", -550, -250, only(g.math("SINE", -650, -250, only(g.math("MULTIPLY", -700, -200, g.out(t, 0),
                1.7).outputs)).outputs), g.out(gi, "Bob"))
    z = g.math("SUBTRACT", -400, -250, g.out(bz, 0), g.out(gi, "Draft"))
    rx = g.math("MULTIPLY", -550, -400, only(g.math("SINE", -650, -400, only(g.math("MULTIPLY_ADD", -700, -400, g.out(t, 0),
                1.1, 0.7).outputs)).outputs), g.out(gi, "Sway"))
    ry = g.math("MULTIPLY", -550, -550, only(g.math("SINE", -650, -550, only(g.math("MULTIPLY_ADD", -700, -550, g.out(t, 0),
                0.8, 2.1).outputs)).outputs), only(g.math("MULTIPLY", -650, -650, g.out(gi, "Sway"), 0.5).outputs))
    tr = g.n("ShaderNodeCombineXYZ", -250, -250)
    g.link(z, 0, tr, "Z")
    rt = g.n("ShaderNodeCombineXYZ", -250, -450)
    g.link(ry, 0, rt, "X")
    g.link(rx, 0, rt, "Y")
    xf = g.n("GeometryNodeTransform", 200, 0)
    g.link(gi, "Geometry", xf, "Geometry")
    g.link(tr, 0, xf, "Translation")
    g.link(rt, 0, xf, "Rotation")
    # a contact ring on the water round the hull (it stays on the water, it does not bob with the boat)
    from .pondlife import ring_disc
    bb = g.n("GeometryNodeBoundBox", -100, -700)
    g.link(gi, "Geometry", bb, "Geometry")
    hx = g.vmath("SUBTRACT", 50, -700, g.out(bb, "Max"), g.out(bb, "Min"))
    hxs = _xyz_s(g, 200, -700, only(hx.outputs))
    rd = ring_disc(g, -100, -900)
    rsc = g.n("ShaderNodeCombineXYZ", 400, -800)
    g.link(g.math("MULTIPLY", 300, -750, g.out(hxs, "X"), 0.47), 0, rsc, "X")
    g.link(g.math("MULTIPLY", 300, -850, g.out(hxs, "Y"), 0.43), 0, rsc, "Y")
    rsc.inputs["Z"].default_value = 1.0
    rxf = g.n("GeometryNodeTransform", 500, -900)
    g.links.new(only(rd.outputs), rxf.inputs["Geometry"])
    g.link(rsc, 0, rxf, "Scale")
    rxf.inputs["Translation"].default_value = (0.0, 0.0, 0.004)
    jn = g.n("GeometryNodeJoinGeometry", 550, 0)
    g.link(xf, 0, jn, "Geometry")
    g.link(rxf, 0, jn, "Geometry")
    nob = g.n("GeometryNodeStoreNamedAttribute", 650, 0, data_type="FLOAT", domain="POINT")    # not a rock (hull
    g.link(jn, 0, nob, "Geometry")                                    # AND its ring): no foam collar on the pond
    nob.inputs["Name"].default_value = "hrp_noobst"
    nob.inputs["Value"].default_value = 1.0
    g.link(nob, 0, go, "Geometry")
    return ng


def add_boat(context, pond, at=None, heading=None):
    """A rowboat floating on this pond (at a world point on it, or near its middle)."""
    lvl = water.pond_level(pond)
    sp = pond.data.splines[0]
    pts = sp.bezier_points if sp.type == "BEZIER" else sp.points
    poly = [(pond.matrix_world @ p.co.to_3d()).to_2d() for p in pts]
    cen = sum(poly, Vector((0.0, 0.0))) / len(poly)
    q = cen.copy() if at is None else Vector((at[0], at[1]))
    for _i in range(40):                       # in open water, at least half a boat length from the bank
        if water._inside([tuple(p) for p in poly], q.x, q.y) and \
                water._edge_dist([tuple(p) for p in poly], q.x, q.y) > 1.1:
            break
        q = q + (cen - q) * 0.12
    at = (q.x, q.y)
    if heading is None:                        # lying along the shore, not pointing at it
        r = q - cen
        heading = (math.atan2(r.y, r.x) + math.pi / 2 if r.length > 0.2 else random.uniform(0, math.tau)) + \
            random.uniform(-0.35, 0.35)
    me = boat_mesh("HRP Boat")
    if not me.materials:
        me.materials.append(boat_material())
    ob = bpy.data.objects.new("Harappa Boat", me)
    ob.location = (at[0], at[1], lvl)
    ob.rotation_euler = (0.0, 0.0, random.uniform(0, math.tau) if heading is None else heading)
    ob.scale = (0.8, 0.8, 0.8)
    from . import rocks
    rocks.props_collection(context.scene).objects.link(ob)
    sol = ob.modifiers.new("Harappa Planks", "SOLIDIFY")                 # a real hull: the inside lights up
    sol.thickness = 0.05
    sol.offset = 1.0
    mod = ob.modifiers.new(FLOAT_MOD, "NODES")
    mod.node_group = float_group()
    ob["hrp_boat"] = pond.name
    return ob


# ----------------------------------------------------------------------------------------------
# dragonflies: hover over ponds and streams, then dart to a new spot
# ----------------------------------------------------------------------------------------------
DRAGON = "HRP Dragonflies"
DRAGON_OB = "Harappa Dragonflies"
DRAGON_MOD = "Harappa Dragonflies"
MAT_DRAGON = "HRP Dragonfly"


def dragonfly_mesh():
    """About 0.16 m long (drawn a little larger than life so it reads), nose at +x; wings carry hrp_wing = 1."""
    me = bpy.data.meshes.get("HRP Dragonfly")
    if me is not None and me.get("hrp_ver") == FAUNA_VER:
        return me
    bm = bmesh.new()
    lay = bm.verts.layers.float.new("hrp_wing")
    ring = []
    for i in range(9):
        x = 0.06 - i * 0.0175
        r = 0.008 if i < 2 else 0.005 * (1 - (i - 2) / 9) + 0.002
        ring.append([bm.verts.new((x, math.cos(a) * r, math.sin(a) * r + 0.01)) for a in
                     (2 * math.pi * k / 6 for k in range(6))])
    for i in range(8):
        for k in range(6):
            bm.faces.new((ring[i][k], ring[i][(k + 1) % 6], ring[i + 1][(k + 1) % 6], ring[i + 1][k]))
    wing_vs = []
    for s in (-1, 1):
        for x0, ln in ((0.035, 0.085), (0.012, 0.078)):          # two pairs of long, narrow wings
            pts = [(x0 + 0.008, s * 0.006), (x0 + 0.016, s * ln * 0.55), (x0 + 0.008, s * ln),
                   (x0 - 0.006, s * ln * 0.95), (x0 - 0.008, s * 0.006)]
            vs = [bm.verts.new((px, py, 0.014)) for px, py in pts]
            bm.faces.new(vs if s > 0 else vs[::-1])
            wing_vs += vs
    for v in wing_vs:
        v[lay] = 1.0
    if me is None:
        me = bpy.data.meshes.new("HRP Dragonfly")
    bm.to_mesh(me)
    bm.free()
    me["hrp_ver"] = FAUNA_VER
    return me


def dragonfly_material():
    mat, rebuilt = shading._fresh_mat(MAT_DRAGON)
    if not rebuilt and mat.get("hrp_fauna_ver") == FAUNA_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_fauna_ver"] = FAUNA_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -800, 0)
    pal.node_tree = shading.palette_group()
    wing = g.n("ShaderNodeAttribute", -800, 300, attribute_name="hrp_wing", attribute_type="GEOMETRY")
    kind = g.n("ShaderNodeAttribute", -800, 450, attribute_name="hrp_dfly", attribute_type="INSTANCER")
    body = g.mix(-500, 300, fac=only(g.math("GREATER_THAN", -650, 450, g.out(kind, "Fac"), 0.6).outputs),
                 a=(0.03, 0.32, 0.55, 1.0), b=(0.72, 0.09, 0.03, 1.0))           # blue darter / red dragonfly
    col = g.mix(-300, 250, fac=g.out(wing, "Fac"), a=g.mixout(body), b=g.out(pal, "water_foam"))
    shading._emit_out(g, g.mixout(col), 0, 200, pal=pal,
                      alpha=only(g.math("SUBTRACT", -300, 0, 1.0, only(g.math("MULTIPLY", -400, 0, g.out(wing, "Fac"), 0.55)
                                   .outputs)).outputs), soft=True)
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    return mat


def dragon_group():
    ng, rebuilt = fresh_group(DRAGON, "GeometryNodeTree", FAUNA_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Water", "INPUT", "NodeSocketCollection", desc="The Harappa Water collection")
    iface(ng, "Count", "INPUT", "NodeSocketInt", 8, 0, 500)
    iface(ng, "Speed", "INPUT", "NodeSocketFloat", 0.6, 0.0, 5.0, "How often they dart to a new spot")
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Body", "INPUT", "NodeSocketObject")
    iface(ng, "Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1800, 0)
    go = g.n("NodeGroupOutput", 1200, 0)
    ci = g.n("GeometryNodeCollectionInfo", -1600, 0, transform_space="RELATIVE")
    g.link(gi, "Water", ci, "Collection")
    ci.inputs["Separate Children"].default_value = False
    re_ = g.n("GeometryNodeRealizeInstances", -1450, 0)
    g.link(ci, 0, re_, "Geometry")
    dist = g.n("GeometryNodeDistributePointsOnFaces", -1300, 0)
    g.link(re_, 0, dist, "Mesh")
    dist.inputs["Density"].default_value = 2.0
    g.link(gi, "Seed", dist, "Seed")
    dsz = g.n("GeometryNodeAttributeDomainSize", -1300, -250, component="POINTCLOUD")
    g.link(dist, "Points", dsz, "Geometry")
    keep = g.n("FunctionNodeRandomValue", -1150, -250, data_type="BOOLEAN")       # a fair pick over all water
    g.link(g.math("DIVIDE", -1250, -350, g.out(gi, "Count"), only(g.math("MAXIMUM", -1350, -400, g.out(dsz, "Point Count"),
           1.0).outputs)), 0, keep, "Probability")
    g.link(gi, "Seed", keep, "Seed")
    sel = g.n("GeometryNodeSeparateGeometry", -1150, 0, domain="POINT")
    g.link(dist, "Points", sel, "Geometry")
    g.link(keep, "Value", sel, "Selection", akind="BOOLEAN")
    # hover, then a quick dart: a random target per step, eased only in the last 20% of each step
    tm = g.n("GeometryNodeInputSceneTime", -1300, -500)
    rp = g.n("FunctionNodeRandomValue", -1300, -650, data_type="FLOAT")
    g.set(rp, "Max", 10.0, "VALUE")
    st_ = g.math("MULTIPLY_ADD", -1150, -500, g.out(tm, "Seconds"), g.out(gi, "Speed"), g.out(rp, "Value", "VALUE"))
    stp = g.math("FLOOR", -1000, -450, g.out(st_, 0))
    fr = g.math("FRACT", -1000, -600, g.out(st_, 0))
    k = g.maprange(-850, -600, g.out(fr, 0), 0.8, 1.0, smooth=True)
    pid = g.n("GeometryNodeInputIndex", -1150, -800)

    def target(x, y, step):
        c = g.n("ShaderNodeCombineXYZ", x, y)
        g.link(pid, 0, c, "X")
        g.link(step, 0, c, "Y")
        nz = g.n("ShaderNodeTexNoise", x + 150, y, noise_dimensions="3D")
        g.set(nz, "Scale", 0.37)
        g.set(nz, "Detail", 0.0)
        g.link(c, 0, nz, "Vector")
        return only(g.vmath("ADD", x + 450, y, only(g.vmath("MULTIPLY", x + 300, y, g.out(nz, "Color"), (3.0, 3.0, 0.9))
                       .outputs), (-1.5, -1.5, 0.3)).outputs)                  # 0.3 m and more above the water
    a = target(-850, -800, stp)
    b = target(-850, -1000, g.math("ADD", -1000, -1000, g.out(stp, 0), 1.0))
    off = g.n("ShaderNodeMix", -350, -850, data_type="VECTOR")
    g.link(k, "Result", off, ("Factor", 0))
    g.links.new(a, sock(off.inputs, ("A", 1)))
    g.links.new(b, sock(off.inputs, ("B", 1)))
    hov = g.n("ShaderNodeCombineXYZ", -350, -650)                     # a tiny bob while hovering
    g.link(g.math("MULTIPLY", -450, -650, only(g.math("SINE", -550, -650, only(g.math("MULTIPLY", -650, -650,
           g.out(tm, "Seconds"), 9.0).outputs)).outputs), 0.015), 0, hov, "Z")
    tot = g.vmath("ADD", -200, -750, sock(off.outputs, ("Result", 1)), only(hov.outputs))
    mv = g.n("GeometryNodeSetPosition", -900, 0)
    g.link(sel, "Selection", mv, "Geometry")
    g.links.new(only(tot.outputs), mv.inputs["Offset"])
    # heading: towards the next spot
    dirv = g.vmath("SUBTRACT", -200, -1000, b, a)
    yaw = g.math("ARCTAN2", -50, -1000, g.out(_xyz(g, -150, -1100, only(dirv.outputs)), "Y"),
                 g.out(_xyz(g, -150, -1200, only(dirv.outputs)), "X"))
    rot = g.n("ShaderNodeCombineXYZ", 100, -1000)
    g.link(yaw, 0, rot, "Z")
    bi = g.n("GeometryNodeObjectInfo", -200, -300)
    g.link(gi, "Body", bi, "Object")
    bi.inputs["As Instance"].default_value = True
    inst = g.n("GeometryNodeInstanceOnPoints", 300, 0)
    g.link(mv, 0, inst, "Points")
    g.link(bi, "Geometry", inst, "Instance")
    g.link(rot, 0, inst, "Rotation")
    inst.inputs["Scale"].default_value = (0.9, 0.9, 0.9)              # life size (about 8 cm wings)
    kd = g.n("FunctionNodeRandomValue", 300, -300, data_type="FLOAT")
    sti = g.n("GeometryNodeStoreNamedAttribute", 500, 0, data_type="FLOAT", domain="INSTANCE")
    g.link(inst, 0, sti, "Geometry")
    sti.inputs["Name"].default_value = "hrp_dfly"
    g.link(kd, "Value", sti, "Value", bkind="VALUE", akind="VALUE")
    sm = g.n("GeometryNodeSetMaterial", 700, 0)
    g.link(sti, 0, sm, "Geometry")
    g.link(gi, "Material", sm, "Material")
    g.link(sm, 0, go, "Geometry")
    return ng


def _xyz(g, x, y, vec):
    sep = g.n("ShaderNodeSeparateXYZ", x, y)
    g.links.new(vec, sock(sep.inputs, "Vector"))
    return sep


def ensure_dragonflies(context, count=8):
    sc = context.scene
    ob = bpy.data.objects.get(DRAGON_OB)
    if ob is None:
        me = bpy.data.meshes.new(DRAGON_OB)
        ob = bpy.data.objects.new(DRAGON_OB, me)
        sc.collection.objects.link(ob)
        ob.visible_shadow = False
        mod = ob.modifiers.new(DRAGON_MOD, "NODES")
    mod = ob.modifiers[DRAGON_MOD]
    mod.node_group = dragon_group()
    body = bpy.data.objects.get("HRP Dragonfly")
    if body is None:
        body = bpy.data.objects.new("HRP Dragonfly", dragonfly_mesh())
        from . import tree
        tree.assets_collection(sc).objects.link(body)
    else:
        body.data = dragonfly_mesh()
    if not body.data.materials:
        body.data.materials.append(dragonfly_material())
    else:
        body.data.materials[0] = dragonfly_material()
    mod_input(mod, "Water", water.water_collection(sc))
    mod_input(mod, "Body", body)
    mod_input(mod, "Material", dragonfly_material())
    mod_input(mod, "Count", count)
    ob.hide_render = ob.hide_viewport = count <= 0
    return ob
