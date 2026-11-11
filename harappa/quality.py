# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Detail levels: one switch that trades richness for speed.

A level only writes the separate 'Detail' inputs and a few render settings. It never touches the densities and
sizes the user set, so switching back and forth loses nothing, and a lower level is always the same picture
with less in it."""
import bpy

from . import build, cumulus
from .util import mod_input

# grass / flower amount, cloud width per voxel, render samples, shadow rays
LEVELS = {
    "FAST": dict(grass=0.45, flowers=0.5, cloud=38.0, samples=8, rays=1),
    "BALANCED": dict(grass=1.0, flowers=1.0, cloud=56.0, samples=16, rays=2),
    "BEST": dict(grass=1.6, flowers=1.5, cloud=84.0, samples=32, rays=3),
}


def cloud_quality(scene):
    return LEVELS[scene.harappa.detail_level]["cloud"] / 56.0


def apply(scene, level=None, render=False):
    """Bring what Harappa made in the scene to the level (default: the scene's own).

    Only inputs that belong to the Detail Level are written ('Detail' on grass and flowers, 'Quality' on clouds).
    The render samples are the user's: they are set only when the user switches the level (render=True)."""
    lv = LEVELS[level or scene.harappa.detail_level]
    for ob in scene.objects:
        for mod in ob.modifiers:
            if mod.type != "NODES" or mod.node_group is None:
                continue
            try:
                if mod.name == build.GRASS_MOD or mod.name == "Harappa Fringe":
                    mod_input(mod, "Detail", lv["grass"])
                elif mod.name == build.FLOWER_MOD:
                    mod_input(mod, "Detail", lv["flowers"])
                elif mod.name == cumulus.MOD:
                    mod_input(mod, "Quality", lv["cloud"] / 56.0)
                else:
                    continue
            except KeyError:
                continue                               # a modifier from before this input existed
            ob.update_tag()                            # a value set from Python does not re-evaluate by itself
    if not render:
        return
    ee = scene.eevee
    for attr, val in (("taa_render_samples", lv["samples"]), ("shadow_ray_count", lv["rays"])):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except (TypeError, AttributeError):
                pass


def update(self, context):
    apply(context.scene, self.detail_level, render=True)
