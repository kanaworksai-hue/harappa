# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ghibli-style rocks: a lumpy sphere cut by a few flat 'chisel' planes so the light falls in painted facets,
moss on the tops in the meadow's own colours (so it follows the season), and pebbles along the water.

* Add Rock: one rock on the ground under the 3D cursor. It joins the "Harappa Props" collection, which the
  meadow's grass and flowers avoid, so nothing grows through it.
* Shore pebbles: a "Harappa Shore" modifier at the END of each meadow's stack scatters small rocks along the
  wet band the water carve leaves (attribute ``hrp_wet``)."""
import math
import random

import bmesh
import bpy
from mathutils import Vector, noise

from . import shading
from .util import G, fresh_group, iface, menu, mod_input, only, sock, stamp

ROCK_VER = 18
MAT_ROCK = "HRP Rock"
PROPS = "Harappa Props"
SHORE = "HRP Shore"
SHORE_MOD = "Harappa Shore"
PEBBLES = "HRP Pebbles"
CLIFF = "HRP Cliff Rocks"


# ----------------------------------------------------------------------------------------------
# mesh
# ----------------------------------------------------------------------------------------------
def rock_mesh(name, seed=0, flat=0.65, cuts=7, subdiv=3, block=False, kind="ROUND"):
    """About 1 m across, base at z = 0 (slightly below so it sits in the ground).
    block=True starts from a rounded cube: squarer, cliff-like blocks for walls.
    kind: ROUND weathered boulder, ANGULAR a chunk with a few big planar breaks, SLAB a flat bedded stone."""
    rs = random.Random(seed * 7919 + 11)
    if kind == "ANGULAR":
        cuts += 5
    elif kind == "SLAB":
        flat = min(flat, 0.45)
    bm = bmesh.new()
    if block:
        bmesh.ops.create_cube(bm, size=1.6)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=5, use_grid_fill=True)
        for v in bm.verts:                                   # keep it boxy, round the corners a little
            d = v.co.normalized()
            v.co = v.co.lerp(d, 0.07)
    else:
        bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    off = Vector((rs.uniform(-50, 50), rs.uniform(-50, 50), rs.uniform(-50, 50)))
    planes = []
    for k in range(cuts):
        n = Vector((rs.gauss(0, 1), rs.gauss(0, 1), rs.gauss(0, 1) * 0.7 + (0.6 if k < 2 else 0.0))).normalized()
        planes.append((n, rs.uniform(0.6, 0.78) if kind == "ANGULAR" else rs.uniform(0.74, 0.9)))
    for v in bm.verts:
        d = v.co.normalized()
        base_r = v.co.length if block else 1.0
        r = base_r * (1.0 + (0.045 if block else (0.07 if kind == "ANGULAR" else 0.16)) * noise.noise(d * 1.4 + off)
                      + 0.05 * noise.noise(d * 4.0 + off * 2))
        for n, o in planes:                                  # flat painted facets
            dot = d.dot(n)
            if dot > 0.05:
                r = min(r, o / dot)
        v.co = d * r
    sx, sy = rs.uniform(0.9, 1.25), rs.uniform(0.75, 1.0)
    if kind == "SLAB":
        sx, sy = sx * 1.25, sy * 1.15
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= flat
        if v.co.z < -0.25 * flat:                            # flat underside, half buried
            v.co.z = -0.25 * flat + (v.co.z + 0.25 * flat) * 0.15
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + 0.12 * flat
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me["hrp_ver"] = ROCK_VER
    return me


def pebble_collection():
    """Four small pebble shapes (hidden collection) instanced along the shore."""
    coll = bpy.data.collections.get(PEBBLES)
    if coll is not None and coll.get("hrp_ver") == ROCK_VER and len(coll.objects) == 4:
        return coll
    if coll is None:
        coll = bpy.data.collections.new(PEBBLES)
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    mat = rock_material()
    for i in range(4):
        me = rock_mesh(f"HRP Pebble {i}", seed=900 + i, flat=0.5, cuts=5, subdiv=2)
        if not me.materials:
            me.materials.append(mat)
        ob = bpy.data.objects.new(f"HRP Pebble {i}", me)
        ob.hide_render = ob.hide_viewport = True
        coll.objects.link(ob)
    coll["hrp_ver"] = ROCK_VER
    return coll


def cliff_collection():
    """Angular rock chunks (hidden collection) that dress steep bare faces of the meadow."""
    coll = bpy.data.collections.get(CLIFF)
    if coll is not None and coll.get("hrp_ver") == ROCK_VER and len(coll.objects) == 4:
        return coll
    if coll is None:
        coll = bpy.data.collections.new(CLIFF)
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    mat = rock_material()
    for i in range(4):
        me = rock_mesh(f"HRP Cliff Rock {i}", seed=700 + i, flat=0.55 + 0.1 * (i % 2), kind="ANGULAR")
        if not me.materials:
            me.materials.append(mat)
        ob = bpy.data.objects.new(f"HRP Cliff Rock {i}", me)
        ob.hide_render = ob.hide_viewport = True
        coll.objects.link(ob)
    coll["hrp_ver"] = ROCK_VER
    return coll


# ----------------------------------------------------------------------------------------------
# material: cel facets, moss on top in the grass colours
# ----------------------------------------------------------------------------------------------
def rock_material():
    mat, rebuilt = shading._fresh_mat(MAT_ROCK)
    if not rebuilt and mat.get("hrp_rock_ver") == ROCK_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_rock_ver"] = ROCK_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -1400, 0)
    pal.node_tree = shading.palette_group()
    geo = g.n("ShaderNodeNewGeometry", -1400, 500)
    nz = g.n("ShaderNodeSeparateXYZ", -1200, 500)
    g.link(geo, "Normal", nz, "Vector")
    mn = g.n("ShaderNodeTexNoise", -1200, 700, noise_dimensions="3D")
    g.set(mn, "Scale", 2.2)
    g.set(mn, "Detail", 3.0)
    g.link(geo, "Position", mn, "Vector")
    mj = g.math("MULTIPLY_ADD", -1000, 650, g.out(mn, "Fac"), 0.7, -0.35)
    top = g.math("ADD", -850, 600, g.out(nz, "Z"), g.out(mj, 0))
    moss = g.maprange(-700, 600, g.out(top, 0), 0.72, 0.8, smooth=True)                 # a cap on top, not camo
    mossw = g.math("MULTIPLY", -550, 600, g.out(moss, "Result"), g.out(pal, "rock_moss"))
    nom = g.n("ShaderNodeAttribute", -700, 800, attribute_name="hrp_nomoss", attribute_type="OBJECT")
    mossw = g.math("MULTIPLY", -450, 650, g.out(mossw, 0), only(g.math("SUBTRACT", -550, 800, 1.0, g.out(nom, "Fac"))
                   .outputs))
    # stone tone varies over the rock in big soft patches
    pn = g.n("ShaderNodeTexNoise", -1200, 200, noise_dimensions="3D")
    g.set(pn, "Scale", 0.9)
    g.link(geo, "Position", pn, "Vector")
    pf = g.maprange(-1000, 200, g.out(pn, "Fac"), 0.4, 0.62, smooth=True)
    lit = g.mix(-800, 200, fac=g.out(pf, "Result"), a=g.out(pal, "rock_lit"), b=g.out(pal, "rock_lit2"))
    mossc = g.mix(-500, 450, fac=0.45, a=g.out(pal, "grass_lit"), b=g.out(pal, "grass_shadow"))   # duller moss
    mp = g.n("ShaderNodeTexNoise", -900, 850, noise_dimensions="3D")
    g.set(mp, "Scale", 1.6)
    g.set(mp, "Detail", 4.0)
    g.link(geo, "Position", mp, "Vector")
    patchy = g.maprange(-750, 850, g.out(mp, "Fac"), 0.36, 0.44, smooth=True)            # broad caps, ragged edge
    mossw = g.math("MULTIPLY", -600, 750, g.out(mossw, 0), g.out(patchy, "Result"))
    lit = g.mix(-400, 300, fac=g.out(mossw, 0), a=g.mixout(lit), b=g.mixout(mossc))
    sh = g.mix(-400, 100, fac=g.out(mossw, 0), a=g.out(pal, "rock_shadow"), b=g.out(pal, "grass_shadow"))
    dp = g.mix(-400, -100, fac=g.out(mossw, 0), a=g.out(pal, "rock_deep"), b=g.out(pal, "grass_deep"))
    cel = shading._cel_node(g, pal, -100, 200, g.out(geo, "Normal"), g.mixout(lit), g.mixout(sh), g.mixout(dp))
    # a thin dark crease where the rock meets the ground
    fz = g.n("ShaderNodeSeparateXYZ", -400, -400)
    g.link(g.n("ShaderNodeTexCoord", -600, -400), "Object", fz, "Vector")
    base = g.maprange(-250, -400, g.out(fz, "Z"), 0.0, 0.08, 0.55, 1.0, smooth=True)
    bc = g.n("ShaderNodeCombineColor", -100, -400)
    for c in ("Red", "Green", "Blue"):
        g.link(base, "Result", bc, c)
    col = g.mix(100, 200, "MULTIPLY", fac=1.0, a=g.out(cel, "Color"), b=only(bc.outputs))
    vz = g.maprange(-250, -250, g.out(nz, "Z"), -0.4, 0.9, 0.86, 1.08, smooth=True)
    vg = g.n("ShaderNodeCombineColor", -100, -250)
    g.link(vz, "Result", vg, "Red")
    g.link(vz, "Result", vg, "Green")
    g.link(g.math("MULTIPLY_ADD", -150, -300, g.out(vz, "Result"), 0.7, 0.3), 0, vg, "Blue")
    col = g.mix(150, 200, "MULTIPLY", fac=1.0, a=g.mixout(col), b=only(vg.outputs))
    cv = g.n("ShaderNodeTexVoronoi", -400, -800, voronoi_dimensions="3D", feature="DISTANCE_TO_EDGE")
    g.set(cv, "Scale", 2.6)
    g.link(g.n("ShaderNodeTexCoord", -600, -900), "Object", cv, "Vector")
    crack = g.maprange(-250, -800, g.out(cv, "Distance"), 0.03, 0.01, smooth=True)         # dark crevice lines
    cn = g.n("ShaderNodeTexNoise", -400, -1000, noise_dimensions="3D")
    g.set(cn, "Scale", 0.9)
    g.link(geo, "Position", cn, "Vector")
    crack = g.math("MULTIPLY", -100, -850, g.out(crack, "Result"), g.out(g.maprange(-250, -1000, g.out(cn, "Fac"),
                   0.6, 0.66, smooth=True), "Result"))                               # a few cracks, not a net
    cnz = g.n("ShaderNodeSeparateXYZ", -400, -1150)
    g.link(geo, "Normal", cnz, "Vector")
    crack = g.math("MULTIPLY", -50, -950, g.out(crack, 0), g.out(g.maprange(-250, -1150, g.out(cnz, "Z"), 0.6,
                   0.2, smooth=True), "Result"))                                    # on the sides, not the tops
    col = g.mix(200, 150, fac=only(g.math("MULTIPLY", 0, -850, g.out(crack, 0), 0.45).outputs), a=g.mixout(col),
                b=g.out(pal, "rock_deep"))
    dark = g.n("ShaderNodeAttribute", -100, -600, attribute_name="hrp_dark", attribute_type="OBJECT")
    col = g.mix(250, 200, fac=only(g.math("MULTIPLY", 100, -600, g.out(dark, "Fac"), 1.0).outputs),
                a=g.mixout(col), b=g.out(pal, "rock_deep"))                  # a shaded recess (waterfall alcove)
    shading._emit_out(g, g.mixout(col), 500, 200, pal=pal)
    mat["hrp_kind"] = "rock"
    shading._done(mat, "rock_material")
    return mat


# ----------------------------------------------------------------------------------------------
# objects
# ----------------------------------------------------------------------------------------------
def props_collection(scene):
    coll = bpy.data.collections.get(PROPS)
    if coll is None:
        coll = bpy.data.collections.new(PROPS)
    if coll.name not in scene.collection.children and not any(
            coll.name in c.children for c in bpy.data.collections):
        scene.collection.children.link(coll)
    return coll


def avoid_props(scene):
    """Grass and flowers make room for rocks and stepping stones: they join the scene's Avoid collection (see
    avoid.py), next to whatever the user avoids there; nothing the user chose is replaced."""
    from . import avoid
    coll = props_collection(scene)
    obs = [o for o in coll.objects if o.type == "MESH"]
    if obs and avoid.meadows(scene):
        col = avoid.ensure(scene)
        for ob in obs:
            if col.objects.get(ob.name) is None:
                col.objects.link(ob)
        for m in avoid._mods(scene):
            m.id_data.update_tag()
    for gnd in scene.objects:                                    # and reeds keep clear of rocks
        m = gnd.modifiers.get(SHORE_MOD) if gnd.type == "MESH" else None
        if m is not None:
            try:
                if mod_input(m, "Props") is None:
                    mod_input(m, "Props", coll)
            except KeyError:
                pass
    from . import water                                          # rocks in the water get a foam collar
    for wob in scene.objects:
        m = wob.modifiers.get(water.SURFACE_MOD) if water.is_water(wob) else None
        if m is not None:
            try:
                if mod_input(m, "Obstacles") is None:
                    mod_input(m, "Obstacles", coll)
            except KeyError:
                pass


def add_rock(context, loc, size=1.0, seed=0, flat=0.65, ground_z=None, block=False, kind=None):
    if kind is None:                                             # a natural mix: mostly boulders, some chunks
        kind = ("ROUND", "ROUND", "ANGULAR", "ROUND", "SLAB")[seed % 5] if not block else "ROUND"
    me = rock_mesh(_rock_name(block, kind, seed, flat), seed=seed, flat=flat, block=block, kind=kind)
    if not me.materials:
        me.materials.append(rock_material())
    ob = bpy.data.objects.new("Harappa Rock", me)
    ob.location = (loc[0], loc[1], loc[2] if ground_z is None else ground_z - 0.1 * size)   # bedded in, not set down
    ob.scale = (size, size, size)
    ob.rotation_euler = (0.0, 0.0, random.Random(seed).uniform(0, math.tau))
    ob["hrp_rock"] = [size, seed, flat, 1 if block else 0]
    ob["hrp_rock_kind"] = kind
    ob["hrp_rsize"] = float(size)
    props_collection(context.scene).objects.link(ob)
    avoid_props(context.scene)
    return ob


def _rock_name(block, kind, seed, flat):
    """One mesh per shape: rocks share it only when they really are the same rock (kind, seed and height ratio)."""
    return f"HRP Rock {'B' if block else ''}{kind[0]}{int(seed)} {float(flat):.2f}"


def edit_rock(ob, seed=None, flat=None):
    """A new shape for an existing rock (same place, same scale, same kind)."""
    info = list(ob.get("hrp_rock", [1.0, 0, 0.65, 0]))
    while len(info) < 4:
        info.append(0)
    if seed is not None:
        info[1] = int(seed)
    if flat is not None:
        info[2] = float(flat)
    block = bool(info[3])
    kind = str(ob.get("hrp_rock_kind", "ROUND"))
    me = rock_mesh(_rock_name(block, kind, info[1], info[2]), seed=int(info[1]), flat=info[2], block=block, kind=kind)
    if not me.materials:
        me.materials.append(rock_material())
    old = ob.data
    ob.data = me
    if old is not None and old.users == 0 and old is not me:
        bpy.data.meshes.remove(old)
    ob["hrp_rock"] = info
    ob.update_tag()


# ----------------------------------------------------------------------------------------------
# shore pebbles: last modifier on the meadow
# ----------------------------------------------------------------------------------------------
def shore_group():
    """Pebbles on the bank just above the water line, reeds and cattails standing in the shallows."""
    ng, rebuilt = fresh_group(SHORE, "GeometryNodeTree", ROCK_VER + 10)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Pebbles", "INPUT", "NodeSocketCollection")
    iface(ng, "Pebble Density", "INPUT", "NodeSocketFloat", 10.0, 0.0, 200.0, "Pebbles per square metre on the bank")
    iface(ng, "Pebble Size", "INPUT", "NodeSocketFloat", 0.14, 0.01, 5.0, "Average pebble size", "DISTANCE")
    iface(ng, "Reed", "INPUT", "NodeSocketObject")
    iface(ng, "Reeds", "INPUT", "NodeSocketFloat", 2.5, 0.0, 50.0, "Reed clumps per square metre in the shallows")
    iface(ng, "Reed Height", "INPUT", "NodeSocketFloat", 1.1, 0.1, 10.0, "Height of the reeds", "DISTANCE")
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Water", "INPUT", "NodeSocketCollection", desc="The Harappa Water collection (no reeds by a waterfall)")
    iface(ng, "Props", "INPUT", "NodeSocketCollection", desc="Rocks: no reeds growing through them")
    iface(ng, "Cliff Rocks", "INPUT", "NodeSocketCollection", desc="Rock chunks that dress steep bare faces")
    iface(ng, "Cliff Density", "INPUT", "NodeSocketFloat", 2.2, 0.0, 20.0, "Rock chunks per square metre on "
          "steep faces (over about 40 degrees)")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1400, 0)
    go = g.n("NodeGroupOutput", 1200, 0)
    sd = g.n("GeometryNodeInputNamedAttribute", -1400, -300, data_type="FLOAT")
    sd.inputs["Name"].default_value = "hrp_sd"
    pos = g.n("GeometryNodeInputPosition", -1400, -900)
    nz = g.n("ShaderNodeTexNoise", -1200, -900, noise_dimensions="3D")
    g.set(nz, "Scale", 0.6)
    g.link(pos, 0, nz, "Vector")

    def band(x, y, a, b, c, d):
        r1 = g.maprange(x, y, g.out(sd, "Attribute"), a, b, smooth=True)
        r2 = g.maprange(x, y - 150, g.out(sd, "Attribute"), c, d, 1.0, 0.0, smooth=True)
        return only(g.math("MULTIPLY", x + 180, y, g.out(r1, "Result"), g.out(r2, "Result")).outputs)

    def scatter(x, y, weight, dens_sock, seed_off):
        d = g.math("MULTIPLY", x, y, weight, dens_sock)
        dist = g.n("GeometryNodeDistributePointsOnFaces", x + 200, y)
        g.link(gi, "Geometry", dist, "Mesh")
        g.link(d, 0, dist, "Density")
        sa = g.n("FunctionNodeIntegerMath", x + 50, y - 150, operation="ADD")
        g.link(gi, "Seed", sa, ("Value", 0))
        sock(sa.inputs, ("Value", 1)).default_value = seed_off
        g.link(sa, 0, dist, "Seed")
        return g.out(dist, "Points")

    # pebbles: bank 0 .. 0.45 m above the water, in loose groups
    pw = band(-1200, -300, -0.14, -0.04, 0.35, 0.75)                   # some half in the water, some up the bank
    pclump = g.maprange(-1050, -900, g.out(nz, "Fac"), 0.46, 0.58, smooth=True)   # a few gravel spits, not a necklace
    pw = only(g.math("MULTIPLY", -900, -400, pw, g.out(pclump, "Result")).outputs)
    nrm0 = g.n("GeometryNodeInputNormal", -1200, -1100)
    nz0 = g.n("ShaderNodeSeparateXYZ", -1050, -1100)
    g.link(nrm0, "Normal", nz0, "Vector")
    pflat = g.maprange(-900, -1100, g.out(nz0, "Z"), 0.7, 0.85, smooth=True)       # not stuck on cliff faces
    pw = only(g.math("MULTIPLY", -850, -450, pw, g.out(pflat, "Result")).outputs)
    ppts = scatter(-800, -300, pw, g.out(gi, "Pebble Density"), 0)
    ci = g.n("GeometryNodeCollectionInfo", -500, -600)
    g.link(gi, "Pebbles", ci, "Collection")
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    pin = g.n("GeometryNodeInstanceOnPoints", -200, -300)
    g.links.new(ppts, pin.inputs["Points"])
    pinst = pin
    g.link(ci, 0, pin, "Instance")
    pin.inputs["Pick Instance"].default_value = True
    rot = g.n("FunctionNodeRandomValue", -400, -800, data_type="FLOAT_VECTOR")
    rot.inputs["Min"].default_value = (-0.25, -0.25, 0.0)
    rot.inputs["Max"].default_value = (0.25, 0.25, 6.28)
    g.link(rot, "Value", pin, "Rotation")
    sc = g.n("FunctionNodeRandomValue", -400, -1000, data_type="FLOAT")
    g.set(sc, "Min", 0.0, "VALUE")
    g.set(sc, "Max", 1.0, "VALUE")
    skew = g.math("MULTIPLY_ADD", -300, -1000, only(g.math("POWER", -350, -1100, g.out(sc, "Value", "VALUE"), 3.0)
                  .outputs), 2.0, 0.35)                                       # many small, a few big
    psz = g.math("MULTIPLY", -250, -1000, g.out(skew, 0), g.out(gi, "Pebble Size"))
    g.link(psz, 0, pin, "Scale")
    bury = g.n("ShaderNodeCombineXYZ", -150, -900)
    g.link(g.math("MULTIPLY", -250, -900, g.out(psz, 0), -0.35), 0, bury, "Z")

    # reeds: from 0.35 m out in the water to 0.15 m up the bank, in clumps, swaying together
    rw = band(-1200, 300, -0.38, -0.25, 0.08, 0.2)
    fl0 = g.n("GeometryNodeInputNamedAttribute", -1200, 150, data_type="FLOAT")
    fl0.inputs["Name"].default_value = "hrp_flat"                                # slope before the carve
    flat_ = g.maprange(-900, 150, g.out(fl0, "Attribute"), 0.8, 0.92, smooth=True)  # not on hillsides or cliffs
    rw = only(g.math("MULTIPLY", -1000, 250, rw, g.out(flat_, "Result")).outputs)
    en_ = g.n("GeometryNodeInputNamedAttribute", -1200, 0, data_type="FLOAT")
    en_.inputs["Name"].default_value = "hrp_endd"
    lipf = g.maprange(-900, 0, g.out(en_, "Attribute"), 3.0, 4.0, smooth=True)     # clear of a waterfall's lip
    has_en = g.n("GeometryNodeSwitch", -800, 0, input_type="FLOAT")
    g.link(en_, "Exists", has_en, "Switch")
    has_en.inputs["False"].default_value = 1.0
    g.link(lipf, "Result", has_en, "True")
    rw = only(g.math("MULTIPLY", -950, 200, rw, g.out(has_en, 0)).outputs)
    wci = g.n("GeometryNodeCollectionInfo", -1500, 600, transform_space="RELATIVE")   # straight-line clearance
    g.link(gi, "Water", wci, "Collection")
    wre = g.n("GeometryNodeRealizeInstances", -1350, 600)
    g.link(wci, 0, wre, "Geometry")
    falls = g.n("GeometryNodeSeparateGeometry", -1200, 600, domain="FACE")
    g.link(wre, 0, falls, "Geometry")
    wfa = g.n("GeometryNodeInputNamedAttribute", -1350, 750, data_type="FLOAT_VECTOR")
    wfa.inputs["Name"].default_value = "hrp_wf"
    wfs = g.n("ShaderNodeSeparateXYZ", -1300, 850)                     # by value: "Exists" is true for all
    g.link(wfa, "Attribute", wfs, "Vector")                                     # faces once the collection is realized
    wsum = g.math("ADD", -1200, 850, g.out(wfs, "Y"), g.out(wfs, "Z"))
    g.link(g.math("GREATER_THAN", -1150, 800, g.out(wsum, 0), 0.0001), 0, falls, "Selection")
    fsz = g.n("GeometryNodeAttributeDomainSize", -1050, 750, component="MESH")
    g.link(falls, "Selection", fsz, "Geometry")
    fpx = g.n("GeometryNodeProximity", -1050, 600, target_element="FACES")
    g.link(falls, "Selection", fpx, "Geometry")
    fclr = g.maprange(-900, 600, g.out(fpx, "Distance"), 6.5, 8.0, smooth=True)       # not by fast water
    fsw = g.n("GeometryNodeSwitch", -750, 650, input_type="FLOAT")
    g.link(g.math("GREATER_THAN", -900, 750, g.out(fsz, "Face Count"), 0.5), 0, fsw, "Switch")
    fsw.inputs["False"].default_value = 1.0
    g.link(fclr, "Result", fsw, "True")
    rw = only(g.math("MULTIPLY", -950, 120, rw, g.out(fsw, 0)).outputs)
    ab_ = g.n("GeometryNodeInputNamedAttribute", -1200, -150, data_type="FLOAT")
    ab_.inputs["Name"].default_value = "hrp_above"
    low = g.maprange(-900, -150, g.out(ab_, "Attribute"), 0.3, 0.15, smooth=True)   # only near the waterline
    shal = g.maprange(-900, -250, g.out(ab_, "Attribute"), -0.42, -0.28, smooth=True)  # never in deep water
    low = g.math("MULTIPLY", -800, -200, g.out(low, "Result"), g.out(shal, "Result"))
    rw = only(g.math("MULTIPLY", -950, 150, rw, g.out(low, 0)).outputs)
    pci = g.n("GeometryNodeCollectionInfo", -1500, 1000, transform_space="RELATIVE")      # never through a rock
    g.link(gi, "Props", pci, "Collection")
    pre = g.n("GeometryNodeRealizeInstances", -1350, 1000)
    g.link(pci, 0, pre, "Geometry")
    psz_ = g.n("GeometryNodeAttributeDomainSize", -1200, 1100, component="MESH")
    g.link(pre, 0, psz_, "Geometry")
    ppx = g.n("GeometryNodeProximity", -1200, 1000, target_element="FACES")
    g.link(pre, 0, ppx, "Geometry")
    pclr = g.maprange(-1050, 1000, g.out(ppx, "Distance"), 0.12, 0.35, smooth=True)
    psw = g.n("GeometryNodeSwitch", -900, 1000, input_type="FLOAT")
    g.link(g.math("GREATER_THAN", -1050, 1100, g.out(psz_, "Face Count"), 0.5), 0, psw, "Switch")
    psw.inputs["False"].default_value = 1.0
    g.link(pclr, "Result", psw, "True")
    rw = only(g.math("MULTIPLY", -850, 350, rw, g.out(psw, 0)).outputs)
    rclump = g.maprange(-1050, 500, g.out(nz, "Fac"), 0.5, 0.62, smooth=True)
    rw = only(g.math("MULTIPLY", -900, 300, rw, g.out(rclump, "Result")).outputs)
    rpts = scatter(-800, 300, rw, g.out(gi, "Reeds"), 7)
    oi = g.n("GeometryNodeObjectInfo", -500, 600)
    g.link(gi, "Reed", oi, "Object")
    tm = g.n("GeometryNodeInputSceneTime", -700, 800)
    rp = g.n("GeometryNodeInputPosition", -700, 950)
    rps = g.n("ShaderNodeSeparateXYZ", -550, 950)
    g.link(rp, 0, rps, "Vector")
    phx = g.math("MULTIPLY_ADD", -400, 950, g.out(rps, "X"), 0.7, only(g.math("MULTIPLY", -550, 800,
                                                                         g.out(tm, "Seconds"), 1.6).outputs))
    swx = g.math("MULTIPLY", -250, 950, only(g.math("SINE", -300, 950, g.out(phx, 0)).outputs), 0.07)
    phy = g.math("MULTIPLY_ADD", -400, 1100, g.out(rps, "Y"), 0.6, only(g.math("MULTIPLY", -550, 1100,
                                                                         g.out(tm, "Seconds"), 1.1).outputs))
    swy = g.math("MULTIPLY", -250, 1100, only(g.math("SINE", -300, 1100, g.out(phy, 0)).outputs), 0.05)
    rz = g.n("FunctionNodeRandomValue", -400, 700, data_type="FLOAT")
    g.set(rz, "Max", 6.28, "VALUE")
    rrot = g.n("ShaderNodeCombineXYZ", -100, 800)
    g.link(rz, "Value", rrot, "Z", akind="VALUE")
    sway = g.n("ShaderNodeCombineXYZ", 50, 950)
    g.link(swx, 0, sway, "X")
    g.link(swy, 0, sway, "Y")
    rs_ = g.n("FunctionNodeRandomValue", -400, 500, data_type="FLOAT")
    g.set(rs_, "Min", 0.7, "VALUE")
    g.set(rs_, "Max", 1.3, "VALUE")
    rsc = g.math("MULTIPLY", -250, 500, g.out(rs_, "Value", "VALUE"), g.out(gi, "Reed Height"))
    rin = g.n("GeometryNodeInstanceOnPoints", 100, 300)
    g.links.new(rpts, rin.inputs["Points"])
    g.link(oi, "Geometry", rin, "Instance")
    g.link(rrot, 0, rin, "Rotation")
    g.link(rsc, 0, rin, "Scale")
    rot_w = g.n("GeometryNodeRotateInstances", 250, 300)                       # neighbours sway together
    g.link(rin, 0, rot_w, "Instances")
    g.link(sway, 0, rot_w, "Rotation")
    rot_w.inputs["Local Space"].default_value = False
    rin = rot_w

    tpin = g.n("GeometryNodeTranslateInstances", 0, -300)                      # half buried
    g.link(pinst, 0, tpin, "Instances")
    g.link(bury, 0, tpin, "Translation")
    # steep bare faces: overlapping angular chunks bedded into the face (a broken rock silhouette, not a wall)
    cn_ = g.n("GeometryNodeInputNormal", -1200, -1500)
    cnz = g.n("ShaderNodeSeparateXYZ", -1050, -1500)
    g.link(cn_, "Normal", cnz, "Vector")
    cbl = g.n("GeometryNodeBlurAttribute", -950, -1500, data_type="FLOAT")      # the slope of the land, not of
    g.link(cnz, "Z", cbl, "Value")                                              # every little bump in it
    cbl.inputs["Iterations"].default_value = 4
    cw_ = g.maprange(-850, -1500, g.out(cbl, 0), 0.78, 0.64, smooth=True)
    gm_ = g.n("GeometryNodeInputNamedAttribute", -1050, -1650, data_type="FLOAT_COLOR")
    gm_.inputs["Name"].default_value = "hrp_grass"
    gms = g.n("FunctionNodeSeparateColor", -950, -1650)
    g.link(gm_, "Attribute", gms, "Color")
    bare = g.n("GeometryNodeSwitch", -850, -1700, input_type="FLOAT")             # only where the carve left
    g.link(gm_, "Exists", bare, "Switch")                                       # the ground bare
    bare.inputs["False"].default_value = 0.0
    g.link(g.math("SUBTRACT", -900, -1750, 1.0, g.out(gms, "Red")), 0, bare, "True")
    cw_ = g.math("MULTIPLY", -750, -1550, g.out(cw_, "Result"), g.out(bare, 0))
    abv = g.n("GeometryNodeInputNamedAttribute", -1050, -1850, data_type="FLOAT")    # dry land only, not the
    abv.inputs["Name"].default_value = "hrp_above"                                    # steep sides of a pond bed
    dry = g.n("GeometryNodeSwitch", -850, -1850, input_type="FLOAT")
    g.link(abv, "Exists", dry, "Switch")
    dry.inputs["False"].default_value = 1.0
    g.link(g.maprange(-950, -1900, g.out(abv, "Attribute"), 0.25, 0.5, smooth=True), "Result", dry, "True")
    cw_ = g.math("MULTIPLY", -700, -1600, g.out(cw_, 0), g.out(dry, 0))
    cpt = g.n("GeometryNodeDistributePointsOnFaces", -700, -1500, distribute_method="POISSON")
    g.link(gi, "Geometry", cpt, "Mesh")
    cpt.inputs["Distance Min"].default_value = 0.42
    g.link(gi, "Cliff Density", cpt, "Density Max")
    g.link(cw_, 0, cpt, "Density Factor")
    g.link(gi, "Seed", cpt, "Seed")
    al = g.n("FunctionNodeAlignRotationToVector", -500, -1650)
    g.link(cpt, "Normal", al, "Vector")
    spin = g.n("FunctionNodeRotateRotation", -350, -1650)
    g.link(al, 0, spin, "Rotation")
    srv = g.n("FunctionNodeRandomValue", -650, -1800, data_type="FLOAT")
    g.set(srv, "Max", 6.28, "VALUE")
    se = g.n("ShaderNodeCombineXYZ", -500, -1800)
    g.link(srv, "Value", se, "Z", akind="VALUE")
    g.link(se, 0, spin, "Rotate By")
    spin.rotation_space = "LOCAL"
    csz = g.n("FunctionNodeRandomValue", -650, -1950, data_type="FLOAT")              # a few big anchors, much fill
    csz2 = g.math("MULTIPLY_ADD", -500, -1950, only(g.math("POWER", -550, -2000, g.out(csz, "Value", "VALUE"), 2.5)
                  .outputs), 1.25, 0.4)
    cci = g.n("GeometryNodeCollectionInfo", -500, -1400)
    g.link(gi, "Cliff Rocks", cci, "Collection")
    cci.inputs["Separate Children"].default_value = True
    cci.inputs["Reset Children"].default_value = True
    cin_ = g.n("GeometryNodeInstanceOnPoints", -200, -1500)
    g.link(cpt, "Points", cin_, "Points")
    g.link(cci, 0, cin_, "Instance")
    cin_.inputs["Pick Instance"].default_value = True
    g.link(spin, 0, cin_, "Rotation")
    g.link(csz2, 0, cin_, "Scale")
    cbed = g.n("GeometryNodeTranslateInstances", 0, -1500)                     # 30% into the face
    g.link(cin_, 0, cbed, "Instances")
    cbv = g.n("ShaderNodeCombineXYZ", -150, -1650)
    cbz = g.n("FunctionNodeRandomValue", -300, -1750, data_type="FLOAT")
    g.set(cbz, "Min", -0.32, "VALUE")
    g.set(cbz, "Max", -0.05, "VALUE")
    g.link(cbz, "Value", cbv, "Z", akind="VALUE")
    g.link(cbv, 0, cbed, "Translation")
    join = g.n("GeometryNodeJoinGeometry", 900, 0)
    g.link(gi, "Geometry", join, "Geometry")
    g.link(tpin, 0, join, "Geometry")
    g.link(rin, 0, join, "Geometry")
    g.link(cbed, 0, join, "Geometry")
    g.link(join, 0, go, "Geometry")
    stamp(ng, ROCK_VER + 10)                                   # built: not rebuilt on every use
    return ng


def attach_shore(scene, ground):
    from . import pondlife
    mod = ground.modifiers.get(SHORE_MOD)
    if mod is None:
        mod = ground.modifiers.new(SHORE_MOD, "NODES")
    mod.node_group = shore_group()
    mod_input(mod, "Pebbles", pebble_collection())
    mod_input(mod, "Reed", pondlife.reed_object())
    from . import water
    mod_input(mod, "Water", water.water_collection(scene))
    mod_input(mod, "Props", props_collection(scene))
    mod_input(mod, "Cliff Rocks", cliff_collection())
    idx = list(ground.modifiers).index(mod)
    last = len(ground.modifiers) - 1
    if idx != last:
        ground.modifiers.move(idx, last)
    return mod
