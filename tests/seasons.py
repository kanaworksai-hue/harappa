"""Small-picture regression test: the default landscape in each of the six seasons against recorded renders.

Catches what the other tests cannot see: a look that changed although every operator still succeeds (clouds
without shading, a missing sky, grass in the wrong colour). The pictures are compared block by block with a
tolerance, so they survive EEVEE's small differences between Blender versions and GPUs.

After changing the look on purpose, record new pictures:  HARAPPA_UPDATE_BASELINE=1 blender -b ... test_generic.py
"""
import os
import shutil

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "baseline")
SIZE = (480, 270)
BLOCK = 10                 # pixels; a block's mean colour is what gets compared
# Measured on the default scene: Blender 5.2 against 5.3 differs by at most 0.001 per block, the same Blender
# twice by 0. Clouds that lost their shading (the 5.3 bug) move 4-6 % of the blocks by 0.05-0.25.
MEAN_TOL = 0.004           # mean block difference over the whole picture (0..1, display values)
BLOCK_TOL = 0.03           # a block further off than this counts as changed ...
CHANGED_TOL = 0.01         # ... and at most this share of the blocks may be


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[:, :, :3]
    bpy.data.images.remove(im)
    return a


def blocks(img):
    h, w = img.shape[0] // BLOCK * BLOCK, img.shape[1] // BLOCK * BLOCK
    return img[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK, 3).mean(axis=(1, 3))


def difference(a, b):
    """(mean block difference, share of blocks that changed) between two pictures of the same size."""
    d = np.abs(blocks(a) - blocks(b)).max(axis=2)
    return float(d.mean()), float((d > BLOCK_TOL).mean())


def build():
    """The landscape a new user gets: Make Anime Meadow on an empty scene, plus six trees."""
    sc = bpy.context.scene
    bpy.ops.harappa.make_meadow()
    bpy.ops.harappa.plant_trees(count=6, seed=2)
    sc.render.resolution_x, sc.render.resolution_y = SIZE
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.frame_set(1)
    return sc


def compare(sc, season, path):
    """Render the scene to path and compare with the recorded picture of that season: (ok, message)."""
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    ref = os.path.join(BASELINE, f"season_{season.lower()}.png")
    if not os.path.exists(ref):
        return False, f"tests/baseline/season_{season.lower()}.png is missing"
    mean, changed = difference(load(path), load(ref))
    return (mean < MEAN_TOL and changed < CHANGED_TOL,
            f"mean diff {mean:.4f}, {changed * 100:.2f}% of blocks changed")


def run(out_dir, seasons, check, update=False):
    """Render every season into out_dir and compare with tests/baseline/season_<name>.png."""
    sc = build()
    for season in seasons:
        sc.harappa.season = season
        path = os.path.join(out_dir, f"season_small_{season.lower()}.png")
        if update:
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            os.makedirs(BASELINE, exist_ok=True)
            shutil.copyfile(path, os.path.join(BASELINE, f"season_{season.lower()}.png"))
            check(True, f"season {season}: baseline picture recorded")
            continue
        ok, msg = compare(sc, season, path)
        check(ok, f"season {season} looks like its baseline ({msg})")
    sc.harappa.season = "SUMMER"
    return sc
