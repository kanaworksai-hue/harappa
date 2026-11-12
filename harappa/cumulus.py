# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cumulus clouds as solid bodies.

Each cloud is its own object: a handful of points with radii (the lobes), turned into one smooth body by a
Geometry Nodes modifier (points -> SDF grid -> mesh). Every lobe shades on its own, so the cloud has lit tops,
shaded undersides and a bright rim when the sun is behind it. The object can be moved, scaled, copied and
deleted like any other."""
import math
import random

import bpy
from mathutils import Vector

from . import shading
from .util import G, fresh_group, iface, mod_input, stamp

CLOUD = "HRP Cloud"
CLOUD_VER = 4
MOD = "Harappa Cloud"
TAG = "hrp_cloud"                       # on every cloud object
RADIUS = "hrp_r"


def available():
    """The SDF grid nodes these clouds are made of (Blender 5.0+)."""
    return all(hasattr(bpy.types, n) for n in ("GeometryNodePointsToSDFGrid", "GeometryNodeGridToMesh"))


def _named(g, x, y, name, dtype="FLOAT"):
    n = g.n("GeometryNodeInputNamedAttribute", x, y, data_type=dtype)
    g.set(n, "Name", name)
    return g.out(n, "Attribute")


def cloud_group():
    ng, rebuilt = fresh_group(CLOUD, "GeometryNodeTree", CLOUD_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Detail", "INPUT", "NodeSocketFloat", 0.018, 0.002, 0.2,
          "Size of the smallest bump the cloud keeps, as a share of its width. Smaller is finer and slower")
    iface(ng, "Quality", "INPUT", "NodeSocketFloat", 1.0, 0.25, 4.0,
          "Set by the Detail Level: multiplies the cloud's resolution without changing its Detail")
    iface(ng, "Height", "INPUT", "NodeSocketFloat", 0.45, 0.001, 100.0,
          "Height of the cloud as a share of its width, for its shading")
    iface(ng, "Flat Base", "INPUT", "NodeSocketFloat", 0.88, 0.0, 1.0, "How flat the underside is", "FACTOR")
    iface(ng, "Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1400, 0)
    go = g.n("NodeGroupOutput", 1600, 0)

    pts = g.n("GeometryNodeMeshToPoints", -1150, 0, mode="VERTICES")
    g.link(gi, "Geometry", pts, "Mesh")
    g.links.new(_named(g, -1350, -250, RADIUS), g.inp(pts, "Radius"))
    sdf = g.n("GeometryNodePointsToSDFGrid", -950, 0)
    g.link(pts, "Points", sdf, "Points")
    g.links.new(_named(g, -1150, -250, RADIUS), g.inp(sdf, "Radius"))
    voxel = g.math("DIVIDE", -1150, 200, g.out(gi, "Detail"), g.out(gi, "Quality"))
    g.links.new(g.out(voxel), g.inp(sdf, "Voxel Size"))
    mesh = g.n("GeometryNodeGridToMesh", -550, 0)
    g.link(sdf, "SDF Grid", mesh, "Grid")

    # shading normal: each vertex looks away from the centre of the lobe it belongs to, mixed with the surface
    # normal and blurred -> every puff gets its own lit top and shaded underside, in broad painted shapes.
    # The lobe a vertex belongs to is the sphere whose surface is nearest (not the nearest centre: between a big
    # lobe and a small one on top of it the nearest centre splits along a flat plane, a straight-edged shadow).
    # Smooth unit spheres on the lobes, sampled for their normal = the direction from that lobe's centre.
    pos = g.n("GeometryNodeInputPosition", -550, -300)
    ico = g.n("GeometryNodeMeshIcoSphere", -750, -650)
    g.set(ico, "Radius", 1.0)
    g.set(ico, "Subdivisions", 2)
    smo = g.n("GeometryNodeSetShadeSmooth", -600, -650)
    g.link(ico, "Mesh", smo, "Mesh" if "Mesh" in smo.inputs else "Geometry")
    inst = g.n("GeometryNodeInstanceOnPoints", -450, -500)
    g.link(pts, "Points", inst, "Points")
    g.link(smo, 0, inst, "Instance")
    g.links.new(_named(g, -650, -800, RADIUS), g.inp(inst, "Scale"))
    real = g.n("GeometryNodeRealizeInstances", -300, -500)
    g.link(inst, "Instances", real, "Geometry")
    near = g.n("GeometryNodeSampleNearestSurface", -150, -300, data_type="FLOAT_VECTOR")
    g.link(real, "Geometry", near, "Mesh")
    g.links.new(g.out(g.n("GeometryNodeInputNormal", -300, -700), "Normal"), g.inp(near, "Value", "VECTOR"))
    g.link(pos, "Position", near, "Sample Position")
    away = g.vmath("NORMALIZE", 200, -300, g.out(near, "Value", "VECTOR"))
    nrm = g.n("GeometryNodeInputNormal", 50, -500)
    mixn = g.mix(350, -350, dtype="VECTOR", fac=0.85, a=g.out(nrm, "Normal"), b=g.out(away))
    blur = g.n("GeometryNodeBlurAttribute", 520, -350, data_type="FLOAT_VECTOR")
    g.links.new(g.mixout(mixn), g.inp(blur, "Value", "VECTOR"))
    its = g.math("MULTIPLY", 350, -550, g.out(gi, "Quality"), 2.0)      # same shapes of light at every resolution
    g.links.new(g.out(g.math("ROUND", 450, -550, g.out(its))), g.inp(blur, "Iterations"))
    soft = g.vmath("NORMALIZE", 700, -350, g.out(blur, "Value", "VECTOR"))
    st = g.n("GeometryNodeStoreNamedAttribute", 900, 0, data_type="FLOAT_VECTOR", domain="POINT")
    g.link(mesh, "Mesh", st, "Geometry")
    g.set(st, "Name", "hrp_n")
    g.links.new(g.out(soft), g.inp(st, "Value", "VECTOR"))
    # height in the cloud (0 base .. 1 top): the base stays in shade, the crown catches the light
    sepz = g.n("ShaderNodeSeparateXYZ", 520, -600)
    g.link(pos, "Position", sepz, "Vector")
    hgt = g.math("DIVIDE", 700, -600, g.out(sepz, "Z"), g.out(gi, "Height"), clamp=True)
    st2 = g.n("GeometryNodeStoreNamedAttribute", 1050, 0, data_type="FLOAT", domain="POINT")
    g.link(st, 0, st2, "Geometry")
    g.set(st2, "Name", "hrp_ch")
    g.links.new(g.out(hgt), g.inp(st2, "Value", "VALUE"))
    # flat underside: everything below the base plane is squashed up to it
    keep = g.math("SUBTRACT", 700, -800, 1.0, g.out(gi, "Flat Base"))
    below = g.math("MINIMUM", 700, -950, g.out(sepz, "Z"), 0.0)
    lift = g.math("MULTIPLY", 880, -900, g.out(below), g.out(g.math("SUBTRACT", 800, -800, g.out(keep), 1.0)))
    off = g.n("ShaderNodeCombineXYZ", 1050, -900)
    g.link(lift, 0, off, "Z")
    sp = g.n("GeometryNodeSetPosition", 1200, 0)
    g.link(st2, 0, sp, "Geometry")
    g.link(off, 0, sp, "Offset")
    sm = g.n("GeometryNodeSetShadeSmooth", 1330, 0)
    g.link(sp, 0, sm, "Mesh" if "Mesh" in sm.inputs else "Geometry")
    mat = g.n("GeometryNodeSetMaterial", 1460, 0)
    g.link(sm, 0, mat, "Geometry")
    g.link(gi, "Material", mat, "Material")
    g.link(mat, 0, go, "Geometry")
    stamp(ng, CLOUD_VER)
    return ng


# ---------------------------------------------------------------------------------------------
# the lobes
# ---------------------------------------------------------------------------------------------
def lobes(width, seed=0, tower=0.0):
    """[(centre, radius)] of one cumulus, base on z = 0, long axis on x. Three sizes: a row of big puffs, medium
    ones on their upper halves, small ones on top - the cauliflower hierarchy. tower 0..1 piles more on top."""
    rng = random.Random(seed * 7919 + 13)
    out = []
    n_big = rng.randint(4, 6)
    big = []
    lean = rng.uniform(-0.25, 0.25)                       # the crown sits off-centre
    for i in range(n_big):
        t = (i + 0.5) / n_big * 2 - 1                     # -1 .. 1 along the cloud
        shape = max(0.0, 1.0 - (t - lean) ** 2) ** 0.6
        r = width * (0.085 + 0.115 * shape) * rng.uniform(0.85, 1.15)
        c = Vector((t * width * (0.4 - 0.12 * tower), rng.uniform(-0.05, 0.05) * width, r * rng.uniform(0.55, 0.9)))
        if abs(t) > 0.7:
            r *= 0.8                                      # round ends, no flat wing sticking out of the base
        big.append((c, r))
    out += big

    def on_top(parents, n, scale, spread):
        made = []
        for _ in range(n):
            pc, pr = rng.choice(parents)
            a = rng.uniform(0, math.tau)
            el = rng.uniform(spread, 1.0)                 # sine of the elevation: mostly upwards
            d = Vector((math.cos(a) * math.sqrt(1 - el * el), math.sin(a) * math.sqrt(1 - el * el) * 0.6, el))
            r = pr * rng.uniform(*scale)
            made.append((pc + d * (pr * 1.02 - r * 0.25), r))      # mostly outside its parent: a bump, not a swelling
        return made

    heavy = sorted(big, key=lambda b: -b[1])[:max(2, n_big // 2)]
    mid = on_top(heavy, rng.randint(6, 9), (0.42, 0.62), 0.35) + on_top(big, rng.randint(3, 5), (0.34, 0.5), 0.1)
    out += mid
    if tower > 0.0:
        # a rising tower: each storey is a few puffs side by side, narrower and smaller than the one below
        col, _r = max(big, key=lambda b: b[1])
        top = max(c.z + r for c, r in out)
        storeys = int(2 + tower * 3)
        r = width * 0.15
        z = top * 0.78
        for k in range(storeys):
            spread = width * 0.2 * (1.0 - 0.7 * k / storeys)
            for _ in range(3 if k < storeys - 1 else 2):
                c = Vector((col.x + rng.uniform(-1, 1) * spread, rng.uniform(-0.04, 0.04) * width,
                            z + rng.uniform(-0.2, 0.2) * r))
                rr = r * rng.uniform(0.8, 1.1)
                mid.append((c, rr))
                out.append((c, rr))
                if k > 0:                                 # a middle-sized puff bulging out of the seam below it
                    sd = 1.0 if c.x >= col.x else -1.0
                    m = Vector((c.x + sd * rr * rng.uniform(0.55, 0.8), c.y + rng.uniform(-0.4, 0.4) * rr,
                                c.z - rr * rng.uniform(0.3, 0.45)))
                    out.append((m, rr * rng.uniform(0.5, 0.65)))
                # cauliflower: smaller puffs bulging out of the storey's sides, so the tower's outline is lumpy
                # instead of a stack of smooth balls
                side = 1.0 if c.x >= col.x else -1.0
                for _j in range(3):
                    a = math.radians(rng.uniform(0, 65))
                    yaw = rng.uniform(-0.6, 0.6)
                    d = Vector((side * math.cos(a) * math.cos(yaw), math.sin(yaw) * 0.6, math.sin(a)))
                    sr = rr * rng.uniform(0.25, 0.38)
                    out.append((c + d * (rr * 0.86), sr))
            z += r * 0.9
            r *= rng.uniform(0.72, 0.84)                  # each storey smaller: the tower narrows as it climbs
    small = on_top(mid, rng.randint(14, 20), (0.4, 0.62), 0.2)
    out += small
    out += on_top(small + mid, rng.randint(8, 14), (0.4, 0.6), 0.45)
    # a puff buried deep inside a bigger one adds nothing to the outline but pulls the shading into a dent
    keep = []
    for c, r in out:
        if any(r2 > r and (c - c2).length + r < r2 + r * 0.15 for c2, r2 in out):   # sticks out < 15 %
            continue
        keep.append((c, r))
    return keep


def _points_mesh(name, pts):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c, _r in pts], [], [])
    a = me.attributes.new(RADIUS, "FLOAT", "POINT")
    a.data.foreach_set("value", [r for _c, r in pts])
    me.update()
    return me


def collection(scene):
    """The scene's cloud collection (made on first use)."""
    for c in scene.collection.children_recursive:
        if c.get("hrp_clouds_coll"):
            return c
    c = bpy.data.collections.new("Harappa Clouds")
    c["hrp_clouds_coll"] = True
    scene.collection.children.link(c)
    return c


