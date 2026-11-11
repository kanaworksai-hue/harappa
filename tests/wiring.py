"""Checks on every node tree Harappa builds: each link joins the sockets it was written for.

Blender adds sockets to existing nodes between releases. A link made by position then lands on a different
socket without any error (5.3: Vector Transform got a 'LightIndex' input in front of 'Vector', and the clouds
turned plain white). These checks catch that on whatever Blender runs the tests:

  * every link is valid and both ends are sockets the node really uses;
  * both ends carry the same kind of data, or one of the few conversions the add-on relies on;
  * links, node settings and the values of unlinked inputs equal tests/baseline/wiring.json, recorded on the
    oldest supported LTS. Sockets a newer Blender adds are fine as long as nothing is linked to them.

They only see the Blender they run on: run the tests on every new Blender release before calling it supported.
After changing nodes on purpose, record a new list:  HARAPPA_UPDATE_BASELINE=1 blender -b ... test_generic.py
"""
import json
import os
import re

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "baseline", "wiring.json")

# implicit conversions the node trees use on purpose (from, to)
CONVERSIONS = {
    ("VALUE", "BOOLEAN"),      # a 0/1 Math result as a Selection or Switch
    ("BOOLEAN", "VALUE"),      # 'Is Hit' / 'Exists' into Math
    ("INT", "VALUE"),          # counts and seeds into Math
    ("VALUE", "INT"),          # Math result as a Seed
    ("RGBA", "VECTOR"),        # noise colour as a vector offset
    ("VALUE", "VECTOR"),       # one number as a uniform scale
}
# node settings worth recording (whatever of these a node has)
SETTINGS = ("operation", "blend_type", "data_type", "use_clamp", "clamp", "clamp_result", "clamp_factor",
            "factor_mode", "interpolation_type", "interpolation", "vector_type", "convert_from", "convert_to",
            "noise_dimensions", "noise_type", "normalize", "voronoi_dimensions", "feature", "distance", "domain",
            "input_type", "distribute_method", "attribute_name", "attribute_type", "transform_space",
            "rotation_space", "axis", "pivot_axis", "target_element", "component", "mode", "samples",
            "extension", "projection", "vector")
VOLATILE = {"moon dir"}        # nodes whose input values follow the scene (the moon follows the camera)
NUMERIC = {"VALUE", "INT", "BOOLEAN", "VECTOR", "RGBA", "STRING", "ROTATION"}


def trees():
    """(label, node tree) for everything the add-on has built in this file."""
    out = []
    for ng in bpy.data.node_groups:
        if ng.name.startswith("HRP"):
            out.append((f"group:{ng.name}", ng))
    for mat in bpy.data.materials:
        if mat.name.startswith("HRP") and mat.node_tree is not None:
            out.append((f"material:{mat.name}", mat.node_tree))
    for world in bpy.data.worlds:
        if world.name.startswith("HRP") and world.node_tree is not None:
            out.append((f"world:{world.name}", world.node_tree))
    return sorted(out, key=lambda t: t[0])


_SUFFIX = re.compile(r"_\d{3}$")
GROUP_NODES = {"NodeGroupInput", "NodeGroupOutput", "ShaderNodeGroup", "GeometryNodeGroup"}


def _sid(node, sock):
    """A socket's stable id. The sockets of the add-on's own groups get a new identifier at every rebuild, so
    those go by the name the add-on gave them."""
    if node.bl_idname in GROUP_NODES:
        return sock.name
    ident = sock.identifier
    # Before 5.2 a few nodes (Random Value) kept one socket per data type: 'Value', 'Value_001', ... with only
    # the current type's enabled. 5.2 merged them into one 'Value'. When the suffix only tells data types apart
    # (no other enabled socket shares the base name) both spellings are the same socket.
    base = _SUFFIX.sub("", ident)
    if base != ident:
        group = node.outputs if sock.is_output else node.inputs
        twins = [s for s in group if s.enabled and s.identifier != ident and _SUFFIX.sub("", s.identifier) == base]
        if not twins:
            return base
    return ident


def _plain(v):
    if isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 5)
    try:
        return [round(float(x), 5) for x in v]
    except TypeError:
        return str(v)


