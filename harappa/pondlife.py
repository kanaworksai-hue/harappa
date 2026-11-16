# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pond life by depth zone (as in a real pond):
  open water ........ nothing on top (fish below)
  floating-leaf zone  lily pads, some with a lotus flower    (normalised depth hrp_dn 0.25 .. 0.85, ponds only)
  emergent zone ..... reeds and cattails, swaying in the wind (signed shore distance -0.35 .. +0.15 m)
Lily pads live on the water object ("Harappa Pond Life", static: no per-frame cost); reeds live on the meadow's
"Harappa Shore" modifier, which already re-evaluates every frame for the grass wind.
Colours come from the meadow palette (grass, blossom, bark), so they follow every season."""
import math
import random

import bmesh
import bpy

from . import shading
from .util import G, fresh_group, iface, menu, mod_input, only, sock

LIFE_VER = 14
LIFE = "HRP Pond Life"
LIFE_MOD = "Harappa Pond Life"
MAT_LILY = "HRP Lily Pad"
MAT_LOTUS = "HRP Lotus"
MAT_REED = "HRP Reed"
MAT_RING = "HRP Contact Ring"
MAT_LEAF = "HRP Fallen Leaf"
LILY_OB = "HRP Lily Pad"
LOTUS_OB = "HRP Lotus"
REED_OB = "HRP Reeds"
ASSETS = "HRP Pond Assets"


def _asset_coll():
    coll = bpy.data.collections.get(ASSETS)
    if coll is None:
        coll = bpy.data.collections.new(ASSETS)
    return coll


def _asset(name, build, mat):
    ob = bpy.data.objects.get(name)
    if ob is not None and ob.get("hrp_ver") == LIFE_VER:
        return ob
    me = build(name)
    me.materials.clear()
    me.materials.append(mat)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        _asset_coll().objects.link(ob)
    else:
        ob.data = me
    ob.hide_render = ob.hide_viewport = True
    ob["hrp_ver"] = LIFE_VER
    return ob


# ----------------------------------------------------------------------------------------------
# meshes (radius / height 1, origin at the waterline / root)
# ----------------------------------------------------------------------------------------------
def lily_mesh(name):
    rings, segs, notch = 6, 40, 0.38
    bm = bmesh.new()
    centre = bm.verts.new((0, 0, 0.012))
    grid = []
    for i in range(1, rings + 1):
        r = i / rings
        row = []
        for j in range(segs + 1):
            a = notch / 2 + (2 * math.pi - notch) * j / segs
            wob = 1 + 0.03 * math.sin(5 * a)
            z = 0.012 * (1 - r) + 0.035 * max(0.0, r - 0.85) / 0.15        # cupped, rim turned up
            row.append(bm.verts.new((math.cos(a) * r * wob, math.sin(a) * r * wob, z)))
        grid.append(row)
    for j in range(segs):
        bm.faces.new((centre, grid[0][j], grid[0][j + 1]))
    for i in range(rings - 1):
        for j in range(segs):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    bm.faces.new([grid[i][0] for i in range(rings)][::-1] + [centre])
    bm.faces.new([centre] + [grid[i][segs] for i in range(rings)])
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    return me


def lotus_mesh(name):
    """Two rings of cupped petals around a yellow centre; petals carry hrp_t (0 base .. 1 tip)."""
    bm = bmesh.new()
    tval = []
    for ring, (n, tilt, length, off) in enumerate(((8, 0.95, 1.0, 0.0), (6, 0.45, 0.85, 0.5))):
        for k in range(n):
            a = 2 * math.pi * (k + off) / n
            ca, sa = math.cos(a), math.sin(a)
            vs = []
            for i in range(5):
                tt = i / 4
                w = 0.32 * math.sin(math.pi * min(0.98, 0.15 + tt * 0.85)) * length
                rad = tt * length * math.sin(tilt) * 0.55 + 0.08
                z = tt * length * math.cos(tilt) * 0.9 + 0.08 * tt * tt
                for sgn in (-1, 1):
                    x = ca * rad - sa * w * sgn * 0.5
                    y = sa * rad + ca * w * sgn * 0.5
                    vs.append(bm.verts.new((x, y, z + 0.02 * abs(sgn))))
                    tval.append(tt)
            for i in range(4):
                a0, a1, b0, b1 = vs[2 * i], vs[2 * i + 1], vs[2 * i + 2], vs[2 * i + 3]
                bm.faces.new((a0, a1, b1, b0))
    c = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.16, radius2=0.12, depth=0.12)
    for v in c["verts"]:
        v.co.z += 0.12
        tval.append(-1.0)
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    a = me.attributes.get("hrp_t") or me.attributes.new("hrp_t", "FLOAT", "POINT")
    a.data.foreach_set("value", tval[:len(me.vertices)] + [0.0] * max(0, len(me.vertices) - len(tval)))
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    return me


def reed_mesh(name, seed=5):
    """A clump of tall tapered blades and two cattail heads; hrp_h = height (0 root .. 1 top), hrp_k = 1 on heads."""
    rs = random.Random(seed)
    bm = bmesh.new()
    hval, kval = [], []
    for b in range(11):
        a = rs.uniform(0, math.tau)
        rr = rs.uniform(0.0, 0.12)
        x0, y0 = math.cos(a) * rr, math.sin(a) * rr
        h = rs.uniform(0.65, 1.0)
        lean = rs.uniform(0.05, 0.28)
        la = rs.uniform(0, math.tau)
        w0 = rs.uniform(0.018, 0.03)
        prev = None
        for i in range(6):
            tt = i / 5
            w = w0 * (1 - tt) + 0.002
            px = x0 + math.cos(la) * lean * tt * tt
            py = y0 + math.sin(la) * lean * tt * tt
            pa = bm.verts.new((px - math.sin(la) * w, py + math.cos(la) * w, h * tt))
            pb = bm.verts.new((px + math.sin(la) * w, py - math.cos(la) * w, h * tt))
            hval += [tt * h, tt * h]
            kval += [0.0, 0.0]
            if prev:
                bm.faces.new((prev[0], prev[1], pb, pa))
            prev = (pa, pb)
    for c in range(2):
        a = rs.uniform(0, math.tau)
        x0, y0 = math.cos(a) * 0.05, math.sin(a) * 0.05
        h = rs.uniform(0.8, 1.05)
        stem = bmesh.ops.create_cone(bm, cap_ends=False, segments=5, radius1=0.006, radius2=0.004, depth=h)
        for v in stem["verts"]:
            v.co.x += x0
            v.co.y += y0
            v.co.z += h / 2
            hval.append(v.co.z)
            kval.append(0.0)
        head = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.022, radius2=0.022, depth=0.16)
        for v in head["verts"]:
            v.co.x += x0
            v.co.y += y0
            v.co.z += h * 0.82
            hval.append(v.co.z)
            kval.append(1.0)
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for nm, vals in (("hrp_h", hval), ("hrp_k", kval)):
        at = me.attributes.get(nm) or me.attributes.new(nm, "FLOAT", "POINT")
        vals = (vals + [0.0] * len(me.vertices))[:len(me.vertices)]
        at.data.foreach_set("value", vals)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    return me


# ----------------------------------------------------------------------------------------------
# materials (palette colours: they follow the season)
# ----------------------------------------------------------------------------------------------
def _mat(name):
    mat, rebuilt = shading._fresh_mat(name)
    if not rebuilt and mat.get("hrp_life_ver") == LIFE_VER:
        return mat, None
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_life_ver"] = LIFE_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1400, 0)
    pal.node_tree = shading.palette_group()
    return mat, (g, pal)


def ring_material():
    """Where something sits in the water: a thin white contact line and a soft ring lapping outwards.
    Drawn on a disc whose attribute hrp_r is 1 at its rim; the object's own edge is at hrp_r = 0.8."""
    mat, gp = _mat(MAT_RING)
    if gp is None:
        return mat
    g, pal = gp
    from . import water
    r = g.out(g.n("ShaderNodeAttribute", -1200, 400, attribute_name="hrp_r", attribute_type="GEOMETRY"), "Fac")
    tg = g.n("ShaderNodeGroup", -1200, 200)
    tg.node_tree = water.time_group()
    t = g.out(tg, "Seconds")
    ph = g.out(g.n("ShaderNodeAttribute", -1200, 0, attribute_name="hrp_pad", attribute_type="INSTANCER"), "Fac")
    line = g.maprange(-800, 400, only(g.math("ABSOLUTE", -900, 400, only(g.math("SUBTRACT", -1000, 400, r, 0.815).outputs))
                      .outputs), 0.02, 0.01, 0.0, 0.8, smooth=True)
    fr_ = g.math("FRACT", -900, 200, only(g.math("MULTIPLY_ADD", -1000, 200, t, 0.4,
                 only(g.math("MULTIPLY", -1100, 100, ph, 7.0).outputs)).outputs))
    rr = g.math("MULTIPLY_ADD", -800, 200, g.out(fr_, 0), 0.17, 0.83)
    lap = g.maprange(-650, 200, only(g.math("ABSOLUTE", -700, 250, only(g.math("SUBTRACT", -750, 250, r, g.out(rr, 0))
                     .outputs)).outputs), 0.02, 0.01, smooth=True)
    lap = g.math("MULTIPLY", -550, 200, g.out(lap, "Result"), only(g.math("MULTIPLY", -650, 100, only(g.math(
        "SUBTRACT", -750, 100, 1.0, g.out(fr_, 0)).outputs), 0.7).outputs))
    # not stamped: the line breaks into arcs, only some pads lap, each its own strength; quieter at night
    ang = g.out(g.n("ShaderNodeAttribute", -1200, -200, attribute_name="hrp_ang", attribute_type="GEOMETRY"), "Fac")
    dv = g.n("ShaderNodeCombineXYZ", -1000, -250)
    g.link(g.math("MULTIPLY", -1100, -200, ang, 3.0), 0, dv, "X")
    g.link(g.math("MULTIPLY", -1100, -300, ph, 17.0), 0, dv, "Y")
    g.link(g.math("MULTIPLY", -1100, -350, t, 0.15), 0, dv, "Z")
    dn_ = g.n("ShaderNodeTexNoise", -850, -250, noise_dimensions="3D")
    g.set(dn_, "Scale", 1.6)
    g.link(dv, 0, dn_, "Vector")
    arcs = g.maprange(-700, -250, g.out(dn_, "Fac"), 0.38, 0.44, smooth=True)
    line = g.math("MULTIPLY", -600, 350, g.out(line, "Result"), g.out(arcs, "Result"))
    some = g.math("LESS_THAN", -700, 100, only(g.math("FRACT", -800, 100, only(g.math("MULTIPLY", -900, 100, ph, 3.7)
                  .outputs)).outputs), 0.4)
    lap = g.math("MULTIPLY", -500, 150, g.out(lap, 0), g.out(some, 0))
    a = g.math("MAXIMUM", -400, 300, g.out(line, 0), g.out(lap, 0))
    stren = g.math("MULTIPLY_ADD", -500, 0, only(g.math("FRACT", -600, 0, only(g.math("MULTIPLY", -700, 0, ph, 7.3).outputs))
                   .outputs), 0.5, 0.5)
    a = g.math("MULTIPLY", -350, 250, g.out(a, 0), g.out(stren, 0))
    a = g.math("MULTIPLY", -300, 200, g.out(a, 0), only(g.math("MULTIPLY_ADD", -400, -100, g.out(pal, "water_glow"),
               -0.7, 1.0).outputs))
    glow = g.math("MULTIPLY_ADD", -500, -100, g.out(pal, "water_glow"), 0.6, 1.0)
    gc = g.n("ShaderNodeCombineColor", -350, -100)
    for ch in ("Red", "Green", "Blue"):
        g.link(glow, 0, gc, ch)
    col = g.mix(-200, 100, "MULTIPLY", fac=1.0, a=g.out(pal, "water_foam"), b=only(gc.outputs))
    shading._emit_out(g, g.mixout(col), 0, 100, pal=pal, alpha=g.out(a, 0), shadow_off=True, soft=True)
    mat.surface_render_method = "BLENDED"
    mat["hrp_kind"] = "ring"
    return mat


