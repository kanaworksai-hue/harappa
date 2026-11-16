"""Headless test: Harappa on scenes it was never tuned for.
blender -b --factory-startup --python tests/test_generic.py -- <out_dir>"""
import math
import os
import re
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np  # noqa: E402

import harappa as H  # noqa: E402
from harappa import build, i18n, pondlife, presets, rocks, scatter, shading  # noqa: E402
from harappa.util import mod_input  # noqa: E402

H.register()
sc = bpy.context.scene
ctx = bpy.context
fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[:, :, :3]
    bpy.data.images.remove(im)
    return a


def render(name, frame=None):
    if frame is not None:
        sc.frame_set(frame)
    sc.render.filepath = f"{OUT}/{name}.png"
    bpy.ops.render.render(write_still=True)
    return load(sc.render.filepath)


def instances(ob, src_prefix=None):
    """Number of Geometry Nodes instances the object outputs."""
    dg = ctx.evaluated_depsgraph_get()
    return sum(1 for inst in dg.object_instances if inst.is_instance and inst.parent
               and inst.parent.original == ob)


# --- 1. the default startup scene: a cube, a camera, a point light; select the cube's floor ----------
cube = bpy.data.objects["Cube"]
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, -1))
floor = ctx.active_object
floor.scale = (1.5, 1.0, 1.0)                              # unapplied scale on purpose
mat = bpy.data.materials.new("FloorOld")
floor.data.materials.append(mat)
bpy.ops.object.select_all(action="DESELECT")
floor.select_set(True)
ctx.view_layer.objects.active = floor
r = bpy.ops.harappa.make_meadow()
check(r == {"FINISHED"}, "make_meadow on a selected plane")
check(floor.modifiers.get(build.GRASS_MOD) is not None and floor.modifiers.get(build.FLOWER_MOD) is not None,
      "grass and flower modifiers added")
check(floor.data.materials[0] == shading.ground_material() and floor.get("hrp_prev_mats") == ["FloorOld"],
      "ground material set, old material remembered")
check(floor.data.color_attributes.get(scatter.MASK_ATTR) is not None, "grass mask attribute created")
check(sc.render.engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") and sc.view_settings.view_transform == "Standard",
      "EEVEE + Standard view")
check(sc.world.name == "HRP Sky" and bpy.data.objects.get("HRP Sun") is not None, "sky and sun added")
n_tufts = instances(floor, "HRP Grass Tuft")
check(n_tufts > 1000, f"grass tufts instanced ({n_tufts})")
check(floor.visible_shadow is False, "ground does not cast shadows")

# the plane has no subdivisions: painting needs vertices, but the mask still works per vertex
me = floor.data
attr = me.color_attributes[scatter.MASK_ATTR]
for d in attr.data[:2]:
    d.color = (0, 0, 0, 1)
me.update()
n2 = instances(floor, "HRP Grass Tuft")
check(n2 < n_tufts, f"painting black removes grass ({n_tufts} -> {n2})")
for d in attr.data:
    d.color = (1, 1, 1, 1)
me.update()

# Avoid: grass grows around the objects of a collection, and an empty collection changes nothing
from harappa.util import mod_input
av = bpy.data.collections.new("Props")
sc.collection.children.link(av)
gm = [m for m in floor.modifiers if m.name in ("Harappa Grass", "Harappa Flowers")]
for m in gm:
    mod_input(m, "Avoid", av)
check(instances(floor, "HRP Grass Tuft") == n_tufts, "an empty Avoid collection changes nothing")
bpy.ops.mesh.primitive_uv_sphere_add(radius=max(floor.dimensions.x, floor.dimensions.y) * 0.2,
                                     location=floor.matrix_world.translation)
rock = ctx.active_object
for c in list(rock.users_collection):
    c.objects.unlink(rock)
av.objects.link(rock)
n_av = instances(floor, "HRP Grass Tuft")
check(n_av < n_tufts * 0.98, f"Avoid removes the grass under an object ({n_tufts} -> {n_av})")
bpy.data.objects.remove(rock)
for m in gm:
    mod_input(m, "Avoid", None)
check(instances(floor, "HRP Grass Tuft") == n_tufts, "clearing Avoid brings the grass back")
ctx.view_layer.objects.active = floor
floor.select_set(True)

