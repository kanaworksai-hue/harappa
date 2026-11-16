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
NOTES = {}                   # scene name -> [(object, reason)] of the last Avoid Selected, shown in the panel
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
        if len(ms) > 1:
            return "Meadows can't avoid themselves or each other", []
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
    if ob.type == "ARMATURE":
        meshes = [o for o in scene.objects if o.type == "MESH" and (o.parent == ob or any(
            m.type == "ARMATURE" and m.object == ob for m in o.modifiers))]
        if meshes:
            return "An armature is avoided through its meshes: they are added instead", meshes
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
    prune(scene)
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
    NOTES[scene.name] = skipped[:6]
    return added, skipped, heavy


def prune(scene):
    """Objects deleted from the scene stay alive inside the (unlinked) avoid collection and would go on clearing
    grass: take them out. Cheap, called from the depsgraph handler."""
    col = scene.harappa.avoid_collection
    if col is None or not len(col.objects):
        return 0
    gone = [o for o in col.objects if not o.users_scene]
    for o in gone:
        col.objects.unlink(o)
    if gone:
        for m in _mods(scene):
            m.id_data.update_tag()
    return len(gone)


def collection_ok(col):
    """The collection picker only offers collections that hold nothing the grass must not avoid."""
    for ob in col.all_objects:
        if (ob.get("hrp_ground") or ob.get("hrp_canopy") or ob.get(cumulus.TAG) or ob.get("hrp_ridge")
                or ob.get("hrp_far_hills") or (ob.type == "MESH" and ob.modifiers.get(build.GRASS_MOD))):
            return False
    return True


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
def _get(name, default, scale=1.0):
    def g(self):
        for m in _mods(self.id_data):
            try:
                v = mod_input(m, name)
                return bool(v) if isinstance(default, bool) else float(v) * scale
            except KeyError:
                continue
        return default * scale if not isinstance(default, bool) else default
    return g


def _set(name, scale=1.0):
    def s(self, value):
        for m in _mods(self.id_data):
            try:
                mod_input(m, name, value / scale if not isinstance(value, bool) else value)
            except KeyError:
                continue
            m.id_data.update_tag()
    return s


def _upd_collection(self, context):
    sc = self.id_data
    col = self.avoid_collection
    if col is not None and not collection_ok(col):     # set from a script or the CLI: the picker's rule still holds
        prev = bpy.data.collections.get(sc.get("hrp_avoid_prev", ""))
        print(f"[Harappa] Avoid collection {col.name!r} holds Harappa scenery: kept {prev.name if prev else None!r}")
        self.avoid_collection = prev if prev is not None and collection_ok(prev) else None
        return
    sc["hrp_avoid_prev"] = col.name if col is not None else ""
    assign(sc, col)


def _poll_collection(self, col):
    return collection_ok(col)


def props():
    return {
        "avoid_collection": bpy.props.PointerProperty(
            name="Avoid Collection", type=bpy.types.Collection, update=_upd_collection, poll=_poll_collection,
            options=set(),
            description="Grass and flowers make room for the objects in this collection (collections that hold a "
                        "meadow, trees, clouds or mountains are not offered)"),
        "avoid_margin": bpy.props.FloatProperty(
            name="Clear Space", min=0.0, max=10.0, subtype="DISTANCE", get=_get("Avoid Margin", 0.16),
            set=_set("Avoid Margin"), options=set(),
            description="How far from the object the grass starts getting shorter"),
        "avoid_floor": bpy.props.FloatProperty(
            name="Shortest Grass", min=0.0, max=100.0, subtype="PERCENTAGE", get=_get("Avoid Floor", 0.3, 100.0),
            set=_set("Avoid Floor", 100.0), options=set(),
            description="How short grass gets right next to the object, as a share of its normal height"),
        "avoid_box": bpy.props.BoolProperty(
            name="Use Simple Box", get=_get("Avoid Box", False), set=_set("Avoid Box"), options=set(),
            description="Faster: treats each object as a box. Good for heavy models or crowds"),
        "avoid_reach": bpy.props.FloatProperty(
            name="Reaches Down From", min=0.0, max=100000.0, subtype="DISTANCE", get=_get("Avoid Reach", 100.0),
            set=_set("Avoid Reach"), options=set(),
            description="Grass under an avoided object (a bridge, a bench, a branch) grows only up to just below "
                        "it. Objects higher above the ground than this leave the grass under them alone"),
    }