def ring_disc(g, x, y):
    """GN: a flat disc of radius 1.25 (hrp_r = 1 at its rim, 0.8 at radius 1) for ring_material."""
    c = g.n("GeometryNodeMeshCircle", x, y, fill_type="TRIANGLE_FAN")
    c.inputs["Vertices"].default_value = 40
    c.inputs["Radius"].default_value = 1.25
    sub = g.n("GeometryNodeSubdivideMesh", x + 150, y)
    g.link(c, 0, sub, "Mesh")
    sub.inputs["Level"].default_value = 2
    pos = g.n("GeometryNodeInputPosition", x, y - 150)
    ln = g.vmath("LENGTH", x + 150, y - 150, only(pos.outputs))
    st = g.n("GeometryNodeStoreNamedAttribute", x + 300, y, data_type="FLOAT", domain="POINT")
    g.link(sub, 0, st, "Geometry")
    st.inputs["Name"].default_value = "hrp_r"
    g.link(g.math("DIVIDE", x + 250, y - 150, g.out(ln, "Value"), 1.25), 0, st, "Value", bkind="VALUE")
    ps_ = g.n("ShaderNodeSeparateXYZ", x + 150, y - 300)
    g.link(pos, 0, ps_, "Vector")
    st2 = g.n("GeometryNodeStoreNamedAttribute", x + 380, y, data_type="FLOAT", domain="POINT")
    g.link(st, 0, st2, "Geometry")
    st2.inputs["Name"].default_value = "hrp_ang"
    g.link(g.math("ARCTAN2", x + 250, y - 300, g.out(ps_, "Y"), g.out(ps_, "X")), 0, st2, "Value", bkind="VALUE")
    sm = g.n("GeometryNodeSetMaterial", x + 450, y)
    g.link(st2, 0, sm, "Geometry")
    sm.inputs["Material"].default_value = ring_material()
    return sm


