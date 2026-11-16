"""Headless test: a meadow needs room. A small plain plane becomes the hill; other small grounds are left alone and
warned about; a big ground is untouched.   blender -b --factory-startup --python tests/test_ground.py -- <out_dir>"""
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

H.register()
ctx = bpy.context
fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    return bpy.context.scene


def grass_share(name):
    """Share of the rendered frame that is grass green (the meadow is on screen, not only sky)."""
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 320, 180, 100
    sc.eevee.taa_render_samples = 8
    sc.render.filepath = f"{OUT}/{name}.png"
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(sc.render.filepath, check_existing=False)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[:, :, :3]
    bpy.data.images.remove(im)
    g = (a[:, :, 1] > a[:, :, 0] * 1.15) & (a[:, :, 1] > a[:, :, 2] * 1.15)
    return float(g.mean())


# 1. Blender's Add > Plane (2 m), one click: the hill, where the plane was, same object
sc = fresh()
bpy.ops.mesh.primitive_plane_add(size=2.0, location=(3.0, -2.0, 0.5))
plane = ctx.active_object
name = plane.name
check(bpy.ops.harappa.make_meadow() == {"FINISHED"}, "Make Anime Meadow on a 2 m plane runs")
ob = bpy.data.objects.get(name)
check(ob is not None and ob.get("hrp_hill") and len(ob.data.vertices) > 1000, "the plane became the rolling hill")
check(abs(H._ground_size(ob) - H.HILL_SIZE) < 1.0, f"the hill is {H.HILL_SIZE:.0f} m ({H._ground_size(ob):.1f})")
check((ob.location - Vector((3.0, -2.0, 0.5))).length < 1e-6, f"it stays where the plane was ({tuple(ob.location)})")
check(sc.camera is not None, "a camera looks at it")
share = grass_share("ground_plane2")
check(share > 0.25, f"grass fills the lower frame ({share:.0%} of the picture is grass)")

# 2. the same with Small Plane to Hill off: the plane stays a plane, and the panel / report say why it looks bare
sc = fresh()
bpy.ops.mesh.primitive_plane_add(size=2.0)
plane = ctx.active_object
check(bpy.ops.harappa.make_meadow(plane_to_hill=False) == {"FINISHED"}, "with Small Plane to Hill off it still runs")
check(len(plane.data.vertices) == 4 and not plane.get("hrp_hill"), "... and the plane is left as it is")
check(H._ground_size(plane) < H.SMALL_GROUND, "... which the panel flags as a small ground")

# 3. a small ground of the user's own (not a plain plane) is never reshaped
sc = fresh()
bpy.ops.mesh.primitive_plane_add(size=5.0)
own = ctx.active_object
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.subdivide(number_cuts=6)
bpy.ops.object.mode_set(mode="OBJECT")
nv = len(own.data.vertices)
check(bpy.ops.harappa.make_meadow() == {"FINISHED"}, "a small subdivided ground runs")
check(len(own.data.vertices) == nv and abs(H._ground_size(own) - 5.0) < 1e-4, "... and keeps its shape and size")

# 4. a big plane is a ground already: untouched
sc = fresh()
bpy.ops.mesh.primitive_plane_add(size=40.0)
big = ctx.active_object
check(bpy.ops.harappa.make_meadow() == {"FINISHED"} and len(big.data.vertices) == 4
      and abs(H._ground_size(big) - 40.0) < 1e-4, "a 40 m plane is used as it is")

# 5. nothing selected: the hill, as before
sc = fresh()
check(bpy.ops.harappa.make_meadow() == {"FINISHED"} and any(o.get("hrp_hill") for o in sc.objects),
      "nothing selected still makes the hill")

# messages are translated
bpy.context.preferences.view.language = "ja_JP"
ok = (H.i18n.report("The 2.0 m plane became a 40 m hill: a meadow needs room") != "The 2.0 m plane became a 40 m hill: a meadow needs room"
      and H.i18n.t("Small ground: only a patch of grass") != "Small ground: only a patch of grass")
bpy.context.preferences.view.language = "en_US"
check(ok, "the new messages are translated")

print("RESULT ALL PASS" if not fails else f"RESULT {len(fails)} FAIL: {fails}")
