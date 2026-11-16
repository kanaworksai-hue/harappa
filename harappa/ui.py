# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Harappa tab in the 3D view sidebar (N). Every text goes through i18n.t(), so the panel follows
Blender's language automatically, or the language picked in the 🌐 header menu."""
import bpy

from . import i18n
from .i18n import t

ENUMS = ("season", "style", "new_shape", "mask_paint", "weather")


def _prop(layout, owner, name, label=None, **kw):
    if label is None:
        label = owner.bl_rna.properties[name].name
    layout.prop(owner, name, text=t(label), translate=False, **kw)


def _op(layout, idname, label, **kw):
    return layout.operator(idname, text=t(label), text_ctxt="Operator", translate=False, **kw)


def _enum(layout, owner, name, label=None):
    prop = owner.bl_rna.properties[name]
    cur = getattr(owner, name)
    item = next((i.name for i in prop.enum_items if i.identifier == cur), cur)
    row = layout.row(align=True)
    row.label(text=t(label or prop.name), translate=False)
    row.menu(f"HRP_MT_{name}", text=t(item), translate=False)


def _enum_menu(prop_name):
    class _M(bpy.types.Menu):
        bl_idname = f"HRP_MT_{prop_name}"
        bl_label = prop_name.title()

        def draw(self, context):
            s = context.scene.harappa
            for it in s.bl_rna.properties[prop_name].enum_items:
                op = self.layout.operator("harappa.set_enum", text=t(it.name), translate=False,
                                          depress=getattr(s, prop_name) == it.identifier)
                op.prop = prop_name
                op.value = it.identifier
    _M.__name__ = f"HRP_MT_{prop_name}"
    return _M


class HRP_MT_water_kind(bpy.types.Menu):
    bl_idname = "HRP_MT_water_kind"
    bl_label = "Water Type"

    def draw(self, context):
        from . import water
        ob = context.active_object
        if not water.is_water(ob):
            return
        ws = ob.harappa_water
        for it in ws.bl_rna.properties["kind"].enum_items:
            op = self.layout.operator("harappa.set_water_enum", text=t(it.name), translate=False,
                                      depress=ws.kind == it.identifier)
            op.value = it.identifier


def _tree_enum_menu(prop_name):
    class _M(bpy.types.Menu):
        bl_idname = f"HRP_MT_tree_{prop_name}"
        bl_label = prop_name.title()

        def draw(self, context):
            from . import tree_root
            root = tree_root(context.active_object)
            if root is None:
                return
            ts = root.harappa_tree
            for it in ts.bl_rna.properties[prop_name].enum_items:
                op = self.layout.operator("harappa.set_tree_enum", text=t(it.name), translate=False,
                                          depress=getattr(ts, prop_name) == it.identifier)
                op.prop = prop_name
                op.value = it.identifier
    _M.__name__ = f"HRP_MT_tree_{prop_name}"
    return _M


def _mod_inputs(layout, mod, names):
    ng = mod.node_group
    if ng is None:
        return
    props = getattr(mod, "properties", None)
    for name in names:
        item = next((i for i in ng.interface.items_tree if getattr(i, "item_type", "") == "SOCKET"
                     and i.in_out == "INPUT" and i.name == name), None)
        if item is None:
            continue
        if props is not None and hasattr(props, "inputs"):
            slot = getattr(props.inputs, item.identifier, None)
            if slot is not None:
                layout.prop(slot, "value", text=t(name), translate=False)
                continue
        layout.prop(mod, f'["{item.identifier}"]', text=t(name), translate=False)


class HrpPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Harappa"


class HrpSub(HrpPanel):
    bl_parent_id = "HRP_PT_main"
    bl_options = {"DEFAULT_CLOSED"}
    title = ""

    def draw_header(self, context):
        self.layout.label(text=t(self.title), translate=False)


