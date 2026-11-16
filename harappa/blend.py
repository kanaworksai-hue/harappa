# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Blend Into Meadow: the user's own models painted the way Harappa paints everything else.

Why: every Harappa material is an emission with its light and shade painted in (HRP Cel), so the world gives
objects no ambient light at all (scene.py, "ambient" = 0). An ordinary material (Principled BSDF from an import,
a generator, a store) is then lit by the sun alone and everything the sun misses renders black.

What: each material of the selected objects (and their children) is swapped for a copy whose surface is the
original colour (its texture or value) painted with HRP Cel: lit = the colour x cloud_lit (the season's light on a
white thing), shadow = lit x flower_shade (the shade tint the meadow's flowers get), deep = one more step, dimmed with
flower_dim at night, then the grade and the haze. So the shadows follow the season,
the style (threshold, softness) and any Look. Cut-out alpha and emission are kept; normal maps and gloss are not.

Undo: the copy keeps a pointer to the original (TAG); restore() puts the originals back and removes copies no one
uses any more. A model that had no material gets the shared plain material and loses it again on restore.
"""
import bpy

from . import shading
from .util import BUILDING, G, VERSION_KEY

TAG = "hrp_blend_of"          # on a blended copy: the original material (an ID pointer, so it is saved with the file)
PLAIN = "hrp_blend_plain"     # on the shared material for objects that had none
ADDED = "hrp_blend_added"     # on an object: Harappa added its only material slot
PLAIN_NAME = "Harappa Plain"
SUFFIX = " · Harappa"
TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES"}
SHADERS = ("BSDF_PRINCIPLED", "BSDF_DIFFUSE", "BSDF_TOON", "SUBSURFACE_SCATTERING", "EMISSION",
           "BSDF_SHEEN", "BSDF_GLOSSY", "BSDF_METALLIC")


# ---------------------------------------------------------------------------------------------
# which objects
# ---------------------------------------------------------------------------------------------
def _own(ob):
    """An object of the user's (not a meadow, tree, cloud, ridge or card Harappa made)."""
    from . import look
    return (ob is not None and ob.type in TYPES and not look.is_harappa(ob) and not ob.get("hrp_card")
            and not ob.name.startswith("HRP "))


def targets(obs):
    """The selected objects and everything parented under them (an imported model is often an empty with meshes)."""
    seen, out = set(), []
    for ob in obs:
        for o in (ob, *ob.children_recursive):
            if o.name not in seen and _own(o):
                seen.add(o.name)
                out.append(o)
    return out


def is_blended(mat):
    return mat is not None and (mat.get(TAG) is not None or bool(mat.get(PLAIN)))


def blended(ob):
    return any(is_blended(s.material) for s in ob.material_slots)


# ---------------------------------------------------------------------------------------------
# reading the original material
# ---------------------------------------------------------------------------------------------
def _output(nt):
    outs = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"]
    for n in outs:
        if n.is_active_output and n.target in ("ALL", "EEVEE"):
            return n
    return outs[0] if outs else None


def _shader(node, depth=0):
    """The colour-carrying shader behind the output: through mix / add shaders, preferring a Principled."""
    if node is None or depth > 6:
        return None
    if node.type in SHADERS:
        return node
    if node.type in ("MIX_SHADER", "ADD_SHADER"):
        found = [_shader(s.links[0].from_node, depth + 1) for s in node.inputs
                 if s.type == "SHADER" and s.is_linked]
        found = [f for f in found if f is not None]
        for f in found:
            if f.type == "BSDF_PRINCIPLED":
                return f
        return found[0] if found else None
    return None


def _input(node, *names):
    for name in names:
        s = node.inputs.get(name)
        if s is not None and s.enabled:
            return s
    return None


def _colour_source(g, mat, x, y):
    """(colour socket, alpha socket or None, emission socket or None) inside mat's own (copied) tree."""
    nt = mat.node_tree
    out = _output(nt) if nt is not None else None
    surf = out.inputs.get("Surface") if out is not None else None
    sh = _shader(surf.links[0].from_node) if surf is not None and surf.is_linked else None
    col = alpha = emit = None
    if sh is not None:
        base = _input(sh, "Base Color", "Color")
        if base is not None:
            if base.is_linked:
                col = base.links[0].from_socket
            else:
                rgb = g.n("ShaderNodeRGB", x, y, label="colour")
                g.out(rgb).default_value = tuple(base.default_value)
                col = g.out(rgb)
        a = _input(sh, "Alpha")
        if a is not None and a.is_linked:                      # a cut-out texture (leaves, a fence): keep the holes
            alpha = a.links[0].from_socket
        ec, es = _input(sh, "Emission Color"), _input(sh, "Emission Strength")
        if sh.type == "BSDF_PRINCIPLED" and ec is not None and es is not None and (es.is_linked or es.default_value > 0):
            lit_emit = ec.is_linked or max(ec.default_value[:3]) > 0.0
            if lit_emit:                                       # lamps, glowing windows: they still glow
                if ec.is_linked:
                    esock = ec.links[0].from_socket
                else:
                    rgb = g.n("ShaderNodeRGB", x, y - 200, label="glow")
                    g.out(rgb).default_value = tuple(ec.default_value)
                    esock = g.out(rgb)
                if es.is_linked:
                    gray = g.n("ShaderNodeCombineColor", x, y - 350)
                    for ch in ("Red", "Green", "Blue"):
                        g.links.new(es.links[0].from_socket, gray.inputs[ch])
                    m = g.mix(x + 200, y - 200, "MULTIPLY", fac=1.0, a=esock, b=g.out(gray))
                else:
                    m = g.mix(x + 200, y - 200, "MULTIPLY", fac=1.0, a=esock,
                              b=(es.default_value,) * 3 + (1.0,))
                emit = g.mixout(m)
    if col is None:                                            # no shader we understand: its viewport colour
        rgb = g.n("ShaderNodeRGB", x, y, label="colour")
        g.out(rgb).default_value = tuple(mat.diffuse_color) if mat is not None else (0.8, 0.8, 0.8, 1.0)
        col = g.out(rgb)
    return col, alpha, emit


# ---------------------------------------------------------------------------------------------
# building the painted copy
# ---------------------------------------------------------------------------------------------
def _paint(mat):
    """Turn mat (a fresh copy, or a new material) into the painted surface. Its own nodes stay as the source of the
    colour; the output is replaced."""
    mat.use_nodes = True
    nt = mat.node_tree
    g = G(nt)
    xs = [n.location.x for n in nt.nodes] or [0.0]
    x0, y0 = max(xs) + 400, 0
    col, alpha, emit = _colour_source(g, mat, x0, y0 + 600)
    for n in [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"]:
        nt.nodes.remove(n)
    pal = g.n("ShaderNodeGroup", x0, y0 - 400)
    pal.node_tree = shading.palette_group()
    geo = g.n("ShaderNodeNewGeometry", x0, y0 - 800)
    # lit = own colour in the season's light on a white thing (cloud_lit: white by day, warm at sunset, dim blue at
    # night); shadow = that x flower_shade (the shade tint the meadow's flowers get); deep = one step more, for eaves
    # and cast shadows; then dimmed with the flowers (night)
    lt = g.mix(x0 + 100, y0 + 300, "MULTIPLY", fac=1.0, a=col, b=g.out(pal, "cloud_lit"), label="lit")
    sh = g.mix(x0 + 250, y0 + 100, "MULTIPLY", fac=1.0, a=g.mixout(lt), b=g.out(pal, "flower_shade"), label="shade")
    dp = g.mix(x0 + 250, y0 - 100, "MULTIPLY", fac=1.0, a=g.mixout(sh), b=g.out(pal, "flower_shade"), label="deep")
    cel = shading._cel_node(g, pal, x0 + 500, y0, g.out(geo, "Normal"), g.mixout(lt), g.mixout(sh), g.mixout(dp))
    dim = g.n("ShaderNodeCombineColor", x0 + 600, y0 + 300)
    for ch in ("Red", "Green", "Blue"):
        g.link(pal, "flower_dim", dim, ch)
    dm = g.mix(x0 + 750, y0 + 100, "MULTIPLY", fac=1.0, a=g.out(cel, "Color"), b=g.out(dim), label="dim")
    colour = g.mixout(dm)
    if emit is not None:
        add = g.mix(x0 + 750, y0 + 200, "ADD", fac=1.0, a=colour, b=emit, label="glow")
        colour = g.mixout(add)
    shading._emit_out(g, colour, x0 + 1800, y0, alpha=alpha, pal=pal, per_object=False)
    mat[VERSION_KEY] = shading.SHADER_VER


def _copy_of(orig):
    """The painted copy of orig, shared by every slot that uses orig."""
    for m in bpy.data.materials:
        if m.get(TAG) == orig and m.get(VERSION_KEY) == shading.SHADER_VER:
            return m
    mat = orig.copy()
    mat.name = (orig.name[:63 - len(SUFFIX)]) + SUFFIX
    for k in ("hrp_kind",):
        if k in mat:
            del mat[k]
    mat[VERSION_KEY] = BUILDING
    _paint(mat)
    mat[TAG] = orig
    return mat


def _plain():
    mat = bpy.data.materials.get(PLAIN_NAME)
    if mat is not None and mat.get(PLAIN) and mat.get(VERSION_KEY) == shading.SHADER_VER:
        return mat
    if mat is None or not mat.get(PLAIN):
        mat = bpy.data.materials.new(PLAIN_NAME)
    mat.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    _paint(mat)
    mat[PLAIN] = True
    return mat


def rebuild_stale():
    """After an update: paint every blended copy again from its original (called by shading._rebuild_stale)."""
    for m in list(bpy.data.materials):
        if m.get(VERSION_KEY) in (shading.SHADER_VER, BUILDING):
            continue
        orig = m.get(TAG)
        if orig is not None:
            name = m.name
            fresh = _copy_of(orig)
            m.user_remap(fresh)
            bpy.data.materials.remove(m)
            fresh.name = name
        elif m.get(PLAIN):
            _plain()


# ---------------------------------------------------------------------------------------------
# the two buttons
# ---------------------------------------------------------------------------------------------
def apply(obs):
    """Paint these objects (and their children) like the meadow. Returns (objects changed, already blended)."""
    shading.palette_group()
    done, already = [], []
    for ob in targets(obs):
        changed = False
        slots = list(ob.material_slots)
        if not slots and hasattr(ob.data, "materials"):
            ob.data.materials.append(_plain())
            ob[ADDED] = True
            changed = True
        for slot in slots:
            m = slot.material
            if is_blended(m):
                continue
            if m is not None and m.get("hrp_kind"):            # one of Harappa's own: leave it
                continue
            slot.material = _plain() if m is None else _copy_of(m)
            changed = True
        if changed:
            done.append(ob)
        elif blended(ob):
            already.append(ob)
    return done, already


def _drop_slot(ob):
    """Remove the slot Harappa added. Popping the mesh's material list leaves the object's slot count behind, so
    this goes through Blender's own operator."""
    ob.active_material_index = len(ob.material_slots) - 1
    try:
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.object.material_slot_remove()
    except RuntimeError:
        pass


def restore(obs):
    """Give these objects (and their children) their own materials back. Returns the objects changed."""
    done = []
    for ob in targets(obs):
        changed = False
        for slot in ob.material_slots:
            m = slot.material
            if m is None:
                continue
            if m.get(TAG) is not None:
                slot.material = m[TAG]
                changed = True
            elif m.get(PLAIN):
                slot.material = None
                changed = True
        if ob.get(ADDED):
            if len(ob.material_slots) == 1 and ob.material_slots[0].material is None:
                _drop_slot(ob)
            del ob[ADDED]
            changed = True
        if changed:
            done.append(ob)
    for m in [m for m in bpy.data.materials if is_blended(m) and m.users == 0]:
        bpy.data.materials.remove(m)
    return done