def leaf_material():
    """A fallen autumn leaf afloat: the trees' own leaf colours, some redder, some browner."""
    mat, gp = _mat(MAT_LEAF)
    if gp is None:
        return mat
    g, pal = gp
    geo = g.n("ShaderNodeNewGeometry", -900, 500)
    r = g.out(g.n("ShaderNodeAttribute", -900, 300, attribute_name="hrp_leaf", attribute_type="INSTANCER"), "Fac")
    lit = g.mix(-700, 300, fac=only(g.math("GREATER_THAN", -800, 300, r, 0.3).outputs), a=(0.62, 0.08, 0.07, 1.0),
                b=(0.85, 0.27, 0.07, 1.0))                                   # crimson / vermilion
    lit = g.mix(-600, 300, fac=only(g.math("GREATER_THAN", -700, 200, r, 0.6).outputs), a=g.mixout(lit),
                b=(0.82, 0.55, 0.13, 1.0))                                   # ochre
    lit = g.mix(-500, 300, fac=only(g.math("GREATER_THAN", -600, 100, r, 0.85).outputs), a=g.mixout(lit),
                b=(0.42, 0.25, 0.12, 1.0))                                   # brown
    vj = g.math("MULTIPLY_ADD", -500, 0, only(g.math("FRACT", -600, 0, only(g.math("MULTIPLY", -700, 0, r, 13.7).outputs))
                .outputs), 0.3, 0.85)
    vjc = g.n("ShaderNodeCombineColor", -400, 0)
    for ch in ("Red", "Green", "Blue"):
        g.link(vj, 0, vjc, ch)
    lit = g.mix(-450, 300, "MULTIPLY", fac=1.0, a=g.mixout(lit), b=only(vjc.outputs))
    vein = g.out(g.n("ShaderNodeTexCoord", -900, 700), "Object")
    _ = vein
    sh = g.mix(-450, 100, "MULTIPLY", fac=1.0, a=g.mixout(lit), b=(0.75, 0.7, 0.8, 1.0))
    cel = shading._cel_node(g, pal, -200, 300, g.out(geo, "Normal"), g.mixout(lit), g.mixout(sh), g.mixout(sh))
    for k, v in (("Threshold", 0.05), ("Deep Threshold", -1.0)):
        for lk in list(cel.inputs[k].links):
            mat.node_tree.links.remove(lk)
        cel.inputs[k].default_value = v
    shading._emit_out(g, g.out(cel, "Color"), 200, 300, pal=pal)
    return mat


