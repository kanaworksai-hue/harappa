# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural anime trees.

A tree is three objects under one empty:
  Trunk   tapered tube mesh: trunk + branches that run into each canopy clump (bark cel material)
  Canopy  a mesh of overlapping clump spheres; the HRP Foliage modifier covers it with camera-facing
          leaf dabs whose normals come from the clump spheres (the "transfer normals from the emitter"
          trick, done in Geometry Nodes). Edit the canopy mesh to re-shape the tree.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import assets, scatter, shading
from .util import mod_input

# shape presets: crown radius (x/y), crown half-height, crown centre height (x height), trunk ratio,
# clump count, clump radius (x crown radius), leaf style, density, leaf size (x height), blossom,
# branch spread, conifer layering
SHAPES = {
    "ROUND": dict(cw=0.42, ch=0.34, cz=0.66, clumps=9, cr=0.47, style="ROUND", dens=48, leaf=0.075,
                  bloom=0.0, trunk=0.038, roundness=0.4),
    "TALL": dict(cw=0.2, ch=0.42, cz=0.6, clumps=13, cr=0.5, style="SMALL", dens=60, leaf=0.06,
                 bloom=0.0, trunk=0.045, roundness=0.55),
    "WIDE": dict(cw=0.58, ch=0.31, cz=0.66, clumps=15, cr=0.36, style="SMALL", dens=55, leaf=0.06,
                 bloom=0.0, trunk=0.06, roundness=0.35),
    "BUSH": dict(cw=0.62, ch=0.36, cz=0.4, clumps=13, cr=0.36, style="ROUND", dens=45, leaf=0.17,
                 bloom=0.0, trunk=0.0, roundness=0.55, bush=True, value=-0.14),
    "CONIFER": dict(cw=0.36, ch=0.42, cz=0.52, clumps=18, cr=0.42, style="NEEDLE", dens=80, leaf=0.06,
                    bloom=0.0, trunk=0.035, roundness=0.25, conifer=True),
    # 1.1: shapes you can name at a glance
    "SAKURA": dict(cw=0.66, ch=0.27, cz=0.7, clumps=19, cr=0.34, style="SMALL", dens=62, leaf=0.055,
                   bloom=0.92, trunk=0.05, roundness=0.4, lean=0.05),
    "PINE": dict(cw=0.5, ch=0.3, cz=0.72, clumps=6, cr=0.5, style="NEEDLE", dens=85, leaf=0.055,
                 bloom=0.0, trunk=0.045, roundness=0.2, pads=True, lean=0.16, value=-0.06),
    "WILLOW": dict(cw=0.44, ch=0.26, cz=0.72, clumps=10, cr=0.44, style="SMALL", dens=70, leaf=0.05,
                   bloom=0.0, trunk=0.045, roundness=0.5, droop=True),
    "COLUMN": dict(cw=0.1, ch=0.44, cz=0.54, clumps=16, cr=0.34, style="SMALL", dens=70, leaf=0.05,
                   bloom=0.0, trunk=0.03, roundness=0.6, value=-0.08),
}


def _ellipsoid_points(rng, n, cw, ch, centre, min_d):
    """Poisson-ish points in an ellipsoid shell (0.25..0.8 of the radius), upper half favoured."""
    pts = []
    tries = 0
    while len(pts) < n and tries < 4000:
        tries += 1
        v = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1) + 0.25))
        if v.length < 1e-6:
            continue
        v.normalize()
        r = rng.uniform(0.25, 0.8)
        if v.z * r < -0.22:            # no separate lobe hanging under the crown
            continue
        p = Vector((v.x * cw * r, v.y * cw * r, v.z * ch * r + rng.uniform(-0.15, 0.15) * ch)) + centre
        if all((p - q).length > min_d for q in pts):
            pts.append(p)
    return pts


