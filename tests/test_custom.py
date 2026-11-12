"""Headless test of the customisation features: brush layers, Avoid Objects, this object's colour, My Looks.
blender -b --factory-startup --python tests/test_custom.py -- <out_dir>"""
import json
import os
import subprocess
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
LOOKS = tempfile.mkdtemp(prefix="hrp_looks_")
os.environ["HARAPPA_LOOKS_DIR"] = LOOKS                    # never the user's real folder
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402

import harappa as H  # noqa: E402
from harappa import avoid, build, layers, look, looks, scatter, shading  # noqa: E402
from harappa.util import mod_input  # noqa: E402

H.register()
sc = bpy.context.scene
ctx = bpy.context
s = sc.harappa
fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def count(ob, prefix):
    dg = ctx.evaluated_depsgraph_get()
    return sum(1 for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == ob
               and i.object.data is not None and i.object.data.name.startswith(prefix))


def heights(ob, prefix="HRP Grass"):
    dg = ctx.evaluated_depsgraph_get()
    zs = [i.matrix_world.to_scale().z for i in dg.object_instances if i.is_instance and i.parent
          and i.parent.original == ob and i.object.data is not None and i.object.data.name.startswith(prefix)]
    return float(np.mean(zs)) if zs else 0.0


def layer(ob, key):
    at = ob.data.color_attributes.get(layers.attr_name(key))
    if at is None:
        return None
    v = np.empty(len(ob.data.vertices) * 4, dtype=np.float32)
    at.data.foreach_get("color", v)
    return v.reshape(-1, 4)


def render(name, size=(240, 135)):
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.filepath = f"{OUT}/{name}.png"
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(sc.render.filepath, check_existing=False)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[:, :, :3]
    bpy.data.images.remove(im)
    return a


# --- 1. brush layers -----------------------------------------------------------------------------------
bpy.ops.harappa.make_meadow()
m = ctx.active_object
g0, f0, h0 = count(m, "HRP Grass"), count(m, "HRP Flower"), heights(m)
for key in ("FLOWERS", "HEIGHT", "COLOUR"):
    layers.ensure(m.data, key)                            # every layer at its starting value
check((count(m, "HRP Grass"), count(m, "HRP Flower")) == (g0, f0) and abs(heights(m) - h0) < 1e-6,
      f"layers at their starting value change nothing ({g0} grass, {f0} flowers)")
check(layers.painted(m) == [], "no layer counts as painted at its starting value")
layers.fill(m, "FLOWERS", layers.target("FLOWERS", "PAINT")[0])
f_all = count(m, "HRP Flower")
layers.fill(m, "FLOWERS", layers.target("FLOWERS", "ERASE")[0])
f_none = count(m, "HRP Flower")
layers.clear(m, "FLOWERS")
check(f_all > f0 * 2 and f_none == 0 and count(m, "HRP Flower") == f0,
      f"Flowers layer: everywhere {f_all}, none {f_none}, back to {count(m, 'HRP Flower')}")
layers.fill(m, "HEIGHT", (1, 1, 1, 1))
h_hi = heights(m)
layers.fill(m, "HEIGHT", (0.25, 0.25, 0.25, 1))
h_lo = heights(m)
layers.clear(m, "HEIGHT")
check(abs(h_hi / h0 - 2.0) < 0.05 and abs(h_lo / h0 - 0.5) < 0.05,
      f"Height layer: white x{h_hi / h0:.2f}, quarter grey x{h_lo / h0:.2f}")
n = layers.paint_disc(m, "GRASS", (0.0, 0.0), 4.0, layers.target("GRASS", "ERASE")[0])
check(n > 50 and count(m, "HRP Grass") < g0, f"erasing grass in a spot clears it ({g0} -> {count(m, 'HRP Grass')})")
layers.paint_disc(m, "COLOUR", (5.0, 5.0), 3.0, layers.target("COLOUR", "PAINT", (1.0, 0.0, 0.0))[0])
layers.paint_disc(m, "FLOWERS", (-6.0, 4.0), 3.0, (1, 1, 1, 1))
layers.paint_disc(m, "HEIGHT", (6.0, -4.0), 3.0, (1, 1, 1, 1))
snap = {k: layer(m, k).copy() for k in layers.LAYERS}
check(set(layers.painted(m)) == set(layers.LAYERS), f"four layers painted ({layers.painted(m)})")
a = layer(m, "COLOUR")
amt_a = a[:, :3].max(axis=1)
check(amt_a.max() > 0.99 and amt_a.min() == 0.0 and a[amt_a > 0.99][:, 1].max() < 0.01,
      "Colour layer: red where painted, black (nothing) elsewhere")