def lily_material():
    mat, gp = _mat(MAT_LILY)
    if gp is None:
        return mat
    g, pal = gp
    geo = g.n("ShaderNodeNewGeometry", -1400, 500)
    tc = g.n("ShaderNodeTexCoord", -1400, 300)
    ob = g.n("ShaderNodeSeparateXYZ", -1200, 300)
    g.link(tc, "Object", ob, "Vector")
    ang = g.math("ARCTAN2", -1000, 350, g.out(ob, "Y"), g.out(ob, "X"))
    rad = g.n("ShaderNodeVectorMath", -1000, 200, operation="LENGTH")
    g.link(tc, "Object", rad, ("Vector", 0))
    vein = g.math("ABSOLUTE", -800, 350, only(g.math("SINE", -900, 350, only(g.math("MULTIPLY", -950, 400, g.out(ang, 0),
                                                                         9.0).outputs)).outputs))
    vein = g.maprange(-650, 350, g.out(vein, 0), 0.10, 0.04, smooth=True)
    vin = g.maprange(-650, 200, g.out(rad, "Value"), 0.15, 0.3, smooth=True)
    vein = g.math("MULTIPLY", -500, 300, g.out(vein, "Result"), g.out(vin, "Result"))
    rim = g.maprange(-650, 50, g.out(rad, "Value"), 0.86, 0.92, smooth=True)
    ptn = g.n("ShaderNodeAttribute", -900, 650, attribute_name="hrp_pad", attribute_type="INSTANCER")
    t1 = g.maprange(-700, 650, g.out(ptn, "Fac"), 0.0, 0.5)
    t2 = g.maprange(-700, 500, g.out(ptn, "Fac"), 0.5, 1.0)
    lit = g.mix(-550, 500, fac=g.out(t1, "Result"), a=g.out(pal, "leaf_mid"), b=g.out(pal, "grass_shadow"))
    lit = g.mix(-400, 400, fac=g.out(t2, "Result"), a=g.mixout(lit), b=g.out(pal, "grass_lit"))
    lit = g.mix(-350, 350, fac=0.35, a=g.mixout(lit), b=g.out(pal, "leaf_shadow"))      # at the grass's value
    # some pads stay green whatever the season (in autumn not every pad turns)
    stay = g.maprange(-700, 1100, g.out(ptn, "Fac"), 0.42, 0.38, smooth=True)
    lit = g.mix(-320, 700, fac=only(g.math("MULTIPLY", -420, 1100, g.out(stay, "Result"), 0.6).outputs),
                a=g.mixout(lit), b=(0.36, 0.62, 0.22, 1.0))                   # fresh green, not olive
    # young pads are bronze-red, a few old ones yellowing
    young = g.maprange(-700, 800, g.out(ptn, "Fac"), 0.86, 0.9, smooth=True)
    lit = g.mix(-300, 600, fac=only(g.math("MULTIPLY", -400, 700, g.out(young, "Result"), 0.3).outputs),
                a=g.mixout(lit), b=(0.62, 0.36, 0.26, 1.0))
    old_ = g.maprange(-700, 950, g.out(ptn, "Fac"), 0.06, 0.02, smooth=True)
    lit = g.mix(-280, 650, fac=only(g.math("MULTIPLY", -400, 900, g.out(old_, "Result"), 0.12).outputs),
                a=g.mixout(lit), b=(0.85, 0.82, 0.42, 1.0))
    lit = g.mix(-250, 400, fac=only(g.math("MULTIPLY", -350, 450, g.out(vein, 0), 0.28).outputs), a=g.mixout(lit),
                b=g.out(pal, "grass_tip"))
    lit = g.mix(-100, 400, fac=only(g.math("MULTIPLY", -200, 450, g.out(rim, "Result"), 0.2).outputs),
                a=g.mixout(lit), b=g.out(pal, "leaf_lit"))
    edge_ = g.maprange(-650, -100, g.out(rad, "Value"), 0.94, 0.985, smooth=True)       # a wet dark lip: sits IN
    lit = g.mix(-50, 450, fac=only(g.math("MULTIPLY", -200, -100, g.out(edge_, "Result"), 0.55).outputs),   # the water
                a=g.mixout(lit), b=g.out(pal, "grass_deep"))
    sh = g.mix(-250, 150, fac=0.4, a=g.out(pal, "grass_shadow"), b=g.out(pal, "leaf_mid"))
    cel = shading._cel_node(g, pal, 100, 300, g.out(geo, "Normal"), g.mixout(lit), g.mixout(sh),
                            g.out(pal, "grass_deep"))
    for k, v in (("Threshold", 0.05), ("Deep Threshold", -1.0)):     # flat like the water: lit unless shaded
        for lk in list(cel.inputs[k].links):
            mat.node_tree.links.remove(lk)
        cel.inputs[k].default_value = v
    shading._emit_out(g, g.out(cel, "Color"), 500, 300, pal=pal)
    return mat