def shape_cloud(ob, seed=0, tower=0.0):
    """(Re)build one cloud's lobes. The lobes are one unit wide: the cloud's size is the object's scale, so its
    position, rotation and size stay as the user left them, and Detail means the same for a small and a big one."""
    pts = lobes(1.0, seed, tower)
    old = ob.data
    ob.data = _points_mesh(ob.name, pts)
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    ob[TAG] = True
    ob["hrp_cloud_args"] = [int(seed), float(tower)]
    ob.visible_shadow = False
    mod = ob.modifiers.get(MOD)
    fresh = mod is None
    if fresh:
        mod = ob.modifiers.new(MOD, "NODES")
    mod.node_group = cloud_group()
    mod_input(mod, "Height", max(c.z + r for c, r in pts))
    mod_input(mod, "Material", shading.cumulus_material())
    if fresh:
        from . import quality
        mod_input(mod, "Quality", quality.cloud_quality(bpy.context.scene))
    return ob


def add_cloud(context, location, width=120.0, seed=0, tower=0.0, yaw=0.0, name="Cloud"):
    scene = context.scene
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    collection(scene).objects.link(ob)
    ob.location = location
    ob.rotation_euler = (0.0, 0.0, yaw)
    ob.scale = (width, width, width)
    return shape_cloud(ob, seed, tower)