# --- 2. trees --------------------------------------------------------------------------------------
sc.cursor.location = (2.0, 2.0, 5.0)
r = bpy.ops.harappa.add_tree(shape="ROUND", height=3.0, seed=5)
root = ctx.active_object
check(r == {"FINISHED"} and root.get("hrp_tree") == "ROUND", "add_tree")
check(abs(root.location.z - (-1.0 - 0.06)) < 0.05, f"tree snapped to the ground below the cursor ({root.location.z:.3f})")
canopy = H.tree_canopy(root)
n_leaves = instances(canopy, "HRP Leaf Card")
check(n_leaves > 300, f"leaf cards instanced ({n_leaves})")
before = len(canopy.data.vertices)
root.harappa_tree.shape = "CONIFER"
check(root.get("hrp_tree") == "CONIFER" and len(canopy.data.vertices) != before, "changing the shape rebuilds")
root.harappa_tree.leaf_style = "NEEDLE"
mod = canopy.modifiers["Harappa Foliage"]
check(mod_input(mod, "Card").name == "HRP Leaf Card Needle", "leaf style switches the card")
bpy.ops.harappa.rebuild_tree(new_seed=True)
check(root.harappa_tree.seed >= 0, "new seed")
for shp in ("ROUND", "TALL", "WIDE", "BUSH", "CONIFER"):
    root.harappa_tree.shape = shp
check(H.tree_canopy(root) is not None, "every shape builds")
root.harappa_tree.shape = "ROUND"
root.harappa_tree.leaf_style = "ROUND"

# make foliage on an arbitrary mesh (the cube)
bpy.ops.object.select_all(action="DESELECT")
cube.select_set(True)
ctx.view_layer.objects.active = cube
r = bpy.ops.harappa.make_foliage()
check(r == {"FINISHED"} and instances(cube, "HRP Leaf Card") > 50, "make_foliage on the cube")

# plant trees
bpy.ops.object.select_all(action="DESELECT")
floor.select_set(True)
ctx.view_layer.objects.active = floor
nb = len([o for o in sc.objects if "hrp_tree" in o])
r = bpy.ops.harappa.plant_trees(count=3, seed=2, height=2.0)
na = len([o for o in sc.objects if "hrp_tree" in o])
check(r == {"FINISHED"} and na > nb, f"plant_trees ({na - nb} planted)")

# --- 3. a first render, then seasons/styles -----------------------------------------------------------
cam = sc.camera
cam.location = (0, -11, 2.2)
cam.rotation_euler = (math.radians(80), 0, 0)
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1280, 720, 50
img = render("default")
lum = img.mean(axis=2)
check(0.25 < lum.mean() < 0.9, f"render is neither black nor blank ({lum.mean():.2f})")
green = (img[..., 1] > img[..., 0] + 0.05).mean()
check(green > 0.3, f"meadow is green ({green:.2f})")

s = sc.harappa
for season in presets.SEASONS:
    s.season = season
    pal = presets.SEASONS[season]["palette"]
    got = shading.palette_get("grass_lit")
    exp = H.srgb(pal["grass_lit"])
    check(all(abs(a - b) < 1e-4 for a, b in zip(got, exp)), f"season {season} writes the palette")
    if season in ("GOLDEN", "AUTUMN", "NIGHT"):
        render(f"season_{season.lower()}")
s.season = "SUMMER"
for st in presets.STYLES:
    s.style = st
    check(abs(shading.palette_get("brush_jitter") - presets.STYLES[st]["keys"]["brush_jitter"]) < 1e-5,
          f"style {st} writes its keys")
s.style = "ANIME"
s.season = "GOLDEN"
s.style = "CRISP"
check(abs(s.threshold - presets.SEASONS["GOLDEN"]["tone"]["threshold"]) < 1e-5, "style keeps season keys")
s.season = "SUMMER"
check(abs(s.softness - presets.STYLES["CRISP"]["keys"]["softness"]) < 1e-5, "season keeps style keys")
s.style = "ANIME"

# variation
base = {k: tuple(getattr(s, k)) for k, _ in H.COLOUR_PROPS}
bpy.ops.harappa.shuffle()
v1 = s.variation
g1 = tuple(s.grass_lit)
check(v1 > 0 and g1 != base["grass_lit"], "shuffle changes the colours")
bpy.ops.harappa.shuffle()
s.variation = v1
check(all(abs(a - b) < 1e-5 for a, b in zip(s.grass_lit, g1)), "variation reproducible from its number")
s.variation = 0
check(all(all(abs(a - b) < 1e-5 for a, b in zip(getattr(s, k), base[k])) for k, _ in H.COLOUR_PROPS),
      "variation 0 restores the base colours")