layers.paint_disc(m, "COLOUR", (5.0, 5.0), 3.0, layers.target("COLOUR", "ERASE", (0, 0, 1))[0], strength=0.5)
b = layer(m, "COLOUR")
amt_b = b[:, :3].max(axis=1)
hue_kept = np.allclose(b[amt_b > 0.05][:, :3] / amt_b[amt_b > 0.05, None], a[amt_b > 0.05][:, :3] / amt_a[amt_b > 0.05, None],
                       atol=1e-4)
check(amt_b.max() < 0.6 and hue_kept, "erasing colour lowers the amount and keeps the colour")
layers.fill(m, "COLOUR", layers.target("COLOUR", "ERASE")[0])
check(layer(m, "COLOUR")[:, :3].max() == 0.0 and "COLOUR" not in layers.painted(m),
      "Erase-filling the Colour layer leaves no colour")
m.data.color_attributes[layers.attr_name("COLOUR")].data.foreach_set("color", snap["COLOUR"].ravel())
check(layers.target("COLOUR", "PAINT", (0.4, 0.2, 0.1))[0][:3] == (1.0, 0.5, 0.25)
      and layers.target("COLOUR", "PAINT", (0, 0, 0))[0][:3] == (1.0, 1.0, 1.0),
      "colours are painted at full value; black (= nothing) can't be painted")

# painting survives everything that rebuilds the look or the meadow
s.season = "AUTUMN"
s.style = "PAINTERLY"
bpy.ops.harappa.shuffle()
bpy.ops.harappa.reset()
for o in ctx.selected_objects:
    o.select_set(False)
m.select_set(True)
ctx.view_layer.objects.active = m
bpy.ops.harappa.make_meadow()
s.detail_level = "FAST"
s.detail_level = "BALANCED"
kept = all(np.allclose(layer(m, k), snap[k]) for k in layers.LAYERS)
check(kept, "seasons, styles, Shuffle, Reset, Make Meadow again and detail levels keep the painted layers")

# the panel's buttons: enter painting with a lighter viewport, Fill / Clear, Done gives the grass back
g_full = count(m, "HRP Grass")
r = bpy.ops.harappa.paint_layer(layer="FLOWERS")
check(r == {"FINISHED"} and ctx.mode == "PAINT_VERTEX" and s.paint_layer == "FLOWERS"
      and m.data.color_attributes.active_color.name == scatter.FLOWERS_ATTR, "a layer button starts painting it")
check(abs(mod_input(m.modifiers[build.GRASS_MOD], "Preview Factor") - layers.PREVIEW) < 1e-6
      and count(m, "HRP Grass") < g_full * 0.5, f"lighter viewport while painting ({g_full} -> {count(m, 'HRP Grass')})")
br = ctx.tool_settings.vertex_paint.brush
if br is not None:
    ups = getattr(ctx.tool_settings.vertex_paint, "unified_paint_settings", None)

    def brush_col():
        a_ = tuple(br.color)
        b_ = tuple(ups.color) if ups is not None and hasattr(ups, "color") else a_
        return a_, b_
    s.paint_layer = "COLOUR"
    s.paint_mode = "ERASE"
    check(br.blend == "MIX" and any(np.allclose(c_, (0, 0, 0)) for c_ in brush_col()),
          "Erase on the Colour layer paints black (= nothing)")
    s.paint_mode = "PAINT"
    s.paint_colour = (0.2, 0.4, 0.9)
    check(br.blend == "MIX" and any(np.allclose(c_, (0.2 / 0.9, 0.4 / 0.9, 1.0), atol=1e-4) for c_ in brush_col()),
          "the brush takes the paint colour (at full value)")
    s.paint_layer = "HEIGHT"
    s.paint_mode = "ERASE"
    check(any(np.allclose(c_, (0, 0, 0)) for c_ in brush_col()), "Erase on Grass Height paints black")
    s.paint_mode = "PAINT"
else:
    print("NOTE no vertex paint brush in background mode on this version")