def _pad_points(rng, n, cw, ch, centre):
    """A pine's flat pads of needles: a few tiers, each set off to one side, the top one over the trunk."""
    pts = []
    a = rng.uniform(0, math.tau)
    for k in range(n):
        t = k / max(1, n - 1)                              # 0 lowest pad .. 1 top
        z = centre.z - ch * 0.75 + t * ch * 1.6
        reach = cw * (0.85 - 0.6 * t) * rng.uniform(0.75, 1.1)
        a += math.radians(rng.uniform(110, 200))           # alternate around the trunk
        pts.append(Vector((centre.x + math.cos(a) * reach, centre.y + math.sin(a) * reach * 0.8, z)))
    return pts


def _droop_points(rng, n, cw, ch, centre, base):
    """A willow's curtain: hanging strands around the rim of the crown, reaching down towards the ground."""
    pts = []
    for k in range(n):
        a = (k + rng.uniform(-0.3, 0.3)) / n * math.tau
        r = cw * rng.uniform(0.72, 0.98)
        z = base + (centre.z - base) * rng.uniform(0.35, 0.6)
        pts.append(Vector((centre.x + math.cos(a) * r, centre.y + math.sin(a) * r, z)))
    return pts


def _conifer_points(rng, n, cw, ch, centre):
    """Stacked tiers: a ring of flat clumps per tier, narrowing to a point."""
    pts = []
    bottom = centre.z - ch
    tiers = max(3, n // 3)
    for k in range(tiers):
        t = (k + 0.5) / tiers
        z = bottom + t * 2 * ch
        rad = cw * (1.0 - t) * 0.7
        m = max(1, int(round(4 * (1.0 - t))) + 1)
        a0 = rng.uniform(0, math.tau)
        for j in range(m):
            a = a0 + j / m * math.tau
            rr = rad if m > 1 else 0.0
            pts.append(Vector((math.cos(a) * rr, math.sin(a) * rr, z + rng.uniform(-0.03, 0.03) * ch)))
    return pts


def _branch_path(rng, a, b, bend, segs=6):
    """Points from a to b with a sideways bow and a little gnarl."""
    side = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0))
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    pts = []
    for i in range(segs + 1):
        t = i / segs
        p = a.lerp(b, t)
        p += side * math.sin(t * math.pi) * bend
        if 0 < i < segs:
            p += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.5, 0.5))) * bend * 0.25
        pts.append(p)
    return pts


def _tube(bm, pts, radii, sides=7):
    prev = None
    for i, p in enumerate(pts):
        if i < len(pts) - 1:
            tng = (pts[i + 1] - p).normalized()
        else:
            tng = (p - pts[i - 1]).normalized()
        up = Vector((0, 0, 1)) if abs(tng.z) < 0.95 else Vector((1, 0, 0))
        x = tng.cross(up).normalized()
        y = tng.cross(x).normalized()
        ring = []
        for k in range(sides):
            a = k / sides * math.tau
            ring.append(bm.verts.new(p + (x * math.cos(a) + y * math.sin(a)) * radii[i]))
        if prev is not None:
            for k in range(sides):
                bm.faces.new((prev[k], prev[(k + 1) % sides], ring[(k + 1) % sides], ring[k]))
        prev = ring