def clouds_of(scene):
    return [o for o in scene.objects if o.get(TAG)]


# ---------------------------------------------------------------------------------------------
# a sky full of them
# ---------------------------------------------------------------------------------------------
def _home(ob):
    return [round(v, 4) for v in (*ob.location, *ob.rotation_euler, *ob.scale)]


def _mods(ob):
    mod = ob.modifiers.get(MOD)
    if mod is None or mod.node_group is None:
        return []
    out = []
    for name in ("Detail", "Flat Base"):
        try:
            out.append(round(float(mod_input(mod, name)), 5))
        except KeyError:
            out.append(0.0)
    return out


def is_auto(ob):
    """Still the layout's own: marked so, and not moved, turned, scaled or given another Detail / Flat Base."""
    if not ob.get("hrp_cloud_auto"):
        return False
    home = ob.get("hrp_cloud_home")
    if home is not None and any(abs(a - b) > 1e-3 for a, b in zip(_home(ob), home)):
        return False
    mods = ob.get("hrp_cloud_mods")
    return mods is None or all(abs(a - b) < 1e-5 for a, b in zip(_mods(ob), mods))


def mark_auto(ob):
    ob["hrp_cloud_auto"] = True
    ob["hrp_cloud_home"] = _home(ob)
    ob["hrp_cloud_mods"] = _mods(ob)