s.paint_layer = "FLOWERS"
bpy.ops.harappa.paint_fill()
check(layer(m, "FLOWERS")[:, 0].min() > 0.99, "Fill Layer fills the layer")
bpy.ops.harappa.paint_fill(clear=True)
check(np.allclose(layer(m, "FLOWERS"), layers.LAYERS["FLOWERS"][1]) and ctx.mode == "PAINT_VERTEX",
      "Clear Layer resets only that layer and keeps painting")
check(np.allclose(layer(m, "HEIGHT"), snap["HEIGHT"]), "other layers are not touched by Clear")
bpy.ops.harappa.paint_done()
check(ctx.mode == "OBJECT" and abs(mod_input(m.modifiers[build.GRASS_MOD], "Preview Factor") - 1.0) < 1e-6
      and count(m, "HRP Grass") == g_full and "hrp_preview" not in m, "Done Painting gives the full grass back")
bpy.ops.harappa.paint_layer(layer="GRASS")
bpy.ops.object.mode_set(mode="OBJECT")                      # leaving paint mode some other way (Tab)
ctx.view_layer.update()
H._follow_camera(sc, ctx.evaluated_depsgraph_get())
check(abs(mod_input(m.modifiers[build.GRASS_MOD], "Preview Factor") - 1.0) < 1e-6,
      "leaving paint mode with Tab also gives the grass back")
bpy.ops.harappa.paint_layer(layer="GRASS")
r1 = render("preview_on", (160, 90))
bpy.ops.harappa.paint_done()
r2 = render("preview_off", (160, 90))
check(np.abs(r1 - r2).mean() < 0.002, f"renders always draw all the grass (diff {np.abs(r1 - r2).mean():.4f})")

# Make Ground Finer: only offered on the user's own ground, keeps what was painted
bpy.ops.mesh.primitive_plane_add(size=10, location=(60, 0, 0))
plane = ctx.active_object
bpy.ops.harappa.make_meadow()
layers.paint_disc(plane, "FLOWERS", (60.0, 0.0), 12.0, (1, 1, 1, 1), soft=0.0)
check(H.HRP_OT_ground_finer.poll(ctx), "Make Ground Finer is offered on a user's ground")
before = len(plane.data.vertices)
exp = layers.finer_count(plane)
bpy.ops.harappa.ground_finer()
fl = layer(plane, "FLOWERS")
check(len(plane.data.vertices) == exp and before == 4 and abs(layers.spacing(plane) - 10 / 13) < 0.01
      and fl[:, 0].min() > 0.99,
      f"Make Ground Finer: {before} -> {len(plane.data.vertices)} points, painting kept")
ctx.view_layer.objects.active = m
check(not H.HRP_OT_ground_finer.poll(ctx), "not offered on Harappa's own hill")

# --- 2. avoid objects ----------------------------------------------------------------------------------------
ctx.view_layer.objects.active = m
for k in ("FLOWERS", "HEIGHT", "COLOUR", "GRASS"):
    layers.clear(m, k)
g_base = count(m, "HRP Grass")
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, location=(2.0, 3.0, m.matrix_world.translation.z + 0.3))
ball = ctx.active_object
bpy.ops.object.empty_add(location=(0, 0, 0))
empty = ctx.active_object
tr = H.tree.add_tree(ctx, "ROUND", 5.0, 3, (8.0, -6.0, 0.0))
canopy = H.tree_canopy(tr)
cl = next(o for o in sc.objects if o.get("hrp_cloud"))
bpy.ops.mesh.primitive_cube_add(size=1, location=(-5, 5, 0))
follower = ctx.active_object
sw = follower.modifiers.new("sw", "SHRINKWRAP")
sw.target = m
for o in ctx.selected_objects:
    o.select_set(False)
for o in (ball, empty, canopy, cl, m, follower):
    o.select_set(True)
ctx.view_layer.objects.active = ball
bpy.ops.harappa.avoid_add()
col = avoid.current(sc)
names = sorted(o.name for o in col.objects)
trunk = next(c for c in tr.children if not c.get("hrp_canopy"))
check(names == sorted([ball.name, trunk.name]), f"Avoid Selected takes the ball and the tree's trunk only ({names})")
reasons = {}
for o in (m, canopy, cl, empty, follower):
    why = avoid.check(sc, o)
    reasons[o.name] = why[0] if why else None