class HRP_PT_main(HrpPanel, bpy.types.Panel):
    bl_label = "Harappa"
    bl_idname = "HRP_PT_main"

    def draw_header_preset(self, context):
        prefs = i18n.prefs(context)
        if prefs is not None:
            self.layout.prop(prefs, "ui_language", text="", icon="WORLD_DATA")

    def draw(self, context):
        s = context.scene.harappa
        layout = self.layout
        col = layout.column(align=True)
        col.scale_y = 1.5
        _op(col, "harappa.make_meadow", "Make Anime Meadow", icon="OUTLINER_OB_POINTCLOUD")
        box = layout.box()
        col = box.column(align=True)
        _enum(col, s, "new_shape")
        row = col.row(align=True)
        _prop(row, s, "new_height", "Height")
        _prop(row, s, "new_blossom")
        row = box.row(align=True)
        row.scale_y = 1.3
        _op(row, "harappa.add_tree", "Add Anime Tree", icon="OUTLINER_OB_FORCE_FIELD")
        row = box.row(align=True)
        _op(row, "harappa.plant_trees", "Plant Trees", icon="OUTLINER_COLLECTION")
        _prop(row, s, "plant_count")
        col = layout.column(align=True)
        _enum(col, s, "season")
        _enum(col, s, "style")
        row = layout.row(align=True)
        _prop(row, s, "variation")
        _op(row, "harappa.shuffle", "Shuffle", icon="FILE_REFRESH")
        row = layout.row(align=True)
        _op(row, "harappa.add_clouds", "Add Clouds", icon="OUTLINER_DATA_VOLUME")
        _prop(row, s, "cloud_count")
        row = layout.row(align=True)
        _op(row, "harappa.make_foliage", "Make Foliage", icon="MOD_PARTICLE_INSTANCE")
        _op(row, "harappa.setup_scene", "Anime Sky & Sun", icon="LIGHT_SUN")
        row = layout.row(align=True)
        _op(row, "harappa.revert", "Remove Grass", icon="LOOP_BACK")
        _op(row, "harappa.reset", "Reset to Defaults", icon="FILE_BLANK")
        if context.scene.render.engine not in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            layout.label(text=t("Made for EEVEE (Anime Sky & Sun switches)"), icon="INFO", translate=False)