def lotus_material():
    mat, gp = _mat(MAT_LOTUS)
    if gp is None:
        return mat
    g, pal = gp
    geo = g.n("ShaderNodeNewGeometry", -1400, 500)
    at = g.n("ShaderNodeAttribute", -1400, 300, attribute_name="hrp_t", attribute_type="GEOMETRY")
    tip = g.maprange(-1100, 300, g.out(at, "Fac"), 0.35, 1.0, smooth=True)
    centre = g.math("LESS_THAN", -1100, 100, g.out(at, "Fac"), -0.5)
    lit = g.mix(-800, 400, fac=g.out(tip, "Result"), a=(1.0, 0.97, 0.95, 1.0), b=g.out(pal, "bloom_lit"))
    lit = g.mix(-650, 400, fac=g.out(centre, 0), a=g.mixout(lit), b=g.out(pal, "flower_centre"))
    sh = g.mix(-650, 150, fac=g.out(tip, "Result"), a=g.out(pal, "flower_shade"), b=g.out(pal, "bloom_shadow"))
    cel = shading._cel_node(g, pal, -300, 300, g.out(geo, "Normal"), g.mixout(lit), g.mixout(sh),
                            g.out(pal, "bloom_deep"))
    shading._emit_out(g, g.out(cel, "Color"), 100, 300, pal=pal)
    return mat


def reed_material():
    mat, gp = _mat(MAT_REED)
    if gp is None:
        return mat
    g, pal = gp
    geo = g.n("ShaderNodeNewGeometry", -1400, 500)
    h = g.n("ShaderNodeAttribute", -1400, 300, attribute_name="hrp_h", attribute_type="GEOMETRY")
    k = g.n("ShaderNodeAttribute", -1400, 100, attribute_name="hrp_k", attribute_type="GEOMETRY")
    up = g.maprange(-1100, 300, g.out(h, "Fac"), 0.1, 0.9, smooth=True)
    lit = g.mix(-900, 400, fac=g.out(up, "Result"), a=g.out(pal, "grass_shadow"), b=g.out(pal, "grass_tip"))
    lit = g.mix(-750, 400, fac=0.5, a=g.mixout(lit), b=g.out(pal, "grass_lit"))
    lit = g.mix(-600, 400, fac=g.out(k, "Fac"), a=g.mixout(lit), b=g.out(pal, "bark_lit"))
    sh = g.mix(-600, 150, fac=g.out(k, "Fac"), a=g.out(pal, "grass_shadow"), b=g.out(pal, "bark_shadow"))
    cel = shading._cel_node(g, pal, -300, 300, g.out(geo, "Normal"), g.mixout(lit), g.mixout(sh),
                            g.out(pal, "grass_deep"))
    shading._emit_out(g, g.out(cel, "Color"), 100, 300, pal=pal)
    mat.use_backface_culling = False
    return mat


def lily_object():
    return _asset(LILY_OB, lily_mesh, lily_material())


def lotus_object():
    return _asset(LOTUS_OB, lotus_mesh, lotus_material())


def reed_object():
    return _asset(REED_OB, reed_mesh, reed_material())


