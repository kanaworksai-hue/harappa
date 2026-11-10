# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Painted cumulus clouds: the same camera-facing card trick as the trees (the reference artist builds
clouds this way too), on flat-bottomed clusters of spheres placed far out in front of the camera."""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import scatter, shading, tree
from .util import mod_input

CLOUDS = "Anime Clouds"


def cloud_card(scene):
    from . import assets
    nm = "HRP Cloud Card"
    me = bpy.data.meshes.get(nm) or assets.card().copy()
    me.name = nm
    return tree.asset_object(scene, nm, me, shading.cloud_material())


def _tree_boxes(scene, cam):
    """Projected canopy points (0..1 screen space) of every tree, so clouds and the moon keep clear of them.
    Points, not bounding boxes: a box around a round crown covers a lot of empty sky."""
    if cam is None:
        return []
    from bpy_extras.object_utils import world_to_camera_view
    out = []
    for ob in scene.objects:
        if not ob.get("hrp_canopy") or ob.get("hrp_clouds") or ob.type != "MESH":
            continue
        mw = ob.matrix_world
        vs = ob.data.vertices
        step = max(1, len(vs) // 400)
        pts = []
        for i in range(0, len(vs), step):
            q = world_to_camera_view(scene, cam, mw @ vs[i].co)
            if q.z > 0:
                pts.append((q.x, q.y))
        if pts:
            out.append(pts)
    return out


def _in_trees(sx, sy, trees, pad=0.06):
    return any(abs(sx - x) < pad and abs(sy - y) < pad * 1.78 for pts in trees for x, y in pts)


def _overlaps(scene, cam, c, w, trees):
    if cam is None:
        return False
    from bpy_extras.object_utils import world_to_camera_view
    side = (cam.matrix_world.to_quaternion() @ Vector((1, 0, 0))) * (w * 0.8)    # real extent incl. puffs
    a = world_to_camera_view(scene, cam, c - side - Vector((0, 0, w * 0.05)))
    b = world_to_camera_view(scene, cam, c + side + Vector((0, 0, w * 0.6)))
    x0, x1 = min(a.x, b.x), max(a.x, b.x)
    y0, y1 = min(a.y, b.y), max(a.y, b.y)
    if x0 < 0.03 or x1 > 0.97:              # keep the whole cloud inside the frame sideways too
        return True
    pad = 0.05                              # leaf cards stick out past the canopy mesh
    return any(x0 - pad < x < x1 + pad and y0 - pad * 1.78 < y < y1 + pad * 1.78 for pts in trees for x, y in pts)


def _cloud_cluster(bm, rng, centre, width, tall=False):
    """5-10 spheres along a line, biggest in the middle, cut flat at the base; a tall one stacks up."""
    if tall:
        for k in range(rng.randint(3, 5)):
            t = k / 4.0
            r = width * (0.4 - 0.2 * t) * rng.uniform(0.85, 1.15)
            x = rng.uniform(-0.2, 0.2) * width
            z = centre.z + width * (0.2 + 0.55 * t)
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0,
                                       matrix=Matrix.Translation(Vector((centre.x + x, centre.y, z)))
                                       @ Matrix.Diagonal((r, r * 0.85, r * 0.9, 1)))
    n = rng.randint(5, 10)
    base_z = centre.z
    for i in range(n):
        t = (i + 0.5) / n - 0.5
        r = width * (0.16 + 0.22 * (1 - abs(t) * 1.6) ** 1.2) * rng.uniform(0.75, 1.2)
        x = t * width * 0.95 + rng.uniform(-0.04, 0.04) * width
        y = rng.uniform(-0.12, 0.12) * width
        z = base_z + r * rng.uniform(0.35, 0.75)
        m = Matrix.Translation(centre + Vector((x, y, z - base_z))) @ Matrix.Diagonal((r, r * 0.8, r * 0.85, 1))
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0, matrix=m)
    # a few smaller puffs on top for the cauliflower crown
    for i in range(rng.randint(3, 4)):              # rounded top: a few big lobes sunk into the body
        r = width * rng.uniform(0.13, 0.2)
        x = rng.uniform(-0.28, 0.28) * width
        z = base_z + width * rng.uniform(0.2, 0.3)
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0,
                                   matrix=Matrix.Translation(centre + Vector((x, 0, z - base_z)))
                                   @ Matrix.Diagonal((r, r, r, 1)))
    return base_z


def add_clouds(context, count=4, seed=0, distance=320.0):
    """(Re)build the cloud layer in front of the scene camera."""
    scene = context.scene
    rng = random.Random(seed * 131 + 7)
    context.view_layer.update()          # a camera made a moment ago has a stale matrix_world
    cam = scene.camera
    if cam is not None:
        origin = cam.matrix_world.translation.copy()
        fwd = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        yaw = math.atan2(fwd.y, fwd.x)
    else:
        origin, yaw = Vector((0, 0, 0)), math.pi / 2
    ob = bpy.data.objects.get(CLOUDS)
    me = bpy.data.meshes.new(CLOUDS)
    bm = bmesh.new()
    flats = []
    tall_i = rng.randrange(count) if count else -1
    hero_i = (tall_i + 1) % count if count else -1          # one big hero cumulus per layout
    boxes = _tree_boxes(scene, cam)
    pitch = 0.0
    vfov = 30.0
    if cam is not None:
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, fwd.z))))
        ren = scene.render
        aspect = (ren.resolution_y * ren.pixel_aspect_y) / max(1.0, ren.resolution_x * ren.pixel_aspect_x)
        vfov = math.degrees(cam.data.angle) * (aspect if cam.data.sensor_fit != "VERTICAL" else 1.0)
    hfov = math.degrees(cam.data.angle) if cam is not None else 80.0
    placed = []
    for i in range(count):
        for _try in range(60):
            if _try < 20:                     # first try the even layout, then search the whole free sky
                a = yaw + ((i + rng.uniform(0.15, 0.85)) / count - 0.5) * math.radians(min(80.0, hfov * 0.9))
            else:
                a = yaw + math.radians(rng.uniform(-0.45, 0.45) * hfov)
            d = distance * rng.uniform(0.6, 1.8)
            w = d * rng.uniform(0.08, 0.26) * (1.5 if i == hero_i else 1.0)
            if _try >= 40:
                w *= 0.7
            top = pitch + vfov * 0.5 - math.degrees(math.atan(w * 0.75 / d)) - 1.0     # whole cloud in frame
            el_deg = pitch + 6.0 + rng.uniform(0.0, 1.0) ** 1.2 * 7.0
            if _try >= 20:
                el_deg = rng.uniform(pitch + 4.0, top)
            elev = math.radians(max(1.5, min(el_deg, top)))
            c = origin + Vector((math.cos(a) * d, math.sin(a) * d, math.tan(elev) * d))
            near_other = any((c - q).length < (w + wq) * 0.6 for q, wq in placed)
            if cam is not None and not near_other:          # no stacking: keep a sideways gap on screen
                from bpy_extras.object_utils import world_to_camera_view
                sx = world_to_camera_view(scene, cam, c).x
                near_other = any(abs(sx - world_to_camera_view(scene, cam, q).x) < 0.16 for q, _w in placed)
            if not near_other and not _overlaps(scene, cam, c, w, boxes):
                break
        else:
            continue                        # no clean spot for this cloud: leave it out
        placed.append((c, w))
        flats.append((_cloud_cluster(bm, rng, c, w, tall=(i == tall_i and i != hero_i)), c, w))
    # flatten each cloud's underside, remember which cloud each vertex belongs to
    owner = []
    for v in bm.verts:
        k = min(range(len(flats)), key=lambda i: (v.co.xy - flats[i][1].xy).length)
        best = flats[k]
        if v.co.z < best[0]:
            v.co.z = best[0] + (v.co.z - best[0]) * 0.12
        owner.append(k)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    # per-cloud centre and half size: the shader computes a smooth normal per pixel from them
    lo = {}
    hi = {}
    for v, k in zip(me.vertices, owner):
        a, b = lo.get(k), hi.get(k)
        lo[k] = v.co.copy() if a is None else Vector(map(min, a, v.co))
        hi[k] = v.co.copy() if b is None else Vector(map(max, b, v.co))
    ac = me.attributes.new("hrp_cc", "FLOAT_VECTOR", "POINT")
    ah = me.attributes.new("hrp_chalf", "FLOAT_VECTOR", "POINT")
    for i, k in enumerate(owner):
        c = (lo[k] + hi[k]) * 0.5
        c.z = lo[k].z + (hi[k].z - lo[k].z) * 0.2           # centre low: only the flat base shades as underside
        ac.data[i].vector = c
        ah.data[i].vector = (hi[k] - lo[k]) * 0.5
    if ob is None:
        ob = bpy.data.objects.new(CLOUDS, me)
        scene.collection.objects.link(ob)
    else:
        old = ob.data
        ob.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
    ob.visible_shadow = False
    ob["hrp_clouds"] = True
    ob["hrp_cloud_args"] = [count, seed, distance]
    mod = ob.modifiers.get("Harappa Clouds") or ob.modifiers.new("Harappa Clouds", "NODES")
    mod.node_group = scatter.foliage_group()
    area = sum(p.area for p in me.polygons) or 1.0
    avg_w = (sum(f[2] for f in flats) / len(flats)) if flats else distance * 0.15
    card = avg_w * 0.22
    mod_input(mod, "Card", cloud_card(scene))
    mod_input(mod, "Leaf Size", card)
    mod_input(mod, "Size Random", 0.5)
    mod_input(mod, "Density", min(5000.0, 2.2 / (card * card)))
    mod_input(mod, "Inflate", card * 0.3)
    mod_input(mod, "Roundness", 0.12)
    mod_input(mod, "Blossom", 0.0)
    mod_input(mod, "Wind Strength", 0.0)
    mod_input(mod, "Fill Inside", True)
    mod_input(mod, "Fill Material", shading.cloud_fill_material())
    mod_input(mod, "Seed", seed)
    if cam is not None:
        cam.data.clip_end = max(cam.data.clip_end, distance * 2.5)
    return ob


def far_hills(context, ground, seed=0):
    """A low ring of hills beyond the meadow so the horizon isn't one smooth edge (hazed by distance)."""
    from mathutils import noise
    scene = context.scene
    size = max(ground.dimensions.x, ground.dimensions.y, 1.0)
    c = ground.matrix_world.translation
    r0, r1 = size * 0.7, size * 6.0
    me = bpy.data.meshes.new("Far Hills")
    bm = bmesh.new()
    seg_a, seg_r = 160, 14
    rows = []
    off = Vector((seed * 3.1, seed * 1.7, 0))
    for j in range(seg_r + 1):
        t = j / seg_r
        rad = r0 + (r1 - r0) * t ** 1.4
        row = []
        for i in range(seg_a):
            a = i / seg_a * math.tau
            p = Vector((math.cos(a), math.sin(a), 0))
            h = (noise.noise(p * 2.2 + off) * 0.5 + 0.5) * size * 0.22 + (noise.noise(p * 7.0 + off) * 0.5 + 0.5) * size * 0.06
            h *= min(1.0, t * 3.0)                        # meet the meadow edge low
            row.append(bm.verts.new((c.x + p.x * rad, c.y + p.y * rad, c.z - size * 0.06 + h * (1.0 - 0.4 * t))))
        rows.append(row)
    for j in range(seg_r):
        for i in range(seg_a):
            # wound so the faces look up: the fringe grass stands along the face normal and is lit by it
            bm.faces.new((rows[j][i], rows[j + 1][i], rows[j + 1][(i + 1) % seg_a], rows[j][(i + 1) % seg_a]))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.get("Far Hills")
    if ob is None:
        ob = bpy.data.objects.new("Far Hills", me)
        scene.collection.objects.link(ob)
    else:
        old = ob.data
        ob.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
    from . import build
    attr = build.ensure_mask(me)             # all grass-coloured (no dirt) ...
    zs = [v.co.z for v in me.vertices]
    zlo, zhi = min(zs), max(zs)
    crest = me.attributes.new("hrp_crest", "FLOAT", "POINT")
    for i, z in enumerate(zs):              # ... grass blades only along the crests, so the horizon breaks up
        crest.data[i].value = max(0.0, min(1.0, ((z - zlo) / max(zhi - zlo, 1e-6) - 0.55) / 0.2))
    me.materials.append(shading.ground_material())
    ob.visible_shadow = False
    ob["hrp_far_hills"] = True
    ob["hrp_haze_boost"] = 1.0
    mod = ob.modifiers.get("Harappa Fringe") or ob.modifiers.new("Harappa Fringe", "NODES")   # not a meadow
    mod.node_group = scatter.grass_group()
    mod_input(mod, "Tuft", tree.tuft_object(scene))
    mod_input(mod, "Mask Attribute", "hrp_crest")
    mod_input(mod, "Density", 3.0)
    mod_input(mod, "Height", size * 0.012)
    mod_input(mod, "Width", 1.4)
    mod_input(mod, "LOD Distance", 0.0)
    mod_input(mod, "Wind Strength", 0.1)
    return ob