class HRP_PT_meadow(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_meadow"
    title = "Active Meadow"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        from . import meadow_of
        return meadow_of(context.active_object) is not None

    def draw(self, context):
        from . import build
        ob = context.active_object
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.2
        op = _op(row, "harappa.paint_mask", "Paint Path", icon="BRUSH_DATA")
        op.value = 0.0
        op = _op(row, "harappa.paint_mask", "Paint Grass", icon="OUTLINER_OB_POINTCLOUD")
        op.value = 1.0
        if context.mode == "PAINT_VERTEX":
            layout.label(text=t("Black = bare path, white = grass"), icon="INFO", translate=False)
        gm = ob.modifiers.get(build.GRASS_MOD)
        _prop(layout, context.scene.harappa, "camera_culling")
        col = layout.column(align=True)
        col.label(text=t("Grass"), translate=False)
        _mod_inputs(col, gm, ("Density", "Height", "Height Random", "Width", "Edge Shrink", "LOD Distance",
                              "Seed"))
        col = layout.column(align=True)
        col.label(text=t("Wind"), translate=False)
        _mod_inputs(col, gm, ("Wind Strength", "Wind Speed", "Wind Scale", "Wind Direction", "Edge Wind"))
        fm = ob.modifiers.get(build.FLOWER_MOD)
        if fm is not None:
            col = layout.column(align=True)
            col.label(text=t("Flowers"), translate=False)
            _mod_inputs(col, fm, ("Density", "Patch Size", "Patch Amount", "Size", "Height", "Seed"))


class HRP_PT_tree(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_tree"
    title = "Active Tree"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        from . import tree_root
        ob = context.active_object
        return tree_root(ob) is not None or (ob is not None and ob.get("hrp_canopy"))

    def draw(self, context):
        from . import tree_canopy, tree_root
        layout = self.layout
        root = tree_root(context.active_object)
        canopy = tree_canopy(root) if root else context.active_object
        if root is not None:
            ts = root.harappa_tree
            col = layout.column(align=True)
            for name in ("shape", "leaf_style"):
                prop = ts.bl_rna.properties[name]
                cur = getattr(ts, name)
                item = next((i.name for i in prop.enum_items if i.identifier == cur), cur)
                row = col.row(align=True)
                row.label(text=t(prop.name), translate=False)
                row.menu(f"HRP_MT_tree_{name}", text=t(item), translate=False)
            row = col.row(align=True)
            _prop(row, ts, "height")
            _prop(row, ts, "seed")
            op = _op(col, "harappa.rebuild_tree", "New Shape", icon="FILE_REFRESH")
            op.new_seed = True
        if canopy is None:
            return
        mod = canopy.modifiers.get("Harappa Foliage")
        if mod is not None:
            col = layout.column(align=True)
            col.label(text=t("Leaves"), translate=False)
            _mod_inputs(col, mod, ("Density", "Leaf Size", "Size Random", "Inflate", "Roundness", "Blossom",
                                   "Blossom Scale", "Fill Inside", "Seed"))
            col = layout.column(align=True)
            col.label(text=t("Wind"), translate=False)
            _mod_inputs(col, mod, ("Wind Strength", "Wind Speed", "Wind Scale", "Wind Direction"))
        col = layout.column(align=True)
        col.label(text=t("Tint"), translate=False)
        if "hrp_hue" in canopy:
            col.prop(canopy, '["hrp_hue"]', text=t("Hue Shift"), translate=False, slider=True)
        if "hrp_value" in canopy:
            col.prop(canopy, '["hrp_value"]', text=t("Brightness"), translate=False, slider=True)
        _op(layout, "harappa.edit_canopy", "Shape Canopy", icon="EDITMODE_HLT")


class HRP_PT_water(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_water"
    title = "Water"

    def draw(self, context):
        from . import water
        s = context.scene.harappa
        layout = self.layout
        ob = context.active_object
        # 1. create
        layout.label(text=t("Create"), translate=False)
        row = layout.row(align=True)
        row.scale_y = 1.3
        _op(row, "harappa.add_pond", "Add Pond", icon="MOD_FLUIDSIM")
        _op(row, "harappa.add_stream", "Add Stream", icon="MOD_OCEAN")
        row = layout.row(align=True)
        row.scale_y = 1.3
        _op(row, "harappa.add_waterfall", "Add Waterfall", icon="FORCE_FLUIDFLOW")
        _op(row, "harappa.add_rock", "Add Rock", icon="MESH_ICOSPHERE")
        _op(layout, "harappa.make_water", "Make Water from Curves", icon="OUTLINER_OB_CURVE")
        # 2. the selected thing
        if ob is not None and ob.get("hrp_waterfall") is not None:
            from . import waterfall
            fall = waterfall.fall_of(context, ob["hrp_waterfall"])
            box = layout.box()
            box.label(text=t("Selected Waterfall"), icon="FORCE_FLUIDFLOW", translate=False)
            if fall is not None:
                col = box.column(align=True)
                _prop(col, fall.harappa_fall, "flow", slider=True)
                _prop(col, fall.harappa_fall, "height")
                _prop(col, fall.harappa_fall, "width")
                _prop(col, fall.harappa_fall, "seed")
            _op(box, "harappa.remove_waterfall", "Remove Waterfall", icon="TRASH")
        if ob is not None and ob.get("hrp_rock") is not None:
            box = layout.box()
            box.label(text=t("Selected Rock"), icon="MESH_ICOSPHERE", translate=False)
            col = box.column(align=True)
            for k in ("size", "flat", "seed"):
                _prop(col, ob.harappa_rock, k)
            _prop(col, ob.harappa_rock, "moss", slider=True)
        if ob is not None and ob.get("hrp_boat") is not None:
            box = layout.box()
            box.label(text=t("Selected Boat"), icon="MOD_OCEAN", translate=False)
            _mod_inputs(box.column(align=True), ob.modifiers.get("Harappa Float"), ("Draft", "Bob", "Sway", "Speed"))
        if water.is_water(ob):
            pond = any(sp.use_cyclic_u for sp in ob.data.splines)
            box = layout.box()
            box.label(text=t("Selected Water") + ": " + ob.name, icon="MOD_FLUIDSIM", translate=False)
            ws = ob.harappa_water
            prop = ws.bl_rna.properties["kind"]
            item = next((i.name for i in prop.enum_items if i.identifier == ws.kind), ws.kind)
            row = box.row(align=True)
            row.label(text=t("Water Type"), translate=False)
            row.menu("HRP_MT_water_kind", text=t(item), translate=False)
            col = box.column(align=True)
            for k in ("hue", "saturation", "brightness", "clarity"):
                _prop(col, ws, k, slider=True)
            if pond:
                row = box.row(align=True)
                _prop(row, ws, "size")
                if ob.get("hrp_pond") is not None:
                    _prop(row, ws, "shape_seed")
            col = box.column(align=True)
            names = ("Depth", "Shelf") if pond else ("Width", "Depth", "Shelf", "Flow Speed")
            _mod_inputs(col, ob.modifiers.get(water.SURFACE_MOD), names)
            life = ob.modifiers.get("Harappa Pond Life")
            if pond or life is not None:
                sub = box.box()
                sub.label(text=t("Pond Life"), translate=False)
                if life is not None:
                    _mod_inputs(sub.column(align=True), life, ("Lily Pads", "Pad Size", "Flowers", "Seed"))
                if pond:
                    row = sub.row(align=True)
                    _op(row, "harappa.add_fish", "Add Koi", icon="OUTLINER_OB_FORCE_FIELD")
                    _op(row, "harappa.add_boat", "Add Boat", icon="MOD_OCEAN")
                    fish = next((c for c in ob.children if c.get("hrp_fish")), None)
                    if fish is not None:
                        _mod_inputs(sub.column(align=True), fish.modifiers.get("Harappa Fish"),
                                    ("Count", "Size", "Speed"))
            if not pond:
                _op(box, "harappa.stepping_stones", "Add Stepping Stones", icon="OUTLINER_DATA_POINTCLOUD")
            row = box.row(align=True)
            if not pond:
                _op(row, "harappa.drop_stream", "Drop Onto Meadow", icon="IMPORT")
            _op(row, "harappa.remove_water", "Remove Water", icon="TRASH")
        # 3. the shore of every pond and stream (on the meadow)
        gnd = next((m for m in water.meadows(context.scene) if m.modifiers.get(water.CARVE_MOD)), None)
        if gnd is not None:
            col = layout.column(align=True)
            col.label(text=t("Shore (all ponds & streams)"), translate=False)
            shore = gnd.modifiers.get("Harappa Shore")
            if shore is not None:
                _mod_inputs(col, shore, ("Reeds", "Reed Height", "Pebble Density", "Pebble Size"))
            _mod_inputs(col, gnd.modifiers.get(water.CARVE_MOD), ("Bank", "Bank Height", "Slope"))
        # 4. every water surface
        col = layout.column(align=True)
        col.label(text=t("All Water"), translate=False)
        for k in ("water_rain", "water_caustics", "water_glints", "water_glow"):
            _prop(col, s, k, slider=True)
        # 5. playback speed
        if gnd is not None:
            col = layout.column(align=True)
            col.label(text=t("Fast Playback (Freeze Banks)"), translate=False)
            row = col.row(align=True)
            if gnd.get("hrp_banks_frozen"):
                op = _op(row, "harappa.freeze_banks", "Update Banks", icon="FILE_REFRESH")
                op.on = True
                op = _op(row, "harappa.freeze_banks", "Live Banks", icon="UNLOCKED")
                op.on = False
            else:
                op = _op(row, "harappa.freeze_banks", "Freeze Banks", icon="LOCKED")
                op.on = True


class HRP_PT_weather(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_weather"
    title = "Weather"

    def draw(self, context):
        s = context.scene.harappa
        layout = self.layout
        _enum(layout, s, "weather")
        if s.weather in ("RAIN", "STORM"):
            col = layout.column(align=True)
            _prop(col, s, "rain_amount", slider=True)
            _prop(col, s, "rain_radius")
            row = layout.row(align=True)
            _prop(row, s, "rain_follow")
            _op(row, "harappa.rain_here", "Rain Here", icon="PIVOT_CURSOR")
        row = layout.row(align=True)
        _prop(row, s, "rainbow")
        sub = row.row(align=True)
        sub.active = s.rainbow
        _prop(sub, s, "rainbow_strength", slider=True)
        _prop(layout, s, "dragonfly_count")
        col = layout.column(align=True)
        _prop(col, s, "firefly_count")
        _prop(col, s, "fireflies", slider=True)
        _prop(col, s, "firefly_colour")
        if s.firefly_count > 0 and s.fireflies <= 0.0:
            layout.label(text=t("Fireflies glow at Golden Hour and Night: raise Firefly Glow for day"), icon="INFO",
                         translate=False)


class HRP_PT_light(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_light"
    title = "Light & Sky"

    def draw(self, context):
        s = context.scene.harappa
        col = self.layout.column(align=True)
        for k in ("sun_elevation", "sun_side"):
            _prop(col, s, k)
        col = self.layout.column(align=True)
        for k in ("threshold", "deep_threshold", "softness"):
            _prop(col, s, k)
        col = self.layout.column(align=True)
        for k in ("haze_amount", "haze_start", "haze_end"):
            _prop(col, s, k)
        col = self.layout.column(align=True)
        for k in ("rim_amount", "rim_colour"):
            _prop(col, s, k)
        col = self.layout.column(align=True)
        for k in ("sky_zenith", "sky_horizon", "haze_colour", "sun_tint"):
            _prop(col, s, k)


class HRP_PT_paint(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_paint"
    title = "Brushwork"

    def draw(self, context):
        s = context.scene.harappa
        col = self.layout.column(align=True)
        for k in ("clump_size", "clump_strength", "clump_small", "brush_jitter"):
            _prop(col, s, k)
        col = self.layout.column(align=True)
        for k in ("root_dark", "tip_light", "wind_sheen", "patch_amount"):
            _prop(col, s, k)
        col = self.layout.column(align=True)
        for k in ("leaf_ao", "leaf_hi_amount", "leaf_deep_threshold", "flower_dim"):
            _prop(col, s, k)


class HRP_PT_colours(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_colours"
    title = "Colours"

    def draw(self, context):
        s = context.scene.harappa
        groups = (
            ("Grass", ("grass_lit", "grass_lit2", "grass_shadow", "grass_deep", "grass_tip")),
            ("Path", ("dirt_lit", "dirt_shadow", "dirt_deep")),
            ("Leaves", ("leaf_lit", "leaf_mid", "leaf_shadow", "leaf_deep", "leaf_hi")),
            ("Blossoms & Bark", ("bloom_lit", "bloom_shadow", "bloom_deep", "bark_lit", "bark_shadow")),
            ("Clouds", ("cloud_lit", "cloud_shadow", "cloud_deep")),
            ("Flowers", ("flower_a", "flower_b", "flower_c", "flower_d", "flower_centre", "flower_shade")),
            ("Water", ("water_shallow", "water_mid", "water_deep", "water_foam", "water_line", "water_sky",
                       "water_shade")),
            ("Rocks", ("rock_lit", "rock_lit2", "rock_shadow", "rock_deep")),
            ("Fireflies", ("firefly_colour",)),
        )
        for title, keys in groups:
            col = self.layout.column(align=True)
            col.label(text=t(title), translate=False)
            flow = col.grid_flow(columns=2, align=True)
            for k in keys:
                _prop(flow, s, k)
            if title == "Rocks":
                _prop(col, s, "rock_moss", slider=True)


class HRP_PT_links(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_links"
    title = "About"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Harappa by KanaWorks_AI", translate=False)
        col.operator("wm.url_open", text=t("Free add-ons (GitHub)"), translate=False,
                     icon="URL").url = "https://github.com/kanaworksai-hue"
        col.operator("wm.url_open", text="X @KanaWorks_AI", translate=False,
                     icon="URL").url = "https://x.com/KanaWorks_AI"


MENUS = [_enum_menu(n) for n in ENUMS] + [_tree_enum_menu(n) for n in ("shape", "leaf_style")] + [HRP_MT_water_kind]
PANELS = (HRP_PT_main, HRP_PT_meadow, HRP_PT_tree, HRP_PT_water, HRP_PT_weather, HRP_PT_light, HRP_PT_paint, HRP_PT_colours, HRP_PT_links)


def register():
    for c in MENUS:
        bpy.utils.register_class(c)
    for c in PANELS:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(PANELS):
        bpy.utils.unregister_class(c)
    for c in reversed(MENUS):
        bpy.utils.unregister_class(c)
