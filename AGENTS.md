# Harappa — instructions for AI agents

The human only says something like *"make an anime meadow with a few trees"*, *「ジブリっぽい草原を作って」* or
*「做一片动画风的草地和树」*. You do everything: install, build the scene, show a preview.
Do not ask the human to click anything in Blender.

## 1. Find Blender
- macOS: `/Applications/Blender*.app/Contents/MacOS/Blender`
- Windows: `C:\Program Files\Blender Foundation\Blender */blender.exe`
- Linux: `blender` on PATH

Needs **5.0+** (EEVEE). Folder names don't always show the version, so ask each one and pick the newest:
```bash
for b in /Applications/Blender*.app/Contents/MacOS/Blender; do echo "$("$b" --version | head -1) | $b"; done
```

## 2. Install (once)
Get the latest `harappa-<version>.zip` from https://github.com/kanaworksai-hue/harappa/releases
and `agent/harappa_agent.py` from the repository:
```bash
git clone --depth 1 https://github.com/kanaworksai-hue/harappa.git
gh release download -R kanaworksai-hue/harappa -p 'harappa-*.zip'      # with gh
# or without gh:
curl -sL "$(curl -s https://api.github.com/repos/kanaworksai-hue/harappa/releases/latest \
  | grep -o 'https://[^"]*harappa-[^"]*\.zip' | head -1)" -o harappa.zip
```
Then:
```bash
<blender> -b --python harappa/agent/harappa_agent.py -- --install harappa-<version>.zip
```
Never add `--factory-startup` to the install command — the install is saved into the user's
preferences and factory startup would overwrite them. The script refuses in that case.
Success = last line starts with `HARAPPA OK`.

## 3. Build

### a) A whole landscape from nothing (Blender closed, headless)
```bash
<blender> -b --python agent/harappa_agent.py -- \
    --meadow --path -1,-20:0.5,-5:-2,8:1,20 --trees 8 --season SUMMER \
    --render preview.png --preview-size 50 --save meadow.blend
```
A 40 m hill, grass + flowers, a winding bare path through the given world points, eight trees off the path,
painted clouds, an anime sky with depth haze, a key sun and a camera. Show the human `preview.png`.

### b) On the human's own ground in a .blend
```bash
<blender> -b scene.blend --python agent/harappa_agent.py -- \
    --meadow --objects Ground --tree ROUND --at 3,4 --tree WIDE --at -5,8 --blossom 0.5 \
    --save scene_meadow.blend --render preview.png
```
The ground needs some vertices for the path mask (subdivide a single plane first). Save to a new file unless
they asked to overwrite.

### c) Into a running Blender (e.g. through a Blender MCP / Python console)
```python
import bpy
s = bpy.context.scene.harappa
bpy.ops.harappa.make_meadow()                 # selected meshes, or a new hill when nothing is selected
bpy.context.scene.cursor.location = (3, 4, 0)
bpy.ops.harappa.add_tree(shape="ROUND", height=5.0, seed=12)   # stands on the ground under the cursor
bpy.ops.harappa.plant_trees(count=8)          # active object must be a meadow
bpy.ops.harappa.make_foliage()                # selected meshes -> hedges / bushes of leaf dabs
bpy.ops.harappa.add_clouds(count=6)           # painted cumulus in front of the scene camera
s.season = "GOLDEN"                           # colour, sun and sky
s.style = "PAINTERLY"                         # how light and shadow are painted
s.variation = 918                             # or bpy.ops.harappa.shuffle()
s.clump_size = 2.5                            # any setting, see --list
root.harappa_tree.shape = "CONIFER"           # per tree: shape / leaf_style / height / seed rebuild live
bpy.ops.harappa.revert()                      # selected objects: remove grass/flowers/foliage, restore materials
```
Grass density, height and wind live on each meadow's **Harappa Grass** / **Harappa Flowers** modifiers; leaves on the
**Harappa Foliage** modifier of a tree's canopy object (`harappa.util.mod_input(mod, "Wind Strength", 0.3)`).

To keep grass out of a character, a rock or a house, put those objects in a collection and give it to both meadow
modifiers. Nothing grows under them, and grass beside them gets shorter and leans away (no blades through the model):
```python
from harappa.util import mod_input
props = bpy.data.collections["Props"]                    # the objects to grow around
for m in meadow.modifiers:
    if m.name in ("Harappa Grass", "Harappa Flowers"):
        mod_input(m, "Avoid", props)
        mod_input(m, "Avoid Margin", 0.16)               # metres of shorter grass around them
        mod_input(m, "Avoid Floor", 0.3)                 # grass height right against them (Grass only matters)
```

## 4. Turning the human's words into options

