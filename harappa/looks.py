# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""My Looks: the colours, light, sky and paint style of a scene, saved as a small JSON file.

A look holds no objects, nothing painted, no positions, so it can go onto any Harappa scene and be shared as a
text file. Plain JSON on purpose: Blender's own preset system writes Python files, and sharing a preset should
never mean sharing a script.

Reading is forgiving: unknown keys are ignored (and counted), missing keys keep the current value, numbers are
clamped to their slider range, colours that do not parse are skipped."""
import json
import os
import re

import bpy

from .util import srgb, to_hex

FORMAT = "harappa-look"
SCHEMA = 1
EXT = ".harappa-look.json"
RENAMES = {}                  # schema migrations: {old key: new key}
GRASS_KEYS = ("Density", "Height", "Height Random", "Width", "Wind Strength", "Wind Speed", "Wind Scale",
              "Wind Direction")
FLOWER_KEYS = ("Density", "Patch Size", "Patch Amount", "Size")


def folder(create=True):
    """Where the looks live: the extension's own user folder (kept through updates), HARAPPA_LOOKS_DIR in tests."""
    env = os.environ.get("HARAPPA_LOOKS_DIR")
    if env:
        if create:
            os.makedirs(env, exist_ok=True)
        return env
    pkg = __package__ or "harappa"
    try:
        return bpy.utils.extension_path_user(pkg, path="looks", create=create)
    except (ValueError, AttributeError, TypeError, RuntimeError):
        path = bpy.utils.user_resource("CONFIG", path=os.path.join("harappa", "looks"), create=create)
        return path


def file_name(name):
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name).strip(" .") or "Look"
    return safe[:80] + EXT


def path_of(name):
    return os.path.join(folder(), file_name(name))


def all_looks():
    """[(name, path)] of the looks in the folder, sorted by name."""
    out = []
    d = folder(create=False)
    if not d or not os.path.isdir(d):
        return out
    for fn in os.listdir(d):
        if not fn.endswith(EXT):
            continue
        p = os.path.join(d, fn)
        name = fn[:-len(EXT)]
        try:
            with open(p, encoding="utf-8") as f:
                name = str(json.load(f).get("name") or name)
        except (OSError, ValueError, AttributeError):
            pass
        out.append((name, p))
    return sorted(out, key=lambda x: x[0].lower())


def _version():
    from . import bl_info_version
    return bl_info_version()


def collect(context, name, grass=False):
    """The scene's look as a dict (what the user sees, variation included)."""
    from . import COLOUR_PROPS, SKY_PROPS, VALUE_PROPS
    sc = context.scene
    s = sc.harappa
    data = {
        "format": FORMAT, "schema": SCHEMA, "addon": _version(), "name": name,
        "season": s.season, "style": s.style,
        "palette": {k: to_hex(getattr(s, k)) for k, _ in COLOUR_PROPS + SKY_PROPS},
        "values": {k: round(float(getattr(s, k)), 5) for k, *_ in VALUE_PROPS},
        "sun": {"elevation": round(s.sun_elevation, 3), "side": round(s.sun_side, 3)},
    }
    if grass:
        from . import avoid, build
        from .util import mod_input
        ms = avoid.meadows(sc)
        layers = {}
        if ms:
            for key, mod_name, keys in (("grass", build.GRASS_MOD, GRASS_KEYS), ("flowers", build.FLOWER_MOD, FLOWER_KEYS)):
                m = ms[0].modifiers.get(mod_name)
                if m is None:
                    continue
                vals = {}
                for k in keys:
                    try:
                        vals[k] = round(float(mod_input(m, k)), 5)
                    except (KeyError, TypeError):
                        pass
                layers[key] = vals
        data["layers"] = layers
    return data


