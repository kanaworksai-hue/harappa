# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""This object's colour: a per-object hue / saturation / brightness shift and an own colour, on any Harappa object.

Every Harappa material reads two object attributes in HRP Grade:
  hrp_look  (hue, saturation, brightness) offsets, 0 = no change
  hrp_own   (r, g, b, amount) an own colour, mixed in at the object's own light and shade
They are composed here from three sources, so none of them overwrites another:
  hrp_hue / hrp_value      what Shuffle (the variation) and the tree shape set
  hrp_user_hsv             what the user set in the panel   (h, s, v)
  hrp_user_tint            the user's own colour            (r, g, b linear, amount)
"""
import bpy

from . import cumulus

USER_HSV = "hrp_user_hsv"
USER_TINT = "hrp_user_tint"


def _tree_root(ob):
    while ob is not None:
        if "hrp_tree" in ob:
            return ob
        ob = ob.parent
    return None


def is_harappa(ob):
    if ob is None:
        return False
    from . import build
    return bool(_tree_root(ob) is not None or ob.get("hrp_canopy") or ob.get(cumulus.TAG) or ob.get("hrp_ridge")
                or ob.get("hrp_far_hills") or (ob.type == "MESH" and ob.modifiers.get(build.GRASS_MOD)))


def targets(ob):
    """The objects one panel edit writes to: a whole tree (crown and trunk) or the object itself."""
    if not is_harappa(ob):
        return []
    root = _tree_root(ob)
    if root is not None:
        return [root] + [c for c in root.children if c.type == "MESH"]
    return [ob]


def user(ob):
    """(h, s, v, (r, g, b), amount) the user set on this object."""
    h, s, v = (list(ob.get(USER_HSV, (0.0, 0.0, 0.0))) + [0.0, 0.0, 0.0])[:3]
    t = (list(ob.get(USER_TINT, (1.0, 1.0, 1.0, 0.0))) + [1.0, 1.0, 1.0, 0.0])[:4]
    return float(h), float(s), float(v), tuple(float(x) for x in t[:3]), float(t[3])


def overridden(ob):
    h, s, v, _c, a = user(ob)
    return any(abs(x) > 1e-6 for x in (h, s, v, a))


def compose(ob):
    """Write hrp_look / hrp_own from the variation and the user's values."""
    h, s, v, col, amt = user(ob)
    look = [float(ob.get("hrp_hue", 0.0)) + h, s, float(ob.get("hrp_value", 0.0)) + v]
    if any(abs(x) > 1e-7 for x in look):
        ob["hrp_look"] = look
    elif "hrp_look" in ob:
        del ob["hrp_look"]
    if amt > 1e-6:
        ob["hrp_own"] = [*(max(c, 0.002) for c in col), amt]     # pure black would read as 'none' (HRP Grade)
    elif "hrp_own" in ob:
        del ob["hrp_own"]
    ob.update_tag()


def set_user(ob, h=None, s=None, v=None, colour=None, amount=None):
    ch, cs, cv, cc, ca = user(ob)
    hsv = [ch if h is None else h, cs if s is None else s, cv if v is None else v]
    tint = [*(cc if colour is None else colour[:3]), ca if amount is None else amount]
    if any(abs(x) > 1e-7 for x in hsv):
        ob[USER_HSV] = hsv
    elif USER_HSV in ob:
        del ob[USER_HSV]
    if tint[3] > 1e-7 or colour is not None:
        ob[USER_TINT] = tint
    elif USER_TINT in ob:
        del ob[USER_TINT]
    compose(ob)


def reset(ob):
    for k in (USER_HSV, USER_TINT):
        if k in ob:
            del ob[k]
    compose(ob)


def migrate(scene=None):
    """Objects from before hrp_look existed (or edited by hand): compose them once."""
    for ob in (scene.objects if scene is not None else bpy.data.objects):
        if ("hrp_hue" in ob or "hrp_value" in ob or USER_HSV in ob or USER_TINT in ob) and "hrp_look" not in ob \
                and "hrp_own" not in ob:
            compose(ob)


# --------------------------------------------------------------------------------------------------
# panel properties: read and write the active object's tree / object
# --------------------------------------------------------------------------------------------------
def _active():
    ob = bpy.context.active_object
    return ob if is_harappa(ob) else None


def _getter(i):
    def g(self):
        ob = _active()
        if ob is None:
            return (1.0, 1.0, 1.0) if i == 3 else 0.0
        vals = user(targets(ob)[-1])
        return vals[i]
    return g


def _setter(key):
    def f(self, value):
        ob = _active()
        if ob is None:
            return
        for o in targets(ob):
            set_user(o, **{key: tuple(value) if key == "colour" else value})
    return f


def props():
    return {
        "obj_hue": bpy.props.FloatProperty(
            name="Hue Shift", min=-0.5, max=0.5, get=_getter(0), set=_setter("h"),
            description="Shift this object's colours around the colour wheel"),
        "obj_sat": bpy.props.FloatProperty(
            name="Saturation Shift", min=-1.0, max=1.0, get=_getter(1), set=_setter("s"),
            description="More vivid or more muted than the rest of the scene"),
        "obj_value": bpy.props.FloatProperty(
            name="Brightness Shift", min=-1.0, max=1.0, get=_getter(2), set=_setter("v"),
            description="Lighter or darker than the rest of the scene"),
        "obj_tint": bpy.props.FloatVectorProperty(
            name="Own Colour", subtype="COLOR", size=3, min=0.0, max=1.0, get=_getter(3), set=_setter("colour"),
            description="This object's own colour. It keeps it when the season changes"),
        "obj_tint_amount": bpy.props.FloatProperty(
            name="Own Colour Amount", min=0.0, max=1.0, subtype="FACTOR", get=_getter(4), set=_setter("amount"),
            description="How much of the own colour the object takes (0 = the scene's colours)"),
    }
