# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Harappa tab in the 3D view sidebar (N). Every text goes through i18n.t(), so the panel follows
Blender's language automatically, or the language picked in the 🌐 header menu."""
import bpy

from . import i18n
from .i18n import t

ENUMS = ("season", "style", "new_shape", "mask_paint")


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
    row = layout.split(factor=0.36, align=True)
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


def _mod_inputs(layout, mod, names, labels=None):
    ng = mod.node_group
    if ng is None:
        return
    labels = labels or {}
    props = getattr(mod, "properties", None)
    for name in names:
        item = next((i for i in ng.interface.items_tree if getattr(i, "item_type", "") == "SOCKET"
                     and i.in_out == "INPUT" and i.name == name), None)
        if item is None:
            continue
        if props is not None and hasattr(props, "inputs"):
            slot = getattr(props.inputs, item.identifier, None)
            if slot is not None:
                layout.prop(slot, "value", text=t(labels.get(name, name)), translate=False)
                continue
        layout.prop(mod, f'["{item.identifier}"]', text=t(labels.get(name, name)), translate=False)


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
        from . import _painting_target
        s = context.scene.harappa
        layout = self.layout
        painting = _painting_target(context)
        if painting is not None:                     # while painting: only what painting needs, Done at the top
            box = layout.box()
            box.label(text=i18n.report(f"Painting {t(_layer_name(s.paint_layer))} on {painting.name}"),
                      icon="BRUSH_DATA", translate=False)
            row = box.row()
            row.scale_y = 1.6
            _op(row, "harappa.paint_done", "Done Painting", icon="CHECKMARK", depress=True)
            box.label(text=t("The other settings come back when you are done"), translate=False)
            return
        col = layout.column(align=True)
        col.scale_y = 1.5
        _op(col, "harappa.make_meadow", "Make Anime Meadow", icon="OUTLINER_OB_POINTCLOUD")
        _avoid_this(layout, context)
        box = layout.box()
        col = box.column(align=True)
        _enum(col, s, "new_shape", "New Tree")
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
        row = col.split(factor=0.36, align=True)
        row.label(text=t("Look"), translate=False)
        sub = row.row(align=True)
        sub.menu("HRP_MT_looks", text=_look_label(context), translate=False)
        sub.operator("harappa.look_save", text=t("Save"), translate=False, icon="ADD")
        sub.menu("HRP_MT_look_more", text="", icon="DOWNARROW_HLT")
        col = layout.column(align=True)
        _prop(col, s, "grade_sat")
        _prop(col, s, "grade_contrast")
        col = layout.column(align=True)
        col.label(text=t("Detail Level"), translate=False)
        row = col.row(align=True)
        for it in s.bl_rna.properties["detail_level"].enum_items:
            op = row.operator("harappa.set_detail", text=t(it.name), translate=False,
                              depress=s.detail_level == it.identifier)
            op.level = it.identifier
        row = layout.split(factor=0.55, align=True)
        _prop(row, s, "variation")
        _op(row, "harappa.shuffle", "Shuffle", icon="FILE_REFRESH")
        row = layout.split(factor=0.62, align=True)
        _op(row, "harappa.add_clouds", "Make Clouds", icon="OUTLINER_DATA_VOLUME")
        _prop(row, s, "cloud_count", "Count")
        row = layout.split(factor=0.62, align=True)
        _op(row, "harappa.add_ridges", "Distant Mountains", icon="IPO_ELASTIC")
        _prop(row, s, "ridge_layers", "Layers")
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
        gm = ob.modifiers.get(build.GRASS_MOD)
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


_previews = {"coll": None}


def _swatch_icon(key, rgb):
    """A small square of a palette colour, for the swatch buttons (redrawn only when the colour changes)."""
    from bpy.utils import previews
    if _previews["coll"] is None:
        _previews["coll"] = previews.new()
    pc = _previews["coll"]
    pv = pc.get(key) or pc.new(key)
    want = tuple(round(c, 4) for c in rgb[:3])
    if _previews.get(key) != want:
        n = 16
        srgb = [c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in want]
        pv.icon_size = (n, n)
        pv.icon_pixels_float = [*srgb, 1.0] * (n * n)
        pv.image_size = (n, n)
        pv.image_pixels_float = [*srgb, 1.0] * (n * n)
        _previews[key] = want
    return pv.icon_id


LAYER_ICONS = {"GRASS": "OUTLINER_OB_POINTCLOUD", "FLOWERS": "OUTLINER_OB_FORCE_FIELD", "HEIGHT": "SORT_ASC",
               "COLOUR": "COLOR"}