**If the human gives no style at all** ("make an anime meadow"), use `--meadow --trees 6 --season SUMMER`.
On later tweaks, omit what they didn't mention: the current season, style and variation are kept.

| They say | `--season` |
|---|---|
| summer, Ghibli, bright, blue sky, 夏, 青空, 夏天, 蓝天 (default) | `SUMMER` |
| spring, cherry blossom, sakura, pastel, 春, 桜, 春天, 樱花 | `SPRING` (add `--blossom 0.5`) |
| sunset, evening, golden, 夕方, 夕焼け, 黄昏, 夕阳 | `GOLDEN` |
| autumn, fall, red leaves, 秋, 紅葉, 秋天, 红叶 | `AUTUMN` |
| night, moonlight, 夜, 月夜, 夜晚 | `NIGHT` |
| misty, foggy, soft morning, calm, 霧, 朝もや, 雾, 清晨 | `MISTY` |

| They say | `--style` |
|---|---|
| anime background, clean (default) | `ANIME` |
| painterly, brushy, hand-painted, 絵画風, 筆っぽく, 手绘感, 笔触 | `PAINTERLY` |
| crisp, graphic, flat, two-tone, くっきり, 硬边, 扁平 | `CRISP` |
| soft, pastel, gentle, ふんわり, 柔和 | `SOFT` |

| They say | option |
|---|---|
| a path, a road, 道, 小道, 小路 | `--path X,Y:X,Y:…` (world points; width `--path-width 1.2`) |
| more / fewer trees, 木を増やして, 多种点树 | `--trees N` |
| one big tree, 一本の木, 一棵大树 | `--tree ROUND --at 0,5 --tree-height 7` |
| cherry tree, blossoms, 桜の木, 樱花树 | `--tree WIDE --blossom 0.55 --season SPRING` |
| pine, cedar, evergreen, 杉, 松, 针叶树 | `--tree CONIFER` |
| bushes, hedge, 茂み, 生け垣, 灌木 | `--tree BUSH`, or `--foliage --objects Hedge` on their own mesh |
| taller / shorter grass, 草を高く, 草长一点 | `--grass-height 0.6` |
| denser grass, 草を濃く, 草密一点 | `--density 70` |
| no flowers, 花なし, 不要花 | `--no-flowers` |
| more / fewer clouds, 雲を増やして, 多点云 / clear sky, 快晴, 晴空 | `--clouds 10` / `--clouds 0` |
| windy / calm, 風を強く, 风大一点 / 静止 | `--wind 2` / `--wind 0` |
| bigger shadow clumps, 影の塊を大きく | `--set clump_size=3` |
| lower / higher sun | `--set sun_elevation=15` |
| "something different", "another version", 別パターン, 换一个 | `--shuffle` (prints the variation number) |
| "go back to version 918" | `--variation 918` |

Unknown names fail with a hint; run `--list` and pick the closest, then tell the human what you chose.

The panel follows Blender's language automatically (English, 日本語, 简体中文, 한국어). If the human wants the panel in
another language than Blender itself, run `--ui-language JA` (or `EN`, `ZH`, `KO`, `AUTO`) — without `--factory-startup`.

## Getting the best result (do this, the human won't ask)
1. Render a preview (`--render preview.png --preview-size 50`) and look at it before reporting back. If the
   camera sees nothing useful, add `--frame-camera` (a separate camera; the human's own camera is not touched).
2. The wind moves over time: render `--frame 1` and `--frame 30` if they want to see it; an animation renders the
   whole frame range as usual.
3. Offer two or three variations as small previews (e.g. two seasons, or `--shuffle` twice) and let the human pick
   in one word.
4. Leaf and flower cards face the **scene camera**. Render from the scene camera; when the human orbits the viewport
   away from it the cards turn edge-on — that is expected.
5. Report what you changed in one sentence, with the preview.

## Notes
- Don't mix up the commands: **installing** must not use `--factory-startup`; the README's Development section uses it
  only for tests and builds.
- Needs EEVEE. The first meadow/tree switches the scene to EEVEE, the Standard view transform, the "HRP Sky" world
  (lighting comes only from the "HRP Sun") and hides Blender's untouched startup cube and point light.
- Sister add-ons: [Senga Sketch](https://github.com/kanaworksai-hue/senga-sketch/blob/main/AGENTS.md) (pen & ink),
  [Painterly 2.5D](https://github.com/kanaworksai-hue/painterly-25d/blob/main/AGENTS.md) (oil / watercolour / anime
  paint), [KiraPaint](https://github.com/kanaworksai-hue/kirapaint/blob/main/AGENTS.md) (sparkly) and
  [MochiToon](https://github.com/kanaworksai-hue/mochitoon/blob/main/AGENTS.md) (cute comic toon). Harappa builds the
  landscape itself; the others restyle existing objects.