def save(context, name, grass=False, path=None):
    data = collect(context, name, grass)
    path = path or path_of(name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def read(path):
    """The look in a file, or raise ValueError with a short reason."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ValueError("can't read the file") from e
    except ValueError as e:
        raise ValueError("not a JSON file") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("not a Harappa look")
    return data


def _clamp(rna, v):
    lo = getattr(rna, "hard_min", None)
    hi = getattr(rna, "hard_max", None)
    out = float(v)
    if out != out:                                        # NaN
        raise ValueError
    if lo is not None:
        out = max(lo, out)
    if hi is not None:
        out = min(hi, out)
    return out


def apply(context, data):
    """Put a look onto the scene. Returns counts: {"set", "unknown", "clamped", "bad", "missing"}."""
    from . import COLOUR_PROPS, SKY_PROPS, VALUE_PROPS, _busy, after_look
    sc = context.scene
    s = sc.harappa
    rna = s.bl_rna.properties
    n = {"set": 0, "unknown": 0, "clamped": 0, "bad": 0, "missing": 0}
    known_top = {"format", "schema", "addon", "name", "season", "style", "palette", "values", "sun", "layers",
                 "author", "notes", "template"}
    n["unknown"] += sum(1 for k in data if k not in known_top)
    colour_keys = {k for k, _ in COLOUR_PROPS + SKY_PROPS}
    value_keys = {k for k, *_ in VALUE_PROPS}
    _busy["on"] = True
    try:
        for key, enum in (("season", "season"), ("style", "style")):
            v = data.get(key)
            if v is None:
                continue
            if isinstance(v, str) and v.upper() in {i.identifier for i in rna[enum].enum_items}:
                setattr(s, enum, v.upper())
                n["set"] += 1
            else:
                n["bad"] += 1
        pal = data.get("palette") if isinstance(data.get("palette"), dict) else {}
        for k, hx in pal.items():
            k = RENAMES.get(k, k)
            if k not in colour_keys:
                n["unknown"] += 1
                continue
            try:
                hx = str(hx).strip()
                if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", hx):
                    raise ValueError
                setattr(s, k, srgb(hx if hx.startswith("#") else "#" + hx))
                n["set"] += 1
            except (ValueError, TypeError):
                n["bad"] += 1
        n["missing"] += len(colour_keys - {RENAMES.get(k, k) for k in pal})
        vals = data.get("values") if isinstance(data.get("values"), dict) else {}
        for k, v in vals.items():
            k = RENAMES.get(k, k)
            if k not in value_keys:
                n["unknown"] += 1
                continue
            try:
                c = _clamp(rna[k], v)
                if abs(c - float(v)) > 1e-9:
                    n["clamped"] += 1
                setattr(s, k, c)
                n["set"] += 1
            except (ValueError, TypeError):
                n["bad"] += 1
        n["missing"] += len(value_keys - {RENAMES.get(k, k) for k in vals})
        sun = data.get("sun") if isinstance(data.get("sun"), dict) else {}
        for k, prop in (("elevation", "sun_elevation"), ("side", "sun_side")):
            if k not in sun:
                continue
            try:
                c = _clamp(rna[prop], sun[k])
                if abs(c - float(sun[k])) > 1e-9:
                    n["clamped"] += 1
                setattr(s, prop, c)
                n["set"] += 1
            except (ValueError, TypeError):
                n["bad"] += 1
        s.variation = 0                                     # the look is what it says, not look + a shuffle
    finally:
        _busy["on"] = False
    if "hrp_base" in sc:
        del sc["hrp_base"]
    layers = data.get("layers") if isinstance(data.get("layers"), dict) else {}
    if layers:
        _apply_layers(sc, layers, n)
    after_look(context)
    s.look_name = str(data.get("name") or "")[:64]
    return n


def _apply_layers(sc, layers, n):
    from . import avoid, build
    from .util import mod_input
    for key, mod_name, keys in (("grass", build.GRASS_MOD, GRASS_KEYS), ("flowers", build.FLOWER_MOD, FLOWER_KEYS)):
        vals = layers.get(key)
        if not isinstance(vals, dict):
            continue
        for ob in avoid.meadows(sc):
            m = ob.modifiers.get(mod_name)
            if m is None or m.node_group is None:
                continue
            for k, v in vals.items():
                if k not in keys:
                    n["unknown"] += 1
                    continue
                it = next((i for i in m.node_group.interface.items_tree if getattr(i, "item_type", "") == "SOCKET"
                           and i.in_out == "INPUT" and i.name == k), None)
                try:
                    c = float(v)
                    if c != c:
                        raise ValueError
                    if it is not None and hasattr(it, "min_value"):
                        c = min(max(c, it.min_value), it.max_value)
                    mod_input(m, k, c)
                    n["set"] += 1
                except (ValueError, TypeError, KeyError):
                    n["bad"] += 1
            ob.update_tag()