check(all(reasons.values()), f"the meadow, a crown, a cloud, an empty and a shrinkwrapped object are refused ({reasons})")
check(all(r in H.i18n.UI for r in reasons.values()), "every refusal reason is translated")
check(all(mod_input(mm, "Avoid") == col for mm in avoid._mods(sc)), "every meadow avoids the same collection")
g_av = count(m, "HRP Grass")
check(g_av < g_base, f"grass makes room for the ball ({g_base} -> {g_av})")
s.avoid_box = True
g_box = count(m, "HRP Grass")
check(g_box < g_av and all(mod_input(mm, "Avoid Box") for mm in avoid._mods(sc)),
      f"Use Simple Box clears the ball's whole box ({g_av} -> {g_box})")
s.avoid_box = False


def ground_z(ob, x, y):
    from mathutils import Vector as V
    inv = ob.matrix_world.inverted()
    ok, hit, _n, _i = ob.ray_cast(inv @ V((x, y, 500.0)), (inv.to_3x3() @ V((0, 0, -1))).normalized())
    return (ob.matrix_world @ hit).z if ok else 0.0


def under_ball():
    dg = ctx.evaluated_depsgraph_get()
    c = ball.matrix_world.translation
    return [i.matrix_world.to_scale().z for i in dg.object_instances if i.is_instance and i.parent
            and i.parent.original == m and i.object.data is not None and i.object.data.name.startswith("HRP Grass")
            and (i.matrix_world.translation.xy - c.xy).length < 0.5]


z_rest = ball.location.z
gzb = ground_z(m, ball.location.x, ball.location.y)
col.objects.unlink(ball)
m.update_tag()
free = under_ball()
col.objects.link(ball)
ball.location.z = gzb + 1.5 + 4.0                          # 4 m above the ground
m.update_tag()
high = under_ball()
check(free and sorted(high) == sorted(free), "grass grows freely under a ball 4 m up")
ball.location.z = gzb + 1.5 + 0.25                         # hovering 0.25 m above the ground
m.update_tag()
low_h = under_ball()
s.avoid_reach = 0.1
free_h = under_ball()
s.avoid_reach = 100.0
check(low_h and max(low_h) < 0.3 and free_h and max(free_h) > max(low_h) + 0.1,
      f"Reaches Down From: a ball hovering just above caps the grass under it ({max(low_h or [0]):.2f} m), "
      f"not when set lower ({max(free_h or [0]):.2f} m)")
ball.location.z = z_rest
# continuous: a small move changes the grass height near the ball only a little (nothing pops)
def near_heights():
    dg = ctx.evaluated_depsgraph_get()
    c = ball.matrix_world.translation
    return sum(i.matrix_world.to_scale().z for i in dg.object_instances if i.is_instance and i.parent
               and i.parent.original == m and i.object.data is not None and i.object.data.name.startswith("HRP Grass")
               and (i.matrix_world.translation - c).length < 3.0)
steps = []
prev = near_heights()
for k in range(6):
    ball.location.x += 0.01
    cur = near_heights()
    steps.append(abs(cur - prev) / max(prev, 1e-9))
    prev = cur
check(max(steps) < 0.02, f"grass next to a moving object changes smoothly (max step {max(steps) * 100:.2f}%)")
for o in ctx.selected_objects:
    o.select_set(False)
ball.select_set(True)
bpy.ops.harappa.avoid_remove()
bpy.ops.harappa.avoid_remove(name=trunk.name)
check(len(col.objects) == 0 and count(m, "HRP Grass") == g_base, "Stop Avoiding brings the grass back")

# --- 3. this object's colour --------------------------------------------------------------------------------
ctx.view_layer.objects.active = canopy
s.obj_hue = 0.2
s.obj_tint = (1.0, 0.1, 0.4)
s.obj_tint_amount = 0.6
check(abs(canopy["hrp_look"][0] - 0.2) < 1e-6 and abs(canopy["hrp_own"][3] - 0.6) < 1e-6
      and abs(s.obj_hue - 0.2) < 1e-6 and "hrp_look" not in trunk, "the panel writes the tree's crown colour")
bpy.ops.harappa.shuffle()
var_h = float(canopy.get("hrp_hue", 0.0))
check(abs(canopy["hrp_look"][0] - (0.2 + var_h)) < 1e-6 and abs(s.obj_hue - 0.2) < 1e-6 and canopy["hrp_own"][3] > 0.59,
      "Shuffle adds its tint and keeps the user's own colour")
