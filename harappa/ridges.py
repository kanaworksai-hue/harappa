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


def build(context, ground, seed=0, layers=3):
    """(Re)build the ridge layers around the ground object."""
    scene = context.scene
    remove(scene)
    size = max(ground.dimensions.x, ground.dimensions.y, 1.0)
    c = ground.matrix_world.translation
    made = []
    seg = 360
    for k, (dist, elev, rough, sharp) in enumerate(LAYERS[:max(0, layers)]):
        rad = size * dist
        peak = rad * math.tan(math.radians(elev))
        foot = -size * 0.2
        me = bpy.data.meshes.new(f"Ridge {k + 1}")
        bm = bmesh.new()
        lo, mid, hi = [], [], []
        hs = []
        for i in range(seg):
            a = i / seg * math.tau
            h = _profile(a, k, seed, rough, sharp)
            x, y = c.x + math.cos(a) * rad, c.y + math.sin(a) * rad
            lo.append(bm.verts.new((x, y, c.z + foot)))
            mid.append(bm.verts.new((x, y, c.z + peak * h * 0.35)))
            hi.append(bm.verts.new((x, y, c.z + peak * h)))
            hs.append(h)
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
        scene.collection.objects.link(ob)
        ob[TAG] = True
        ob["hrp_layer"] = float(k)
        ob["hrp_ridge_top"] = float(elev)
        ob.visible_shadow = False
        ob.hide_select = False
        made.append(ob)
    cam = scene.camera
    if cam is not None and made:
        cam.data.clip_end = max(cam.data.clip_end, size * LAYERS[len(made) - 1][0] * 1.3)
    return made