# --- 4. wind moves (frame 1 vs 30), a static shot is stable --------------------------------------------
sc.frame_end = 60
a = render("wind_f1", 1)
b = render("wind_f1b", 1)
# stable = no visible change: < 0.01 % of pixels move more than 2 %, none more than 5 % (EEVEE may differ on a pixel)
check((np.abs(a - b) > 0.02).mean() < 1e-4 and np.abs(a - b).max() < 0.05, "same frame renders the same")
c = render("wind_f30", 30)
diff = (np.abs(a - c).max(axis=2) > 0.05).mean()
check(diff > 0.01, f"wind animates the grass ({diff * 100:.1f}% pixels change)")
sc.frame_set(1)

# --- 5. translations: label, operator, tooltip, enum item, report, in every language ---------------------
import bpy.app.translations as T  # noqa: E402
view = bpy.context.preferences.view
view.use_translate_interface = view.use_translate_tooltips = True
for loc, exp_label, exp_op, exp_enum in (("ja_JP", "季節", "アニメの草原にする", "夏の草原"),
                                         ("zh_HANS", "季节", "生成动画草原", "夏日草原"),
                                         ("ko_KR", "계절", "애니 초원 만들기", "여름 초원")):
    view.language = loc
    ok = (T.pgettext_iface("Season") == exp_label and T.pgettext_iface("Make Anime Meadow", "Operator") == exp_op
          and T.pgettext_iface("Summer Meadow") == exp_enum and i18n.t("Season") == exp_label
          and T.pgettext_tip("Breaks shadow edges into blade-like strokes") != "Breaks shadow edges into blade-like strokes"
          and i18n.report("Planted 3 tree(s)") != "Planted 3 tree(s)")
    check(ok, f"translations work in {loc}")
view.language = "en_US"
check(i18n.t("Season") == "Season", "English is the source")

# every msgid the UI can show has ja/zh/ko
msgids = set()
for cls in (H.HRP_Settings, H.HRP_TreeSettings):
    for p in cls.bl_rna.properties:
        if p.identifier in ("rna_type", "name"):
            continue
        msgids.add(p.name)
        if p.description:
            msgids.add(p.description)
        if p.type == "ENUM":
            for it in p.enum_items:
                msgids.add(it.name)
                if it.description:
                    msgids.add(it.description)
for cls in H.CLASSES:
    if issubclass(cls, bpy.types.Operator) and not cls.bl_idname.endswith("set_enum"):
        msgids.add(cls.bl_label)
        msgids.add(cls.bl_description)
        for ident in getattr(cls, "__annotations__", {}):
            p = cls.bl_rna.properties.get(ident)
            if p is None or p.is_hidden:
                continue
            msgids.add(p.name)
            if p.description:
                msgids.add(p.description)
src = open(os.path.join(HERE, "..", "harappa", "ui.py"), encoding="utf-8").read()
msgids |= set(re.findall(r'\bt\("([^"]+)"\)', src))
msgids |= set(re.findall(r'\b_op\([^"\n]*?"[^"]+",\s*"([^"]+)"', src))
msgids |= set(re.findall(r'\b_prop\(\w+,\s*\w+,\s*"[^"]+",\s*"([^"]+)"\)', src))
msgids |= set(re.findall(r'title = "([^"]+)"', src))
for tup in re.findall(r'_mod_inputs\([^)]*\(([^)]*)\)\)', src):
    msgids |= set(re.findall(r'"([^"]+)"', tup))
msgids = {m for m in msgids if m and not m.startswith("HRP") and m not in ("Name", "Prop", "Value ")}
missing = sorted(m for m in msgids if m not in i18n.UI and m not in i18n.OPS)
check(not missing, f"{len(msgids)} UI strings translated (missing: {missing})")

# --- 5b. water: pond + stream carve a bed, clear the grass, follow the seasons, clean up -------------------
from harappa import water  # noqa: E402
bpy.ops.object.select_all(action="DESELECT")
bpy.ops.mesh.primitive_grid_add(x_subdivisions=100, y_subdivisions=100, size=24, location=(60, 0, 0))
wg = ctx.active_object
bpy.ops.harappa.make_meadow()
dg = ctx.evaluated_depsgraph_get()


