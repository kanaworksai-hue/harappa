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
            "haze_colour": "#CFE6F2", "cloud_lit": "#FFFFFF", "cloud_shadow": "#CDD0E6", "cloud_deep": "#D6D2E6", "bloom_deep": "#B58AB0",
        },
        "tone": {"threshold": 0.42, "deep_threshold": 0.12, "patch_amount": 0.5, "wind_sheen": 0.35, "haze_amount": 0.3, "flower_dim": 1.0, "leaf_deep_threshold": 0.18, "rim_amount": 0.12},
        "sky": ("#3E86D6", "#CFE6F2", "#C9DFD8"),
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
            "haze_colour": "#E6F0F2", "cloud_lit": "#FFFFFF", "cloud_shadow": "#D2CBE2", "cloud_deep": "#F0E2E6", "bloom_deep": "#C08AB2",
        },
        "tone": {"threshold": 0.36, "deep_threshold": 0.08, "patch_amount": 0.55, "wind_sheen": 0.4, "haze_amount": 0.38, "flower_dim": 1.0, "leaf_deep_threshold": 0.18, "rim_amount": 0.12},
        "sky": ("#6FAEE6", "#EEEEEC", "#D8E8DC"),
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
            "haze_colour": "#F6D2A8", "cloud_lit": "#FFE2B8", "cloud_shadow": "#C9A0B4", "cloud_deep": "#F0B8A0", "bloom_deep": "#9A6E92",
        },
        "tone": {"threshold": 0.5, "deep_threshold": 0.16, "patch_amount": 0.45, "wind_sheen": 0.45, "haze_amount": 0.3, "flower_dim": 0.95, "leaf_deep_threshold": 0.182, "rim_amount": 0.6},
        "sky": ("#6A86C4", "#FFCF9E", "#E6C3A6"),
        "sun": {"elevation": 16.0, "side": -75.0, "colour": "#FFD9A0", "strength": 4.0},
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
            "haze_colour": "#EADCC4", "cloud_lit": "#FFF8EC", "cloud_shadow": "#CDBFCB", "cloud_deep": "#EEDCD0", "bloom_deep": "#A8703A",
        },
        "tone": {"threshold": 0.44, "deep_threshold": 0.13, "patch_amount": 0.35, "wind_sheen": 0.3, "haze_amount": 0.32, "flower_dim": 1.0, "leaf_deep_threshold": 0.18, "rim_amount": 0.3},
        "sky": ("#4F86C6", "#F0E2CA", "#DCCDB4"),
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
            "haze_colour": "#2E4670", "cloud_lit": "#6E82B6", "cloud_shadow": "#2A3A64", "cloud_deep": "#1E2C52", "bloom_deep": "#4E4A80",
        },
        "tone": {"threshold": 0.46, "deep_threshold": 0.14, "patch_amount": 0.4, "wind_sheen": 0.5, "haze_amount": 0.45, "flower_dim": 0.6, "leaf_deep_threshold": 0.18, "rim_amount": 0.25},
        "sky": ("#0B1838", "#34507E", "#26385A"),
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
            "haze_colour": "#DDE6E3", "cloud_lit": "#F4F6F6", "cloud_shadow": "#DDE2E6", "cloud_deep": "#E6E8E8", "bloom_deep": "#B89AAE",
        },
        "tone": {"threshold": 0.3, "deep_threshold": 0.05, "patch_amount": 0.5, "wind_sheen": 0.25, "haze_amount": 0.75, "flower_dim": 1.0, "leaf_deep_threshold": 0.1, "rim_amount": 0.0},
        "sky": ("#A8C4D8", "#EEF2F0", "#DDE6E0"),
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
