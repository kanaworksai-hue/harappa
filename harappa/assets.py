# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural source assets: the grass tuft, the camera-facing card, and the brush-stroke atlases
(leaves, blossoms, meadow flowers) drawn with numpy and packed into the .blend, so nothing ships as a
file and every look can be re-rolled from a seed."""
import math
import random

import bmesh
import bpy
import numpy as np

ASSET_VER = 8
TUFT_MESH = "HRP Grass Tuft"
CARD_MESH = "HRP Card"
LEAF_ATLAS = "HRP Leaf Atlas"
BLOSSOM_ATLAS = "HRP Blossom Atlas"
FLOWER_ATLAS = "HRP Flower Atlas"
CLOUD_ATLAS = "HRP Cloud Atlas"
ATLAS_N = 4            # tiles per side (leaf and blossom atlases)
FLOWER_N = 2           # meadow flower atlas is 2 x 2


def _fresh_mesh(name):
    me = bpy.data.meshes.get(name)
    if me is not None and me.get("hrp_ver") == ASSET_VER:
        return me, False
    if me is None:
        me = bpy.data.meshes.new(name)
    me["hrp_ver"] = ASSET_VER
    return me, True


# ----------------------------------------------------------------------------------------------
# meshes
# ----------------------------------------------------------------------------------------------
def grass_tuft(seed=7, blades=9):
    """A clump of tapered, slightly curved blades, 1 unit tall, root at the origin.

    Point attribute ``hrp_h`` = height along the blade (0 root .. 1 tip) for root-dark / tip-light.
    Normals are irrelevant: the shader replaces them with the ground's clump normal."""
    me, rebuild = _fresh_mesh(TUFT_MESH)
    if not rebuild:
        return me
    rng = random.Random(seed)
    bm = bmesh.new()
    hl = bm.verts.layers.float.new("hrp_h")
    for b in range(blades):
        ang = (b / blades) * math.tau + rng.uniform(-0.35, 0.35)
        r0 = rng.uniform(0.0, 0.06)
        base = (math.cos(ang) * r0, math.sin(ang) * r0)
        h = rng.uniform(0.55, 1.0) if b else 1.0
        lean = rng.uniform(0.12, 0.42) * (1.0 if b else 0.4)
        curl = rng.uniform(0.05, 0.25)
        w = rng.uniform(0.05, 0.085)
        face_ang = ang + math.pi / 2 + rng.uniform(-0.5, 0.5)
        sx, sy = math.cos(face_ang), math.sin(face_ang)
        segs = 3
        ring = []
        for i in range(segs + 1):
            t = i / segs
            z = h * t
            off = (lean * t + curl * t * t) * h
            cx = base[0] + math.cos(ang) * off
            cy = base[1] + math.sin(ang) * off
            half = w * 0.5 * (1.0 - t) ** 0.85
            if i == segs:
                v = bm.verts.new((cx, cy, z))
                v[hl] = t * h
                ring.append((v,))
            else:
                a = bm.verts.new((cx - sx * half, cy - sy * half, z))
                c = bm.verts.new((cx + sx * half, cy + sy * half, z))
                a[hl] = c[hl] = t * h
                ring.append((a, c))
        for i in range(segs):
            lo, hi = ring[i], ring[i + 1]
            if len(hi) == 1:
                bm.faces.new((lo[0], lo[1], hi[0]))
            else:
                bm.faces.new((lo[0], lo[1], hi[1], hi[0]))
    bm.to_mesh(me)
    bm.free()
    return me


def card():
    """Unit quad in XY facing +Z, centred, with UVs — leaves, blossoms and meadow flowers."""
    me, rebuild = _fresh_mesh(CARD_MESH)
    if not rebuild:
        return me
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new(p) for p in ((-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0))]
    f = bm.faces.new(vs)
    for loop, co in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = co
    bm.to_mesh(me)
    bm.free()
    return me


# ----------------------------------------------------------------------------------------------
# atlases (numpy raster, 2x supersampled)
# ----------------------------------------------------------------------------------------------
def _grid(n):
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    return (xs + 0.5) / n, (ys + 0.5) / n


def _stamp_leaf(cov, shade, X, Y, x0, y0, ang, length, width, tone, tip=1.6):
    """Lens-shaped leaf from (x0, y0) along angle; max() into coverage, tone where it wins."""
    ca, sa = math.cos(ang), math.sin(ang)
    u = (X - x0) * ca + (Y - y0) * sa          # along the leaf, 0..length
    v = -(X - x0) * sa + (Y - y0) * ca
    t = u / length
    prof = np.clip(t, 0, 1) ** 0.6 * np.clip(1 - t, 0, 1) ** (1 / tip)     # round base, pointed tip
    half = width * 0.5 * prof * 1.9
    d = np.abs(v) - half
    px = 1.0 / X.shape[0]
    a = np.clip(0.5 - d / (px * 1.2), 0, 1) * ((t > 0) & (t < 1))
    win = a > cov
    shade[win] = tone
    np.maximum(cov, a, out=cov)