def remove_layout(scene):
    """Delete the clouds the layout made (and the single card-cloud object of 1.0).

    A cloud the user has moved, turned, scaled, copied or given another Detail / Flat Base is theirs from then
    on: it loses its 'auto' mark and stays. Clouds added by hand never had the mark."""
    for ob in list(scene.objects):
        if ob.get("hrp_cloud_auto") and not is_auto(ob):
            del ob["hrp_cloud_auto"]
            continue
        if ob.get("hrp_cloud_auto") or ob.get("hrp_clouds"):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)


def _frame(scene, cam):
    """dir(sx, sy): world direction through a point of the camera frame (0..1), for any lens, shift or aspect."""
    tr, br, bl, tl = cam.data.view_frame(scene=scene)
    q = cam.matrix_world.to_quaternion()

    def direction(sx, sy):
        p = bl.lerp(br, sx).lerp(tl.lerp(tr, sx), sy)
        return (q @ p).normalized()
    return direction


def _skyline(scene, origin):
    """elev(az, half, max_dist): the mean height in degrees of the mountain ridge line seen from 'origin' over the
    azimuths az +- half (radians), counting only mountains nearer than max_dist; 0 with none there."""
    bins = {}
    step = math.radians(0.5)
    for ob in scene.objects:
        if not ob.get("hrp_ridge") or ob.type != "MESH":
            continue
        mw = ob.matrix_world
        for v in ob.data.vertices:
            p = mw @ v.co - origin
            flat = p.xy.length
            if flat < 1e-6:
                continue
            k = int(math.floor(math.atan2(p.y, p.x) / step))
            bins.setdefault(k, []).append((flat, math.degrees(math.atan2(p.z, flat))))

    def elev(az, half, max_dist=float("inf")):
        ks = range(int(math.floor((az - half) / step)), int(math.floor((az + half) / step)) + 1)
        es = [max((e for f, e in bins[k] if f < max_dist), default=None) for k in ks if k in bins]
        es = [e for e in es if e is not None]
        return sum(es) / len(es) if es else 0.0
    return elev