def _describe(nt):
    """Links, settings and unlinked input values of one tree. Nodes are numbered in the order they were made
    (their names change with Blender's interface language)."""
    key = {n: f"{i:03d}<{n.bl_idname}>" for i, n in enumerate(nt.nodes)}
    links = sorted(f"{key[l.from_node]}.{_sid(l.from_node, l.from_socket)}:{l.from_socket.type} -> "
                   f"{key[l.to_node]}.{_sid(l.to_node, l.to_socket)}:{l.to_socket.type}" for l in nt.links)
    values = {}
    for n in nt.nodes:
        for name in SETTINGS:
            if hasattr(n, name):
                values[f"{key[n]}#{name}"] = _plain(getattr(n, name))
        tree = getattr(n, "node_tree", None)
        if tree is not None:
            values[f"{key[n]}#node_tree"] = tree.name
        if n.label in VOLATILE:
            continue
        for s in n.inputs:
            if s.enabled and not s.is_linked and s.type in NUMERIC and hasattr(s, "default_value"):
                values[f"{key[n]}.{_sid(n, s)}"] = _plain(s.default_value)
    return {"links": links, "values": values}


def snapshot():
    return {label: _describe(nt) for label, nt in trees()}


def problems():
    """Links that are broken, end on a socket the node does not use, or join two different kinds of data."""
    bad = []
    for label, nt in trees():
        for l in nt.links:
            a, b = l.from_socket, l.to_socket
            where = (f"{label}: {l.from_node.bl_idname}.{a.identifier}:{a.type} -> "
                     f"{l.to_node.bl_idname}.{b.identifier}:{b.type}")
            if not l.is_valid or l.is_muted:
                bad.append(where + " (invalid link)")
            elif not a.enabled or not b.enabled or getattr(a, "is_unavailable", False) or getattr(b, "is_unavailable", False):
                bad.append(where + " (socket not in use)")
            elif a.type != b.type and (a.type, b.type) not in CONVERSIONS:
                bad.append(where + " (different data types)")
    return bad


def positional_access(root):
    """Source lines that pick a socket by position (node.inputs[0]). The helpers in util.py refuse numbers too;
    a position hidden behind other code (list(node.inputs)[0]) only shows up in the checks above."""
    pat = re.compile(r"\.(?:inputs|outputs)\[\s*-?\d")
    hits = []
    for folder in ("harappa", "agent"):
        d = os.path.join(root, folder)
        for name in sorted(os.listdir(d)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(d, name), encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if pat.search(line.split("#", 1)[0]):
                        hits.append(f"{folder}/{name}:{i}")
    return hits


def _same(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(abs(x - y) < 2e-5 for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) < 2e-5
    return a == b


def compare(update=False):
    """(ok, message) against the recorded trees; update=True records them instead."""
    now = snapshot()
    n_links = sum(len(t["links"]) for t in now.values())
    n_values = sum(len(t["values"]) for t in now.values())
    if update:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(now, f, indent=1, sort_keys=True)
            f.write("\n")
        return True, f"recorded {n_links} links and {n_values} values in {len(now)} trees"
    if not os.path.exists(BASELINE):
        return False, "tests/baseline/wiring.json is missing"
    with open(BASELINE, encoding="utf-8") as f:
        ref = json.load(f)
    diff = []
    for label in sorted(set(ref) | set(now)):
        a, b = ref.get(label, {"links": [], "values": {}}), now.get(label, {"links": [], "values": {}})
        la, lb = set(a["links"]), set(b["links"])
        diff += [f"{label}: missing link {x}" for x in sorted(la - lb)]
        diff += [f"{label}: unexpected link {x}" for x in sorted(lb - la)]
        for k, v in sorted(a["values"].items()):            # sockets a newer Blender adds are not in the record
            if k not in b["values"]:
                diff.append(f"{label}: {k} is gone or linked")
            elif not _same(v, b["values"][k]):
                diff.append(f"{label}: {k} is {b['values'][k]}, recorded {v}")
    if diff:
        return False, f"{len(diff)} differences: {diff[:6]}"
    return True, f"{n_links} links and {n_values} values in {len(now)} trees"