def build_meshes(shape="ROUND", height=5.0, seed=0, name="Anime Tree"):
    """Returns (trunk_mesh or None, canopy_mesh) built in local space with the root at the origin."""
    sp = SHAPES[shape]
    rng = random.Random(seed * 7919 + 17)
    H = height
    cw, ch = sp["cw"] * H, sp["ch"] * H
    lean = sp.get("lean", 0.0) * H                       # the crown sits off the root: a leaning trunk
    la = rng.uniform(0, math.tau)
    centre = Vector((rng.uniform(-0.03, 0.03) * H + math.cos(la) * lean,
                     rng.uniform(-0.03, 0.03) * H + math.sin(la) * lean, sp["cz"] * H))
    cr = sp["cr"] * max(cw, ch * 0.8)
    strands = []
    if sp.get("conifer"):
        clumps = _conifer_points(rng, sp["clumps"], cw, ch, centre)
    elif sp.get("pads"):
        clumps = _pad_points(rng, sp["clumps"], cw, ch, centre)
    else:
        clumps = _ellipsoid_points(rng, sp["clumps"], cw, ch, centre, cr * 0.75)
    # canopy: one ico sphere per clump, radius varies, slightly squashed
    cm = bpy.data.meshes.new(name + " Canopy")
    bm = bmesh.new()
    clump_r = []
    for i, c in enumerate(clumps):
        r = cr * rng.uniform(0.62, 1.3)
        if sp.get("conifer"):
            r *= 0.45 + 0.75 * (1 - (c.z - (centre.z - ch)) / (2 * ch))
        if sp.get("bush"):
            c.z = max(c.z, r * 0.55)
        clump_r.append(r)
        flat = 0.42 if sp.get("conifer") else (0.34 if sp.get("pads") else 0.85)
        if sp.get("pads"):
            r *= 0.9 - 0.35 * (c.z - (centre.z - ch * 0.75)) / (ch * 1.6)      # smaller pads towards the top
        m = Matrix.Translation(c) @ Matrix.Diagonal((r, r, r * flat, 1.0))
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0, matrix=m)
    # top-of-crown cap so the silhouette is not flat
    if not sp.get("conifer") and sp["trunk"] > 0:
        top = centre + Vector((0, 0, ch * 0.55))
        r = cr * 0.9
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0,
                                   matrix=Matrix.Translation(top) @ Matrix.Diagonal((r, r, r * 0.8, 1)))
    if sp.get("droop"):
        strands = _droop_points(rng, 13, cw, ch, centre, H * 0.16)
        for c in strands:
            r = cr * rng.uniform(0.3, 0.42)
            m = Matrix.Translation(c) @ Matrix.Diagonal((r, r, (c.z - H * 0.12) * rng.uniform(0.8, 1.0), 1.0))
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0, matrix=m)
    if sp.get("conifer"):                      # a pointed tip, so no bare trunk pokes out of the top tier
        tip = Vector((centre.x, centre.y, centre.z + ch * 0.9))
        r = cr * 0.42
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0,
                                   matrix=Matrix.Translation(tip) @ Matrix.Diagonal((r, r, r * 2.0, 1)))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(cm)
    bm.free()

    if sp["trunk"] <= 0:
        return None, cm
    tm = bpy.data.meshes.new(name + " Trunk")
    bm = bmesh.new()
    r0 = sp["trunk"] * H
    if sp.get("conifer"):
        fork = Vector((0, 0, centre.z + ch * 0.78))
    elif sp.get("pads"):
        fork = Vector((centre.x, centre.y, centre.z + ch * 0.7))       # a pine's trunk runs up through its pads
    else:
        fork = Vector((centre.x * 0.9, centre.y * 0.9, centre.z - ch * 0.55))
    trunk = _branch_path(rng, Vector((0, 0, 0)), fork, H * 0.03, segs=8)
    trunk_r = []
    for i, p in enumerate(trunk):
        t = i / (len(trunk) - 1)
        flare = 1.0 + 0.7 * max(0.0, 1 - t * 6) ** 2
        trunk_r.append(r0 * (1.0 - (0.9 if sp.get("conifer") else 0.45) * t) * flare)    # a conifer's leader thins out
    _tube(bm, trunk, trunk_r, sides=9)
    # branches from the upper trunk into each clump
    for i, c in enumerate(clumps):
        if sp.get("conifer") or sp.get("pads"):
            t0 = max(0.15, min(0.95, c.z / fork.z))
        else:
            t0 = rng.uniform(0.6, 0.95)
        idx = min(len(trunk) - 1, int(t0 * (len(trunk) - 1)))
        a = trunk[idx]
        b = c.lerp(a, 0.25)
        pts = _branch_path(rng, a, b, (b - a).length * 0.18, segs=5)
        rb = trunk_r[idx] * 0.55
        radii = [rb * (1 - 0.75 * (k / (len(pts) - 1))) for k in range(len(pts))]
        _tube(bm, pts, radii, sides=6)
        # a twig or two poking out of the clump edge
        for _ in range(rng.randint(0, 2)):
            d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.8))).normalized()
            tw = [b, b + d * clump_r[i] * 0.6, b + d * clump_r[i] * 1.0]
            _tube(bm, tw, [radii[-1], radii[-1] * 0.6, radii[-1] * 0.25], sides=5)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(tm)
    bm.free()
    return tm, cm