def _stamp_flower(cov, shade, X, Y, x0, y0, r, petals, rot, tone, centre=0.2, petal_w=0.55):
    """Round-petal flower: R = petal tone, 0 in the yellow centre."""
    dx, dy = X - x0, Y - y0
    rr = np.sqrt(dx * dx + dy * dy) + 1e-6
    th = np.arctan2(dy, dx) - rot
    # petal outline: radius modulated by |cos(petals*th/2)|^k
    lobe = np.abs(np.cos(th * petals / 2.0)) ** (1.0 / max(petal_w, 0.05))
    k = np.floor(((th % math.tau) / math.tau) * petals + 0.5) % petals          # which petal
    seed = (x0 * 131.7 + y0 * 71.3) % 1.0
    plen = 0.82 + 0.18 * np.abs(np.sin(k * 12.9898 + seed * 78.233))           # uneven petal lengths
    edge = r * (0.45 + 0.55 * lobe) * plen
    px = 1.0 / X.shape[0]
    a = np.clip(0.5 - (rr - edge) / (px * 1.2), 0, 1)
    win = a > cov
    pet = np.where(rr < r * centre, 0.0, tone * (0.82 + 0.18 * np.clip(rr / r, 0, 1)))
    shade[win] = pet[win]
    np.maximum(cov, a, out=cov)


def _tile_leaves(n, rng, style):
    X, Y = _grid(n)
    cov = np.zeros((n, n), np.float32)
    shade = np.ones((n, n), np.float32)
    if style == "NEEDLE":
        cnt, L, W, S = rng.randint(18, 26), (0.2, 0.32), (0.04, 0.06), 0.18
    elif style == "SMALL":
        cnt, L, W, S = rng.randint(16, 24), (0.15, 0.22), (0.09, 0.12), 0.28
    else:  # ROUND broadleaf
        cnt, L, W, S = rng.randint(10, 14), (0.22, 0.32), (0.13, 0.18), 0.22
    ox, oy = 0.5 + rng.uniform(-0.04, 0.04), 0.5 + rng.uniform(-0.04, 0.04)
    for i in range(cnt):
        ang = rng.uniform(0, math.tau)
        ln = rng.uniform(*L)
        # start away from the hub so the cluster reads as a rounded brush dab, not a star
        st = rng.uniform(0.0, S)
        x0, y0 = ox + math.cos(ang) * st, oy + math.sin(ang) * st
        ln = min(ln, 0.48 - st)
        _stamp_leaf(cov, shade, X, Y, x0, y0, ang + rng.uniform(-0.3, 0.3), ln, rng.uniform(*W),
                    rng.uniform(0.72, 1.0))
    return cov, shade


def _tile_blossoms(n, rng):
    X, Y = _grid(n)
    cov = np.zeros((n, n), np.float32)
    shade = np.ones((n, n), np.float32)
    for i in range(rng.randint(10, 15)):
        ang = rng.uniform(0, math.tau)
        d = rng.uniform(0.0, 0.33) ** 0.8
        r = rng.uniform(0.08, 0.12)
        _stamp_flower(cov, shade, X, Y, 0.5 + math.cos(ang) * d, 0.5 + math.sin(ang) * d, r, 5,
                      rng.uniform(0, math.tau), rng.uniform(0.8, 1.0), centre=0.22, petal_w=0.7)
    return cov, shade


def _tile_meadow(n, rng, kind):
    X, Y = _grid(n)
    cov = np.zeros((n, n), np.float32)
    shade = np.ones((n, n), np.float32)
    if kind == 0:      # one five-petal flower
        _stamp_flower(cov, shade, X, Y, 0.5, 0.5, 0.42, 5, rng.uniform(0, 1), 1.0, centre=0.18)
    elif kind == 1:    # three small ones
        for (x, y, r) in ((0.33, 0.62, 0.2), (0.66, 0.58, 0.19), (0.5, 0.3, 0.21)):
            _stamp_flower(cov, shade, X, Y, x, y, r, 5, rng.uniform(0, 6), rng.uniform(0.85, 1.0))
    elif kind == 2:    # daisy
        _stamp_flower(cov, shade, X, Y, 0.5, 0.5, 0.44, 11, 0.3, 1.0, centre=0.22, petal_w=0.35)
    else:              # tiny four-petal cluster
        for i in range(5):
            ang = i / 5 * math.tau + rng.uniform(-0.3, 0.3)
            d = 0.2 if i else 0.0
            _stamp_flower(cov, shade, X, Y, 0.5 + math.cos(ang) * d, 0.5 + math.sin(ang) * d, 0.15, 4,
                          rng.uniform(0, 6), rng.uniform(0.85, 1.0), centre=0.18)
    return cov, shade