bpy.ops.harappa.reset()
check(abs(s.obj_hue - 0.2) < 1e-6 and look.overridden(canopy), "Reset to Defaults keeps each object's own colour")
s.season = "SUMMER"
tr2 = H.tree.add_tree(ctx, "ROUND", 5.0, 4, (-8.0, -6.0, 0.0))
for o in ctx.selected_objects:
    o.select_set(False)
tr2.select_set(True)
canopy.select_set(True)
ctx.view_layer.objects.active = canopy
bpy.ops.harappa.tint_copy()
check(look.user(H.tree_canopy(tr2)) == look.user(canopy), "Copy to Selected copies the colour settings")
bpy.ops.harappa.tint_reset()
check(not look.overridden(canopy) and "hrp_own" not in canopy and not look.overridden(H.tree_canopy(tr2)),
      "Follow the Scene removes the overrides")
cl = next(o for o in sc.objects if o.get("hrp_cloud"))          # Shuffle made new clouds
rg = next(o for o in sc.objects if o.get("hrp_ridge"))
check(all(look.is_harappa(o) for o in (m, canopy, tr, cl, rg)) and not look.is_harappa(ball),
      "meadows, trees, clouds and mountains get the panel, the user's own objects do not")
# it shows in the render, on every material, within 5.0 / 5.1's 8 object attributes per material
ctx.view_layer.objects.active = m
base = render("tint_none")
s.obj_tint = (1.0, 0.05, 0.05)
s.obj_tint_amount = 1.0
red = render("tint_red")
low = slice(0, int(base.shape[0] * 0.25))          # pixel rows start at the bottom
check(red[low, :, 0].mean() > red[low, :, 1].mean() and red[low, :, 0].mean() > base[low, :, 0].mean() + 0.1,
      f"a red own colour turns the meadow red (R {base[low, :, 0].mean():.2f} -> {red[low, :, 0].mean():.2f})")
s.obj_tint_amount = 0.0
s.obj_hue = 0.0
again = render("tint_back")
check(np.abs(again - base).mean() < 0.003, "with the own colour off the picture is as before")
layers.fill(m, "COLOUR", (0.9, 0.1, 0.8, 1.0))
painted_r = render("paint_colour")
check(painted_r[low, :, 2].mean() > base[low, :, 2].mean() + 0.05,
      f"a painted colour shows on grass and ground (B {base[low, :, 2].mean():.2f} -> {painted_r[low, :, 2].mean():.2f})")
layers.clear(m, "COLOUR")

# --- 4. my looks -------------------------------------------------------------------------------------------
s.season = "GOLDEN"
s.style = "CRISP"
s.grade_sat = 1.3
s.grass_lit = (0.9, 0.2, 0.1)
r = bpy.ops.harappa.look_save(name="Test: Dusk/1", grass=True)
p = looks.path_of("Test: Dusk/1")
check(r == {"FINISHED"} and os.path.isfile(p) and os.path.dirname(p) == LOOKS and "/" not in os.path.basename(p)[:-5]
      .replace(".harappa-look", ""), f"Save Look writes a file in the looks folder ({os.path.basename(p)})")
data = json.load(open(p, encoding="utf-8"))
check(data["format"] == "harappa-look" and data["season"] == "GOLDEN" and data["palette"]["grass_lit"].startswith("#")
      and "layers" in data and "hrp_grass" not in json.dumps(data), "the file holds the look, not the painting")
snapshot = H._snapshot(s)
s.season = "SPRING"
s.style = "SOFT"
s.grade_sat = 0.7
r = bpy.ops.harappa.look_apply(filepath=p)
after = H._snapshot(s)
diff = [k for k, v in snapshot.items() if not np.allclose(np.atleast_1d(after[k]), np.atleast_1d(v), atol=5e-3)]  # 8-bit hex
same = not diff
print("look round trip differences:", diff)
check(r == {"FINISHED"} and same and s.season == "GOLDEN" and s.style == "CRISP" and s.look_name == "Test: Dusk/1",
      "Apply Look brings back every colour, value, the season and the style")
check(np.allclose(shading.palette_get("grass_lit"), tuple(s.grass_lit), atol=1e-5)
      and abs(shading.palette_get("grade_sat") - 1.3) < 1e-4, "the applied look reaches the materials")
