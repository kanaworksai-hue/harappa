"""Headless test: Harappa on scenes it was never tuned for.
blender -b --factory-startup --python tests/test_generic.py -- <out_dir>

Node wiring and the six season pictures are compared with tests/baseline/. After changing nodes or the look on
purpose, record new ones with HARAPPA_UPDATE_BASELINE=1 (on the oldest supported LTS) and check the pictures."""
import math
import os
import re
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
UPDATE = os.environ.get("HARAPPA_UPDATE_BASELINE") == "1"
import numpy as np  # noqa: E402

import harappa as H  # noqa: E402
from harappa import build, i18n, presets, scatter, shading, util  # noqa: E402
from harappa.util import mod_input  # noqa: E402
import seasons  # noqa: E402
import wiring  # noqa: E402

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

# --- 3b. node wiring: every link joins the sockets it was written for, on this Blender version ------------
shading.all_materials()
for build_group in (scatter.wind_group, scatter.grass_group, scatter.flowers_group, scatter.foliage_group):
    build_group()
bad = wiring.problems()
check(not bad, f"every node link is valid and joins matching sockets ({len(bad)} bad: {bad[:4]})")
ok, msg = wiring.compare(update=UPDATE)
check(ok, f"node links, settings and input values are the recorded ones ({msg})")
hits = wiring.positional_access(os.path.join(HERE, ".."))
check(not hits, f"no socket is picked by position in the source ({hits})")
probe = bpy.data.materials[shading.MAT_GROUND].node_tree.nodes.new("ShaderNodeVectorTransform")
try:
    util.sock(probe.inputs, 0)
    refused = False
except TypeError:
    refused = True
check(refused and util.sock(probe.inputs, "Vector").type == "VECTOR" and util.only(probe.outputs).type == "VECTOR",
      "socket helpers find 'Vector' by name and refuse a position")
bpy.data.materials[shading.MAT_GROUND].node_tree.nodes.remove(probe)

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

# --- 7. the look: the default landscape in all six seasons against the recorded pictures -------------------
bpy.ops.wm.read_factory_settings()
H.register()
sc = seasons.run(OUT, list(presets.SEASONS), check, update=UPDATE)
clouds_ob = bpy.data.objects.get("Anime Clouds")
check(clouds_ob is not None and len(clouds_ob.data.vertices) > 0, "the default landscape has clouds")
hills = bpy.data.objects["Far Hills"]
check(min(p.normal.z for p in hills.data.polygons) > 0.0, "far hills face up (their fringe stands on the face normal)")

# --- 8. a scene made with an older version: the first action brings every material up to date -------------
# The materials share HRP Palette / HRP Cel / HRP Clump Normal. Rebuilding one of those for a new version drops
# the links of every material that is not rebuilt with it, and the scene turns grey without any error.
s = sc.harappa
s.season = "AUTUMN"
autumn_lit = shading.palette_get("grass_lit")
old = [ng for ng in bpy.data.node_groups if ng.name in (shading.PALETTE, shading.CLUMP, shading.CEL)]
old += [m for m in bpy.data.materials if m.name.startswith("HRP") and m.get(util.VERSION_KEY) is not None]
for idb in old:
    idb[util.VERSION_KEY] = shading.SHADER_VER - 1
s.clump_size = s.clump_size                                # any one palette write, e.g. moving a slider
check(all(idb.get(util.VERSION_KEY) == shading.SHADER_VER for idb in old) and len(old) >= 10,
      f"an older scene: one action rebuilds all {len(old)} shader groups and materials")
ok, msg = wiring.compare()
check(ok and not wiring.problems(), f"an older scene: no link is lost in the rebuild ({msg})")
check(all(abs(a - b) < 1e-5 for a, b in zip(shading.palette_get("grass_lit"), autumn_lit)),
      "an older scene keeps its colours")
pal = bpy.data.node_groups[shading.PALETTE]
check(pal.animation_data is not None and len(pal.animation_data.drivers) == 1, "an older scene keeps the sun driver")
if not UPDATE:
    ok, msg = seasons.compare(sc, "AUTUMN", os.path.join(OUT, "upgrade_autumn.png"))
    check(ok, f"an older scene renders like a new one ({msg})")

# --- 9. a scene made with older geometry nodes: the rebuild keeps what the user set on the modifiers ---------
# Rebuilding a group must not replace its interface sockets: a new socket gets a new identifier, and the values
# on every modifier (density, height, wind, the Avoid collection) would silently fall back to the defaults.
def _iface(ng):
    return [(i.in_out, i.name, i.socket_type) for i in ng.interface.items_tree
            if getattr(i, "item_type", "") == "SOCKET"]


ground = next(o for o in sc.objects if o.get("hrp_ground") and o.modifiers.get(build.GRASS_MOD))
gmod, fmod = ground.modifiers[build.GRASS_MOD], ground.modifiers[build.FLOWER_MOD]
gn_groups = [bpy.data.node_groups[n] for n in (scatter.WIND, scatter.GRASS, scatter.FLOWERS, scatter.FOLIAGE)]
declared = {ng.name: _iface(ng) for ng in gn_groups}
ids_before = {ng.name: sorted(i.identifier for i in ng.interface.items_tree
                              if getattr(i, "item_type", "") == "SOCKET") for ng in gn_groups}
avoid_coll = bpy.data.collections.new("Test Avoid")
sc.collection.children.link(avoid_coll)
mine = {(gmod, "Density"): 33.0, (gmod, "Height"): 0.61, (gmod, "Seed"): 5, (gmod, "Avoid Margin"): 0.44,
        (gmod, "Avoid"): avoid_coll, (fmod, "Height"): 0.52, (fmod, "Size"): 0.21, (fmod, "Seed"): 9}
for (m, name), v in mine.items():
    mod_input(m, name, v)
tuft_before = mod_input(gmod, "Tuft")
for ng in gn_groups:                                          # what an older version left behind
    ng[util.VERSION_KEY] = scatter.GN_VER - 1
    ng.interface.new_socket("Gone In 1.1", in_out="INPUT", socket_type="NodeSocketFloat")
    first = next(i for i in ng.interface.items_tree if getattr(i, "item_type", "") == "SOCKET" and i.in_out == "INPUT")
    ng.interface.move(first, len(ng.interface.items_tree) - 1)
scatter.wind_group(), scatter.grass_group(), scatter.flowers_group(), scatter.foliage_group()
check(all(ng.get(util.VERSION_KEY) == scatter.GN_VER for ng in gn_groups), "older geometry nodes are rebuilt")
check(all(_iface(ng) == declared[ng.name] for ng in gn_groups),
      "rebuilt groups have exactly the declared sockets, in the declared order")
check(all(sorted(i.identifier for i in ng.interface.items_tree if getattr(i, "item_type", "") == "SOCKET")
          == ids_before[ng.name] for ng in gn_groups), "rebuilt groups keep their socket identifiers")
kept = []
for (m, name), v in mine.items():
    now = mod_input(m, name)
    kept.append(now == v if not isinstance(v, float) else abs(now - v) < 1e-5)
check(all(kept) and mod_input(gmod, "Tuft") == tuft_before,
      f"the rebuild keeps the values set on the modifiers ({sum(kept)}/{len(kept)})")
ok, msg = wiring.compare()
check(ok and not wiring.problems(), f"rebuilt geometry nodes are wired as recorded ({msg})")
H.unregister()
print("RESULT", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
