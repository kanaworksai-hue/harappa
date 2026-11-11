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
SKY_VER = 10


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
        nd = g.vmath("NORMALIZE", -700, -300, g.out(tc, "Generated"))
        sep = g.n("ShaderNodeSeparateXYZ", -700, 0)
        g.links.new(g.out(nd), sep.inputs["Vector"])
        # the gradient spans what the camera sees: 'sky top' is the height (z of the view direction) of the
        # top edge of the frame, so the zenith colour reaches the picture instead of staying overhead
        top = g.n("ShaderNodeValue", -800, 150, label="sky top")
        g.out(top).default_value = 0.5
        mr = g.maprange(-600, 0, g.out(sep, "Z"), -0.03, g.out(top), 0.0, 1.0)
        ramp = g.n("ShaderNodeValToRGB", -400, 0, label="sky ramp")
        g.link(mr, "Result", ramp, "Fac")
        cr = ramp.color_ramp
        cr.interpolation = "EASE"
        cr.elements[0].position = 0.0
        cr.elements[1].position = 1.0
        cr.elements.new(0.06)
        cr.elements.new(0.5)
        # night: stars + moon, scaled by two values the season sets
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
        glow = g.maprange(-150, -850, g.out(dt, "Value"), 0.955, 1.0)          # a wide, soft halo round the moon
        gl2 = g.math("POWER", 0, -850, g.out(glow, "Result"), 3.0)
        mv = g.n("ShaderNodeValue", 0, -1000, label="sky moon")
        md2 = g.math("MULTIPLY", 300, -800, g.out(disc, "Result"), g.out(mv))
        lights = g.math("ADD", 450, -500, g.out(s3), g.out(md2))
        hal = g.math("MULTIPLY", 300, -950, g.out(g.math("MULTIPLY", 150, -950, g.out(gl2), 0.55)),
                     g.out(mv))
        base = _sky_day(g, nd, sep, g.out(ramp, "Color"))
        sky0 = g.mix(-200, 450, "ADD", fac=g.out(hal), a=base, b=(0.35, 0.44, 0.66, 1.0))
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
    sun = bpy.data.objects.get(SUN)
    if sun is not None:
        drive_sun(world, sun)
    return world


def _sky_day(g, nd, sep, sky):
    """High cirrus, the sun's glow and its disc, painted into the sky colour. No geometry: nothing to sort,
    nothing to clip, and they cost nothing to render."""
    x, y = -900, 900
    # cirrus: the view direction projected on a plane overhead (so the streaks converge towards the horizon),
    # a stretched, warped noise cut into wisps, in patches
    z = g.math("MAXIMUM", x, y, g.out(sep, "Z"), 0.05)
    uv = g.vmath("DIVIDE", x + 160, y, g.out(nd), g.out(z))
    ang = g.n("ShaderNodeVectorRotate", x + 320, y, label="cirrus angle", rotation_type="Z_AXIS")
    g.links.new(g.out(uv), g.inp(ang, "Vector"))
    g.set(ang, "Angle", 0.5)
    st = g.vmath("MULTIPLY", x + 480, y, g.out(ang), (0.16, 1.5, 0.0))
    n1 = g.n("ShaderNodeTexNoise", x + 640, y, noise_dimensions="3D")
    g.links.new(g.out(st), g.inp(n1, "Vector"))
    for k, v in (("Scale", 1.6), ("Detail", 5.0), ("Roughness", 0.62), ("Distortion", 1.4)):
        g.set(n1, k, v)
    wisps = g.maprange(x + 800, y, g.out(n1, "Fac"), 0.5, 0.74, smooth=True)
    n2 = g.n("ShaderNodeTexNoise", x + 640, y - 260, noise_dimensions="3D")
    g.links.new(g.out(ang), g.inp(n2, "Vector"))
    for k, v in (("Scale", 0.55), ("Detail", 1.0), ("Roughness", 0.5), ("Distortion", 0.0)):
        g.set(n2, k, v)
    patch = g.maprange(x + 800, y - 260, g.out(n2, "Fac"), 0.42, 0.62, smooth=True)
    low = g.maprange(x + 800, y - 520, g.out(sep, "Z"), 0.03, 0.22, smooth=True)     # none on the horizon
    amt = g.n("ShaderNodeValue", x + 800, y + 160, label="sky cirrus")
    g.out(amt).default_value = 0.0
    m = g.math("MULTIPLY", x + 960, y, g.out(wisps, "Result"), g.out(patch, "Result"))
    m = g.math("MULTIPLY", x + 1100, y, g.out(m), g.out(low, "Result"))
    m = g.math("MULTIPLY", x + 1240, y, g.out(m), g.out(amt), clamp=True)
    ccol = g.n("ShaderNodeRGB", x + 1100, y + 200, label="cirrus colour")
    g.out(ccol).default_value = (0.9, 0.95, 1.0, 1.0)
    sky = g.mixout(g.mix(x + 1400, y, "MIX", fac=g.out(m), a=sky, b=g.out(ccol)))
    # sun: a wide tinted glow, a tight bright one and the disc
    sd = g.n("ShaderNodeCombineXYZ", x, y - 800, label="sun dir")
    g.set(sd, "Z", 1.0)
    dt = g.vmath("DOT_PRODUCT", x + 160, y - 800, g.out(nd), g.out(sd))
    samt = g.n("ShaderNodeValue", x + 160, y - 1000, label="sky sun")
    g.out(samt).default_value = 0.0
    gcol = g.n("ShaderNodeRGB", x + 160, y - 1150, label="sun glow")
    g.out(gcol).default_value = (1.0, 0.95, 0.8, 1.0)
    wide = g.math("POWER", x + 480, y - 800, g.out(g.maprange(x + 320, y - 800, g.out(dt, "Value"), 0.55, 1.0),
                                                   "Result"), 2.5)
    tight = g.math("POWER", x + 480, y - 950, g.out(g.maprange(x + 320, y - 950, g.out(dt, "Value"), 0.94, 1.0),
                                                    "Result"), 5.0)
    glow = g.math("ADD", x + 640, y - 850, g.out(g.math("MULTIPLY", x + 560, y - 800, g.out(wide), 0.45)),
                  g.out(tight))
    glow = g.math("MULTIPLY", x + 800, y - 850, g.out(glow), g.out(samt), clamp=True)
    sky = g.mixout(g.mix(x + 1400, y - 400, "SCREEN", fac=g.out(glow), a=sky, b=g.out(gcol)))
    disc = g.maprange(x + 320, y - 1100, g.out(dt, "Value"), 0.99955, 0.9998)
    disc = g.math("MULTIPLY", x + 800, y - 1100, g.out(disc, "Result"),
                  g.out(g.math("MINIMUM", x + 640, y - 1100, g.out(samt), 1.0)))
    return g.mixout(g.mix(x + 1560, y - 400, "MIX", fac=g.out(disc), a=sky, b=(1.0, 0.98, 0.9, 1.0)))