MODE_LABELS = {                                    # what Paint / Erase mean on each layer
    "GRASS": ("Grow Grass", "Make Path"),
    "FLOWERS": ("More Flowers", "No Flowers"),
    "HEIGHT": ("Taller", "Shorter"),
    "COLOUR": ("Paint Colour", "Remove Colour"),
}
LAYER_HINTS = {
    "GRASS": "Make Path clears the grass, Grow Grass brings it back",
    "FLOWERS": "More Flowers paints dense flower beds",
    "HEIGHT": "Up to twice as tall, down to bare ground",
    "COLOUR": "The sunlit grass takes the colour; shade still falls on it",
}
SWATCH_NAMES = {"grass_tip": "Sunlit Tips", "grass_lit2": "Fresh Green", "flower_b": "Flower Yellow",
                "flower_c": "Flower Pink", "flower_d": "Flower Violet"}


def _layer_name(key):
    from . import PAINT_LAYERS
    return next((n for k, n, _d in PAINT_LAYERS if k == key), key)


def _look_label(context):
    from . import looks
    s = context.scene.harappa
    if not s.look_name:
        return t("Season Default")
    try:
        same = context.scene.get("hrp_look_fp") == looks.fingerprint(context)
    except (AttributeError, KeyError, TypeError):
        same = True
    return s.look_name + ("" if same else " *")


def _avoid_this(layout, context):
    """The user's own object is selected and there is a meadow: offer to make the grass avoid it right here."""
    from . import avoid, look
    ob = context.active_object
    if ob is None or look.is_harappa(ob) or ob.type not in ("MESH", "ARMATURE") or ob.get("hrp_card") \
            or ob.name.startswith("HRP ") or not avoid.meadows(context.scene):
        return
    col = avoid.current(context.scene)
    row = layout.row(align=True)
    if col is not None and col.objects.get(ob.name) is ob:
        op = _op(row, "harappa.avoid_remove", "Let Grass Grow Through It", icon="REMOVE")
        op.name = ob.name
    else:
        _op(row, "harappa.avoid_add", "Make Grass Avoid It", icon="MOD_PHYSICS")


def _brush_panel(layout, context, ob):
    from . import SWATCHES, layers
    s = context.scene.harappa
    painting = context.mode == "PAINT_VERTEX" and context.active_object == ob
    col = layout.column(align=True)
    grid = col.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    grid.scale_y = 1.3
    prop = s.bl_rna.properties["paint_layer"]
    for it in prop.enum_items:
        op = grid.operator("harappa.paint_layer", text=t(it.name), translate=False, icon=LAYER_ICONS[it.identifier],
                           depress=painting and s.paint_layer == it.identifier)
        op.layer = it.identifier
    if not painting:
        layout.label(text=t("Click a layer to paint it"), icon="INFO", translate=False)
    else:
        row = layout.row()
        row.scale_y = 1.4
        _op(row, "harappa.paint_done", "Done Painting", icon="CHECKMARK", depress=True)
        paint_l, erase_l = MODE_LABELS[s.paint_layer]
        row = layout.row(align=True)
        for ident, label in (("PAINT", paint_l), ("ERASE", erase_l), ("SMOOTH", "Smooth")):
            row.prop_enum(s, "paint_mode", ident, text=t(label), translate=False)
        col = layout.column(align=True)
        _prop(col, s, "paint_strength")
        if s.paint_layer == "COLOUR":
            _prop(col, s, "paint_colour", "Paint Colour")
            row = col.row(align=True)
            for k in SWATCHES:
                op = row.operator("harappa.paint_swatch", text="", icon_value=_swatch_icon(k, getattr(s, k)))
                op.key = k
        row = layout.row(align=True)
        fill = "Erase Whole Layer" if s.paint_mode == "ERASE" else "Fill Whole Layer"
        _op(row, "harappa.paint_fill", fill, icon="SNAP_FACE").clear = False
        _op(row, "harappa.paint_fill", "Reset Layer", icon="LOOP_BACK").clear = True
        layout.label(text=t(LAYER_HINTS[s.paint_layer]), icon="INFO", translate=False)
        layout.label(text=t("F = brush size, Shift+F = strength"), icon="MOUSE_MOVE", translate=False)
        layout.label(text=t("Fewer grass blades shown while painting"), icon="HIDE_OFF", translate=False)
    if layers.spacing(ob) > 0.5:
        layout.label(text=t("Ground is coarse: strokes will look blocky"), icon="ERROR", translate=False)
        if not ob.get("hrp_hill"):
            _op(layout, "harappa.ground_finer", "Make Ground Finer", icon="MOD_SUBSURF")


