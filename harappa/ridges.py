# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Distant ridges: flat painted silhouettes in layers behind the far hills.

Near ones are round and keep some of the land's colour, far ones are taller, sharper, bluer and paler; each fades
towards the haze colour at its foot, which leaves a band of 'air' between the layers. Every ridge is its own
object: move, scale or delete it freely."""
import math

import bmesh
import bpy
from mathutils import Vector, noise

from . import shading

TAG = "hrp_ridge"
# layer: distance (x ground size), peak elevation seen from the middle (degrees), roughness, sharpness
LAYERS = ((6.6, 5.2, 3.4, 0.0), (8.2, 7.6, 5.0, 0.6), (10.0, 10.5, 6.5, 1.0))


def ridges_of(scene):
    return sorted((o for o in scene.objects if o.get(TAG)), key=lambda o: o.get("hrp_layer", 0))


def remove(scene):
    for ob in ridges_of(scene):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def _profile(a, layer, seed, rough, sharp):
    """Height 0..1 of the ridge line at angle a."""
    p = Vector((math.cos(a), math.sin(a), 0.0))
    off = Vector((seed * 2.3 + layer * 11.7, seed * 0.9 - layer * 5.1, layer * 3.3))
    h = noise.noise(p * rough + off) * 0.5 + 0.5
    h = h * 0.7 + (noise.noise(p * rough * 2.7 + off * 1.7) * 0.5 + 0.5) * 0.3
    if sharp > 0.0:                                        # ridged detail: peaks instead of domes
        r = 1.0 - abs(noise.noise(p * rough * 3.2 + off * 0.6))
        h = h * (1.0 - 0.3 * sharp) + (r * r) * 0.3 * sharp * (0.4 + 0.6 * h)
    big = noise.noise(p * 0.9 + off * 0.3) * 0.5 + 0.5      # one side of the panorama stands taller
    h = max(0.0, min(1.0, (h - 0.2) / 0.6)) ** 1.3          # full range: real valleys between the tops
    return max(0.0, min(1.0, 0.1 + 0.9 * h * (0.45 + 0.55 * big)))


def collection(scene):
    """Scenery (ridges) lives in its own collection, next to the clouds."""
    for c in scene.collection.children_recursive:
        if c.get("hrp_scenery_coll"):
            return c
    c = bpy.data.collections.new("Harappa Scenery")
    c["hrp_scenery_coll"] = True
    scene.collection.children.link(c)
    return c


def build(context, ground=None, seed=0, layers=3):
    """(Re)build the ridge layers around the ground object (or around the world origin, 40 m wide).

    The meshes are built for a ground one unit wide; the objects sit at the ground's centre and carry the
    ground's size as their scale. So they turn and scale about the middle of the scene, and their painted
    shapes look the same around a small garden and a huge landscape."""
    scene = context.scene
    remove(scene)
    scene["hrp_ridge_layout"] = [int(layers), int(seed)]
    if ground is not None:
        size = max(ground.dimensions.x, ground.dimensions.y, 1.0)
        c = ground.matrix_world.translation.copy()
    else:
        size, c = 40.0, Vector((0.0, 0.0, 0.0))
    made = []
    seg = 720
    for k, (dist, elev, rough, sharp) in enumerate(LAYERS[:max(0, min(layers, len(LAYERS)))]):
        peak = dist * math.tan(math.radians(elev))
        foot = -0.2
        me = bpy.data.meshes.new(f"Ridge {k + 1}")
        bm = bmesh.new()
        lo, mid, hi = [], [], []
        for i in range(seg):
            a = i / seg * math.tau
            h = _profile(a, k, seed, rough, sharp)
            if sharp > 0.0:                                  # fine breaks along the crest of the far layers
                p = Vector((math.cos(a), math.sin(a), 0.0)) * (rough * 9.0)
                h = max(0.0, h + noise.noise(p + Vector((seed * 1.3, k * 7.7, 0.0))) * 0.035 * sharp)
            x, y = math.cos(a) * dist, math.sin(a) * dist
            lo.append(bm.verts.new((x, y, foot)))
            mid.append(bm.verts.new((x, y, peak * h * 0.35)))
            hi.append(bm.verts.new((x, y, peak * h)))
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((lo[i], lo[j], mid[j], mid[i]))        # facing the middle
            bm.faces.new((mid[i], mid[j], hi[j], hi[i]))
        bm.to_mesh(me)
        bm.free()
        t = me.attributes.new("hrp_t", "FLOAT", "POINT")           # 0 foot .. 1 crest of this spot
        for i in range(seg):
            t.data[i * 3].value, t.data[i * 3 + 1].value, t.data[i * 3 + 2].value = 0.0, 0.35, 1.0
        me.materials.append(shading.ridge_material())
        ob = bpy.data.objects.new(me.name, me)
        collection(scene).objects.link(ob)
        ob.location = c
        ob.scale = (size, size, size)
        ob[TAG] = True
        ob["hrp_layer"] = float(k)
        ob["hrp_ridge_top"] = float(elev)
        ob.visible_shadow = False
        made.append(ob)
    cam = scene.camera
    if cam is not None and cam.type == "CAMERA" and made:
        from .cumulus import fit_clip
        fit_clip(cam, size * LAYERS[len(made) - 1][0] * 1.3)
    return made