def _tile_puff(n, rng):
    """A cauliflower puff of overlapping discs; R shades the underside a touch darker."""
    X, Y = _grid(n)
    cov = np.zeros((n, n), np.float32)
    px = 1.0 / n
    for i in range(rng.randint(3, 5)):
        ang = rng.uniform(0, math.tau)
        d = rng.uniform(0.0, 0.16)
        r = rng.uniform(0.2, 0.3)
        cx, cy = 0.5 + math.cos(ang) * d, 0.5 + math.sin(ang) * d * 0.7
        rr = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        th = np.arctan2(Y - cy, X - cx)
        ph = [rng.uniform(0, math.tau) for _ in range(3)]
        wob = 1.0 + 0.06 * np.sin(th * 5 + ph[0]) + 0.04 * np.sin(th * 9 + ph[1]) + 0.025 * np.sin(th * 17 + ph[2])
        np.maximum(cov, np.clip(0.5 - (rr - r * wob) / (px * 1.2), 0, 1), out=cov)
    shade = (0.86 + 0.14 * np.clip(Y * 1.4 - 0.2, 0, 1)).astype(np.float32)
    return cov, shade


def cloud_atlas(seed=4, tile_px=128):
    img = bpy.data.images.get(CLOUD_ATLAS)
    key = f"{ASSET_VER}:{seed}:{tile_px}"
    if img is not None and img.get("hrp_key") == key:
        return img
    rng = random.Random(seed)
    tiles = [_tile_puff(tile_px * 2, rng) for _ in range(ATLAS_N * ATLAS_N)]
    img = _atlas_image(CLOUD_ATLAS, tiles, ATLAS_N, tile_px)
    img["hrp_key"] = key
    return img


def _atlas_image(name, tiles, per_side, tile_px):
    """tiles: list of (coverage, shade) at 2x tile_px. Builds RGBA: R = shade, A = coverage."""
    n2 = tile_px * 2
    size = per_side * tile_px
    rgba = np.zeros((size, size, 4), np.float32)
    for idx, (cov, shade) in enumerate(tiles):
        # 2x2 box downsample, premultiply-safe: shade averaged by coverage
        c = cov.reshape(tile_px, 2, tile_px, 2).mean(axis=(1, 3))
        s = (shade * cov).reshape(tile_px, 2, tile_px, 2).mean(axis=(1, 3)) / np.maximum(c, 1e-4)
        s = np.where(c > 1e-4, s, 1.0)
        tx, ty = idx % per_side, idx // per_side
        sl = (slice(ty * tile_px, (ty + 1) * tile_px), slice(tx * tile_px, (tx + 1) * tile_px))
        rgba[sl + (0,)] = s
        rgba[sl + (1,)] = s
        rgba[sl + (2,)] = s
        rgba[sl + (3,)] = c
    img = bpy.data.images.get(name)
    if img is None or img.size[0] != size:
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(name, size, size, alpha=True)
    img.colorspace_settings.name = "Non-Color"
    img.alpha_mode = "STRAIGHT"
    img.pixels.foreach_set(rgba.ravel())
    img.update()
    img.pack()
    return img


def leaf_atlas_name(style):
    return f"{LEAF_ATLAS} {style.title()}"


def leaf_atlas(seed=1, style="ROUND", tile_px=128):
    name = leaf_atlas_name(style)
    img = bpy.data.images.get(name)
    key = f"{ASSET_VER}:{seed}:{style}:{tile_px}"
    if img is not None and img.get("hrp_key") == key:
        return img
    rng = random.Random(seed)
    tiles = [_tile_leaves(tile_px * 2, rng, style) for _ in range(ATLAS_N * ATLAS_N)]
    img = _atlas_image(name, tiles, ATLAS_N, tile_px)
    img["hrp_key"] = key
    return img


def blossom_atlas(seed=2, tile_px=128):
    img = bpy.data.images.get(BLOSSOM_ATLAS)
    key = f"{ASSET_VER}:{seed}:{tile_px}"
    if img is not None and img.get("hrp_key") == key:
        return img
    rng = random.Random(seed)
    tiles = [_tile_blossoms(tile_px * 2, rng) for _ in range(ATLAS_N * ATLAS_N)]
    img = _atlas_image(BLOSSOM_ATLAS, tiles, ATLAS_N, tile_px)
    img["hrp_key"] = key
    return img


def flower_atlas(seed=3, tile_px=128):
    img = bpy.data.images.get(FLOWER_ATLAS)
    key = f"{ASSET_VER}:{seed}:{tile_px}"
    if img is not None and img.get("hrp_key") == key:
        return img
    rng = random.Random(seed)
    tiles = [_tile_meadow(tile_px * 2, rng, k) for k in range(FLOWER_N * FLOWER_N)]
    img = _atlas_image(FLOWER_ATLAS, tiles, FLOWER_N, tile_px)
    img["hrp_key"] = key
    return img
