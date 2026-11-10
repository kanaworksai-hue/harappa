# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render settings, the anime sky world and the key sun."""
import math

import bpy
from mathutils import Euler, Vector

from . import shading
from .util import BUILDING, G, only, srgb, stamp

WORLD = "HRP Sky"
SUN = shading.SUN
SKY_VER = 8


def setup_render(scene):
    prev = scene.get("hrp_prev")
    if prev is None:
        scene["hrp_prev"] = {
            "engine": scene.render.engine,
            "view": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
            "world": scene.world.name if scene.world else "",
        }
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
    except TypeError:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    ee = scene.eevee
    for attr, val in (("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8),
                      ("fast_gi_distance", 1.0), ("taa_render_samples", 16)):   # flat cel colours: 16 is plenty
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except (TypeError, AttributeError):
                pass


def sky_world(scene, zenith="#4E9BD6", horizon="#DCEEF0", ground="#C9DFD8"):
    world = bpy.data.worlds.get(WORLD)
    if world is None or world.get("hrp_ver") != SKY_VER:
        if world is None:
            world = bpy.data.worlds.new(WORLD)
        world["hrp_ver"] = BUILDING
        world.use_nodes = True
        nt = world.node_tree
        nt.nodes.clear()
        g = G(nt)
        tc = g.n("ShaderNodeTexCoord", -900, 0)
        sep = g.n("ShaderNodeSeparateXYZ", -700, 0)
        g.link(tc, "Generated", sep, "Vector")
        mr = g.maprange(-600, 0, g.out(sep, "Z"), -0.03, 0.5, 0.0, 1.0)
        ramp = g.n("ShaderNodeValToRGB", -400, 0, label="sky ramp")
        g.link(mr, "Result", ramp, "Fac")
        cr = ramp.color_ramp
        cr.interpolation = "EASE"
        cr.elements[0].position = 0.0
        cr.elements[1].position = 1.0
        cr.elements.new(0.06)
        # night: stars + moon, scaled by two values the season sets
        nd = g.vmath("NORMALIZE", -700, -300, g.out(tc, "Generated"))
        vs = g.n("ShaderNodeTexVoronoi", -500, -300, voronoi_dimensions="3D")
        g.set(vs, "Scale", 160.0)
        g.link(nd, 0, vs, "Vector")
        st = g.maprange(-300, -300, g.out(vs, "Distance"), 0.12, 0.05)
        sc_ = g.n("ShaderNodeSeparateColor", -300, -450)
        g.link(vs, "Color", sc_, "Color")
        keep = g.math("GREATER_THAN", -150, -450, g.out(sc_, "Red"), 0.55)
        up = g.maprange(-150, -600, g.out(sep, "Z"), 0.04, 0.3)
        s1 = g.math("MULTIPLY", 0, -300, g.out(st, "Result"), g.out(keep))
        s2 = g.math("MULTIPLY", 150, -350, g.out(s1), g.out(up, "Result"))
        sv = g.n("ShaderNodeValue", 0, -500, label="sky stars")
        s3 = g.math("MULTIPLY", 300, -350, g.out(s2), g.out(sv))
        md = g.n("ShaderNodeCombineXYZ", -500, -750, label="moon dir")
        dt = g.vmath("DOT_PRODUCT", -300, -700, g.out(nd), g.out(md))
        disc = g.maprange(-150, -700, g.out(dt, "Value"), 0.99935, 0.99955)
        glow = g.maprange(-150, -850, g.out(dt, "Value"), 0.982, 1.0)
        gl2 = g.math("POWER", 0, -850, g.out(glow, "Result"), 3.0)
        mv = g.n("ShaderNodeValue", 0, -1000, label="sky moon")
        md2 = g.math("MULTIPLY", 300, -800, g.out(disc, "Result"), g.out(mv))
        lights = g.math("ADD", 450, -500, g.out(s3), g.out(md2))
        hal = g.math("MULTIPLY", 300, -950, g.out(g.math("MULTIPLY", 150, -950, g.out(gl2), 0.35)),
                     g.out(mv))
        sky0 = g.mix(-200, 450, "ADD", fac=g.out(hal), a=g.out(ramp, "Color"), b=(0.35, 0.44, 0.66, 1.0))
        sky = g.mix(-200, 300, "ADD", fac=g.out(lights), a=g.mixout(sky0), b=(1.0, 0.97, 0.88, 1.0))
        bg = g.n("ShaderNodeBackground", -200, 100)
        g.links.new(g.mixout(sky), bg.inputs["Color"])
        amb = g.n("ShaderNodeBackground", -200, -100, label="ambient")
        amb.inputs["Strength"].default_value = 0.0
        lp = g.n("ShaderNodeLightPath", -200, 300)
        ms = g.n("ShaderNodeMixShader", 50, 0)
        g.link(lp, "Is Camera Ray", ms, "Fac")
        g.link(amb, 0, ms, ("Shader", 0))
        g.link(bg, 0, ms, ("Shader", 1))
        out = g.n("ShaderNodeOutputWorld", 250, 0)
        g.link(ms, 0, out, "Surface")
        stamp(world, SKY_VER)
    set_sky_colours(world, zenith, horizon, ground)
    scene.world = world
    return world


def set_night(world, stars=0.0, moon=0.0, camera=None):
    nt = world.node_tree
    for key, val in (("sky stars", stars), ("sky moon", moon)):
        n = nt.nodes.get(key)
        if n is not None:
            only(n.outputs).default_value = val
    md = nt.nodes.get("moon dir")
    bpy.context.view_layer.update()
    if md is not None:
        d = _moon_direction(camera)
        for c, v in zip("XYZ", d):
            md.inputs[c].default_value = v


def _moon_direction(camera):
    """A spot in open sky in the upper part of the frame, clear of tree crowns."""
    scene = bpy.context.scene
    if camera is None:
        return Vector((0.0, 0.9, 0.42)).normalized()
    from .clouds import _tree_boxes
    boxes = _tree_boxes(scene, camera)
    frame = camera.data.view_frame(scene=scene)          # tr, br, bl, tl in camera space
    tr, br, bl, tl = frame
    best = None
    from bpy_extras.object_utils import world_to_camera_view
    cloud_pts = []
    cl = bpy.data.objects.get("Anime Clouds")
    if cl is not None:
        mw = cl.matrix_world
        vs = cl.data.vertices
        for i in range(0, len(vs), 7):
            q = world_to_camera_view(scene, camera, mw @ vs[i].co)
            if q.z > 0:
                cloud_pts.append((q.x, q.y))
    for sy in (0.84, 0.74, 0.92):
        for sx in (0.62, 0.38, 0.75, 0.25, 0.5, 0.85, 0.15):
            from .clouds import _in_trees
            if _in_trees(sx, sy, boxes):
                continue
            if any((sx - x) ** 2 + ((sy - y) * 0.56) ** 2 < 0.07 ** 2 for x, y in cloud_pts):
                continue
            best = (sx, sy)
            break
        if best:
            break
    sx, sy = best or (0.62, 0.86)
    top = tl.lerp(tr, sx)
    bot = bl.lerp(br, sx)
    p = bot.lerp(top, sy)
    return (camera.matrix_world.to_quaternion() @ p).normalized()


def set_sky_colours(world, zenith, horizon, ground):
    ramp = world.node_tree.nodes.get("sky ramp")
    if ramp is None:
        return
    els = sorted(ramp.color_ramp.elements, key=lambda e: e.position)
    for el, hx in zip(els, (ground, horizon, zenith)):
        el.color = (*srgb(hx), 1.0)


def key_sun(scene, camera=None, elevation=42.0, side=-55.0, colour="#FFF6E6", strength=4.0):
    """A sun lighting the scene from in front-left of the camera (3/4 light)."""
    sun = bpy.data.objects.get(SUN)
    if sun is None or sun.type != "LIGHT":
        data = bpy.data.lights.new(SUN, "SUN")
        sun = bpy.data.objects.new(SUN, data)
        scene.collection.objects.link(sun)
    elif sun.name not in scene.objects:
        scene.collection.objects.link(sun)
    sun.data.energy = strength
    sun.data.color = srgb(colour)
    sun.data.angle = math.radians(2.0)
    cam_yaw = 0.0
    bpy.context.view_layer.update()
    if camera is not None:
        fwd = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        cam_yaw = math.degrees(math.atan2(fwd.y, fwd.x))
    # direction the light travels: from the light towards the scene
    yaw = math.radians(cam_yaw - 180 - side)
    el = math.radians(elevation)
    to_light = Vector((math.cos(yaw) * math.cos(el), math.sin(yaw) * math.cos(el), math.sin(el)))
    sun.rotation_euler = to_light.to_track_quat("Z", "Y").to_euler()
    shading.drive_light_scale(sun)
    return sun