def eval_z_mask(ob, x, y, r=0.4):
    dg_ = ctx.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg_).to_mesh()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) + np.array(ob.location)
    sel = np.hypot(co[:, 0] - x, co[:, 1] - y) < r
    a = me.attributes.get("hrp_grass")
    m = np.zeros(len(a.data) * 4)
    a.data.foreach_get("color", m)
    m = m.reshape(-1, 4)[:, 0]
    z, mm = float(co[sel, 2].min()), float(m[sel].mean())
    ob.evaluated_get(dg_).to_mesh_clear()
    return z, mm


z_before, _ = eval_z_mask(wg, 60, 0)
sc.cursor.location = (60, 0, 0)
bpy.ops.harappa.add_pond(radius=3.0, depth=0.7)
pond = ctx.active_object
check(water.is_water(pond), "Add Pond made a water curve")
check(wg.modifiers[0].name == water.CARVE_MOD, "carve is the first modifier on the meadow")
z_after, m_in = eval_z_mask(wg, 60, 0)
check(z_after < z_before - 0.4, f"pond lowered the meadow ({z_before:.2f} -> {z_after:.2f})")
check(m_in < 0.05, f"no grass in the pond (mask {m_in:.2f})")
_, m_far = eval_z_mask(wg, 60, 10.5, 0.6)
check(m_far > 0.95, f"grass kept away from the water (mask {m_far:.2f})")
pe = pond.evaluated_get(ctx.evaluated_depsgraph_get()).to_mesh()
check(len(pe.polygons) > 100 and pe.attributes.get("hrp_shore") is not None, "pond surface mesh with shore distance")
pond.evaluated_get(ctx.evaluated_depsgraph_get()).to_mesh_clear()
pond.harappa_water.kind = "TEA"
from harappa.util import srgb  # noqa: E402
check(pond.get("hrp_wuse") == 1.0 and max(abs(a - b) for a, b in zip(pond["hrp_wcol_m"],
      srgb(water.WATER_TYPES["TEA"][3][1]))) < 1e-5 and pond.harappa_water.clarity < 0,
      "water type gives that pond its own colours")
ext0 = max(p.co.x for p in pond.data.splines[0].bezier_points) - min(p.co.x for p in pond.data.splines[0].bezier_points)
pond.harappa_water.size = 1.3
ext1 = max(p.co.x for p in pond.data.splines[0].bezier_points) - min(p.co.x for p in pond.data.splines[0].bezier_points)
check(abs(ext1 / ext0 - 1.3) < 1e-3 and abs(pond.scale.x - 1.0) < 1e-6,
      "pond Size reshapes the shoreline (object scale stays 1, pads keep their size)")
pond.harappa_water.size = 1.0
sc.cursor.location = (60, 0, 0)
n_trees = len([o for o in bpy.data.objects if H.tree_root(o) is o])
r_ = bpy.ops.harappa.add_tree(shape="ROUND", height=4.0, seed=3)
check(r_ == {"CANCELLED"} and len([o for o in bpy.data.objects if H.tree_root(o) is o]) == n_trees,
      "no tree planted in the pond")
sc.cursor.location = (52, -9, 0)
bpy.ops.harappa.add_stream(length=10.0)
stream = ctx.active_object
zs = [p.co.z for p in stream.data.splines[0].bezier_points]
check(all(b <= a + 1e-6 for a, b in zip(zs, zs[1:])), "stream runs downhill only")
zs0 = [p.co.z for p in stream.data.splines[0].bezier_points]
ctx.view_layer.objects.active = stream
bpy.ops.harappa.drop_stream()
bpy.ops.harappa.drop_stream()
zs2 = [p.co.z for p in stream.data.splines[0].bezier_points]
check(max(abs(a - b) for a, b in zip(zs0, zs2)) < 1e-5, "Drop Onto Meadow is repeatable (no sinking)")
water.make_water(ctx, pond)
check(sum(1 for m in pond.modifiers if m.name == water.SURFACE_MOD) == 1
      and sum(1 for m in wg.modifiers if m.name == water.CARVE_MOD) == 1, "re-running makes no duplicates")
