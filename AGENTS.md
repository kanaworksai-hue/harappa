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
solid cumulus clouds, distant mountains, an anime sky with depth haze, a key sun and a camera. Show the human
`preview.png`.

Painting, avoiding and looks (same command, any order):
```bash
<blender> -b meadow.blend --python agent/harappa_agent.py -- \
    --paint grass:erase@0,-6,1.2 --paint flowers:paint@-4,2,3 --paint height:1@6,4,3 \
    --paint colour:#F2D25C@-2,6,3 --fill flowers:0.5 --avoid Hero,Bench \
    --preset-file golden.harappa-look.json --save-preset "My Golden" --save meadow.blend --render preview.png
```
`--paint LAYER:VALUE@X,Y,RADIUS` paints a round spot on a brush layer, exactly like the panel's brush:
`grass` (paint = grass, erase = bare path), `flowers` (paint = dense flower bed, erase = none, 0.5 = natural patches),
`height` (paint = up to ×2, erase = flat, 0.5 = normal), `colour` (`#RRGGBB` = that colour at full brightness,
erase = none). `--paint-strength F` for softer strokes, `--fill LAYER:VALUE` / `--clear LAYER` for a whole layer.
`--blend A,B` paints the human's own models like the meadow (no black shadows, shade colours follow the season and look;
`--unblend A,B` gives their own materials back). `--avoid A,B` makes grass and flowers room for those meshes (an armature adds its meshes; `--avoid-box` for heavy
models). `--preset NAME` / `--preset-file PATH` apply a saved look (colours, light, sky, paint style),
`--save-preset NAME` saves the current one, `--list-presets` prints them.

### b) On the human's own ground in a .blend
```bash
<blender> -b scene.blend --python agent/harappa_agent.py -- \
    --meadow --objects Ground --tree ROUND --at 3,4 --tree WIDE --at -5,8 --blossom 0.5 \
    --save scene_meadow.blend --render preview.png
```
The ground should be 30 m or more (a plain plane under 10 m becomes the 40 m hill; another small ground stays a
small patch of grass). The ground needs some vertices for the brush layers (subdivide a single plane first, or run
`bpy.ops.harappa.ground_finer()` with the ground active). Save to a new file unless
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
bpy.ops.harappa.add_clouds(count=6)           # solid cumulus in front of the scene camera (0 removes them)
bpy.ops.harappa.add_ridges(layers=3)          # distant mountain layers (0 removes them)
s.detail_level = "BEST"                       # FAST / BALANCED / BEST
s.season = "GOLDEN"                           # colour, sun and sky
s.style = "PAINTERLY"                         # how light and shadow are painted
s.variation = 918                             # or bpy.ops.harappa.shuffle()
s.clump_size = 2.5                            # any setting, see --list
root.harappa_tree.shape = "CONIFER"           # per tree: shape / leaf_style / height / seed rebuild live
bpy.ops.harappa.revert()                      # selected objects: remove grass/flowers/foliage, restore materials
```
Grass density, height and wind live on each meadow's **Harappa Grass** / **Harappa Flowers** modifiers; leaves on the
**Harappa Foliage** modifier of a tree's canopy object (`harappa.util.mod_input(mod, "Wind Strength", 0.3)`).

Brush layers, Avoid, per-object colour and looks from Python:
```python
from harappa import avoid, layers, look, looks
layers.paint_disc(meadow, "GRASS", (0, -6), 1.2, layers.target("GRASS", "ERASE")[0])     # a bare path spot
layers.paint_disc(meadow, "COLOUR", (2, 6), 3.0, layers.target("COLOUR", "PAINT", (0.9, 0.7, 0.2))[0])
avoid.add(bpy.context, [hero, bench])          # grass and flowers make room (refusals come back with a reason)
from harappa import blend
blend.apply([hero, house])                     # painted like the meadow, no black shadows; blend.restore([...]) undoes it
s.avoid_box = True                             # each avoided object as its box (heavy models)
look.set_user(tree_canopy, colour=(1.0, 0.7, 0.8), amount=0.9)   # this tree pink; look.reset(ob) undoes it
looks.save(bpy.context, "My Golden")           # into the extension's looks folder
looks.apply(bpy.context, looks.read(path))     # a .harappa-look.json
```
Avoid is continuous: nothing grows inside the objects, grass beside them gets shorter and leans away, and under an
object that hangs above the ground (a bench, a bridge) grass grows up to just below it — nothing pops when it moves.

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
| a flower bed here, 花畑, 花坛 | `--paint flowers:paint@X,Y,3` |
| tall grass there / a mown lawn, 草を高く, 草坪 | `--paint height:1@X,Y,4` / `--paint height:erase@X,Y,4` |
| a sunlit / dry patch, 陽だまり, 枯れ草, 阳光斑 | `--paint colour:#F2D25C@X,Y,3` / `--paint colour:#C9A15A@X,Y,3` |
| grass through my character, 草がキャラを突き抜ける, 草穿模 | `--avoid CharacterMesh` |
| save these colours, この色を保存, 保存这个配色 | `--save-preset "Name"`; reuse with `--preset "Name"` |
| more / fewer trees, 木を増やして, 多种点树 | `--trees N` |
| one big tree, 一本の木, 一棵大树 | `--tree ROUND --at 0,5 --tree-height 7` |
| cherry tree, blossoms, 桜の木, 樱花树 | `--tree SAKURA` (always in blossom) |
| pine, Japanese pine, 松, 松树 / cedar, evergreen, 杉, 针叶树 | `--tree PINE` / `--tree CONIFER` |
| willow, weeping, 柳, 柳树 / poplar, slim, ポプラ, 杨树 | `--tree WILLOW` / `--tree COLUMN` |
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