odd = dict(data, palette=dict(data["palette"], grass_lit="nonsense", foo="#123456"),
           values={"grade_sat": 99.0, "threshold": "x", "bar": 1.0}, extra=1)
del odd["sun"]
s.sun_elevation = 33.0
n = looks.apply(ctx, odd)
check(n["unknown"] == 3 and n["bad"] == 2 and n["clamped"] == 1 and abs(s.grade_sat - 2.0) < 1e-6
      and abs(s.sun_elevation - 33.0) < 1e-6, f"unknown keys ignored, bad ones skipped, numbers clamped, missing kept ({n})")
bad = os.path.join(LOOKS, "bad.json")
open(bad, "w").write('{"format": "something-else"}')
try:
    refused = bpy.ops.harappa.look_apply(filepath=bad) == {"CANCELLED"}
except RuntimeError as e:                     # an ERROR report raises in background mode
    refused = "Not a look" in str(e)
check(refused, "a file that is not a look is refused")
exp_p = os.path.join(tempfile.mkdtemp(), "shared.harappa-look.json")
check(bpy.ops.harappa.look_export(filepath=exp_p) == {"FINISHED"} and os.path.isfile(exp_p), "Export Look")
os.remove(p)
check(bpy.ops.harappa.look_import(filepath=exp_p) == {"FINISHED"} and len(looks.all_looks()) == 1, "Import Look")
check(bpy.ops.harappa.look_delete(filepath=looks.all_looks()[0][1]) == {"FINISHED"} and not looks.all_looks(),
      "Delete Look")
check(bpy.ops.harappa.look_delete(filepath=bad) == {"CANCELLED"} and os.path.isfile(bad), "Delete only takes looks")
s.season = "SUMMER"
check(s.look_name == "", "changing the season replaces the look's colours")
bpy.ops.harappa.look_season()
check(abs(s.grade_sat - 2.0) < 1e-6 and np.allclose(tuple(s.grass_lit), H.srgb(H.presets.SEASONS["SUMMER"]["palette"]["grass_lit"]),
                                                     atol=1e-5), "Season Default restores the season colours")

# --- 5. the agent CLI writes the same layers and looks as the panel ------------------------------------------
cli_blend = os.path.join(tempfile.mkdtemp(), "cli.blend")
look_file = os.path.join(LOOKS, "cli.harappa-look.json")
looks.save(ctx, "CLI Look", path=look_file)
boot = f"import sys; sys.path.insert(0, {ROOT!r}); import harappa; harappa.register()"
env = dict(os.environ)
cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python-expr", boot, "--python",
       os.path.join(ROOT, "agent", "harappa_agent.py"), "--", "--meadow", "--paint", "grass:erase@0,0,3",
       "--paint", "colour:#FF2000@6,6,3", "--paint", "height:1@-6,6,3", "--fill", "flowers:paint",
       "--preset-file", look_file, "--save-preset", "From CLI", "--avoid", "Harappa Camera", "--save", cli_blend]
res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
tail = [ln for ln in res.stdout.splitlines() if ln.startswith("HARAPPA")]
check(res.returncode == 0 and tail and tail[-1].startswith("HARAPPA OK"), f"agent CLI runs ({tail[-1:] or res.stderr[-300:]})")
if res.returncode == 0:
    with bpy.data.libraries.load(cli_blend) as (src, dst):
        dst.meshes = [n for n in src.meshes if n == "Meadow"]
    me = dst.meshes[0]
    def lay(name):
        at = me.color_attributes.get(name)
        v = np.empty(len(me.vertices) * 4, dtype=np.float32)
        at.data.foreach_get("color", v)
        return v.reshape(-1, 4)
    gl, tl, hl, fl = (lay(layers.attr_name(k)) for k in ("GRASS", "COLOUR", "HEIGHT", "FLOWERS"))
    tm = tl[:, :3].max(axis=1)
    check(gl[:, 0].min() < 0.01 and tm.max() > 0.99 and tl[tm > 0.99][:, 0].min() > 0.99 and tl[tm > 0.99][:, 2].max() < 0.01
          and hl[:, 0].max() > 0.99 and fl[:, 0].min() > 0.99, "the CLI paints the four layers like the brush")
    check(any(fn.startswith("From CLI") for fn in os.listdir(LOOKS)), "the CLI saves a look")
    check("avoid skipped Harappa Camera" in res.stdout, "the CLI reports the objects Avoid refused")