sc.harappa.season = "NIGHT"
check(abs(shading.palette_get("water_glow") - 1.0) < 1e-6, "night makes the water glow")
sc.harappa.season = "SUMMER"
check(shading.palette_get("water_glow") == 0.0, "summer water does not glow")
img = render("water")
check(img.std() > 0.03, "water scene renders")
bpy.ops.object.select_all(action="DESELECT")
for w_ in (pond, stream):
    ctx.view_layer.objects.active = w_
    bpy.ops.harappa.remove_water()
check(wg.modifiers.get(water.CARVE_MOD) is None, "removing all water removes the carve")
z_back, m_back = eval_z_mask(wg, 60, 0)
check(abs(z_back - z_before) < 1e-4 and m_back > 0.95, "meadow restored after removing the water")
bpy.data.objects.remove(wg)
# stream first, then a pond over its lower end: they still meet (no step at the mouth)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=100, y_subdivisions=100, size=24, location=(60, 0, 0))
wg2 = ctx.active_object
bpy.ops.harappa.make_meadow()
st2 = water.add_stream(ctx, [(52, -8, 0), (56, -3, 0), (59, 0, 0), (61, 1, 0)])
pd2 = water.add_pond(ctx, (60.5, 0.5, 0.0), radius=2.6, depth=0.7)
lvl2 = sum(p.co.z for p in pd2.data.splines[0].bezier_points) / len(pd2.data.splines[0].bezier_points)
poly2 = [((pd2.matrix_world @ p.co).x, (pd2.matrix_world @ p.co).y) for p in pd2.data.splines[0].bezier_points]
inside2 = [p.co.z for p in st2.data.splines[0].bezier_points if water._inside(poly2, p.co.x, p.co.y)]
check(inside2 and max(abs(z - (lvl2 - 0.015)) for z in inside2) < 1e-4,
      f"pond added after the stream: mouth meets the pond ({[round(z - lvl2, 3) for z in inside2]})")
for o in (st2, pd2):
    ctx.view_layer.objects.active = o
    bpy.ops.harappa.remove_water()
bpy.data.objects.remove(wg2)
# lily pads only in the floating-leaf zone, reeds in the shallows
sc.cursor.location = (60, 0, 0)
pd3 = water.add_pond(ctx, (60.0, 0.0, 0.0), radius=3.0, depth=0.9)
ctx.view_layer.update()
dg3 = ctx.evaluated_depsgraph_get()
ev3 = pd3.evaluated_get(dg3)
pads = [ii.matrix_world.translation.copy() for ii in dg3.object_instances
        if ii.is_instance and ii.parent and ii.parent.original == pd3]
check(len(pads) > 5, f"lily pads on the pond ({len(pads)})")
lvl3 = water.pond_level(pd3)
in_zone = all(water.in_water(ctx, t_.x, t_.y, 0.0) for t_ in pads)
check(in_zone, "every lily pad floats on the water")
ctx.view_layer.objects.active = pd3
bpy.ops.harappa.remove_water()
# rocks, pond life and a waterfall
bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120, size=30, location=(60, 0, 0))
wg3 = ctx.active_object
bpy.ops.harappa.make_meadow()
sc.cursor.location = (60, 6, 0)
bpy.ops.harappa.add_rock(size=1.2, seed=5)
rk = ctx.active_object
check(rk.name in bpy.data.collections["Harappa Props"].objects, "Add Rock joins Harappa Props")
check(mod_input(wg3.modifiers[build.GRASS_MOD], "Avoid") == bpy.data.collections["Harappa Props"],
      "grass grows around the props")
sc.cursor.location = (68, 8, 0)
bpy.ops.harappa.add_tree(shape="ROUND", height=3.0, seed=2)
old_tree = ctx.active_object.name
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(69.0, 8.4, 1.5))   # a block standing 2 m above the coming pond
blk = ctx.active_object
sc.cursor.location = (69.0, 8.4, 2.0)
bpy.ops.harappa.add_tree(shape="ROUND", height=1.5, seed=3)
high_tree = ctx.active_object.name
bpy.ops.harappa.add_pond(radius=2.0, seed=1)
check(bpy.data.objects.get(old_tree) is None, "a new pond clears a tree that stood there")
check(bpy.data.objects.get(high_tree) is not None, "...but not a tree up on a block above the water")
ht = bpy.data.objects.get(high_tree)
for o_ in ([ht] + list(ht.children_recursive) if ht else []) + [blk]:
    bpy.data.objects.remove(o_)
