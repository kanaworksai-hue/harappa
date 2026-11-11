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
            "grass_lit": "#7CCB3A", "grass_lit2": "#A6D83C", "grass_shadow": "#278449",
            "grass_deep": "#0C493E", "grass_tip": "#E4F06A",
            "dirt_lit": "#D9C9A0", "dirt_shadow": "#A89878", "dirt_deep": "#7D6F5E",
            "leaf_lit": "#A8DC4A", "leaf_mid": "#4FA83A", "leaf_shadow": "#1C6D51", "leaf_deep": "#09353F",
            "leaf_hi": "#E6F58A", "bloom_lit": "#F7D6E2", "bloom_shadow": "#C995AE",
            "bark_lit": "#7A6250", "bark_shadow": "#2C293F",
            "flower_a": "#FFFFFF", "flower_b": "#F2A7C3", "flower_c": "#FFE45C", "flower_d": "#B79CFF",
            "flower_centre": "#FFC531", "flower_shade": "#B7B9E8", "sun_tint": "#FFFFFF", "rim_colour": "#FFF4C8",
            "haze_colour": "#B4DDF2", "cloud_lit": "#FFFFFF", "cloud_shadow": "#94B4E5", "cloud_deep": "#6790CF", "cloud_rim": "#FFF6D6", "ever_lit": "#8FCB46", "ever_mid": "#3F9440", "ever_shadow": "#19624A", "ever_deep": "#08313A", "mountain_1": "#3F9A6A", "mountain_2": "#5AA0B4", "mountain_3": "#8FBFE0", "bloom_deep": "#B58AB0",
        },
        "tone": {"cloud_shade": 0.8, "cloud_threshold": 0.4, "season_sat": 1.04, "season_contrast": 1.18, "cloud_rim_amount": 0.35, "threshold": 0.44, "deep_threshold": 0.27, "patch_amount": 0.5, "wind_sheen": 0.35, "haze_amount": 0.22, "flower_dim": 1.0, "leaf_deep_threshold": 0.3, "rim_amount": 0.2},
        "sky": ("#1F6FD8", "#A8DBF5", "#B4DDF2"),
        "sky_more": {"mid": "#4E9BEA", "glow": "#FFF8E0", "sun": 0.6, "cirrus": 0.6, "cirrus_colour": "#E8F4FF"},
        "sun": {"elevation": 48.0, "side": -55.0, "colour": "#FFF4D6", "strength": 4.5},
        "night": (0.0, 0.0),
    },
    "SPRING": {
        "name": "Spring Blossom",
        "desc": "Fresh yellow-greens, pink blossoms and pastel flowers",
        "palette": {
            "grass_lit": "#A8DE58", "grass_lit2": "#BEE04E", "grass_shadow": "#277F4F",
            "grass_deep": "#0E443B", "grass_tip": "#E8F57A",
            "dirt_lit": "#E6D6B4", "dirt_shadow": "#B9A88E", "dirt_deep": "#8C7E70",
            "leaf_lit": "#B4E25A", "leaf_mid": "#6FBE4A", "leaf_shadow": "#277055", "leaf_deep": "#0E3B44",
            "leaf_hi": "#EEF7A8", "bloom_lit": "#FFD0E0", "bloom_shadow": "#F08DB4",
            "bark_lit": "#6A5058", "bark_shadow": "#31253A",
            "flower_a": "#FFFFFF", "flower_b": "#FF7FB2", "flower_c": "#FFE04A", "flower_d": "#9C86FF",
            "flower_centre": "#FFD24A", "flower_shade": "#C9C4EC", "sun_tint": "#FFFDF6", "rim_colour": "#FFF6D8",
            "haze_colour": "#C4E2F8", "cloud_lit": "#FFFFFF", "cloud_shadow": "#B0B8F0", "cloud_deep": "#8AA2D9", "cloud_rim": "#FFE9F0", "ever_lit": "#9AD452", "ever_mid": "#4AA046", "ever_shadow": "#236E4F", "ever_deep": "#09343D", "mountain_1": "#5FAE78", "mountain_2": "#86BFC4", "mountain_3": "#94C0EE", "bloom_deep": "#C2588E",
        },
        "tone": {"cloud_shade": 0.75, "cloud_threshold": 0.4, "season_sat": 1.2, "season_contrast": 1.38, "cloud_rim_amount": 0.35, "threshold": 0.42, "deep_threshold": 0.34, "patch_amount": 0.55, "wind_sheen": 0.4, "haze_amount": 0.22, "flower_dim": 1.0, "leaf_deep_threshold": 0.36, "rim_amount": 0.12},
        "sky": ("#3486EA", "#FFC8DC", "#C4E2F8"),
        "sky_more": {"mid": "#56A6F0", "glow": "#FFF6E8", "sun": 0.6, "cirrus": 0.35, "cirrus_colour": "#F4F8FF"},
        "blossom": 0.85,
        "sun": {"elevation": 44.0, "side": -50.0, "colour": "#FFF8EA", "strength": 4.2},
        "night": (0.0, 0.0),
    },
    "GOLDEN": {
        "name": "Golden Hour",
        "desc": "Low warm sun, golden grass, violet shadows",
        "palette": {
            "grass_lit": "#E8C23C", "grass_lit2": "#FFA93A", "grass_shadow": "#9B6832",
            "grass_deep": "#3D245E", "grass_tip": "#FFE88A",
            "dirt_lit": "#EBC59A", "dirt_shadow": "#9A7F86", "dirt_deep": "#5E5068",
            "leaf_lit": "#F0B840", "leaf_mid": "#7E9A3A", "leaf_shadow": "#704255", "leaf_deep": "#4A2E66",
            "leaf_hi": "#FFE27A", "bloom_lit": "#FFD2C8", "bloom_shadow": "#C58AA8",
            "bark_lit": "#B8703C", "bark_shadow": "#2C224C",
            "flower_a": "#FFF2E0", "flower_b": "#FFC94A", "flower_c": "#FF8E8E", "flower_d": "#B58CF0",
            "flower_centre": "#FF9F2E", "flower_shade": "#A99AD8", "sun_tint": "#FFE9C8", "rim_colour": "#FFD36A",
            "haze_colour": "#FFC48A", "cloud_lit": "#FFCC88", "cloud_shadow": "#E16F5C", "cloud_deep": "#AF4A68", "cloud_rim": "#FFF2B0", "ever_lit": "#D8A840", "ever_mid": "#5E8A3E", "ever_shadow": "#43475E", "ever_deep": "#251B4B", "mountain_1": "#4A3C8C", "mountain_2": "#7A6AA8", "mountain_3": "#D89AB8", "bloom_deep": "#9A6E92",
        },
        "tone": {"cloud_shade": 0.7, "cloud_threshold": 0.24, "season_sat": 1.25, "season_contrast": 1.22, "cloud_rim_amount": 0.4, "threshold": 0.34, "deep_threshold": 0.14, "patch_amount": 0.45, "wind_sheen": 0.6, "haze_amount": 0.3, "flower_dim": 0.95, "leaf_deep_threshold": 0.03, "rim_amount": 1.0},
        "sky": ("#2E4CB0", "#FFB25A", "#FFC48A"),
        "sky_more": {"mid": "#8A5CD8", "glow": "#FFD060", "sun": 0.7, "cirrus": 0.7, "cirrus_colour": "#FF9E8A"},
        "sun": {"elevation": 14.0, "side": 158.0, "colour": "#FFB45E", "strength": 5.0},
        "night": (0.0, 0.0),
    },
    "AUTUMN": {
        "name": "Autumn Leaves",
        "desc": "Orange and red trees, dry golden grass",
        "palette": {
            "grass_lit": "#E0A83A", "grass_lit2": "#F08A3A", "grass_shadow": "#9B6430",
            "grass_deep": "#4B2030", "grass_tip": "#F6E28A",
            "dirt_lit": "#D8BC94", "dirt_shadow": "#A08470", "dirt_deep": "#6E5A54",
            "leaf_lit": "#FFA62E", "leaf_mid": "#E85A24", "leaf_shadow": "#9B2127", "leaf_deep": "#4B1732",
            "leaf_hi": "#FFDE5A", "bloom_lit": "#FFE08A", "bloom_shadow": "#D99A48",
            "bark_lit": "#7E5E52", "bark_shadow": "#35292E",
            "flower_a": "#FFF4E2", "flower_b": "#FFC24A", "flower_c": "#E8584A", "flower_d": "#A877D8",
            "flower_centre": "#FF9A30", "flower_shade": "#B39AC8", "sun_tint": "#FFF3DE", "rim_colour": "#FFD08A",
            "haze_colour": "#D2E2EC", "cloud_lit": "#FFFAF0", "cloud_shadow": "#A9B8DF", "cloud_deep": "#8095C9", "cloud_rim": "#FFE6B0", "ever_lit": "#7FB04A", "ever_mid": "#2F6B4A", "ever_shadow": "#1A4F42", "ever_deep": "#0C3136", "mountain_1": "#C8843A", "mountain_2": "#5E86B0", "mountain_3": "#9EC0E0", "bloom_deep": "#A8703A",
        },
        "tone": {"cloud_shade": 0.75, "cloud_threshold": 0.4, "season_sat": 1.1, "season_contrast": 1.15, "cloud_rim_amount": 0.45, "threshold": 0.44, "deep_threshold": 0.2, "patch_amount": 0.35, "wind_sheen": 0.3, "haze_amount": 0.2, "flower_dim": 1.0, "leaf_deep_threshold": 0.22, "rim_amount": 0.4},
        "sky": ("#2466C8", "#CDE6F2", "#D2E2EC"),
        "sky_more": {"mid": "#5A9BE0", "glow": "#FFF2D8", "sun": 0.6, "cirrus": 0.9, "cirrus_colour": "#FFFFFF"},
        "sun": {"elevation": 28.0, "side": -60.0, "colour": "#FFE8BE", "strength": 4.5},
        "night": (0.0, 0.0),
    },
    "NIGHT": {
        "name": "Moonlit Night",
        "desc": "Blue night meadow under a bright moon",
        "palette": {
            "grass_lit": "#4FA6A8", "grass_lit2": "#5BB0A0", "grass_shadow": "#1F5078",
            "grass_deep": "#0E2550", "grass_tip": "#B6F0DC",
            "dirt_lit": "#7E8AA2", "dirt_shadow": "#4C5672", "dirt_deep": "#2C3550",
            "leaf_lit": "#5AA0A0", "leaf_mid": "#2F6A80", "leaf_shadow": "#1A4068", "leaf_deep": "#0A1638",
            "leaf_hi": "#A8E0D2", "bloom_lit": "#E6D8FF", "bloom_shadow": "#7E74B8",
            "bark_lit": "#3A3E66", "bark_shadow": "#141634",
            "flower_a": "#E8F0FF", "flower_b": "#FFF0A8", "flower_c": "#D8A8E8", "flower_d": "#8FA8FF",
            "flower_centre": "#FFE08A", "flower_shade": "#6E78B8", "sun_tint": "#DCE8FF", "rim_colour": "#B8C8F0",
            "haze_colour": "#244E90", "cloud_lit": "#B4C6F6", "cloud_shadow": "#4A5AA8", "cloud_deep": "#323E86", "cloud_rim": "#E6F0FF", "ever_lit": "#5AA0A0", "ever_mid": "#2F6A80", "ever_shadow": "#1A4068", "ever_deep": "#0A1638", "mountain_1": "#16305E", "mountain_2": "#1F4480", "mountain_3": "#2C5A9C", "bloom_deep": "#4E4A80",
        },
        "tone": {"cloud_shade": 0.2, "cloud_threshold": 0.16, "season_sat": 1.0, "season_contrast": 1.15, "cloud_rim_amount": 0.5, "threshold": 0.46, "deep_threshold": 0.14, "patch_amount": 0.25, "wind_sheen": 0.5, "haze_amount": 0.45, "flower_dim": 0.8, "leaf_deep_threshold": 0.18, "rim_amount": 0.25},
        "sky": ("#060F3A", "#2F62B0", "#244E90"),
        "sky_more": {"mid": "#14307A", "glow": "#7FA8FF", "sun": 0.0, "cirrus": 0.15, "cirrus_colour": "#5C78C8"},
        "sun": {"elevation": 34.0, "side": -40.0, "colour": "#DCE8FF", "strength": 3.6},
        "night": (1.0, 1.0),
    },
    "MISTY": {
        "name": "Misty Morning",
        "desc": "Soft pale greens and a hazy low-contrast light",
        "palette": {
            "grass_lit": "#8FD06A", "grass_lit2": "#B4DC70", "grass_shadow": "#27765F",
            "grass_deep": "#104246", "grass_tip": "#EAF7B0",
            "dirt_lit": "#DCD6C4", "dirt_shadow": "#B8B4A8", "dirt_deep": "#9A9890",
            "leaf_lit": "#A0D870", "leaf_mid": "#6CB878", "leaf_shadow": "#418875", "leaf_deep": "#2A5E62",
            "leaf_hi": "#E4F0C8", "bloom_lit": "#FBE6EE", "bloom_shadow": "#D2AFC2",
            "bark_lit": "#8C8078", "bark_shadow": "#555257",
            "flower_a": "#FFFFFF", "flower_b": "#F8EEA8", "flower_c": "#F2C6D8", "flower_d": "#CBC2EE",
            "flower_centre": "#F2D27A", "flower_shade": "#C8CCE0", "sun_tint": "#FAFCFF", "rim_colour": "#FFE6B0",
            "haze_colour": "#D6EAF2", "cloud_lit": "#FFF6EC", "cloud_shadow": "#B5C2E1", "cloud_deep": "#93A6D1", "cloud_rim": "#FFE0B0", "ever_lit": "#8ED070", "ever_mid": "#4A9E60", "ever_shadow": "#236B59", "ever_deep": "#2A5A58", "mountain_1": "#4E9A86", "mountain_2": "#6EB2BE", "mountain_3": "#B4CCE0", "bloom_deep": "#B89AAE",
        },
        "tone": {"cloud_shade": 0.55, "cloud_threshold": 0.4, "season_sat": 1.18, "season_contrast": 1.25, "cloud_rim_amount": 0.6, "threshold": 0.42, "deep_threshold": 0.18, "patch_amount": 0.5, "wind_sheen": 0.25, "haze_amount": 0.3, "flower_dim": 1.0, "leaf_deep_threshold": 0.08, "rim_amount": 0.45},
        "sky": ("#4A96E4", "#FFD8B0", "#D6EAF2"),
        "sky_more": {"mid": "#86C0EE", "glow": "#FFF0C8", "sun": 0.8, "cirrus": 0.3, "cirrus_colour": "#FFF4E6"},
        "sun": {"elevation": 14.0, "side": -120.0, "colour": "#FFE6C0", "strength": 3.8},
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
                       "leaf_hi_amount": 0.5,
                       "style_sat": 1.0, "style_contrast": 1.0, "cloud_jitter": 1.0,
                       "sky_brush": 0.0, "sky_bands": 0.0, "cirrus_mult": 1.0, "ridge_soft": 0.02, "sky_curve": 1.0}},
    "PAINTERLY": {"name": "Painterly", "desc": "Broken, brushy shadow edges and lots of small clumps",
                  "keys": {"softness": 0.05, "brush_jitter": 1.1, "clump_size": 0.9, "clump_strength": 2.4,
                           "clump_small": 1.1, "root_dark": 0.5, "tip_light": 0.75, "leaf_ao": 0.9,
                           "leaf_hi_amount": 0.9,
                       "style_sat": 0.94, "style_contrast": 1.06, "cloud_jitter": 2.4,
                       "sky_brush": 0.7, "sky_bands": 0.0, "cirrus_mult": 1.7, "ridge_soft": 0.1, "sky_curve": 0.44}},
    "CRISP": {"name": "Crisp Cel", "desc": "Hard two-tone edges, big graphic shapes",
              "keys": {"softness": 0.0, "brush_jitter": 0.04, "clump_size": 3.2, "clump_strength": 1.5,
                       "clump_small": 0.12, "root_dark": 0.15, "tip_light": 0.0, "leaf_ao": 0.5,
                       "leaf_hi_amount": 0.0,
                       "style_sat": 1.05, "style_contrast": 1.14, "cloud_jitter": 0.15,
                       "sky_brush": 0.0, "sky_bands": 1.0, "cirrus_mult": 0.3, "ridge_soft": 0.004, "sky_curve": 0.45}},
    "SOFT": {"name": "Soft Pastel", "desc": "Gentle gradients, quiet shadows",
             "keys": {"softness": 0.2, "brush_jitter": 0.08, "clump_size": 2.6, "clump_strength": 1.3,
                      "clump_small": 0.2, "root_dark": 0.45, "tip_light": 0.2, "leaf_ao": 0.3,
                      "leaf_hi_amount": 0.15,
                       "style_sat": 1.04, "style_contrast": 1.02, "cloud_jitter": 0.6,
                       "sky_brush": 0.08, "sky_bands": 0.0, "cirrus_mult": 0.7, "ridge_soft": 0.3, "sky_curve": 1.55}},
}

STYLE_KEYS = tuple(STYLES["ANIME"]["keys"].keys())
TONE_KEYS = ("threshold", "deep_threshold", "patch_amount", "wind_sheen", "haze_amount", "flower_dim",
             "cloud_rim_amount", "cloud_threshold", "season_sat", "season_contrast",
             "leaf_deep_threshold", "rim_amount", "cloud_shade")
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
