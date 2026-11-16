# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Weather and night life: rain (everywhere, or only under a rain cloud you place), overcast skies, a rainbow
after the rain, and fireflies that gather by the water at dusk and night.

* Rain: "Harappa Rain" object. Its location and Radius say where it rains (it follows the camera, or stays where
  Rain Here put it); streaks fall by scene time, slanted by the wind; raindrop rings appear on the water inside
  the rain area (palette water_rain x the HRP Rain Zone group). A circle shows the area in the viewport.
* Weather overlay (Clear / Cloudy / Rain / Storm) greys the sky, dims the sun and thickens the haze on top of
  the season, and is undone by choosing Clear.
* Rainbow: a translucent arc centred on the anti-solar point (42 degrees), as a real one.
* Fireflies: points over the meadow, most of them near water, drifting and blinking out of step; their glow
  follows the palette (none by day). A small compositor bloom is added when the scene has no compositor yet."""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from . import shading
from .util import G, fresh_group, iface, mod_input, only, sock, srgb

WEATHER_VER = 13
RAIN = "HRP Rain"
RAIN_OB = "Harappa Rain"
RAIN_MOD = "Harappa Rain"
MAT_RAIN = "HRP Rain"
RAINBOW_OB = "Harappa Rainbow"
MAT_RAINBOW = "HRP Rainbow"
FLIES = "HRP Fireflies"
FLIES_OB = "Harappa Fireflies"
FLIES_MOD = "Harappa Fireflies"
MAT_FLY = "HRP Firefly"
BLOOM = "HRP Bloom"

WEATHERS = {
    # name, description, sky grey, sun, haze add, rain, cloud grey
    "CLEAR": ("Clear Sky", "The season as it is", 0.0, 1.0, 0.0, 0.0, 0.0),
    "CLOUDY": ("Cloudy", "Grey sky, soft light", 0.45, 0.55, 0.12, 0.0, 0.35),
    "RAIN": ("Rain", "Rain streaks, raindrop rings on the water, a dim grey sky", 0.65, 0.35, 0.22, 0.6, 0.55),
    "STORM": ("Storm", "Heavy rain, strong wind in the grass and trees, a dark sky", 0.85, 0.2, 0.3, 1.0, 0.75),
}


# ----------------------------------------------------------------------------------------------
# rain
# ----------------------------------------------------------------------------------------------
def rain_material():
    mat, rebuilt = shading._fresh_mat(MAT_RAIN)
    if not rebuilt and mat.get("hrp_weather_ver") == WEATHER_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_weather_ver"] = WEATHER_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -800, 0)
    pal.node_tree = shading.palette_group()
    ry = g.n("ShaderNodeAttribute", -800, 300, attribute_name="hrp_ry", attribute_type="GEOMETRY")
    a = g.math("MULTIPLY", -400, 300, only(g.math("SINE", -500, 300, only(g.math("MULTIPLY", -550, 350, g.out(ry, "Fac"),
               math.pi).outputs)).outputs), 0.6)
    cd = g.n("ShaderNodeCameraData", -800, 500)
    near = g.maprange(-600, 500, g.out(cd, "View Distance"), 2.0, 6.0, smooth=True)   # no streaks across the lens
    a = g.math("MULTIPLY", -300, 400, g.out(a, 0), g.out(near, "Result"))
    col = g.mix(-300, 0, fac=0.5, a=g.out(pal, "water_foam"), b=g.out(pal, "haze_colour"))
    em = g.n("ShaderNodeEmission", -100, 0)
    g.links.new(g.mixout(col), em.inputs["Color"])
    tr = g.n("ShaderNodeBsdfTransparent", -100, 150)
    ms = g.n("ShaderNodeMixShader", 100, 100)
    g.link(a, 0, ms, "Factor")
    g.link(tr, 0, ms, ("Shader", 0))
    g.link(em, 0, ms, ("Shader", 1))
    out = g.n("ShaderNodeOutputMaterial", 300, 100)
    g.link(ms, 0, out, "Surface")
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    shading._done(mat, "rain_material")
    return mat


def rain_group():
    ng, rebuilt = fresh_group(RAIN, "GeometryNodeTree", WEATHER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Amount", "INPUT", "NodeSocketFloat", 0.6, 0.0, 1.0, "How hard it rains", "FACTOR")
    iface(ng, "Radius", "INPUT", "NodeSocketFloat", 25.0, 1.0, 1000.0, "Rain falls within this distance of the "
          "rain object", "DISTANCE")
    iface(ng, "Height", "INPUT", "NodeSocketFloat", 14.0, 1.0, 200.0, "Height the drops fall from", "DISTANCE")
    iface(ng, "Wind", "INPUT", "NodeSocketFloat", 0.25, -3.0, 3.0, "Slant of the rain (wind)")
    iface(ng, "Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1600, 0)
    go = g.n("NodeGroupOutput", 1200, 0)
    # count ~ area x amount, capped
    area = g.math("MULTIPLY", -1400, -200, only(g.math("MULTIPLY", -1500, -200, g.out(gi, "Radius"), g.out(gi, "Radius"))
                  .outputs), 3.1416)
    cnt = g.math("MULTIPLY", -1250, -200, g.out(area, 0), only(g.math("MULTIPLY", -1350, -300, g.out(gi, "Amount"), 9.0)
                 .outputs))
    cnt = g.math("MINIMUM", -1100, -200, g.out(cnt, 0), 40000.0)
    pts = g.n("GeometryNodePoints", -950, 0)
    g.link(cnt, 0, pts, "Count")
    # random position in a disc x height, falling with time (wrapped)
    r1 = g.n("FunctionNodeRandomValue", -1250, -500, data_type="FLOAT_VECTOR")
    r1.inputs["Max"].default_value = (1.0, 1.0, 1.0)
    rs = _xyz(g, -1100, -500, g.out(r1, "Value", "VECTOR"))
    rad = g.math("MULTIPLY", -950, -450, only(g.math("SQRT", -1000, -450, g.out(rs, "X")).outputs), g.out(gi, "Radius"))
    ang = g.math("MULTIPLY", -950, -600, g.out(rs, "Y"), 6.2832)
    tm = g.n("GeometryNodeInputSceneTime", -1250, -800)
    fall = g.math("FRACT", -850, -800, only(g.math("MULTIPLY_ADD", -950, -800, g.out(tm, "Seconds"),
                  only(g.math("DIVIDE", -1050, -900, 9.0, g.out(gi, "Height")).outputs), g.out(rs, "Z")).outputs))
    z = g.math("MULTIPLY", -700, -800, only(g.math("SUBTRACT", -800, -850, 1.0, g.out(fall, 0)).outputs),
               g.out(gi, "Height"))
    x = g.math("MULTIPLY_ADD", -700, -450, only(g.math("COSINE", -800, -450, g.out(ang, 0)).outputs), g.out(rad, 0),
               only(g.math("MULTIPLY", -800, -650, g.out(z, 0), g.out(gi, "Wind")).outputs))
    y = g.math("MULTIPLY", -700, -600, only(g.math("SINE", -800, -600, g.out(ang, 0)).outputs), g.out(rad, 0))
    p = g.n("ShaderNodeCombineXYZ", -550, -500)
    g.link(x, 0, p, "X")
    g.link(y, 0, p, "Y")
    g.link(z, 0, p, "Z")
    sp = g.n("GeometryNodeSetPosition", -400, 0)
    g.link(pts, 0, sp, "Geometry")
    g.link(p, 0, sp, "Position")
    # a streak: two crossed thin quads, 0.5 m long, leaning with the wind
    q1 = g.n("GeometryNodeMeshGrid", -550, -1100)
    q1.inputs["Size X"].default_value = 0.018
    q1.inputs["Size Y"].default_value = 0.6
    q1.inputs["Vertices X"].default_value = 2
    q1.inputs["Vertices Y"].default_value = 2
    quv = g.n("GeometryNodeStoreNamedAttribute", -450, -1000, data_type="FLOAT", domain="CORNER")
    g.link(q1, "Mesh", quv, "Geometry")
    quv.inputs["Name"].default_value = "hrp_ry"
    g.link(_xyz(g, -550, -1000, g.out(q1, "UV Map")), "Y", quv, "Value", bkind="VALUE")
    rot1 = g.n("GeometryNodeTransform", -400, -1100)
    g.link(quv, 0, rot1, "Geometry")
    rot1.inputs["Rotation"].default_value = (1.5708, 0.0, 0.0)
    rot2 = g.n("GeometryNodeTransform", -400, -1250)
    g.link(rot1, 0, rot2, "Geometry")
    rot2.inputs["Rotation"].default_value = (0.0, 0.0, 1.5708)
    jn = g.n("GeometryNodeJoinGeometry", -250, -1150)
    g.link(rot1, 0, jn, "Geometry")
    g.link(rot2, 0, jn, "Geometry")
    lean = g.n("ShaderNodeCombineXYZ", -250, -900)
    g.link(g.math("ARCTAN2", -350, -900, g.out(gi, "Wind"), 1.0), 0, lean, "Y")
    inst = g.n("GeometryNodeInstanceOnPoints", -50, 0)
    g.link(sp, 0, inst, "Points")
    g.link(jn, 0, inst, "Instance")
    g.link(lean, 0, inst, "Rotation")
    sm = g.n("GeometryNodeSetMaterial", 200, 0)
    g.link(inst, 0, sm, "Geometry")
    g.link(gi, "Material", sm, "Material")
    # the rain area as a circle in the viewport only (edges do not render)
    cc = g.n("GeometryNodeMeshCircle", 200, -300)
    cc.inputs["Vertices"].default_value = 64
    g.link(gi, "Radius", cc, "Radius")
    vp = g.n("GeometryNodeIsViewport", 200, -450)
    sw = g.n("GeometryNodeSwitch", 400, -300, input_type="GEOMETRY")
    g.link(vp, 0, sw, "Switch")
    g.link(cc, 0, sw, "True")
    jn2 = g.n("GeometryNodeJoinGeometry", 600, 0)
    g.link(sm, 0, jn2, "Geometry")
    g.link(sw, 0, jn2, "Geometry")
    g.link(jn2, 0, go, "Geometry")
    return ng


def _xyz(g, x, y, vec):
    sep = g.n("ShaderNodeSeparateXYZ", x, y)
    g.links.new(vec, sock(sep.inputs, "Vector"))
    return sep


def follow_camera(ob, scene, on):
    """Rain over wherever the camera looks (on), or where the object stands (off)."""
    con = next((c for c in ob.constraints if c.type == "COPY_LOCATION"), None)
    if on and scene.camera is not None:
        if con is None:
            con = ob.constraints.new("COPY_LOCATION")
            con.use_z = False
        con.target = scene.camera
    elif con is not None:
        mw = ob.matrix_world.translation.copy()
        ob.constraints.remove(con)
        ob.location = (mw.x, mw.y, 0.0)


def ensure_rain(context, amount=0.6, radius=None, at=None, follow=None, wind=None):
    sc = context.scene
    ob = bpy.data.objects.get(RAIN_OB)
    new = ob is None
    if new:
        me = bpy.data.meshes.new(RAIN_OB)
        ob = bpy.data.objects.new(RAIN_OB, me)
        sc.collection.objects.link(ob)
        mod = ob.modifiers.new(RAIN_MOD, "NODES")
        mod.node_group = rain_group()
        mod_input(mod, "Material", rain_material())
        ob.visible_shadow = False
        ob.hide_select = False
        if follow is None:
            follow = at is None
    else:
        rain_group()
        ob.modifiers[RAIN_MOD].node_group = bpy.data.node_groups[RAIN]
    if at is not None:
        follow_camera(ob, sc, False)
        ob.location = (at[0], at[1], 0.0)
    if follow is not None:
        follow_camera(ob, sc, follow)
    mod = ob.modifiers[RAIN_MOD]
    mod_input(mod, "Amount", amount)
    if radius is not None:
        mod_input(mod, "Radius", radius)
    if wind is not None:
        mod_input(mod, "Wind", wind)
    on = amount > 0.0
    ob.hide_render = ob.hide_viewport = not on
    ob["hrp_rain_r"] = float(mod_input(mod, "Radius")) if on else 1.0e6
    from . import water
    if bpy.data.node_groups.get(water.RAIN_ZONE) is not None:
        water.drive_rain_zone()
    ob.update_tag()
    return ob


# ----------------------------------------------------------------------------------------------
# rainbow
# ----------------------------------------------------------------------------------------------
def rainbow_material():
    mat, rebuilt = shading._fresh_mat(MAT_RAINBOW)
    if not rebuilt and mat.get("hrp_weather_ver") == WEATHER_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_weather_ver"] = WEATHER_VER
    g = G(mat.node_tree)
    uv = g.n("ShaderNodeUVMap", -900, 0)
    sep = g.n("ShaderNodeSeparateXYZ", -700, 0)
    g.link(uv, 0, sep, "Vector")
    ramp = g.n("ShaderNodeValToRGB", -500, 0)
    g.link(sep, "Y", ramp, "Factor")
    cols = ["#9B6BD8", "#5A7BE0", "#4FB6E8", "#7CD67A", "#F4E35C", "#F7A04C", "#E8584E"]
    els = ramp.color_ramp.elements
    ramp.color_ramp.interpolation = "LINEAR"
    for i, hx in enumerate(cols):
        pos = (i + 0.5) / len(cols)
        e = els[i] if i < 2 else els.new(pos)
        e.position = pos
        e.color = (*srgb(hx), 1.0)
    # soft across the band, fading near the ground at the ends
    across = g.math("SINE", -500, -250, only(g.math("MULTIPLY", -600, -250, g.out(sep, "Y"), math.pi).outputs))
    ends = g.maprange(-500, -400, only(g.math("SINE", -600, -400, only(g.math("MULTIPLY", -700, -400, g.out(sep, "X"),
                      math.pi).outputs)).outputs), 0.05, 0.75, smooth=True)          # the lower third fades out
    amt = g.n("ShaderNodeAttribute", -700, -600, attribute_name="hrp_rainbow", attribute_type="OBJECT")
    a = g.math("MULTIPLY", -300, -300, g.out(across, 0), g.out(ends, "Result"))
    a = g.math("MULTIPLY", -150, -300, g.out(a, 0), g.out(amt, "Fac"))
    a = g.math("MULTIPLY", -50, -300, g.out(a, 0), 0.55)
    em = g.n("ShaderNodeEmission", -100, 0)
    g.link(ramp, "Color", em, "Color")
    tr = g.n("ShaderNodeBsdfTransparent", -100, 150)
    ms = g.n("ShaderNodeMixShader", 150, 100)
    g.link(a, 0, ms, "Factor")
    g.link(tr, 0, ms, ("Shader", 0))
    g.link(em, 0, ms, ("Shader", 1))
    out = g.n("ShaderNodeOutputMaterial", 350, 100)
    g.link(ms, 0, out, "Surface")
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    shading._done(mat, "rainbow_material")
    return mat


def add_rainbow(context, strength=1.0, distance=700.0):
    """A rainbow on the anti-solar point as seen from the scene camera (rebuilt in place)."""
    sc = context.scene
    cam = sc.camera
    sun = next((o for o in sc.objects if o.type == "LIGHT" and o.data.type == "SUN"), None)
    if cam is None or sun is None:
        return None
    ob = bpy.data.objects.get(RAINBOW_OB)
    if ob is not None:
        bpy.data.objects.remove(ob)
    cam.data.clip_end = max(cam.data.clip_end, distance * 1.6)      # far behind the clouds
    c = cam.matrix_world.translation
    fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    fwd.z = 0.0
    fwd = fwd.normalized() if fwd.length > 1e-4 else Vector((0, 1, 0))
    sd = sun.matrix_world.to_3x3() @ Vector((0, 0, 1))              # towards the sun
    az = Vector((-sd.x, -sd.y, 0.0))                                # a rainbow faces away from the sun
    az = az.normalized() if az.length > 1e-4 else fwd
    if az.dot(fwd) < 0.92:                                          # out of frame: pull it into view (painted sky)
        az = (az * 0.35 + fwd).normalized() if az.dot(fwd) > -0.2 else fwd
    anti = (az + Vector((0, 0, -0.2))).normalized()                 # the bow's centre a little below the horizon
    centre = c + anti * distance
    R = distance * math.tan(math.radians(25.0))                    # drawn smaller than 42 deg so it fits the frame
    w = R * 0.07
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    seg = 96
    # ring in a plane facing the camera, around the anti-solar point
    fwd = anti
    up0 = Vector((0, 0, 1))
    right = fwd.cross(up0).normalized()
    up = right.cross(fwd).normalized()
    verts = []
    for i in range(seg + 1):
        a = math.pi * i / seg                                  # upper half
        d = right * math.cos(a) + up * math.sin(a)
        verts.append((bm.verts.new(centre + d * (R - w)), bm.verts.new(centre + d * (R + w)), i / seg))
    for (a0, b0, u0), (a1, b1, u1) in zip(verts, verts[1:]):
        f = bm.faces.new((a0, b0, b1, a1))
        for lp, uv in zip(f.loops, ((u0, 0), (u0, 1), (u1, 1), (u1, 0))):
            lp[uvl].uv = uv
    me = bpy.data.meshes.new(RAINBOW_OB)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(rainbow_material())
    ob = bpy.data.objects.new(RAINBOW_OB, me)
    sc.collection.objects.link(ob)
    ob["hrp_rainbow"] = float(strength)
    ob.visible_shadow = False
    return ob


# ----------------------------------------------------------------------------------------------
# fireflies
# ----------------------------------------------------------------------------------------------
def fly_material():
    mat, rebuilt = shading._fresh_mat(MAT_FLY)
    if not rebuilt and mat.get("hrp_weather_ver") == WEATHER_VER:
        return mat
    if not rebuilt:
        mat.node_tree.nodes.clear()
    mat["hrp_weather_ver"] = WEATHER_VER
    g = G(mat.node_tree)
    pal = g.n("ShaderNodeGroup", -800, 0)
    pal.node_tree = shading.palette_group()
    bl = g.n("ShaderNodeAttribute", -800, 300, attribute_name="hrp_blink", attribute_type="GEOMETRY")
    st = g.math("MULTIPLY", -550, 200, g.out(bl, "Fac"), g.out(pal, "fireflies"))
    st = g.math("MULTIPLY", -400, 200, g.out(st, 0), 4.5)
    lw = g.n("ShaderNodeLayerWeight", -800, 550)                     # a soft glowing dot: bright core, clear edge
    g.set(lw, "Blend", 0.5)
    core = g.math("POWER", -600, 550, only(g.math("SUBTRACT", -700, 550, 1.0, g.out(lw, "Facing")).outputs), 2.5)
    st = g.math("MULTIPLY", -400, 300, g.out(st, 0), g.out(core, 0))
    em = g.n("ShaderNodeEmission", -200, 0)
    g.link(pal, "firefly_colour", em, "Color")
    g.link(st, 0, em, "Strength")
    vis = g.math("GREATER_THAN", -400, 350, g.out(pal, "fireflies"), 0.01)
    lit_ = g.maprange(-400, 450, g.out(bl, "Fac"), 0.03, 0.2, smooth=True)       # dark between blinks = invisible
    vis = g.math("MULTIPLY", -300, 400, g.out(vis, 0), g.out(lit_, "Result"))
    vis = g.math("MULTIPLY", -250, 450, g.out(vis, 0), g.out(core, 0))
    tr = g.n("ShaderNodeBsdfTransparent", -200, 200)
    ms = g.n("ShaderNodeMixShader", 0, 100)
    g.link(vis, 0, ms, "Factor")
    g.link(tr, 0, ms, ("Shader", 0))
    g.link(em, 0, ms, ("Shader", 1))
    out = g.n("ShaderNodeOutputMaterial", 200, 100)
    g.link(ms, 0, out, "Surface")
    mat.surface_render_method = "BLENDED"
    shading._done(mat, "fly_material")
    return mat


def flies_group():
    ng, rebuilt = fresh_group(FLIES, "GeometryNodeTree", WEATHER_VER)
    if not rebuilt:
        return ng
    g = G(ng)
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Meadow", "INPUT", "NodeSocketObject")
    iface(ng, "Count", "INPUT", "NodeSocketInt", 160, 0, 5000)
    iface(ng, "Near Water", "INPUT", "NodeSocketFloat", 0.8, 0.0, 1.0, "Share that gathers along the water",
          "FACTOR")
    iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    iface(ng, "Material", "INPUT", "NodeSocketMaterial")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    gi = g.n("NodeGroupInput", -1600, 0)
    go = g.n("NodeGroupOutput", 1200, 0)
    oi = g.n("GeometryNodeObjectInfo", -1400, 0, transform_space="RELATIVE")
    g.link(gi, "Meadow", oi, "Object")
    sd = g.n("GeometryNodeInputNamedAttribute", -1400, -250, data_type="FLOAT")
    sd.inputs["Name"].default_value = "hrp_sd"
    near = g.maprange(-1200, -250, g.out(sd, "Attribute"), 3.0, 0.2, smooth=True)
    near = g.math("POWER", -1100, -250, g.out(near, "Result"), 0.5)
    dry = g.maprange(-1200, -400, g.out(sd, "Attribute"), -0.1, 0.2, smooth=True)
    w = g.math("MULTIPLY_ADD", -1000, -300, g.out(near, 0), only(g.math("MULTIPLY", -1100, -350, g.out(gi, "Near Water"),
               6.0).outputs),
               only(g.math("SUBTRACT", -1100, -450, 1.0, g.out(gi, "Near Water")).outputs))
    w = g.math("MULTIPLY", -850, -300, g.out(w, 0), g.out(dry, "Result"))
    ground = g.n("GeometryNodeSeparateComponents", -850, 100)      # the meadow's own surface, not its grass instances
    g.link(oi, "Geometry", ground, "Geometry")
    dist = g.n("GeometryNodeDistributePointsOnFaces", -700, 0)
    g.link(ground, "Mesh", dist, "Mesh")
    g.link(w, 0, dist, "Density")
    g.link(gi, "Seed", dist, "Seed")
    idx = g.n("GeometryNodeInputIndex", -700, -300)
    keep = g.n("FunctionNodeCompare", -550, -300, data_type="INT", operation="LESS_THAN")
    g.link(idx, 0, keep, "A", bkind="INT")
    g.link(gi, "Count", keep, "B", bkind="INT")
    sel = g.n("GeometryNodeSeparateGeometry", -550, 0, domain="POINT")
    g.link(dist, "Points", sel, "Geometry")
    g.link(keep, 0, sel, "Selection")
    # drift: smooth noise over time, 0.3..1.6 m up
    tm = g.n("GeometryNodeInputSceneTime", -550, -500)
    pos = g.n("GeometryNodeInputPosition", -550, -650)
    nv = g.n("ShaderNodeCombineXYZ", -400, -600)
    ps = _xyz(g, -500, -750, only(pos.outputs))
    g.link(ps, "X", nv, "X")
    g.link(ps, "Y", nv, "Y")
    g.link(g.math("MULTIPLY", -500, -550, g.out(tm, "Seconds"), 0.18), 0, nv, "Z")
    nz = g.n("ShaderNodeTexNoise", -250, -600, noise_dimensions="3D")
    g.set(nz, "Scale", 0.35)
    g.set(nz, "Detail", 1.0)
    g.link(nv, 0, nz, "Vector")
    dv = only(g.vmath("MULTIPLY_ADD", -100, -600, g.out(nz, "Color"), (1.6, 1.6, 0.8)).outputs)
    dv = only(g.vmath("ADD", 0, -600, dv, (-0.8, -0.8, 0.15)).outputs)
    mv = g.n("GeometryNodeSetPosition", -350, 0)
    g.link(sel, "Selection", mv, "Geometry")
    g.links.new(dv, mv.inputs["Offset"])
    # blink out of step: each fly on its own slow clock
    rp = g.n("FunctionNodeRandomValue", -200, -900, data_type="FLOAT")
    g.set(rp, "Max", 1.0, "VALUE")
    ph = g.math("FRACT", -50, -900, only(g.math("MULTIPLY_ADD", -150, -900, g.out(tm, "Seconds"), 0.45,
                g.out(rp, "Value", "VALUE")).outputs))
    blink = g.maprange(100, -900, g.out(ph, 0), 0.0, 0.18, smooth=True)
    blink2 = g.maprange(100, -1050, g.out(ph, 0), 0.5, 0.25, smooth=True)
    bl = g.math("MULTIPLY", 250, -950, g.out(blink, "Result"), g.out(blink2, "Result"))
    st = g.n("GeometryNodeStoreNamedAttribute", -150, 0, data_type="FLOAT", domain="POINT")
    g.link(mv, 0, st, "Geometry")
    st.inputs["Name"].default_value = "hrp_blink"
    g.link(bl, 0, st, "Value", bkind="VALUE")
    ico = g.n("GeometryNodeMeshIcoSphere", 50, -300)
    ico.inputs["Radius"].default_value = 0.035
    ico.inputs["Subdivisions"].default_value = 1        # tiny glowing dots: 42 vertices each (a heavy realized,
    #                                                     moving mesh exhausts the GPU buffers and breaks other objects)
    fv = g.n("FunctionNodeRandomValue", 100, -450, data_type="FLOAT")
    g.set(fv, "Min", 0.5, "VALUE")
    g.set(fv, "Max", 1.3, "VALUE")
    scl = g.math("MULTIPLY", 250, -300, only(g.math("MULTIPLY_ADD", 150, -350, g.out(bl, 0), 0.8, 0.2).outputs),
                 g.out(fv, "Value", "VALUE"))
    inst = g.n("GeometryNodeInstanceOnPoints", 300, 0)
    g.link(st, 0, inst, "Points")
    icos = g.n("GeometryNodeSetShadeSmooth", 150, -300)
    g.link(ico, "Mesh", icos, "Geometry")
    g.link(icos, 0, inst, "Instance")
    g.link(scl, 0, inst, "Scale")
    real = g.n("GeometryNodeRealizeInstances", 500, 0)
    g.link(inst, 0, real, "Geometry")
    sm = g.n("GeometryNodeSetMaterial", 700, 0)
    g.link(real, 0, sm, "Geometry")
    g.link(gi, "Material", sm, "Material")
    g.link(sm, 0, go, "Geometry")
    return ng


def ensure_fireflies(context, meadow, count=160):
    sc = context.scene
    ob = bpy.data.objects.get(FLIES_OB)
    if ob is None:
        me = bpy.data.meshes.new(FLIES_OB)
        ob = bpy.data.objects.new(FLIES_OB, me)
        sc.collection.objects.link(ob)
        ob.visible_shadow = False
        mod = ob.modifiers.new(FLIES_MOD, "NODES")
        mod.node_group = flies_group()
        mod_input(mod, "Material", fly_material())
    ob.matrix_world = meadow.matrix_world.copy()
    mod = ob.modifiers[FLIES_MOD]
    mod_input(mod, "Meadow", meadow)
    mod_input(mod, "Count", count)
    ensure_bloom(sc)
    return ob


# ----------------------------------------------------------------------------------------------
# bloom (only when the scene has no compositor of its own)
# ----------------------------------------------------------------------------------------------
def ensure_bloom(scene, strength=0.6):
    cur = getattr(scene, "compositing_node_group", None)
    if cur is not None and cur.name != BLOOM:
        return False
    ng = bpy.data.node_groups.get(BLOOM)
    if ng is None:
        ng = bpy.data.node_groups.new(BLOOM, "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        out = ng.nodes.new("NodeGroupOutput")
        try:
            gl.glare_type = "BLOOM"
        except (TypeError, AttributeError):
            try:
                gl.inputs["Type"].default_value = "Bloom"
            except Exception:
                pass
        for nm, v in (("Threshold", 1.0), ("Strength", strength), ("Size", 0.6)):
            try:
                gl.inputs[nm].default_value = v
            except (KeyError, TypeError):
                pass
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], out.inputs["Image"])
    try:
        scene.compositing_node_group = ng
        scene.render.use_compositing = True
    except AttributeError:
        return False
    return True
