# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Avoid Objects: grass and flowers make room for the objects in one collection (characters, props, houses).

The work is done by the 'Avoid' inputs of the grass and flower modifiers (scatter._avoid): distance-based and
continuous, so nothing pops when an avoided object moves. Here: which collection, which objects may go in (and
why some may not), and the settings, written to every meadow of the scene at once."""
import bpy

from . import build, cumulus
from .util import mod_input

TAG = "hrp_avoid"
NAME = "Harappa Avoid"
HEAVY_FACES = 50_000
SETTINGS = (("Avoid Margin", "avoid_margin"), ("Avoid Floor", "avoid_floor"), ("Avoid Box", "avoid_box"),
            ("Avoid Reach", "avoid_reach"))


def meadows(scene):
    return [o for o in scene.objects if o.type == "MESH" and o.modifiers.get(build.GRASS_MOD) is not None]


def _mods(scene):
    for ob in meadows(scene):
        for name in (build.GRASS_MOD, build.FLOWER_MOD):
            m = ob.modifiers.get(name)
            if m is not None and m.node_group is not None:
                yield m


def current(scene):
    """The collection the scene's meadows avoid (the panel's choice, else the first meadow's)."""
    col = scene.harappa.avoid_collection
    if col is not None:
        return col
    for m in _mods(scene):
        try:
            col = mod_input(m, "Avoid")
        except KeyError:
            continue
        if col is not None:
            return col
    return None


def ensure(scene):
    """The scene's avoid collection, made when there is none, and set on every meadow. It is not linked into the
    scene: objects stay where they are and are only listed in it."""
    col = current(scene)
    if col is None:
        col = next((c for c in bpy.data.collections if c.get(TAG) == scene.name), None)
        if col is None:
            col = bpy.data.collections.new(NAME)
            col[TAG] = scene.name
    if scene.harappa.avoid_collection != col:
        scene.harappa.avoid_collection = col           # the update writes it to the meadows
    else:
        assign(scene, col)
    return col


def assign(scene, col):
    for m in _mods(scene):
        try:
            if mod_input(m, "Avoid") != col:
                mod_input(m, "Avoid", col)
                m.id_data.update_tag()
        except KeyError:
            pass


def _refers_to(ob, targets):
    """Does ob read one of the targets (a modifier or constraint pointing at it)? Then avoiding ob would make a
    loop: the meadow would wait for ob and ob for the meadow."""
    for m in ob.modifiers:
        if m.type == "NODES" and m.node_group is not None:
            for it in m.node_group.interface.items_tree:
                if getattr(it, "item_type", "") == "SOCKET" and it.in_out == "INPUT" and it.socket_type == "NodeSocketObject":
                    try:
                        if mod_input(m, it.name) in targets:
                            return True
                    except (KeyError, TypeError):
                        pass
        for p in m.bl_rna.properties:
            if p.type == "POINTER" and getattr(p, "fixed_type", None) is not None and p.fixed_type.identifier == "Object":
                if getattr(m, p.identifier, None) in targets:
                    return True
    for c in getattr(ob, "constraints", []):
        if getattr(c, "target", None) in targets:
            return True
    return False


def check(scene, ob):
    """None when ob can be avoided, else (reason, replacement objects or [])."""
    ms = meadows(scene)
    if ob in ms or ob.get("hrp_ground"):
        return "A meadow can't avoid itself", []
    if ob.get("hrp_canopy"):
        trunk = [c for c in (ob.parent.children if ob.parent else []) if c.type == "MESH" and not c.get("hrp_canopy")]
        return "Tree crowns hang above the grass and would clear it under them: the trunk is added instead", trunk
    if "hrp_tree" in ob:
        trunk = [c for c in ob.children if c.type == "MESH" and not c.get("hrp_canopy")]
        return "Trees avoid with their trunk", trunk
    if ob.get(cumulus.TAG) or ob.get("hrp_ridge") or ob.get("hrp_far_hills") or ob.get("hrp_clouds"):
        return "Clouds and distant mountains never touch the grass", []
    if ob.name.startswith("HRP ") or ob.get("hrp_card"):
        return "Harappa's own parts can't be avoided", []
    if ob.type != "MESH":
        return "Only mesh objects (for a character, pick its mesh, not the armature)", []
    if _refers_to(ob, set(ms)):
        return "This object follows the meadow (a modifier or constraint points at it); avoiding it would make a loop", []
    return None


def add(context, obs):
    """Put objects into the avoid collection. Returns (added names, [(name, reason)], heavy?)."""
    scene = context.scene
    col = ensure(scene)
    added, skipped, heavy = [], [], False
    todo = list(obs)
    seen = set()
    while todo:
        ob = todo.pop(0)
        if ob in seen:
            continue
        seen.add(ob)
        why = check(scene, ob)
        if why is not None:
            reason, instead = why
            skipped.append((ob.name, reason))
            todo.extend(instead)
            continue
        if col.objects.get(ob.name) is None:
            col.objects.link(ob)
            added.append(ob.name)
            if len(ob.data.polygons) > HEAVY_FACES:
                heavy = True
    for m in _mods(scene):
        m.id_data.update_tag()
    return added, skipped, heavy


def remove(context, obs):
    col = current(context.scene)
    n = 0
    if col is None:
        return 0
    for ob in obs:
        if col.objects.get(ob.name) is ob:
            col.objects.unlink(ob)
            n += 1
    for m in _mods(context.scene):
        m.id_data.update_tag()
    return n


# --------------------------------------------------------------------------------------------------
# panel settings: read the first meadow, write all of them
# --------------------------------------------------------------------------------------------------
def _get(name, default):
    def g(self):
        for m in _mods(self.id_data):
            try:
                v = mod_input(m, name)
                return bool(v) if isinstance(default, bool) else float(v)
            except KeyError:
                continue
        return default
    return g


def _set(name):
    def s(self, value):
        for m in _mods(self.id_data):
            try:
                mod_input(m, name, value)
            except KeyError:
                continue
            m.id_data.update_tag()
    return s


def _upd_collection(self, context):
    assign(self.id_data, self.avoid_collection)


def props():
    return {
        "avoid_collection": bpy.props.PointerProperty(
            name="Avoid Collection", type=bpy.types.Collection, update=_upd_collection,
            description="Grass and flowers make room for the objects in this collection"),
        "avoid_margin": bpy.props.FloatProperty(
            name="Clear Space", min=0.0, max=10.0, subtype="DISTANCE", get=_get("Avoid Margin", 0.16),
            set=_set("Avoid Margin"), description="How far from the object the grass starts getting shorter"),
        "avoid_floor": bpy.props.FloatProperty(
            name="Shortest Grass", min=0.0, max=1.0, subtype="FACTOR", get=_get("Avoid Floor", 0.3),
            set=_set("Avoid Floor"), description="How short grass gets right next to the object"),
        "avoid_box": bpy.props.BoolProperty(
            name="Use Simple Box", get=_get("Avoid Box", False), set=_set("Avoid Box"),
            description="Faster: treats each object as a box. Good for heavy models or crowds"),
        "avoid_reach": bpy.props.FloatProperty(
            name="Reach Above", min=0.0, max=100000.0, subtype="DISTANCE", get=_get("Avoid Reach", 100.0),
            set=_set("Avoid Reach"),
            description="Grass under an avoided object is cleared up to this height below it: lower it for a bridge "
                        "or a branch the grass should grow under"),
    }
