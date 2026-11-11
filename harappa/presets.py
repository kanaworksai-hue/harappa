# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Seasons (colour + light + sky) and Styles (how the paint is put down).

Seasons only touch colour/mood keys, Styles only technique keys, so any season combines with any style
and switching back and forth is lossless."""

# ---------------------------------------------------------------------------------------------
# Seasons: palette colours (sRGB hex), tone split, sky and sun
# ---------------------------------------------------------------------------------------------
SEASONS = {
    "SUMMER": {
        "name": "Summer Meadow",
        "desc": "Bright green hills, blue sky, white clouds of light",
        "palette": {
            "grass_lit": "#84C048", "grass_lit2": "#A9CC55", "grass_shadow": "#3F7F4E",
            "grass_deep": "#1F5640", "grass_tip": "#D6E37A",
            "dirt_lit": "#D9C9A0", "dirt_shadow": "#A89878", "dirt_deep": "#7D6F5E",
            "leaf_lit": "#BCDF5E", "leaf_mid": "#5FA040", "leaf_shadow": "#3F7F66", "leaf_deep": "#183C46",
            "leaf_hi": "#DDF08F", "bloom_lit": "#F7D6E2", "bloom_shadow": "#C995AE",
            "bark_lit": "#6E5444", "bark_shadow": "#3A3440",
            "flower_a": "#FFFFFF", "flower_b": "#F2A7C3", "flower_c": "#FFE45C", "flower_d": "#B79CFF",
            "flower_centre": "#FFC531", "flower_shade": "#B7B9E8", "sun_tint": "#FFFFFF", "rim_colour": "#FFF4C8",
            "haze_colour": "#CFE6F2", "cloud_lit": "#FFFFFF", "cloud_shadow": "#A9C4EC", "cloud_deep": "#7FA3DA", "cloud_rim": "#FFF6D6", "bloom_deep": "#B58AB0",
        },
        "tone": {"cloud_rim_amount": 0.35, "threshold": 0.42, "deep_threshold": 0.12, "patch_amount": 0.5, "wind_sheen": 0.35, "haze_amount": 0.3, "flower_dim": 1.0, "leaf_deep_threshold": 0.18, "rim_amount": 0.12},
        "sky": ("#1F6FD8", "#A8DBF5", "#B4DDF2"),
        "sky_more": {"mid": "#4E9BEA", "glow": "#FFF8E0", "sun": 0.6, "cirrus": 0.6, "cirrus_colour": "#E8F4FF"},
        "sun": {"elevation": 42.0, "side": -55.0, "colour": "#FFF6E6", "strength": 4.0},
        "night": (0.0, 0.0),
    },
    "SPRING": {
        "name": "Spring Blossom",
        "desc": "Fresh yellow-greens, pink blossoms and pastel flowers",
        "palette": {
            "grass_lit": "#B5DC7A", "grass_lit2": "#CFE58A", "grass_shadow": "#5A9E5C",
            "grass_deep": "#2E6A55", "grass_tip": "#EAF5A0",
            "dirt_lit": "#E6D6B4", "dirt_shadow": "#B9A88E", "dirt_deep": "#8C7E70",
            "leaf_lit": "#C2E07A", "leaf_mid": "#7DB85E", "leaf_shadow": "#4E8A6A", "leaf_deep": "#2F5E5C",
            "leaf_hi": "#EEF7A8", "bloom_lit": "#FFE1EC", "bloom_shadow": "#E39BBE",
            "bark_lit": "#8E6E62", "bark_shadow": "#54424C",
            "flower_a": "#FFFFFF", "flower_b": "#FFB3D1", "flower_c": "#FFD6E6", "flower_d": "#C9B5FF",
            "flower_centre": "#FFD24A", "flower_shade": "#C9C4EC", "sun_tint": "#FFFDF6", "rim_colour": "#FFF6D8",
            "haze_colour": "#E6F0F2", "cloud_lit": "#FFFFFF", "cloud_shadow": "#C2D2F2", "cloud_deep": "#9FB4E4", "cloud_rim": "#FFE9F0", "bloom_deep": "#C08AB2",
        },
        "tone": {"cloud_rim_amount": 0.35, "threshold": 0.36, "deep_threshold": 0.08, "patch_amount": 0.55, "wind_sheen": 0.4, "haze_amount": 0.38, "flower_dim": 1.0, "leaf_deep_threshold": 0.18, "rim_amount": 0.12},
        "sky": ("#3F8FE8", "#D5EEF8", "#D0E8F6"),
        "sky_more": {"mid": "#7DBDF2", "glow": "#FFF6E8", "sun": 0.6, "cirrus": 0.35, "cirrus_colour": "#F4F8FF"},
        "blossom": 0.45,
        "sun": {"elevation": 48.0, "side": -50.0, "colour": "#FFFBF2", "strength": 4.0},
        "night": (0.0, 0.0),
    },
    "GOLDEN": {
        "name": "Golden Hour",
        "desc": "Low warm sun, golden grass, violet shadows",
        "palette": {
            "grass_lit": "#C2B656", "grass_lit2": "#D9B45E", "grass_shadow": "#5E6E62",
            "grass_deep": "#4A4060", "grass_tip": "#E6BE6A",
            "dirt_lit": "#EBC59A", "dirt_shadow": "#9A7F86", "dirt_deep": "#5E5068",
            "leaf_lit": "#D8C25E", "leaf_mid": "#8D9A50", "leaf_shadow": "#66704F", "leaf_deep": "#4A4858",
            "leaf_hi": "#FFD98A", "bloom_lit": "#FFD2C8", "bloom_shadow": "#C58AA8",
            "bark_lit": "#A86E50", "bark_shadow": "#4A3550",
            "flower_a": "#FFF2E0", "flower_b": "#FFC94A", "flower_c": "#FF8E8E", "flower_d": "#B58CF0",
            "flower_centre": "#FF9F2E", "flower_shade": "#A99AD8", "sun_tint": "#FFE9C8", "rim_colour": "#F4C478",
            "haze_colour": "#F6D2A8", "cloud_lit": "#FFC98A", "cloud_shadow": "#8A6CA8", "cloud_deep": "#5B4C8C", "cloud_rim": "#FFF2B0", "bloom_deep": "#9A6E92",
        },
        "tone": {"cloud_rim_amount": 0.9, "threshold": 0.5, "deep_threshold": 0.16, "patch_amount": 0.45, "wind_sheen": 0.45, "haze_amount": 0.3, "flower_dim": 0.95, "leaf_deep_threshold": 0.182, "rim_amount": 0.6},
        "sky": ("#3A5FB8", "#FFB25A", "#FFC48A"),
        "sky_more": {"mid": "#8E7FC8", "glow": "#FFE48A", "sun": 1.0, "cirrus": 0.7, "cirrus_colour": "#FF9E8A"},
        "sun": {"elevation": 9.0, "side": 158.0, "colour": "#FFB45E", "strength": 5.0},
        "night": (0.0, 0.0),
    },
    "AUTUMN": {
        "name": "Autumn Leaves",
        "desc": "Orange and red trees, dry golden grass",
        "palette": {
            "grass_lit": "#B9B456", "grass_lit2": "#D3B65C", "grass_shadow": "#6C7A4E",
            "grass_deep": "#3E4A40", "grass_tip": "#EED68A",
            "dirt_lit": "#D8BC94", "dirt_shadow": "#A08470", "dirt_deep": "#6E5A54",
            "leaf_lit": "#F2A040", "leaf_mid": "#D9622E", "leaf_shadow": "#9A3A2C", "leaf_deep": "#5A2430",
            "leaf_hi": "#FFD36E", "bloom_lit": "#FFE08A", "bloom_shadow": "#D99A48",
            "bark_lit": "#7E5E52", "bark_shadow": "#3E3036",
            "flower_a": "#FFF4E2", "flower_b": "#FFC24A", "flower_c": "#E8584A", "flower_d": "#A877D8",
            "flower_centre": "#FF9A30", "flower_shade": "#B39AC8", "sun_tint": "#FFF3DE", "rim_colour": "#FFD08A",
            "haze_colour": "#EADCC4", "cloud_lit": "#FFFAF0", "cloud_shadow": "#B9C6E6", "cloud_deep": "#94A6D4", "cloud_rim": "#FFE6B0", "bloom_deep": "#A8703A",
        },
        "tone": {"cloud_rim_amount": 0.45, "threshold": 0.44, "deep_threshold": 0.13, "patch_amount": 0.35, "wind_sheen": 0.3, "haze_amount": 0.32, "flower_dim": 1.0, "leaf_deep_threshold": 0.18, "rim_amount": 0.3},
        "sky": ("#2466C8", "#CDE6F2", "#D2E2EC"),
        "sky_more": {"mid": "#5A9BE0", "glow": "#FFF2D8", "sun": 0.6, "cirrus": 0.9, "cirrus_colour": "#FFFFFF"},
        "sun": {"elevation": 30.0, "side": -60.0, "colour": "#FFEBCC", "strength": 4.0},
        "night": (0.0, 0.0),
    },
    "NIGHT": {
        "name": "Moonlit Night",
        "desc": "Blue night meadow under a bright moon",
        "palette": {
            "grass_lit": "#447E84", "grass_lit2": "#4E8890", "grass_shadow": "#264A64",
            "grass_deep": "#132A44", "grass_tip": "#9CD0C8",
            "dirt_lit": "#7E8AA2", "dirt_shadow": "#4C5672", "dirt_deep": "#2C3550",
            "leaf_lit": "#548E8E", "leaf_mid": "#386A76", "leaf_shadow": "#244762", "leaf_deep": "#121F38",
            "leaf_hi": "#A8E0D2", "bloom_lit": "#E6D8FF", "bloom_shadow": "#7E74B8",
            "bark_lit": "#4E4A62", "bark_shadow": "#22213A",
            "flower_a": "#E8F0FF", "flower_b": "#FFF0A8", "flower_c": "#D8A8E8", "flower_d": "#8FA8FF",
            "flower_centre": "#FFE08A", "flower_shade": "#6E78B8", "sun_tint": "#DCE8FF", "rim_colour": "#B8C8F0",
            "haze_colour": "#2E4670", "cloud_lit": "#8FA6E8", "cloud_shadow": "#2E3F86", "cloud_deep": "#1A2560", "cloud_rim": "#E6F0FF", "bloom_deep": "#4E4A80",
        },
        "tone": {"cloud_rim_amount": 0.5, "threshold": 0.46, "deep_threshold": 0.14, "patch_amount": 0.4, "wind_sheen": 0.5, "haze_amount": 0.45, "flower_dim": 0.6, "leaf_deep_threshold": 0.18, "rim_amount": 0.25},
        "sky": ("#060F3A", "#2F62B0", "#244E90"),
        "sky_more": {"mid": "#14307A", "glow": "#7FA8FF", "sun": 0.0, "cirrus": 0.15, "cirrus_colour": "#5C78C8"},
        "sun": {"elevation": 38.0, "side": -40.0, "colour": "#C8D8FF", "strength": 3.0},
        "night": (1.0, 1.0),
    },
    "MISTY": {
        "name": "Misty Morning",
        "desc": "Soft pale greens and a hazy low-contrast light",
        "palette": {
            "grass_lit": "#A8CC88", "grass_lit2": "#BCD69A", "grass_shadow": "#7FA488",
            "grass_deep": "#5E8478", "grass_tip": "#E0EEC4",
            "dirt_lit": "#DCD6C4", "dirt_shadow": "#B8B4A8", "dirt_deep": "#9A9890",
            "leaf_lit": "#B4D294", "leaf_mid": "#88AE84", "leaf_shadow": "#6C9284", "leaf_deep": "#4E7272",
            "leaf_hi": "#E4F0C8", "bloom_lit": "#FBE6EE", "bloom_shadow": "#D2AFC2",
            "bark_lit": "#8C8078", "bark_shadow": "#646066",
            "flower_a": "#FFFFFF", "flower_b": "#F8EEA8", "flower_c": "#F2C6D8", "flower_d": "#CBC2EE",
            "flower_centre": "#F2D27A", "flower_shade": "#C8CCE0", "sun_tint": "#FAFCFF", "rim_colour": "#FFFFFF",
            "haze_colour": "#DDE6E3", "cloud_lit": "#FFF6EC", "cloud_shadow": "#C4CEE8", "cloud_deep": "#A6B6DC", "cloud_rim": "#FFE0B0", "bloom_deep": "#B89AAE",
        },
        "tone": {"cloud_rim_amount": 0.6, "threshold": 0.3, "deep_threshold": 0.05, "patch_amount": 0.5, "wind_sheen": 0.25, "haze_amount": 0.75, "flower_dim": 1.0, "leaf_deep_threshold": 0.1, "rim_amount": 0.0},
        "sky": ("#5FA2E0", "#FFE2C0", "#D6EAF2"),
        "sky_more": {"mid": "#A8D0EE", "glow": "#FFF0C8", "sun": 0.8, "cirrus": 0.3, "cirrus_colour": "#FFF4E6"},
        "sun": {"elevation": 34.0, "side": -45.0, "colour": "#FFFFFF", "strength": 4.0},
        "night": (0.0, 0.0),
    },
}

# ---------------------------------------------------------------------------------------------
# Styles: technique keys only
# ---------------------------------------------------------------------------------------------
STYLES = {
    "ANIME": {"name": "Anime Background", "desc": "Clean cel shading with broad grass clumps",
              "keys": {"softness": 0.035, "brush_jitter": 0.22, "clump_size": 1.8, "clump_strength": 1.6,
                       "clump_small": 0.35, "root_dark": 0.4, "tip_light": 0.45, "leaf_ao": 0.65,
                       "leaf_hi_amount": 0.5}},
    "PAINTERLY": {"name": "Painterly", "desc": "Broken, brushy shadow edges and lots of small clumps",
                  "keys": {"softness": 0.05, "brush_jitter": 1.1, "clump_size": 0.9, "clump_strength": 2.4,
                           "clump_small": 1.1, "root_dark": 0.5, "tip_light": 0.75, "leaf_ao": 0.9,
                           "leaf_hi_amount": 0.9}},
    "CRISP": {"name": "Crisp Cel", "desc": "Hard two-tone edges, big graphic shapes",
              "keys": {"softness": 0.0, "brush_jitter": 0.04, "clump_size": 3.2, "clump_strength": 1.5,
                       "clump_small": 0.12, "root_dark": 0.15, "tip_light": 0.0, "leaf_ao": 0.5,
                       "leaf_hi_amount": 0.0}},
    "SOFT": {"name": "Soft Pastel", "desc": "Gentle gradients, quiet shadows",
             "keys": {"softness": 0.3, "brush_jitter": 0.08, "clump_size": 2.6, "clump_strength": 0.7,
                      "clump_small": 0.2, "root_dark": 0.1, "tip_light": 0.2, "leaf_ao": 0.3,
                      "leaf_hi_amount": 0.15}},
}

STYLE_KEYS = tuple(STYLES["ANIME"]["keys"].keys())
TONE_KEYS = ("threshold", "deep_threshold", "patch_amount", "wind_sheen", "haze_amount", "flower_dim",
             "cloud_rim_amount",
             "leaf_deep_threshold", "rim_amount")
assert not set(STYLE_KEYS) & set(TONE_KEYS)

# Shuffle picks flower colours from these (curated: always reads as wildflowers)
FLOWER_SETS = [
    ("#FFFFFF", "#FFE45C", "#FF9EC4", "#B79CFF"),
    ("#FFFFFF", "#FFD23F", "#FF6F6F", "#7FA8FF"),
    ("#FFF6E8", "#FFC0D9", "#E28AE6", "#FFFFFF"),
    ("#FFFFFF", "#FFF08A", "#9CC8FF", "#C6A6FF"),
    ("#FFE9A8", "#FF9F5A", "#FFFFFF", "#FF7FA8"),
    ("#FFFFFF", "#FFFFFF", "#FFE45C", "#BFA6FF"),
]