# --- 6. a translated Blender: node groups still build (zone items get translated names when they are created) ----
view = bpy.context.preferences.view
view.use_translate_interface = True
view.use_translate_new_dataname = True
built = {}
for loc in ("zh_HANS", "ja_JP", "ko_KR"):
    view.language = loc
    for ng in (scatter.grass_group(), scatter.flowers_group()):
        ng[H.util.VERSION_KEY] = 0                       # force a rebuild in this language
    try:
        ok_ = scatter.grass_group().get(H.util.VERSION_KEY) == scatter.GN_VER and \
            scatter.flowers_group().get(H.util.VERSION_KEY) == scatter.GN_VER
    except KeyError as e:
        ok_ = False
        print("build error", e)
    built[loc] = ok_
view.language = "en_US"
m2 = next(o for o in sc.objects if o.modifiers.get(build.GRASS_MOD) and o.get("hrp_hill"))
check(all(built.values()) and count(m2, "HRP Grass") > 1000, f"grass builds in a translated Blender ({built})")

# --- 7. review round 1: older meadows, limits, deleted objects, overhangs, materials ------------------------------
# an older meadow (nodes without this version's inputs): the rebuild gives the new inputs their defaults
gng = scatter.grass_group()
for nm in ("Preview Factor", "Avoid Reach", "Avoid Box"):
    it = next(i for i in gng.interface.items_tree if getattr(i, "item_type", "") == "SOCKET" and i.name == nm
              and i.in_out == "INPUT")
    gng.interface.remove(it)
gng[H.util.VERSION_KEY] = 1
H.upgrade_groups()                                         # what opening the file does
gm_ = m2.modifiers[build.GRASS_MOD]
check(abs(mod_input(gm_, "Preview Factor") - 1.0) < 1e-6 and abs(mod_input(gm_, "Avoid Reach") - 100.0) < 1e-6
      and mod_input(gm_, "Avoid Box") is False and count(m2, "HRP Grass") > 1000,
      "an older meadow gets the new inputs at their defaults (grass still in the viewport)")
def ground_z(ob, x, y):
    from mathutils import Vector as V
    inv = ob.matrix_world.inverted()
    ok, hit, _n, _i = ob.ray_cast(inv @ V((x, y, 500.0)), (inv.to_3x3() @ V((0, 0, -1))).normalized())
    return (ob.matrix_world @ hit).z if ok else 0.0


# a look's grass density stays under the meadow's tuft limit
bpy.ops.mesh.primitive_plane_add(size=150, location=(0, 300, 0))
big = ctx.active_object
bpy.ops.harappa.make_meadow()
lim = big["hrp_max_density"]
n_ = looks.apply(ctx, {"format": "harappa-look", "layers": {"grass": {"Density": 40.0}}})
check(lim < 12 and mod_input(big.modifiers[build.GRASS_MOD], "Density") <= lim + 1e-6 and n_["clamped"] >= 1,
      f"a look can't push the grass density over the meadow's limit ({lim:.1f}/m2)")
n_ = looks.apply(ctx, {"format": "harappa-look", "values": {"grade_sat": int("9" * 400)}})
check(n_["bad"] == 1, "a huge number in a look is skipped, not a crash")
bpy.data.objects.remove(big)
# deleting an avoided object gives the grass back
ctx.view_layer.objects.active = m2
g0_ = count(m2, "HRP Grass")
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, m2.matrix_world.translation.z))
cube_ = ctx.active_object
avoid.add(ctx, [cube_])
g1_ = count(m2, "HRP Grass")
bpy.ops.object.delete()
avoid.prune(sc)
check(g1_ < g0_ and count(m2, "HRP Grass") == g0_, f"a deleted avoided object stops clearing grass ({g0_}/{g1_})")
check(not avoid.collection_ok(m2.users_collection[0]), "the collection picker refuses a collection with the meadow in it")
# overhangs: grass grows under a plank up to just below it, nothing pops as it moves
def plank(z):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(3, -4, 0))
    p_ = ctx.active_object
    p_.scale = (2.0, 0.6, 0.04)
    p_.location.z = max(ground_z(m2, 3 + dx, -4 + dy) for dx in (-1, 0, 1) for dy in (-0.3, 0, 0.3)) + z
    return p_
