# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Node-building helpers shared by the Harappa modules."""
import bpy

TAG = "harappa"
VERSION_KEY = "hrp_ver"


def sock(sockets, name, kind=None):
    """Enabled socket by name (and optional type); falls back to any match. Ints index directly."""
    if isinstance(name, int):
        return sockets[name]
    for s in sockets:
        if s.name == name and s.enabled and (kind is None or s.type == kind):
            return s
    for s in sockets:
        if (s.name == name or s.identifier == name) and (kind is None or s.type == kind):
            return s
    raise KeyError(f"{name} ({kind}) not in {[x.name for x in sockets]}")


class G:
    """Tiny builder around a node tree: g.n(idname, x, y, **props), g.link(a, 'Out', b, 'In')."""

    def __init__(self, tree):
        self.t = tree
        self.nodes = tree.nodes
        self.links = tree.links

    def n(self, idname, x=0, y=0, label=None, **props):
        node = self.nodes.new(idname)
        node.location = (x, y)
        if label:
            node.label = label
            node.name = label
        for k, v in props.items():
            setattr(node, k, v)
        return node

    def out(self, node, name=0, kind=None):
        return sock(node.outputs, name, kind)

    def inp(self, node, name=0, kind=None):
        return sock(node.inputs, name, kind)

    def link(self, a, aname, b, bname, akind=None, bkind=None):
        src = a if isinstance(a, bpy.types.NodeSocket) else self.out(a, aname, akind)
        dst = b if isinstance(b, bpy.types.NodeSocket) else self.inp(b, bname, bkind)
        return self.links.new(src, dst)

    def set(self, node, name, value, kind=None):
        s = self.inp(node, name, kind)
        s.default_value = value
        return s

    # common shortcuts -------------------------------------------------------------------------
    def math(self, op, x, y, a=None, b=None, c=None, clamp=False, label=None):
        idn = "ShaderNodeMath"
        node = self.n(idn, x, y, label, operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.links.new(v, node.inputs[i])
            else:
                node.inputs[i].default_value = v
        return node

    def vmath(self, op, x, y, a=None, b=None, label=None, scale=None):
        node = self.n("ShaderNodeVectorMath", x, y, label, operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.links.new(v, node.inputs[i])
            else:
                node.inputs[i].default_value = v
        if scale is not None:
            s = node.inputs["Scale"]
            if isinstance(scale, bpy.types.NodeSocket):
                self.links.new(scale, s)
            else:
                s.default_value = scale
        return node

    def mix(self, x, y, blend="MIX", dtype="RGBA", fac=None, a=None, b=None, label=None, clamp=False):
        m = self.n("ShaderNodeMix", x, y, label)
        m.data_type = dtype
        if dtype == "RGBA":
            m.blend_type = blend
            m.clamp_result = clamp
        kind = {"RGBA": "RGBA", "VECTOR": "VECTOR"}.get(dtype, "VALUE")
        for name, v, k in (("Factor", fac, "VALUE"), ("A", a, kind), ("B", b, kind)):
            if v is None:
                continue
            s = sock(m.inputs, name, k)
            if isinstance(v, bpy.types.NodeSocket):
                self.links.new(v, s)
            else:
                s.default_value = v
        return m

    def mixout(self, m):
        kind = {"RGBA": "RGBA", "VECTOR": "VECTOR"}.get(m.data_type, "VALUE")
        return sock(m.outputs, "Result", kind)

    def maprange(self, x, y, v=None, fmin=0.0, fmax=1.0, tmin=0.0, tmax=1.0, smooth=False, clamp=True,
                 label=None):
        node = self.n("ShaderNodeMapRange", x, y, label)
        node.clamp = clamp
        if smooth:
            node.interpolation_type = "SMOOTHSTEP"
        vals = {"From Min": fmin, "From Max": fmax, "To Min": tmin, "To Max": tmax}
        for k, val in vals.items():
            s = sock(node.inputs, k, "VALUE")
            if isinstance(val, bpy.types.NodeSocket):
                self.links.new(val, s)
            else:
                s.default_value = val
        if v is not None:
            self.links.new(v, sock(node.inputs, "Value", "VALUE"))
        return node


def iface(ng, name, in_out, stype, default=None, lo=None, hi=None, desc=None, subtype=None):
    s = ng.interface.new_socket(name, in_out=in_out, socket_type=stype)
    if default is not None and hasattr(s, "default_value"):
        s.default_value = default
    if lo is not None and hasattr(s, "min_value"):
        s.min_value = lo
    if hi is not None and hasattr(s, "max_value"):
        s.max_value = hi
    if desc:
        s.description = desc
    if subtype and hasattr(s, "subtype"):
        try:
            s.subtype = subtype
        except TypeError:
            pass
    return s


def menu(sock_, *choices):
    """Set a menu socket / enum to the first choice this Blender build accepts."""
    for c in choices:
        try:
            sock_.default_value = c
            return c
        except TypeError:
            continue
    print(f"[Harappa] menu value not accepted: {choices}")
    return None


def srgb(hexstr):
    """'#3B1F14' -> linear RGB tuple."""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def to_hex(lin):
    out = []
    for c in lin[:3]:
        c = max(0.0, min(1.0, c))
        s = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        out.append(round(s * 255))
    return "#%02X%02X%02X" % tuple(out)


def fresh_group(name, kind, version):
    """Return (group, rebuilt?) — rebuilds the node group when its version tag differs."""
    ng = bpy.data.node_groups.get(name)
    if ng is not None and ng.get(VERSION_KEY) == version:
        return ng, False
    if ng is None:
        ng = bpy.data.node_groups.new(name, kind)
    else:
        ng.nodes.clear()
        ng.interface.clear()
    ng[VERSION_KEY] = version
    return ng, True


def mod_input(mod, name, value=None):
    """Read or set a Geometry Nodes modifier input by its interface name (5.x and 4.x)."""
    ng = mod.node_group
    item = next((i for i in ng.interface.items_tree
                 if getattr(i, "item_type", "") == "SOCKET" and i.in_out == "INPUT" and i.name == name), None)
    if item is None:
        raise KeyError(name)
    ident = item.identifier
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):          # Blender 5.x
        slot = getattr(props.inputs, ident, None)
        if slot is not None:
            if value is None:
                return slot.value
            try:
                slot.value = value
            except TypeError:
                slot.value = type(slot.value)(value)
            return value
    if value is None:                                             # Blender 4.x
        try:
            return mod[ident]
        except KeyError:
            return item.default_value
    try:
        mod[ident] = value
    except TypeError:
        mod[ident] = type(mod[ident])(value)
    return value