bpy.ops.harappa.remove_water()
sc.cursor.location = (60, -6, 0)
bpy.ops.harappa.add_waterfall(height=2.2, width=1.0, seed=3)
fall = ctx.active_object
tag = fall.get("hrp_waterfall")
parts = [o for o in sc.objects if o.get("hrp_waterfall") == tag]
check(len(parts) > 8 and any(o.get("hrp_terrace") for o in parts), f"Add Waterfall built its parts ({len(parts)})")
feed = next(o for o in parts if o.get("hrp_fall_feed"))
zs3 = [p.co.z for p in feed.data.splines[0].bezier_points]
check(mod_input(fall.modifiers[0], "Drop") > 1.5 and max(zs3) - min(zs3) < 0.05, "the stream stays on the terrace, the drop is real")
pool = next(o for o in parts if water.is_water(o) and o.get("hrp_pond") is not None)
check(any(water.is_water(o) and o is not feed and o.get("hrp_pond") is None for o in parts) and
      any(o.get("hrp_tree") for o in parts), "the pool spills into an outflow stream, trees stand on the terrace")
check(abs(mod_input(fall.modifiers[0], "Drop") - 2.2) < 0.15, f"the drop matches the height asked for ({mod_input(fall.modifiers[0], 'Drop'):.2f})")
check(pool.modifiers.get(pondlife.LIFE_MOD) is not None and wg3.modifiers[-1].name == rocks.SHORE_MOD,
      "pond life on the pool, shore pebbles last on the meadow")
# Freeze Banks: same ground, the carve is no longer re-run every frame
import time  # noqa: E402
z_live, m_live = eval_z_mask(wg3, 60, -5.0, 1.0)
sc.frame_set(1)
t0 = time.perf_counter()
for f_ in range(2, 12):
    sc.frame_set(f_)
t_live = (time.perf_counter() - t0) / 10
bpy.ops.harappa.freeze_banks(on=True)
z_fz, m_fz = eval_z_mask(wg3, 60, -5.0, 1.0)
t0 = time.perf_counter()
for f_ in range(12, 22):
    sc.frame_set(f_)
t_fz = (time.perf_counter() - t0) / 10
print(f"PERF waterfall meadow: live {t_live * 1000:.0f} ms/frame, frozen {t_fz * 1000:.0f} ms/frame")
check(abs(z_fz - z_live) < 1e-4 and t_fz < t_live * 0.8, "Freeze Banks keeps the ground and speeds up playback")
bpy.ops.harappa.freeze_banks(on=False)
# Grass Only in Camera View: off by default, fewer tufts when on, all back when off again
def n_inst(ob_):
    dg_ = ctx.evaluated_depsgraph_get()
    return sum(1 for i_ in dg_.object_instances if i_.is_instance and i_.parent and i_.parent.original == ob_)
n_all = n_inst(wg3)
sc.harappa.camera_culling = True
n_cull = n_inst(wg3)
sc.harappa.camera_culling = False
check(n_cull < n_all * 0.9 and n_inst(wg3) == n_all and
      mod_input(wg3.modifiers[build.GRASS_MOD], "Camera Culling") is False,
      f"Grass Only in Camera View thins what the camera can't see ({n_all} -> {n_cull})")
# Selected Waterfall: Flow is live, Height rebuilds the whole fall in place
fall.harappa_fall.flow = 1.8
check(abs(mod_input(fall.modifiers[0], "Throw") - (0.45 + 0.5 * 1.8)) < 1e-4, "waterfall Flow changes the sheet live")
from harappa import waterfall as hwf  # noqa: E402
fall = hwf.rebuild_waterfall(ctx, fall, height=3.0)
tag = fall.get("hrp_waterfall")
parts = [o for o in sc.objects if o.get("hrp_waterfall") == tag]
pool = next(o for o in parts if water.is_water(o) and o.get("hrp_pond") is not None)
check(abs(mod_input(fall.modifiers[0], "Drop") - 3.0) < 0.2 and abs(fall.harappa_fall.flow - 1.8) < 1e-5 and
      abs(fall.harappa_fall.height - 3.0) < 1e-5, "waterfall Height rebuilds it in place, Flow kept")
