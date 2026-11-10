# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Harappa in one command. Written for AI agents; humans just ask their agent.

Install (once, permanent):
  blender -b --python harappa_agent.py -- --install harappa-x.y.z.zip
  (never add --factory-startup here: the install is saved into the user's preferences)

A whole anime landscape from nothing:
  blender -b --python harappa_agent.py -- --meadow --trees 8 --season SUMMER --render preview.png --save meadow.blend

Grass on the human's own ground object, plus one tree:
  blender -b scene.blend --python harappa_agent.py -- --meadow --objects Ground --tree ROUND --at 2,3 --save out.blend

Options:
  --install ZIP         install + enable the extension from a zip (saved to user preferences)
  --meadow              grow grass + flowers on --objects (or on a new hill when no objects are given)
  --objects A,B         ground objects for --meadow / meshes for --foliage
  --no-flowers          grass only
  --density N           grass tufts per m² (default 40)        --grass-height M   grass height in metres (0.35)
  --path X0,Y0:X1,Y1:…  paint a bare path through the meadow along these world points (width --path-width, 1.2 m)
  --trees N             plant N trees over the meadow (mixed shapes, off the path)
  --tree SHAPE          add one tree: ROUND TALL WIDE BUSH CONIFER (repeatable; positions from --at, repeatable)
  --at X,Y              where the matching --tree stands (it is dropped onto the ground)
  --tree-height M       tree height in metres (default 5)        --blossom F   share of blossoms 0..1
  --foliage             cover --objects with anime leaf dabs (hedges, bushes)
  --clouds N            (re)build N painted cumulus clouds in front of the camera (0 removes them;
                        a new --meadow hill gets 6 automatically)
  --season NAME         SUMMER SPRING GOLDEN AUTUMN NIGHT MISTY
  --style NAME          ANIME PAINTERLY CRISP SOFT
  --variation N         re-roll colours / clumps / flowers / sun / tree tints (0 = off)
  --shuffle             pick a random variation (printed, so it can be repeated with --variation N)
  --set KEY=VALUE       any look setting, repeatable, e.g. --set clump_size=2.5 --set sun_elevation=20
  --wind S              wind strength multiplier for every meadow and tree (1 = default, 0 = still)
  --frame-camera        add a "Harappa Camera" looking over the meadow (the human's camera is left alone)
  --frame F             frame to render (the wind moves over time)
  --preview-size PCT    render size in % of the scene resolution, e.g. 50 for quick previews
  --render PATH         render a PNG          --save PATH   save the .blend
  --revert              remove Harappa grass/flowers/foliage from every object
  --ui-language L       panel language AUTO EN JA ZH KO (saved to user preferences)
  --list                print seasons, styles, tree shapes and settings, then exit
Exit code 0 on success; the last line printed starts with "HARAPPA OK" or "HARAPPA ERROR".
"""

import math
import os
import random
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None, flag=False):
    if name not in argv:
        return default
    if flag:
        return True
    i = argv.index(name)
    return argv[i + 1] if i + 1 < len(argv) else default


def args(name):
    return [argv[i + 1] for i, a in enumerate(argv) if a == name and i + 1 < len(argv)]


def fail(msg):
    print("HARAPPA ERROR", msg)
    sys.exit(1)


def installed():
    return "harappa" in bpy.types.Scene.bl_rna.properties


def install(zip_path):
    zip_path = os.path.abspath(zip_path)
    if not os.path.isfile(zip_path):
        fail(f"zip not found: {zip_path}")
    if bpy.app.factory_startup:
        fail("do not use --factory-startup when installing; it would overwrite the user's preferences")
    bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    if not installed():
        import addon_utils
        addon_utils.enable("bl_ext.user_default.harappa", default_set=True, persistent=True)
    bpy.ops.wm.save_userpref()
    if not installed():
        fail("install finished but the add-on did not load")
    print("Harappa installed:", zip_path)


def pkg():
    """The installed add-on module (bl_ext.<repo>.harappa or a dev checkout named harappa)."""
    for name, mod in list(sys.modules.items()):
        if name.endswith("harappa") and hasattr(mod, "tree_root") and hasattr(mod, "build"):
            return mod
    fail("Harappa module not found")


def parse_value(prop, text):
    rna = bpy.types.Scene.bl_rna.properties["harappa"].fixed_type.bl_rna.properties[prop]
    if rna.type == "BOOLEAN":
        return text.lower() in ("1", "true", "yes", "on")
    if rna.type == "INT":
        return int(float(text))
    if rna.type == "ENUM":
        return text.upper()
    if getattr(rna, "is_array", False):
        if text.startswith("#"):
            return pkg().srgb(text)
        return tuple(float(x) for x in text.split(","))
    return float(text)


def objects_named(scene, names):
    objs = [scene.objects.get(n) for n in names]
    missing = [n for n, o in zip(names, objs) if o is None]
    if missing:
        fail(f"objects not found: {', '.join(missing)}")
    return objs


def select_only(ctx, objs):
    for o in ctx.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    if objs:
        ctx.view_layer.objects.active = objs[0]


def paint_path(ground, pts, width):
    H = pkg()
    me = ground.data
    attr = H.build.ensure_mask(me)
    mw = ground.matrix_world
    segs = list(zip(pts[:-1], pts[1:]))
    cols = [0.0] * (len(me.vertices) * 4)
    attr.data.foreach_get("color", cols)
    for v in me.vertices:
        p = mw @ v.co
        best = 1e9
        for a, b in segs:
            ab = b - a
            t = max(0.0, min(1.0, (Vector((p.x, p.y)) - a).dot(ab) / max(ab.length_squared, 1e-9)))
            best = min(best, (Vector((p.x, p.y)) - (a + ab * t)).length)
        m = min(1.0, max(0.0, (best - width * 0.5) / (width * 0.4)))
        i = v.index * 4
        cols[i] = cols[i + 1] = cols[i + 2] = min(cols[i], m)
    attr.data.foreach_set("color", cols)
    me.update()


def frame_camera(scene, ground):
    H = pkg()
    cam = scene.objects.get("Harappa Camera")
    if cam is not None:
        bpy.data.objects.remove(cam)
    return H._add_camera(bpy.context, ground)


def main():
    zip_path = arg("--install")
    if zip_path and not installed():
        install(zip_path)
    elif zip_path:
        print("Harappa already installed")
    if not installed():
        fail("Harappa is not installed (run with --install harappa-x.y.z.zip)")
    S = bpy.types.Scene.bl_rna.properties["harappa"].fixed_type.bl_rna.properties
    ctx = bpy.context

    lang = arg("--ui-language")
    if lang:
        lang = lang.upper()
        if lang not in ("AUTO", "EN", "JA", "ZH", "KO"):
            fail("--ui-language must be AUTO, EN, JA, ZH or KO")
        if bpy.app.factory_startup:
            fail("do not use --factory-startup with --ui-language; it is saved into the user's preferences")
        addon = next((a for k, a in ctx.preferences.addons.items() if k.endswith("harappa")), None)
        if addon is None or addon.preferences is None:
            fail("Harappa preferences not found")
        addon.preferences.ui_language = lang
        bpy.ops.wm.save_userpref()
        print("panel language:", lang)

    if arg("--list", flag=True):
        for key in ("season", "style", "new_shape"):
            for it in S[key].enum_items:
                print(f"{key:9s} {it.identifier:10s} {it.name:18s} {it.description}")
        skip = {"rna_type", "name", "season", "style", "new_shape", "mask_paint"}
        print("settings:", " ".join(k for k in S.keys() if k not in skip))
        print("HARAPPA OK listed")
        return

    scene = ctx.scene
    H = pkg()
    s = scene.harappa
    if ctx.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    if arg("--revert", flag=True):
        select_only(ctx, list(scene.objects))
        bpy.ops.harappa.revert()
        report = "reverted"
    else:
        job = ("--meadow", "--trees", "--tree", "--foliage", "--clouds", "--season", "--style", "--variation",
               "--shuffle", "--set", "--wind", "--path", "--save", "--render")
        if not any(a in argv for a in job):
            print("HARAPPA OK", "installed" if zip_path else "nothing to do")
            return
        names = arg("--objects")
        objs = objects_named(scene, names.split(",")) if names else []
        ground = None
        if arg("--meadow", flag=True):
            select_only(ctx, objs)
            if not objs:
                for o in list(ctx.selected_objects):
                    o.select_set(False)
            kw = {"flowers": not arg("--no-flowers", flag=True)}
            if arg("--density"):
                kw["density"] = float(arg("--density"))
            if arg("--grass-height"):
                kw["height"] = float(arg("--grass-height"))
            if bpy.ops.harappa.make_meadow(**kw) != {"FINISHED"}:
                fail("Make Anime Meadow did not finish")
            ground = ctx.active_object if not objs else objs[0]
        if ground is None:
            ground = next((o for o in scene.objects if H.meadow_of(o)), None)
        if arg("--path"):
            if ground is None:
                fail("--path needs a meadow (add --meadow)")
            pts = [Vector(tuple(float(x) for x in p.split(","))) for p in arg("--path").split(":")]
            if len(pts) < 2:
                fail("--path needs at least two points X,Y:X,Y")
            paint_path(ground, pts, float(arg("--path-width", 1.2)))
        if arg("--foliage", flag=True):
            if not objs:
                fail("--foliage needs --objects")
            select_only(ctx, objs)
            bpy.ops.harappa.make_foliage()
        th = float(arg("--tree-height", 5.0))
        if arg("--blossom") is not None:
            s.new_blossom = float(arg("--blossom"))
        if arg("--trees"):
            if ground is None:
                fail("--trees needs a meadow (add --meadow or --objects of a meadow)")
            select_only(ctx, [ground])
            bpy.ops.harappa.plant_trees(count=int(arg("--trees")), height=th, seed=random.randint(0, 99999))
        ats = args("--at")
        for i, shape in enumerate(args("--tree")):
            shape = shape.upper()
            if shape not in ("ROUND", "TALL", "WIDE", "BUSH", "CONIFER"):
                fail(f"unknown tree shape {shape!r} (ROUND TALL WIDE BUSH CONIFER)")
            if i < len(ats):
                x, y = (float(v) for v in ats[i].split(","))
                scene.cursor.location = (x, y, 0.0)
            bpy.ops.harappa.add_tree(shape=shape, height=th if shape != "BUSH" else th * 0.4,
                                     seed=random.randint(0, 99999))
        if arg("--clouds") is not None:
            bpy.ops.harappa.add_clouds(count=int(arg("--clouds")), seed=random.randint(0, 99999))
        try:
            if arg("--season"):
                s.season = arg("--season").upper()
            if arg("--style"):
                s.style = arg("--style").upper()
            if arg("--shuffle", flag=True):
                s.variation = random.randint(1, 99999)
            elif arg("--variation") is not None:
                s.variation = int(arg("--variation"))
            for kv in args("--set"):
                k, _, v = kv.partition("=")
                if k not in S.keys():
                    fail(f"unknown setting {k!r} (see --list)")
                setattr(s, k, parse_value(k, v))
        except TypeError as err:
            fail(f"{err} (see --list for valid names)")
        if arg("--wind") is not None:
            f = float(arg("--wind"))
            for o in scene.objects:
                for m in o.modifiers:
                    if m.type == "NODES" and m.name.startswith("Harappa"):
                        try:
                            base = m.get("hrp_wind_base")
                            cur = H.mod_input(m, "Wind Strength")
                            if base is None:
                                m["hrp_wind_base"] = base = cur
                            H.mod_input(m, "Wind Strength", base * f)
                        except (KeyError, TypeError):
                            pass
        if not H._scene_ready(scene):
            H.setup_scene(ctx)
        n_trees = len([o for o in scene.objects if "hrp_tree" in o])
        report = (f"season {s.season}, style {s.style}, variation {s.variation}, "
                  f"{len([o for o in scene.objects if H.meadow_of(o)])} meadow(s), {n_trees} tree(s)")
    print(report)

    render = arg("--render")
    if render:
        if arg("--frame-camera", flag=True) or scene.camera is None:
            g = next((o for o in scene.objects if H.meadow_of(o)), None)
            if g is not None:
                frame_camera(scene, g)
        if arg("--frame"):
            scene.frame_set(int(arg("--frame")))
        if arg("--preview-size"):
            scene.render.resolution_percentage = int(float(arg("--preview-size")))
        scene.render.filepath = os.path.abspath(render)
        bpy.ops.render.render(write_still=True)
        print("preview:", scene.render.filepath)
    save = arg("--save")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(save))
        print("saved:", os.path.abspath(save))
    print("HARAPPA OK", report)


main()
