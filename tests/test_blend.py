"""Headless test of Blend Into Meadow (blend.py): the user's own models painted like the meadow, and back.
blender -b --factory-startup --python tests/test_blend.py -- <out_dir>"""
import os
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
os.environ["HARAPPA_LOOKS_DIR"] = tempfile.mkdtemp(prefix="hrp_looks_")
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import harappa as H  # noqa: E402
from harappa import blend, shading  # noqa: E402
from harappa.util import VERSION_KEY  # noqa: E402

H.register()
sc = bpy.context.scene
ctx = bpy.context
fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def render(name, size=(320, 180)):
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.filepath = f"{OUT}/{name}.png"
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(sc.render.filepath, check_existing=False)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[:, :, :3]
    bpy.data.images.remove(im)
    return a


def principled(name, colour=None, image=None, normal=False, alpha_checker=False, glow=None):
    """A material as an importer makes it: Principled BSDF, maybe a base colour texture, normal map, cut-out, glow."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if colour is not None:
        p.inputs["Base Color"].default_value = colour
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])
    if normal:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nt.links.new(nz.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    if alpha_checker:
        ck = nt.nodes.new("ShaderNodeTexChecker")
        ck.inputs["Scale"].default_value = 4.0
        nt.links.new(ck.outputs["Fac"], p.inputs["Alpha"])
    if glow is not None:
        p.inputs["Emission Color"].default_value = glow
        p.inputs["Emission Strength"].default_value = 3.0
    return m


# --- a Harappa scene and a model in front of the camera, backlit -----------------------------------------------
bpy.ops.harappa.make_meadow()
meadow = ctx.active_object
H.setup_scene(ctx)
if sc.camera is None:
    H._add_camera(ctx, meadow)
cam = sc.camera
fwd = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
ok, hit, *_ = sc.ray_cast(ctx.evaluated_depsgraph_get(), cam.matrix_world.translation, fwd)
target = hit if ok else cam.matrix_world.translation + fwd * 15
cam.matrix_world.translation = target - fwd * 10.0               # close enough that the model fills the frame
cam.data.lens = 50
view = Vector((fwd.x, fwd.y, 0)).normalized()
side = view.cross(Vector((0, 0, 1))).normalized()
sun = bpy.data.objects[shading.SUN]
sun.rotation_euler = (-view * 0.55 + side * 0.65 + Vector((0, 0, -0.55))).normalized().to_track_quat("-Z", "Y").to_euler()

grid = bpy.data.images.new("hrp_test_grid", 64, 64)
grid.generated_type = "COLOR_GRID"
for o in [o for o in sc.objects if o.select_get()]:
    o.select_set(False)
root = bpy.data.objects.new("Model Root", None)                  # what a glTF import gives: an empty with meshes
sc.collection.objects.link(root)
root.location = target
bpy.ops.mesh.primitive_cube_add(size=2.4, location=target + Vector((0, 0, 1.2)), rotation=(0, 0, 0.5))
house = ctx.active_object
house.name = "House"
wall = principled("Wall", image=grid, normal=True)
house.data.materials.append(wall)
bpy.ops.mesh.primitive_cone_add(radius1=1.9, depth=1.4, location=target + Vector((0, 0, 3.1)), rotation=(0, 0, 0.5))
roof = ctx.active_object
roof.name = "Roof"
roof_m = principled("Roof Tiles", colour=(0.7, 0.12, 0.06, 1))
roof.data.materials.append(roof_m)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=target + side * 2.3 + Vector((0, 0, 0.5)))
ball = ctx.active_object
ball.name = "Bare Ball"                                           # no material at all
bpy.ops.mesh.primitive_plane_add(size=1.4, location=target - side * 2.2 + Vector((0, 0, 0.9)), rotation=(1.5708, 0, 0.3))
fence = ctx.active_object
fence.name = "Fence"
fence.data.materials.append(principled("Fence Cutout", colour=(0.5, 0.35, 0.2, 1), alpha_checker=True))
bpy.ops.mesh.primitive_cube_add(size=0.35, location=target + Vector((0, 0, 1.0)) - view * 1.3)
lamp = ctx.active_object
lamp.name = "Lamp"
lamp.data.materials.append(principled("Lamp Glow", colour=(0.3, 0.3, 0.3, 1), glow=(1.0, 0.8, 0.3, 1)))
twin = house.copy()                                               # shares the wall material
twin.data = house.data.copy()
twin.name = "House Twin"
twin.location = target + side * 6.0 + Vector((0, 0, 1.2))
sc.collection.objects.link(twin)
for o in (house, roof, ball, fence, lamp):
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()
parts = [house, roof, ball, fence, lamp, twin]
originals = {o.name: [s.material.name if s.material else None for s in o.material_slots] for o in parts}

# --- the problem it fixes, and the fix --------------------------------------------------------------------------
for o in parts:
    o.hide_render = True
r0 = render("blend_0_without")
for o in parts:
    o.hide_render = False
r1 = render("blend_1_as_imported")
mask = np.abs(r1 - r0).max(axis=2) > 0.03
lum = lambda a: a @ np.array([0.2126, 0.7152, 0.0722])          # noqa: E731
check(mask.mean() > 0.05, f"the model fills part of the frame ({mask.mean():.0%})")
dark1 = float((lum(r1)[mask] < 0.03).mean())

bpy.ops.object.select_all(action="DESELECT")
root.select_set(True)
twin.select_set(True)
ctx.view_layer.objects.active = root
check(bpy.ops.harappa.blend_in.poll(), "Blend Into Meadow is offered for an imported model's empty")
check(bpy.ops.harappa.blend_in() == {"FINISHED"}, "Blend Into Meadow runs")
for o in parts:
    for s in o.material_slots:
        check(blend.is_blended(s.material), f"{o.name}: its material is blended ({s.material.name if s.material else None})")
check(house.material_slots[0].material is twin.material_slots[0].material,
      "a material shared by two models gets one painted copy")
check(house.material_slots[0].material.get(blend.TAG) == wall, "the copy points at the original")
check(len(ball.material_slots) == 1 and ball.material_slots[0].material.name == blend.PLAIN_NAME,
      "a model with no material gets the plain painted one")
fm = fence.material_slots[0].material
check(any(n.type == "BSDF_TRANSPARENT" for n in fm.node_tree.nodes), "a cut-out keeps its holes")
lm = lamp.material_slots[0].material
check(any(n.label == "glow" for n in lm.node_tree.nodes), "a glowing material still glows")
wm = house.material_slots[0].material
surf = next(n for n in wm.node_tree.nodes if n.type == "OUTPUT_MATERIAL").inputs["Surface"].links[0].from_node
check(surf.type in ("EMISSION", "MIX_SHADER"), f"the painted copy renders an emission, not the Principled ({surf.type})")
pal_links = {l.from_socket.name for n in wm.node_tree.nodes if n.type == "MIX" and n.label in ("lit", "shade", "deep")
             for b in n.inputs if b.name == "B" and b.type == "RGBA" for l in b.links}
check(pal_links == {"cloud_lit", "flower_shade"}, f"light and shade tints are the season's, from the palette ({sorted(pal_links)})")

r2 = render("blend_2_blended")
dark2 = float((lum(r2)[mask] < 0.03).mean())
check(dark1 > 0.05 and dark2 < 0.01, f"no black shadows any more ({dark1:.1%} -> {dark2:.1%} of the model near black)")
rest = float(np.abs(r2 - r1)[~mask].mean())
check(rest < 0.004, f"the rest of the picture is untouched (mean difference {rest:.4f})")

sc.harappa.season = "GOLDEN"
r3 = render("blend_3_golden")
shift = float(np.abs(r3[mask].mean(axis=0) - r2[mask].mean(axis=0)).max())
check(shift > 0.03, f"the model's colours follow the season ({shift:.3f})")
sc.harappa.season = "SUMMER"

check(bpy.ops.harappa.blend_in() == {"CANCELLED"}, "blending twice changes nothing")

# --- survives saving, and an update of the add-on ------------------------------------------------------------
path = os.path.join(tempfile.mkdtemp(prefix="hrp_blend_"), "blend.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
sc = bpy.context.scene
ctx = bpy.context
house, twin = bpy.data.objects["House"], bpy.data.objects["House Twin"]
wm = house.material_slots[0].material
check(wm.get(blend.TAG) is not None and wm[blend.TAG].name == "Wall", "the link to the original is saved with the file")
wm[VERSION_KEY] = 1                                              # as if made by an older Harappa
stale_name = wm.name
shading._rebuild_stale()
nm = house.material_slots[0].material
check(nm.get(VERSION_KEY) == shading.SHADER_VER and nm.get(blend.TAG).name == "Wall" and nm.name == stale_name
      and twin.material_slots[0].material is nm, f"an update repaints the copy from its original ({stale_name} -> {nm.name})")

# --- back to the original look ---------------------------------------------------------------------------------
root = bpy.data.objects["Model Root"]
bpy.ops.object.select_all(action="DESELECT")
root.select_set(True)
bpy.data.objects["House Twin"].select_set(True)
ctx.view_layer.objects.active = root
check(bpy.ops.harappa.blend_out() == {"FINISHED"}, "Original Look runs")
back = {n: [s.material.name if s.material else None for s in bpy.data.objects[n].material_slots] for n in originals}
check(back == originals, f"every model has its own materials back ({back})")
left = [m.name for m in bpy.data.materials if blend.is_blended(m)]
check(not left, f"no painted copies are left in the file ({left})")
check(not bpy.ops.harappa.blend_out.poll(), "Original Look is not offered once restored")
check(not blend.targets([bpy.data.objects[n] for n in ("Meadow",) if n in bpy.data.objects]),
      "the meadow itself is never blended")

print("RESULT ALL PASS" if not fails else f"RESULT {len(fails)} FAIL: {fails}")