# Selected Rock: size / seed / moss straight on the object
sc0 = tuple(rk.scale)
rk.harappa_rock.size = 2.4
me0 = rk.data
rk.harappa_rock.seed = 77
rk.harappa_rock.moss = 0.2
check(abs(rk.scale[0] - sc0[0] * 2.0) < 1e-4 and rk.data is not me0 and rk.harappa_rock.seed == 77 and
      abs(rk.get("hrp_nomoss") - 0.8) < 1e-5, "Selected Rock: size, seed and moss edit the rock")
# water type keeps the user's tint and a lily amount the user chose
pool.harappa_water.hue = 0.1
lm = pool.modifiers[pondlife.LIFE_MOD]
mod_input(lm, "Lily Pads", 0.33)
pool.harappa_water.kind = "LOTUS"
check(abs(pool.harappa_water.hue - 0.1) < 1e-6 and abs(mod_input(lm, "Lily Pads") - 0.33) < 1e-5,
      "changing water type keeps the user's hue and lily amount")
mod_input(lm, "Lily Pads", water.LILY_COVER["LOTUS"])
pool.harappa_water.kind = "CLEAR"
check(abs(mod_input(lm, "Lily Pads") - water.LILY_COVER["CLEAR"]) < 1e-5, "...but follows the type when untouched")
# koi, a boat, weather, rainbow, fireflies
from harappa import fauna, weather as hwe  # noqa: E402
ctx.view_layer.objects.active = pool
bpy.ops.harappa.add_fish(count=4)
fish_ob = next((c for c in pool.children if c.get("hrp_fish")), None)
check(fish_ob is not None, "Add Koi makes a fish object on the pond")
bpy.ops.harappa.add_boat()
check(ctx.active_object.get("hrp_boat") == pool.name, "Add Boat floats a boat on the pond")
sc.harappa.weather = "RAIN"
grass_before = tuple(sc.harappa.grass_lit)
check(bpy.data.objects.get(hwe.RAIN_OB) is not None and shading.palette_get("water_rain") > 0.3, "rain: streaks and rings")
check(shading.palette_get("grass_lit")[1] < grass_before[1] - 0.02 and tuple(sc.harappa.grass_lit) == grass_before,
      "rain dims the sunlit grass without touching the user's colours")
rob = bpy.data.objects[hwe.RAIN_OB]
check(any(c.type == "COPY_LOCATION" for c in rob.constraints), "rain follows the camera by default")
sc.cursor.location = (60, -6, 0)
sc.harappa.rain_radius = 5.0
bpy.ops.harappa.rain_here()
ctx.view_layer.update()
zone = bpy.data.node_groups[water.RAIN_ZONE]
check(not rob.constraints and abs(rob.location.x - 60) < 1e-4 and not sc.harappa.rain_follow and
      abs(zone.nodes["R"].outputs[0].default_value - 5.0) < 1e-3 and abs(zone.nodes["X"].outputs[0].default_value - 60)
      < 1e-3, "Rain Here: rain (and its ripples) only around the cursor")
sc.harappa.rain_follow = True
check(any(c.type == "COPY_LOCATION" for c in rob.constraints), "Follow Camera puts it back over the view")
gm = wg3.modifiers[build.GRASS_MOD]
w0 = mod_input(gm, "Wind Strength")
sc.harappa.weather = "STORM"
w1 = mod_input(gm, "Wind Strength")
sc.harappa.weather = "CLEAR"
check(abs(w1 - min(2.0, w0 * 2)) < 1e-5 and abs(mod_input(gm, "Wind Strength") - w0) < 1e-6,
      "Storm doubles the grass wind, Clear puts it back")
check(shading.palette_get("water_rain") == sc.harappa.water_rain and
      max(abs(a - b) for a, b in zip(shading.palette_get("grass_lit"), grass_before)) < 1e-5, "clear weather undoes it")