pl = plank(0.25)
avoid.add(ctx, [pl])
def under():
    dg = ctx.evaluated_depsgraph_get()
    out = []
    for i in dg.object_instances:
        if not (i.is_instance and i.parent and i.parent.original == m2 and i.object.data is not None
                and i.object.data.name.startswith("HRP Grass")):
            continue
        p0 = i.matrix_world.translation
        if abs(p0.x - pl.location.x) < 0.9 and abs(p0.y - pl.location.y) < 0.2:
            room = pl.location.z - 0.02 - p0.z
            out.append(i.matrix_world.to_scale().z / max(room, 1e-3))
    return out
hs_ = under()
check(hs_ and max(hs_) <= 0.81, f"grass under a low plank grows up to just below it "
      f"({len(hs_)} blades, tallest {max(hs_ or [0]) * 100:.0f}% of the room under it)")
pl.location.z += 0.65                                      # 0.9 m up: grass grows freely under it
counts = []
for k_ in range(8):
    pl.location.x += 0.01
    counts.append(count(m2, "HRP Grass"))
check(len(set(counts)) == 1, f"a plank moving above the grass makes no blade appear or vanish ({set(counts)})")
avoid.remove(ctx, [pl])
bpy.data.objects.remove(pl)
# an armature is avoided through its meshes
bpy.ops.object.armature_add(location=(-3, 3, 0))
arm = ctx.active_object
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(-3, 3, 0.3))
body = ctx.active_object
body.parent = arm
added_, skipped_, _h = avoid.add(ctx, [arm])
check(added_ == [body.name] and skipped_ and "armature" in skipped_[0][1], "an armature is avoided through its mesh")
avoid.remove(ctx, [body])
# a painted colour that is cleared again gives the meadow its plain (faster) grass back
layers.fill(m2, "COLOUR", (1.0, 0.5, 0.2, 1.0))
t_custom = mod_input(m2.modifiers[build.GRASS_MOD], "Tuft").name
layers.clear(m2, "COLOUR")
t_plain = mod_input(m2.modifiers[build.GRASS_MOD], "Tuft").name
check(t_custom.endswith("Custom") and not t_plain.endswith("Custom"), "the custom grass material only while needed")
# a tree's own colour goes on its crown, the trunk stays bark
trx = H.tree.add_tree(ctx, "ROUND", 5.0, 9, (12.0, 12.0, 0.0))
ctx.view_layer.objects.active = trx
s.obj_tint = (1.0, 0.4, 0.6)
trunk_ = next(c for c in trx.children if not c.get("hrp_canopy"))
check("hrp_own" in H.tree_canopy(trx) and "hrp_own" not in trunk_ and abs(s.obj_tint_amount - 0.9) < 1e-6,
      "picking an own colour shows it at once, on the crown only")
# proxies on the scene are not animatable (they write to whatever object is active)
rna = s.bl_rna.properties
check(not any(rna[k].is_animatable for k in ("obj_hue", "obj_sat", "obj_value", "obj_tint", "obj_tint_amount",
                                              "avoid_margin", "avoid_floor", "avoid_box", "avoid_reach", "cloud_width")),
      "per-object and Avoid sliders can't be keyframed by mistake")
# every material stays within Blender 5.0 / 5.1's 8 object + instancer attributes
def attr_names(nt, seen=None):
    out = set()
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeAttribute" and n.attribute_type in ("OBJECT", "INSTANCER"):
            out.add((n.attribute_type, n.attribute_name))
        if getattr(n, "node_tree", None) is not None:
            out |= attr_names(n.node_tree)
    return out
over = {mat.name: len(attr_names(mat.node_tree)) for mat in bpy.data.materials
        if mat.name.startswith("HRP") and mat.node_tree is not None}
check(max(over.values()) <= 8, f"every material reads at most 8 object / instancer attributes ({max(over.values())})")
# fixed messages are translated too
bpy.context.preferences.view.language = "ja_JP"
tr_ok = H.i18n.report("Look deleted") != "Look deleted" and H.i18n.report("Give the look a name") != "Give the look a name"
bpy.context.preferences.view.language = "en_US"
check(tr_ok, "fixed report messages are translated")

print("RESULT ALL PASS" if not fails else f"RESULT {len(fails)} FAIL: {fails}")