def assets_collection(scene):
    """Hidden collection holding the tuft and card objects the modifiers instance."""
    coll = bpy.data.collections.get("Harappa Assets")
    if coll is None:
        coll = bpy.data.collections.new("Harappa Assets")
    if coll.name not in scene.collection.children:
        try:
            scene.collection.children.link(coll)
        except RuntimeError:
            pass
    coll.hide_render = True
    coll.hide_viewport = False
    lc = _layer_coll(bpy.context.view_layer.layer_collection, coll.name)
    if lc is not None:
        lc.hide_viewport = True
    return coll


def _layer_coll(lc, name):
    if lc.collection.name == name:
        return lc
    for c in lc.children:
        r = _layer_coll(c, name)
        if r is not None:
            return r
    return None


def asset_object(scene, name, mesh, material):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, mesh)
    else:
        ob.data = mesh
    coll = assets_collection(scene)
    if ob.name not in coll.objects:
        coll.objects.link(ob)
    mesh.materials.clear()
    mesh.materials.append(material)
    ob.hide_render = True
    return ob


def card_object(scene, kind, style="ROUND"):
    """kind: 'leaf' (per leaf style) or 'flower' — the same quad with a different material."""
    if kind == "leaf":
        nm = "HRP Leaf Card" if style == "ROUND" else f"HRP Leaf Card {style.title()}"
        me2 = bpy.data.meshes.get(nm) or assets.card().copy()
        me2.name = nm
        return asset_object(scene, nm, me2, shading.leaves_material(style))
    me = assets.card()
    me2 = bpy.data.meshes.get("HRP Flower Card") or me.copy()
    me2.name = "HRP Flower Card"
    return asset_object(scene, "HRP Flower Card", me2, shading.flower_material())


def tuft_object(scene):
    return asset_object(scene, "HRP Grass Tuft", assets.grass_tuft(), shading.grass_material())


def add_tree(context, shape="ROUND", height=5.0, seed=0, location=(0, 0, 0), leaf_style=None, blossom=None):
    scene = context.scene
    sp = SHAPES[shape]
    name = "Anime Tree"
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = height * 0.1
    root.location = location
    root["hrp_tree"] = shape
    root["hrp_seed"] = seed
    root["hrp_height"] = height
    coll = context.collection or scene.collection
    coll.objects.link(root)
    tm, cm = build_meshes(shape, height, seed, name)
    if tm is not None:
        trunk = bpy.data.objects.new(name + " Trunk", tm)
        tm.materials.append(shading.bark_material())
        coll.objects.link(trunk)
        trunk.parent = root
    canopy = bpy.data.objects.new(name + " Canopy", cm)
    coll.objects.link(canopy)
    canopy.parent = root
    canopy["hrp_canopy"] = True
    canopy.visible_shadow = True
    style = leaf_style or sp["style"]
    card = card_object(scene, "leaf", style)
    canopy["hrp_hue"] = 0.0
    canopy["hrp_value"] = sp.get("value", 0.0)
    canopy["hrp_value_base"] = sp.get("value", 0.0)
    mod = canopy.modifiers.new("Harappa Foliage", "NODES")
    mod.node_group = scatter.foliage_group()
    mod_input(mod, "Card", card)
    mod_input(mod, "Density", float(sp["dens"]) * (5.0 / max(height, 0.1)) ** 2 * 1.0)
    mod_input(mod, "Leaf Size", sp["leaf"] * height)
    mod_input(mod, "Inflate", 0.025 * height)
    mod_input(mod, "Roundness", sp["roundness"])
    mod_input(mod, "Blossom", blossom if blossom is not None else sp["bloom"])
    mod_input(mod, "Blossom Scale", 0.16 * height)
    mod_input(mod, "Seed", seed)
    mod_input(mod, "Fill Material", shading.fill_material())
    mod_input(mod, "Fill Inside", True)
    root["hrp_leaf"] = style
    return root