# ----------------------------------------------------------------------------------------------
# lily pads on a pond (second modifier on the water curve)
# ----------------------------------------------------------------------------------------------
def life_group():
    ng, rebuilt = fresh_group(LIFE, "GeometryNodeTree", LIFE_VER + 5)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Lily Pads", "INPUT", "NodeSocketFloat", 0.6, 0.0, 1.0, "How much of the floating-leaf zone the "
          "lily pads cover", "FACTOR")
    iface(ng, "Pad Size", "INPUT", "NodeSocketFloat", 0.3, 0.05, 5.0, "Lily pad radius", "DISTANCE")
    iface(ng, "Flowers", "INPUT", "NodeSocketFloat", 0.18, 0.0, 1.0, "Share of pads with a water-lily flower",
          "FACTOR")
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Lily", "INPUT", "NodeSocketObject")
    iface(ng, "Lotus", "INPUT", "NodeSocketObject")
    iface(ng, "Avoid", "INPUT", "NodeSocketCollection", desc="No pads under boats and props")
    iface(ng, "Fallen Leaves", "INPUT", "NodeSocketFloat", 0.0, 0.0, 3.0,
          "Leaves floating on the water, gathering by the banks (set by the Autumn season)")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1600, 0)
    go = g.n("NodeGroupOutput", 1200, 0)
    a = g.n("GeometryNodeInputNamedAttribute", -1600, -400, data_type="FLOAT_VECTOR")
    a.inputs["Name"].default_value = "hrp_a"
    c = g.n("GeometryNodeInputNamedAttribute", -1600, -600, data_type="FLOAT_VECTOR")
    c.inputs["Name"].default_value = "hrp_c"
    sa = g.n("ShaderNodeSeparateXYZ", -1400, -400)
    g.link(a, "Attribute", sa, "Vector")
    sc_ = g.n("ShaderNodeSeparateXYZ", -1400, -600)
    g.link(c, "Attribute", sc_, "Vector")
    cv = g.n("GeometryNodeInputNamedAttribute", -1600, -200, data_type="FLOAT_VECTOR")
    cv.inputs["Name"].default_value = "hrp_carve"
    scv = g.n("ShaderNodeSeparateXYZ", -1450, -200)
    g.link(cv, "Attribute", scv, "Vector")
    depth = g.math("MULTIPLY", -1300, -250, g.out(sa, "X"), g.out(scv, "Y"))       # metres of water here
    z1 = g.maprange(-1200, -350, g.out(depth, 0), 0.12, 0.28, smooth=True)          # floating-leaf zone:
    z2 = g.maprange(-1200, -500, g.out(depth, 0), 1.8, 1.4, smooth=True)            # ~0.2 .. 1.6 m deep
    zone = g.math("MULTIPLY", -1000, -400, g.out(z1, "Result"), g.out(z2, "Result"))
    pond = g.math("SUBTRACT", -1000, -550, 1.0, g.out(sa, "Z"))
    zone = g.math("MULTIPLY", -850, -450, g.out(zone, 0), g.out(pond, 0))
    zone = g.math("MULTIPLY", -700, -450, g.out(zone, 0), g.out(sc_, "Y"))          # not in stream mouths
    pos = g.n("GeometryNodeInputPosition", -1200, -800)
    nz = g.n("ShaderNodeTexNoise", -1000, -800, noise_dimensions="3D")
    g.set(nz, "Scale", 0.9)
    g.link(pos, 0, nz, "Vector")
    clump = g.maprange(-850, -800, g.out(nz, "Fac"), 0.40, 0.48, smooth=True)       # tight colonies, open water between       # pads gather in colonies
    cov = g.math("MULTIPLY", -700, -650, g.out(clump, "Result"), g.out(gi, "Lily Pads"))
    fac = g.math("MULTIPLY", -550, -500, g.out(zone, 0), g.out(cov, 0))
    dist = g.n("GeometryNodeDistributePointsOnFaces", -350, -300, distribute_method="POISSON")
    g.link(gi, "Geometry", dist, "Mesh")
    pr = g.math("MULTIPLY", -550, -300, g.out(gi, "Pad Size"), 1.15)                 # pads may touch in clusters
    g.link(pr, 0, dist, "Distance Min")
    g.link(fac, 0, dist, "Density Factor")
    dist.inputs["Density Max"].default_value = 30.0
    g.link(gi, "Seed", dist, "Seed")
    pts = g.out(dist, "Points")
    tone = g.n("FunctionNodeRandomValue", -350, -150, data_type="FLOAT")
    g.set(tone, "Max", 1.0, "VALUE")
    aci = g.n("GeometryNodeCollectionInfo", -700, 100, transform_space="RELATIVE")
    g.link(gi, "Avoid", aci, "Collection")
    are = g.n("GeometryNodeRealizeInstances", -550, 100)
    g.link(aci, 0, are, "Geometry")
    asz = g.n("GeometryNodeAttributeDomainSize", -400, 200, component="MESH")
    g.link(are, 0, asz, "Geometry")
    ahas = g.math("GREATER_THAN", -250, 200, g.out(asz, "Face Count"), 0.5)
    apx = g.n("GeometryNodeProximity", -400, 100, target_element="FACES")
    g.link(are, 0, apx, "Geometry")
    clear = g.math("LESS_THAN", -250, 100, g.out(apx, "Distance"), only(g.math("MULTIPLY", -350, 0, g.out(gi, "Pad Size"),
                   1.3).outputs))
    under = g.math("MULTIPLY", -150, 100, g.out(clear, 0), g.out(ahas, 0))
    dpads = g.n("GeometryNodeDeleteGeometry", -100, -100, domain="POINT")
    g.link(dist, "Points", dpads, "Geometry")
    g.link(under, 0, dpads, "Selection")
    pts = g.n("GeometryNodeStoreNamedAttribute", -250, -250, data_type="FLOAT", domain="POINT")
    g.links.new(only(dpads.outputs), pts.inputs["Geometry"])
    pts.inputs["Name"].default_value = "hrp_pad"
    g.link(tone, "Value", pts, "Value", akind="VALUE", bkind="VALUE")
    pts = only(pts.outputs)
    lift = g.n("ShaderNodeCombineXYZ", -250, -150)
    g.link(g.math("MULTIPLY_ADD", -300, -100, g.out(tone, "Value", "VALUE"), 0.003, 0.02), 0, lift, "Z")
    up = g.n("GeometryNodeSetPosition", -150, -300)
    g.links.new(pts, up.inputs["Geometry"])
    g.link(lift, 0, up, "Offset")
    rnd = g.n("FunctionNodeRandomValue", -350, -650, data_type="FLOAT")
    g.set(rnd, "Max", 1.0, "VALUE")
    g.link(gi, "Seed", rnd, "Seed")
    rot = g.n("ShaderNodeCombineXYZ", -150, -650)
    g.link(g.math("MULTIPLY", -250, -650, g.out(rnd, "Value", "VALUE"), 6.283), 0, rot, "Z")
    ss = g.n("FunctionNodeRandomValue", -350, -850, data_type="FLOAT")
    g.set(ss, "Min", 0.0, "VALUE")
    g.set(ss, "Max", 1.0, "VALUE")
    ssq = g.math("POWER", -250, -900, g.out(ss, "Value", "VALUE"), 2.2)              # many small pads, a few big
    ssq = g.math("MULTIPLY_ADD", -200, -900, g.out(ssq, 0), 1.25, 0.32)
    scl0 = g.math("MULTIPLY", -150, -850, g.out(ssq, 0), g.out(gi, "Pad Size"))
    sq = g.n("FunctionNodeRandomValue", -350, -1000, data_type="FLOAT")
    g.set(sq, "Min", 0.8, "VALUE")
    g.set(sq, "Max", 1.0, "VALUE")
    sxy = g.n("ShaderNodeCombineXYZ", -50, -900)                                      # slightly squashed ellipses
    g.link(scl0, 0, sxy, "X")
    g.link(g.math("MULTIPLY", -150, -1000, g.out(scl0, 0), g.out(sq, "Value", "VALUE")), 0, sxy, "Y")
    g.link(scl0, 0, sxy, "Z")
    scl = scl0
    oi = g.n("GeometryNodeObjectInfo", -150, -1050)
    g.link(gi, "Lily", oi, "Object")
    inst = g.n("GeometryNodeInstanceOnPoints", 100, -300)
    g.link(up, 0, inst, "Points")
    g.link(oi, "Geometry", inst, "Instance")
    g.link(rot, 0, inst, "Rotation")
    g.link(sxy, 0, inst, "Scale")
    # a lotus on some pads
    fr_ = g.n("FunctionNodeRandomValue", -150, -1250, data_type="FLOAT")
    g.set(fr_, "Max", 1.0, "VALUE")
    fr_.inputs["Seed"].default_value = 77
    fsel = g.math("LESS_THAN", 0, -1250, g.out(fr_, "Value", "VALUE"), g.out(gi, "Flowers"))
    fs = g.n("GeometryNodeSeparateGeometry", 100, -700, domain="POINT")
    g.link(up, 0, fs, "Geometry")
    g.link(fsel, 0, fs, "Selection")
    fa = g.n("FunctionNodeRandomValue", 0, -1450, data_type="FLOAT")
    g.set(fa, "Max", 6.283, "VALUE")
    fa.inputs["Seed"].default_value = 31
    fo = g.n("ShaderNodeCombineXYZ", 200, -1400)
    fr2 = g.math("MULTIPLY", 100, -1500, g.out(gi, "Pad Size"), 0.75)
    g.link(g.math("MULTIPLY", 150, -1350, only(g.math("COSINE", 100, -1350, g.out(fa, "Value", "VALUE")).outputs),
                  g.out(fr2, 0)), 0, fo, "X")
    g.link(g.math("MULTIPLY", 150, -1450, only(g.math("SINE", 100, -1450, g.out(fa, "Value", "VALUE")).outputs),
                  g.out(fr2, 0)), 0, fo, "Y")
    fmove = g.n("GeometryNodeSetPosition", 250, -700)
    g.link(fs, "Selection", fmove, "Geometry")
    g.link(fo, 0, fmove, "Offset")
    oi2 = g.n("GeometryNodeObjectInfo", 100, -1050)
    g.link(gi, "Lotus", oi2, "Object")
    fsc = g.math("MULTIPLY", 100, -900, g.out(scl, 0), 0.7)
    inst2 = g.n("GeometryNodeInstanceOnPoints", 350, -700)
    g.link(fmove, 0, inst2, "Points")
    g.link(oi2, "Geometry", inst2, "Instance")
    g.link(rot, 0, inst2, "Rotation")
    g.link(fsc, 0, inst2, "Scale")
    rdisc = ring_disc(g, -100, -1700)
    rdown = g.n("GeometryNodeSetPosition", 250, -1500)                       # back down to the water line
    g.link(up, 0, rdown, "Geometry")
    rdo = g.n("ShaderNodeCombineXYZ", 150, -1600)
    rdo.inputs["Z"].default_value = -0.016
    g.link(rdo, 0, rdown, "Offset")
    rins = g.n("GeometryNodeInstanceOnPoints", 450, -1500)
    g.link(rdown, 0, rins, "Points")
    g.link(rdisc, 0, rins, "Instance")
    g.link(rot, 0, rins, "Rotation")
    g.link(sxy, 0, rins, "Scale")
    # autumn: leaves afloat, more of them near the banks, drifting a little
    lnear = g.maprange(-700, -2300, g.out(sa, "Y"), 1.2, 0.15, 0.04, 1.0, smooth=True)     # rafts by the banks
    lcl = g.n("ShaderNodeTexNoise", -800, -2500, noise_dimensions="2D")               # rafts, open water between
    g.set(lcl, "Scale", 1.6)
    g.link(g.n("GeometryNodeInputPosition", -950, -2500), 0, lcl, "Vector")
    lclump = g.maprange(-650, -2500, g.out(lcl, "Fac"), 0.5, 0.58, smooth=True)
    lden = g.math("MULTIPLY", -550, -2300, only(g.math("MULTIPLY", -650, -2400, g.out(lnear, "Result"),
                  g.out(pond, 0)).outputs), g.out(sc_, "Y"))
    lden = g.math("MULTIPLY", -500, -2350, g.out(lden, 0), g.out(lclump, "Result"))
    ldist = g.n("GeometryNodeDistributePointsOnFaces", -400, -2300, distribute_method="POISSON")
    g.link(gi, "Geometry", ldist, "Mesh")
    ldist.inputs["Distance Min"].default_value = 0.06
    g.link(g.math("MULTIPLY", -500, -2450, g.out(gi, "Fallen Leaves"), 22.0), 0, ldist, "Density Max")
    g.link(lden, 0, ldist, "Density Factor")
    g.link(gi, "Seed", ldist, "Seed")
    ltm = g.n("GeometryNodeInputSceneTime", -400, -2550)
    lpos = g.n("GeometryNodeInputPosition", -400, -2650)
    lnv = g.vmath("ADD", -250, -2600, only(g.vmath("SCALE", -300, -2650, only(lpos.outputs), scale=0.5).outputs),
                  only(g.vmath("SCALE", -300, -2550, (0, 0, 1.0), scale=only(g.math("MULTIPLY", -350, -2500,
                          g.out(ltm, "Seconds"), 0.04).outputs)).outputs))
    lnz = g.n("GeometryNodeInputPosition", -100, -2650)
    lns = g.n("ShaderNodeTexNoise", -100, -2600, noise_dimensions="3D")
    g.link(lnv, 0, lns, "Vector")
    ldr = g.vmath("MULTIPLY_ADD", 50, -2600, g.out(lns, "Color"), (0.5, 0.5, 0.0))
    sock(ldr.inputs, ("Vector", 2)).default_value = (-0.25, -0.25, 0.012)
    lmv = g.n("GeometryNodeSetPosition", -100, -2300)
    g.link(ldist, "Points", lmv, "Geometry")
    g.link(ldr, 0, lmv, "Offset")
    lmesh = g.n("GeometryNodeMeshCircle", -400, -2850, fill_type="TRIANGLE_FAN")
    lmesh.inputs["Vertices"].default_value = 16
    lpp = g.n("GeometryNodeInputPosition", -400, -3000)
    lps = g.n("ShaderNodeSeparateXYZ", -300, -3000)
    g.link(lpp, 0, lps, "Vector")
    tipk = g.math("POWER", -200, -3050, only(g.math("MAXIMUM", -250, -3100, g.out(lps, "X"), 0.0).outputs), 2.0)
    ly_ = g.math("MULTIPLY", -100, -3000, g.out(lps, "Y"), only(g.math("SUBTRACT", -150, -3100, 1.0, g.out(tipk, 0))
                 .outputs))                                               # pointed tip
    lx_ = g.math("SUBTRACT", -100, -2950, g.out(lps, "X"), only(g.math("MULTIPLY", -200, -2950, only(g.math(
        "MAXIMUM", -300, -2950, only(g.math("MULTIPLY", -350, -2950, g.out(lps, "X"), -1.0).outputs), 0.0).outputs),
        only(g.math("MULTIPLY", -250, -2900, only(g.math("SUBTRACT", -300, -2900, 1.0, only(g.math("ABSOLUTE", -350, -2900,
               only(g.math("MULTIPLY", -400, -2900, g.out(lps, "Y"), 6.0).outputs)).outputs)).outputs), 0.25)
        .outputs)).outputs))                                            # a notch at the stem end
    lz_ = g.math("MULTIPLY", -100, -3150, only(g.math("MULTIPLY", -150, -3150, g.out(lps, "Y"), g.out(lps, "Y")).outputs),
                 1.2)                                                       # curled up a little
    lnp = g.n("ShaderNodeCombineXYZ", 0, -3000)
    g.link(lx_, 0, lnp, "X")
    g.link(ly_, 0, lnp, "Y")
    g.link(lz_, 0, lnp, "Z")
    lshape = g.n("GeometryNodeSetPosition", -200, -2850)
    g.link(lmesh, 0, lshape, "Geometry")
    g.link(lnp, 0, lshape, "Position")
    lxf = g.n("GeometryNodeTransform", -100, -2850)
    g.link(lshape, 0, lxf, "Geometry")
    lxf.inputs["Scale"].default_value = (0.075, 0.05, 0.02)
    lmat = g.n("GeometryNodeSetMaterial", 50, -2850)
    g.link(lxf, 0, lmat, "Geometry")
    lmat.inputs["Material"].default_value = leaf_material()
    lrz = g.n("FunctionNodeRandomValue", 50, -2450, data_type="FLOAT_VECTOR")
    lrz.inputs["Min"].default_value = (-0.15, -0.15, 0.0)
    lrz.inputs["Max"].default_value = (0.15, 0.15, 6.28)
    lrs = g.n("FunctionNodeRandomValue", 50, -2550, data_type="FLOAT")
    g.set(lrs, "Min", 0.6, "VALUE")
    g.set(lrs, "Max", 1.4, "VALUE")
    lin = g.n("GeometryNodeInstanceOnPoints", 200, -2300)
    g.link(lmv, 0, lin, "Points")
    g.link(lmat, 0, lin, "Instance")
    g.link(lrz, "Value", lin, "Rotation", akind="VECTOR")
    g.link(lrs, "Value", lin, "Scale", akind="VALUE")
    lst = g.n("GeometryNodeStoreNamedAttribute", 350, -2300, data_type="FLOAT", domain="INSTANCE")
    g.link(lin, 0, lst, "Geometry")
    lst.inputs["Name"].default_value = "hrp_leaf"
    lrc = g.n("FunctionNodeRandomValue", 200, -2650, data_type="FLOAT")
    lrc.inputs["Seed"].default_value = 13
    g.link(lrc, "Value", lst, "Value", akind="VALUE", bkind="VALUE")
    join = g.n("GeometryNodeJoinGeometry", 900, 0)
    g.link(gi, "Geometry", join, "Geometry")
    g.link(inst, 0, join, "Geometry")
    g.link(inst2, 0, join, "Geometry")
    g.link(rins, 0, join, "Geometry")
    g.link(lst, 0, join, "Geometry")
    g.link(join, 0, go, "Geometry")
    return ng


def attach_life(ob, lilies=0.6, flowers=0.15):
    mod = ob.modifiers.get(LIFE_MOD)
    if mod is None:
        mod = ob.modifiers.new(LIFE_MOD, "NODES")
    mod.node_group = life_group()
    mod_input(mod, "Lily", lily_object())
    mod_input(mod, "Lotus", lotus_object())
    mod_input(mod, "Lily Pads", lilies)
    from . import rocks
    mod_input(mod, "Avoid", rocks.props_collection(bpy.context.scene))
    mod_input(mod, "Flowers", flowers)
    hs = getattr(bpy.context.scene, "harappa", None)
    mod_input(mod, "Fallen Leaves", 1.0 if hs is not None and hs.season == "AUTUMN" else 0.0)
    return mod