def auto_distance(scene):
    """How far the clouds float when nobody says: where the last layout put them, else behind the farthest
    mountains of the biggest meadow (12 x its size, at least 160 m)."""
    grounds = [o for o in scene.objects if o.get("hrp_ground") and not o.get("hrp_far_hills")]
    size = max((max(o.dimensions.x, o.dimensions.y) for o in grounds), default=40.0)
    lay = scene.get("hrp_cloud_layout")
    if lay is not None and len(lay) > 2 and float(lay[2]) >= size * 11.0:    # still behind the mountains
        return float(lay[2])
    return max(160.0, size * 12.0)


def layout(context, count=5, seed=0, distance=0.0):
    """(Re)build the clouds in front of the scene camera: one big tower, small clouds high up and a band of small
    far ones on the mountain tops, inside the frame and clear of the tree crowns. Returns the cloud objects it made.

    With no sky in the frame (a camera looking down) or no camera, the clouds go above the horizon ahead."""
    from . import clouds as old
    scene = context.scene
    if distance <= 0.0:
        distance = auto_distance(scene)
    remove_layout(scene)
    scene["hrp_cloud_layout"] = [int(count), int(seed), float(distance)]
    if count <= 0:
        return []
    rng = random.Random(seed * 131 + 7)
    context.view_layer.update()
    cam = scene.camera if scene.camera is not None and scene.camera.type == "CAMERA" else None
    if cam is not None and cam.data.type != "ORTHO":
        origin = cam.matrix_world.translation.copy()
        direction = _frame(scene, cam)
        hfov = max(1e-3, direction(0.0, 0.5).angle(direction(1.0, 0.5)))
    else:
        origin = cam.matrix_world.translation.copy() if cam is not None else Vector((0, 0, 0))
        fwd = (cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))) if cam is not None else Vector((0, 1, 0))
        yaw0 = math.atan2(fwd.y, fwd.x)
        hfov = math.radians(60.0)

        def direction(sx, sy):                          # a plain 60 x 34 degree window on the horizon ahead
            a = yaw0 - (sx - 0.5) * hfov
            e = math.radians(1.0 + sy * 33.0)
            return Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    if math.degrees(math.asin(direction(0.5, 1.0).z)) < 6.0:        # hardly any sky in the frame
        fwd = direction(0.5, 0.5)
        yaw0 = math.atan2(fwd.y, fwd.x)

        def direction(sx, sy):                          # noqa: F811
            a = yaw0 - (sx - 0.5) * hfov
            e = math.radians(1.0 + sy * 30.0)
            return Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    boxes = old._tree_boxes(scene, cam) if cam is not None else []
    skyline = _skyline(scene, origin)
    # three layers, as a painter would place them: one big tower rising from behind the mountains (about a third
    # of the frame wide), one or two small clouds high up, and the rest a band of small far clouds sitting low on
    # the mountain tops, partly hidden behind them
    n_high = 0 if count < 3 else (1 if count < 6 else 2)
    roles = ["hero"] + ["high"] * n_high + ["band"] * (count - 1 - n_high)
    placed, made = [], []
    for i, role in enumerate(roles):
        cseed = seed * 17 + i
        for attempt in range(90):
            shrink = 1.0 if attempt < 12 else (0.8 if attempt < 30 else (0.62 if attempt < 55 else 0.45))
            if role == "hero":
                d = distance * rng.uniform(1.0, 1.15)
                frac, tower = rng.uniform(0.3, 0.36), rng.uniform(0.55, 0.85)
            elif role == "high":                            # the first a little bigger, the next small and flat
                d = distance * rng.uniform(1.0, 1.5)
                frac = rng.uniform(0.075, 0.095) if roles.index("high") == i else rng.uniform(0.04, 0.055)
                tower = 0.0
            else:
                d = distance * rng.uniform(1.35, 1.9)
                frac, tower = rng.uniform(0.05, 0.11), rng.uniform(0.0, 0.25)
            rel = frac * hfov * shrink                  # width / distance
            w = d * rel
            height_deg = math.degrees(math.atan(max(c.z + r for c, r in lobes(1.0, cseed, tower)) * rel))
            sx = rng.uniform(0.12, 0.88) if role != "band" else rng.uniform(0.04, 0.96)
            top = math.degrees(math.asin(max(-1.0, min(1.0, direction(sx, 1.0).z)))) - height_deg - 1.0
            low = max(0.8, math.degrees(math.asin(max(-1.0, min(1.0, direction(sx, 0.0).z)))) + 2.0)
            flat = direction(sx, 0.5)
            az = math.atan2(flat.y, flat.x)
            ridge = skyline(az, 0.5 * rel, d)                   # only the mountains in front of it
            if role == "hero":                          # its foot hidden behind the mountain tops
                if ridge > 0.0:
                    low = max(low, ridge - 0.25 * height_deg)
                lo_el, hi_el = low, low + 0.1 * height_deg
            elif role == "band":                        # sitting on the tops, partly behind them
                if ridge > 0.0:
                    low = max(low, ridge - 0.4 * height_deg)
                lo_el, hi_el = low, low + 0.35 * height_deg
            else:                                       # high up in the frame
                lo_el, hi_el = max(low, top - 7.0), top
            if top < lo_el:
                if attempt < 80:
                    continue                            # does not fit the frame: try another place or smaller
                top = lo_el
            el = rng.uniform(lo_el, max(lo_el, min(top, hi_el)))
            c = origin + Vector((math.cos(az) * d, math.sin(az) * d, math.tan(math.radians(el)) * d))
            gap = 0.5 * rel / hfov + (0.025 if role != "band" else 0.0)
            if role == "band" or attempt >= 50:
                gap *= 0.6                              # the band may crowd; and rather close than a cloud short
            if attempt < 80 and any(abs(sx - qx) < gap + qg and (role != "band" or qr != "band")
                                    for qx, qg, qr in placed if qr == role or "hero" in (qr, role)):
                continue                                # the last tries take any free-ish spot: never a cloud short
            hw = max(c_.z + r for c_, r in lobes(1.0, cseed, tower)) * w          # its height in metres
            if cam is not None and attempt < 65 and any(
                    old._overlaps(scene, cam, c + Vector((0, 0, z)), w * 0.62, boxes)
                    for z in (w * 0.2, max(w * 0.2, hw - w * 0.42))):            # a tall tower: its top too
                continue
            placed.append((sx, gap, role))
            ob = add_cloud(context, c, w, seed=cseed, tower=tower, yaw=az - math.pi / 2,
                           name="Cloud Hero" if role == "hero" else "Cloud")
            if role == "high" and roles.index("high") != i:
                ob.scale.z = w * 0.62                    # a flattened little one
            if role == "hero":                          # its small side puffs need a finer grid to stay round
                mod_input(ob.modifiers[MOD], "Detail", 0.011)
            mark_auto(ob)
            made.append(ob)
            break
    if cam is not None and made:
        far = max((o.location - origin).length + o.scale.x for o in made)
        fit_clip(cam, far * 1.2)
    return made


def fit_clip(cam, far):
    """Let the camera see as far as 'far' without wrecking depth precision for what is near."""
    cd = cam.data
    cd.clip_end = max(cd.clip_end, far)
    cd.clip_start = max(cd.clip_start, cd.clip_end / 99000.0)