class HRP_PT_brush(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_brush"
    title = "Paint the Meadow"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        from . import avoid
        return bool(avoid.meadows(context.scene))

    def draw_header(self, context):
        from . import _paint_target
        ob = _paint_target(context)
        self.layout.label(text=t(self.title) + (f": {ob.name}" if ob is not None else ""), translate=False)

    def draw(self, context):
        from . import _paint_target
        ob = _paint_target(context)
        if ob is None:
            self.layout.label(text=t("Select a meadow to paint on"), icon="INFO", translate=False)
            return
        _brush_panel(self.layout, context, ob)


class HRP_PT_avoid(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_avoid"
    title = "Avoid Objects"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        from . import avoid
        return bool(avoid.meadows(context.scene))

    def draw(self, context):
        from . import avoid
        s = context.scene.harappa
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.2
        _op(row, "harappa.avoid_add", "Avoid Selected", icon="ADD")
        _op(row, "harappa.avoid_remove", "Stop Avoiding", icon="REMOVE")
        coll = avoid.current(context.scene)
        notes = avoid.NOTES.get(context.scene.name) or []
        if notes:
            nb = layout.box()
            for name, why in notes[:3]:
                nb.label(text=f"{name}: {t(why)}", icon="ERROR", translate=False)
        box = layout.box()
        objs = list(coll.objects) if coll is not None else []
        if not objs:
            box.label(text=t("Select your character, then click Avoid Selected"), icon="INFO", translate=False)
        for ob in objs[:12]:
            why = avoid.check(context.scene, ob)
            row = box.row(align=True)
            row.alert = why is not None
            op = row.operator("harappa.avoid_select", text=ob.name, translate=False,
                              icon="ERROR" if why else "OBJECT_DATA", emboss=False)
            op.name = ob.name
            op = row.operator("harappa.avoid_remove", text="", icon="X", emboss=False)
            op.name = ob.name
            if why:
                box.label(text=t(why[0]), translate=False)
        if len(objs) > 12:
            box.label(text=i18n.report(f"and {len(objs) - 12} more"), translate=False)
        col = layout.column(align=True)
        _prop(col, s, "avoid_margin")
        _prop(col, s, "avoid_floor")
        _prop(col, s, "avoid_box")
        head, body = layout.panel("hrp_avoid_more", default_closed=True)
        head.label(text=t("More"), translate=False)
        if body is not None:
            col = body.column(align=True)
            _prop(col, s, "avoid_reach")
            col.label(text=t("Avoid Collection"), translate=False)
            col.prop(s, "avoid_collection", text="")


class HRP_PT_tint(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_tint"
    title = "This Object's Colour"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        from . import look
        return look.is_harappa(context.active_object)

    def draw_header(self, context):
        from . import look
        mark = any(look.overridden(o) for o in look.targets(context.active_object))
        self.layout.label(text=t(self.title) + (" " + t("(changed)") if mark else ""), translate=False)

    def draw(self, context):
        s = context.scene.harappa
        layout = self.layout
        col = layout.column(align=True)
        for k in ("obj_hue", "obj_sat", "obj_value"):
            _prop(col, s, k, slider=True)
        col = layout.column(align=True)
        _prop(col, s, "obj_tint")
        _prop(col, s, "obj_tint_amount", "Amount", slider=True)
        from . import tree_canopy, tree_root
        root = tree_root(context.active_object)
        canopy = tree_canopy(root) if root is not None else None
        mod = canopy.modifiers.get("Harappa Foliage") if canopy is not None else None
        if mod is not None:                          # the quick way to a cherry tree: blossom on this one
            _mod_inputs(layout.column(align=True), mod, ("Blossom",), labels={"Blossom": "Blossom on This Tree"})
        row = layout.row(align=True)
        _op(row, "harappa.tint_copy", "Copy to Selected", icon="COPYDOWN")
        _op(row, "harappa.tint_reset", "Follow the Scene", icon="LOOP_BACK")


class HRP_MT_looks(bpy.types.Menu):
    bl_idname = "HRP_MT_looks"
    bl_label = "My Looks"

    def draw(self, context):
        from . import looks
        layout = self.layout
        layout.operator("harappa.look_season", text=t("Season Default"), translate=False, icon="FILE_REFRESH")
        layout.separator()
        items = looks.all_looks()
        if not items:
            layout.label(text=t("No saved looks yet: click + to save one"), translate=False)
        for name, path in items:
            op = layout.operator("harappa.look_apply", text=name, translate=False, icon="COLOR",
                                 depress=name == context.scene.harappa.look_name)
            op.filepath = path


class HRP_MT_look_delete(bpy.types.Menu):
    bl_idname = "HRP_MT_look_delete"
    bl_label = "Delete Look"

    def draw(self, context):
        from . import looks
        items = looks.all_looks()
        if not items:
            self.layout.label(text=t("No saved looks yet: click + to save one"), translate=False)
        for name, path in items:
            op = self.layout.operator("harappa.look_delete", text=name, translate=False, icon="TRASH")
            op.filepath = path


class HRP_MT_look_more(bpy.types.Menu):
    bl_idname = "HRP_MT_look_more"
    bl_label = "Looks"

    def draw(self, context):
        layout = self.layout
        _op(layout, "harappa.look_import", "Import Look", icon="IMPORT")
        _op(layout, "harappa.look_export", "Export Look", icon="EXPORT")
        _op(layout, "harappa.look_folder", "Open Looks Folder", icon="FILE_FOLDER")
        layout.separator()
        layout.menu("HRP_MT_look_delete", text=t("Delete Look"), translate=False, icon="TRASH")


class HRP_PT_cloud(HrpSub, bpy.types.Panel):
    bl_label = ""
    bl_idname = "HRP_PT_cloud"
    title = "Active Cloud"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        from . import _active_cloud
        return _active_cloud(context) is not None

    def draw(self, context):
        from . import cumulus
        s = context.scene.harappa
        ob = context.active_object
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.2
        _op(row, "harappa.cloud_new_shape", "New Shape", icon="FILE_REFRESH")
        col = layout.column(align=True)
        for k in ("cloud_tower", "cloud_width"):
            _prop(col, s, k)
        mod = ob.modifiers.get(cumulus.MOD)
        if mod is not None:
            col = layout.column(align=True)
            _mod_inputs(col, mod, ("Detail", "Flat Base"), labels={"Detail": "Bump Size"})
        if cumulus.is_auto(ob):
            layout.label(text=t("Managed by Make Clouds"), icon="INFO", translate=False)
        else:
            _op(layout, "harappa.cloud_give_back", "Give Back to Auto Layout", icon="LOOP_BACK")


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
        _op(layout, "harappa.edit_canopy", "Shape Canopy", icon="EDITMODE_HLT")


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
        col = self.layout.column(align=True)
        col.label(text=t("Sky & Clouds"), translate=False)
        for k in ("sky_curve", "cloud_shade"):
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
            ("Evergreens", ("ever_lit", "ever_mid", "ever_shadow", "ever_deep")),
            ("Blossoms & Bark", ("bloom_lit", "bloom_shadow", "bloom_deep", "bark_lit", "bark_shadow")),
            ("Clouds", ("cloud_lit", "cloud_shadow", "cloud_deep", "cloud_rim")),
            ("Mountains", ("mountain_1", "mountain_2", "mountain_3")),
            ("Flowers", ("flower_a", "flower_b", "flower_c", "flower_d", "flower_centre", "flower_shade")),
        )
        _prop(self.layout, s, "tint_amount")
        for title, keys in groups:
            col = self.layout.column(align=True)
            col.label(text=t(title), translate=False)
            flow = col.grid_flow(columns=2, align=True)
            for k in keys:
                _prop(flow, s, k)


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


MENUS = ([_enum_menu(n) for n in ENUMS] + [_tree_enum_menu(n) for n in ("shape", "leaf_style")]
         + [HRP_MT_looks, HRP_MT_look_delete, HRP_MT_look_more])
PANELS = (HRP_PT_main, HRP_PT_brush, HRP_PT_meadow, HRP_PT_tree, HRP_PT_cloud, HRP_PT_tint, HRP_PT_avoid,
          HRP_PT_light, HRP_PT_paint, HRP_PT_colours, HRP_PT_links)


def register():
    for c in MENUS:
        bpy.utils.register_class(c)
    for c in PANELS:
        bpy.utils.register_class(c)


def unregister():
    if _previews["coll"] is not None:
        from bpy.utils import previews
        previews.remove(_previews["coll"])
        _previews.clear()
        _previews["coll"] = None
    for c in reversed(PANELS):
        bpy.utils.unregister_class(c)
    for c in reversed(MENUS):
        bpy.utils.unregister_class(c)