sc.harappa.rainbow = True
check(bpy.data.objects.get(hwe.RAINBOW_OB) is not None, "rainbow in the sky")
sc.harappa.rainbow = False
sc.harappa.dragonfly_count = 6
dfo = bpy.data.objects.get(fauna.DRAGON_OB)
dg_ = ctx.evaluated_depsgraph_get()
n_df = len([i for i in dg_.object_instances if i.is_instance and i.parent and i.parent.original == dfo]) if dfo else 0
check(dfo is not None and n_df > 0, f"dragonflies over the water ({n_df})")
sc.harappa.dragonfly_count = 0
check(mod_input(fall.modifiers[0], "Mist Material") is not None, "waterfall spray mist has its material")
sc.harappa.firefly_count = 50
check(bpy.data.objects.get(hwe.FLIES_OB) is not None, "fireflies by the water")
sc.harappa.firefly_count = 0
img = render("water_life")
check(img.std() > 0.03, "pond life scene renders")
feed_ = next((o for o in parts if o.get("hrp_fall_feed")), None)
ctx.view_layer.objects.active = feed_
sc.cursor.location = feed_.matrix_world @ feed_.data.splines[0].bezier_points[2].co
bpy.ops.harappa.stepping_stones()
stones = [o for o in sc.objects if o.get("hrp_stone") == feed_.name]
check(len(stones) >= 2, f"stepping stones across the stream ({len(stones)})")
for o in stones:
    bpy.data.objects.remove(o)
hwf.remove_waterfall(ctx, tag)
check(not [o for o in sc.objects if o.get("hrp_waterfall") == tag], "remove the whole waterfall")
bpy.data.objects.remove(rk)
bpy.data.objects.remove(wg3)
# the agent CLI with water flags (dev copy: the agent finds the registered package)
import runpy  # noqa: E402
_argv = sys.argv
sys.argv = [_argv[0], "--", "--meadow", "--pond", "2,-4,2.4", "--stream", "-7,8:-4,3:-1,-1:1.2,-3.6",
            "--rain", "0.3", "--water-type", "LOTUS", "--rock", "6,3,0.8", "--koi", "3", "--boat",
            "--weather", "CLOUDY", "--rainbow", "--fireflies", "30"]
n_before = len([o for o in bpy.data.objects if water.is_water(o)])
try:
    runpy.run_path(os.path.join(HERE, "..", "agent", "harappa_agent.py"), run_name="__main__")
    cli_ok = True
except SystemExit as e:
    cli_ok = e.code in (None, 0)
sys.argv = _argv
n_after = len([o for o in bpy.data.objects if water.is_water(o)])
check(cli_ok and n_after - n_before == 2, f"CLI --pond/--stream made water ({n_after - n_before})")
check(abs(sc.harappa.water_rain - 0.3) < 1e-6, "CLI --rain sets the rain ripples")
check(sc.harappa.weather == "CLOUDY" and sc.harappa.rainbow and sc.harappa.firefly_count == 30 and
      any(o.get("hrp_boat") for o in sc.objects) and any(o.get("hrp_fish") for o in sc.objects),
      "CLI --koi/--boat/--weather/--rainbow/--fireflies")
sc.harappa.weather = "CLEAR"
sc.harappa.rainbow = False
sc.harappa.firefly_count = 0
for o in [o for o in sc.objects if o.get("hrp_boat") or o.get("hrp_fish")]:
    bpy.data.objects.remove(o)
for o in [o for o in bpy.data.objects if water.is_water(o)]:
    ctx.view_layer.objects.active = o
    bpy.ops.harappa.remove_water()
# an older file: the palette is rebuilt on upgrade and must not leave the meadow materials unlinked
palng = bpy.data.node_groups[shading.PALETTE]
palng["hrp_ver"] = shading.SHADER_VER - 1
check(H.ensure_shading(ctx), "upgrade detected")
gmat = bpy.data.materials[shading.MAT_GRASS]
pal_users = [n for n in gmat.node_tree.nodes if n.type == "GROUP" and n.node_tree == palng]
check(pal_users and any(o.is_linked for n in pal_users for o in n.outputs), "materials relinked to the palette after upgrade")

# --- 6. revert and unregister ---------------------------------------------------------------------------
bpy.ops.object.select_all(action="DESELECT")
floor.select_set(True)
cube.select_set(True)
r = bpy.ops.harappa.revert()
check(floor.modifiers.get(build.GRASS_MOD) is None and cube.modifiers.get("Harappa Foliage") is None,
      "revert removed modifiers")
check(floor.data.materials[0] == mat and floor.visible_shadow, "revert restored material and shadows")
H.unregister()
check(not hasattr(bpy.types.Scene, "harappa"), "unregister clean")
print("RESULT", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