def aim_sky(scene, world=None, update=True):
    """Fit the sky gradient to the camera: its top to the height of the frame's top edge. Called when the camera,
    the lens or the picture format changes (the add-on watches for that)."""
    world = world or scene.world
    if world is None or world.node_tree is None:
        return
    cam = scene.camera
    top = world.node_tree.nodes.get("sky top")
    if top is None:
        return
    v = 0.5
    if cam is not None and cam.type == "CAMERA":
        if update:
            bpy.context.view_layer.update()
        tr, _br, _bl, tl = cam.data.view_frame(scene=scene)
        d = (cam.matrix_world.to_quaternion() @ tl.lerp(tr, 0.5)).normalized()
        v = min(max(d.z * 1.08 + 0.03, 0.16), 1.0)
    sock = only(top.outputs)
    if abs(sock.default_value - v) > 1e-4:
        sock.default_value = v


def camera_signature(scene):
    """Everything the sky's fit depends on; when it changes the sky is fitted again."""
    cam = scene.camera
    if cam is None or cam.type != "CAMERA":
        return None
    r = scene.render
    cd = cam.data
    return (tuple(round(x, 4) for row in cam.matrix_world for x in row), round(cd.lens, 3), round(cd.sensor_width, 3),
            round(cd.shift_x, 4), round(cd.shift_y, 4), cd.sensor_fit, r.resolution_x, r.resolution_y)


def drive_sun(world, sun):
    """The sky's sun glow and the palette's sun direction follow the sun object by drivers."""
    sd = world.node_tree.nodes.get("sun dir") if world is not None and world.node_tree is not None else None
    if sd is not None:
        for axis, expr in shading.SUN_AXES:
            shading.drive_direction(sd.inputs[axis.upper()], sun, expr)
    shading.drive_sun_dir(sun)


def set_sky_extras(world, mid=None, glow="#FFF6DC", sun=0.6, cirrus=0.0, cirrus_colour="#EEF6FF"):
    """Mid-sky colour (None = between horizon and zenith), sun glow and cirrus of a season."""
    nt = world.node_tree
    ramp = nt.nodes.get("sky ramp")
    if ramp is not None and len(ramp.color_ramp.elements) == 4:
        els = sorted(ramp.color_ramp.elements, key=lambda e: e.position)
        if mid is None:
            els[2].color = [a * 0.45 + b * 0.55 for a, b in zip(els[1].color, els[3].color)]
        else:
            els[2].color = (*srgb(mid), 1.0)
    for key, val in (("sky sun", sun), ("sky cirrus", cirrus)):
        n = nt.nodes.get(key)
        if n is not None:
            only(n.outputs).default_value = val
    for key, hx in (("sun glow", glow), ("cirrus colour", cirrus_colour)):
        n = nt.nodes.get(key)
        if n is not None:
            only(n.outputs).default_value = (*srgb(hx), 1.0)


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
    for cl in scene.objects:                              # keep the moon out of the clouds
        if not cl.get("hrp_cloud"):
            continue
        mw = cl.matrix_world
        for v in cl.data.vertices:
            q = world_to_camera_view(scene, camera, mw @ v.co)
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
    cols = [(*srgb(hx), 1.0) for hx in (ground, horizon, zenith)]
    els[0].color, els[1].color, els[-1].color = cols
    if len(els) == 4:                                    # mid sky follows until a season sets its own
        els[2].color = [a * 0.45 + b * 0.55 for a, b in zip(cols[1], cols[2])]


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
    sun.rotation_mode = "XYZ"
    shading.drive_light_scale(sun)
    drive_sun(scene.world if scene.world is not None and scene.world.name == WORLD else None, sun)
    aim_sky(scene)
    return sun
