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
bpy.context.scene.cursor.location = (2, -4, 0)
bpy.ops.harappa.add_pond(radius=2.5, depth=0.7)   # toon pond at the cursor; digs its bed, grass steps back
bpy.ops.harappa.add_stream(length=12, width=1.4)  # stream from the cursor away from the camera, downhill
bpy.ops.harappa.make_water()                  # selected curves -> water (closed = pond, open = stream, upstream first)
s.water_rain = 0.4                            # raindrop rings; also water_caustics, water_glints, water_glow
pond.harappa_water.kind = "LOTUS"             # SEASON CLEAR LOTUS GLACIER STREAM TEA; also hue/saturation/brightness/
                                              # clarity, size (scale x1) and shape_seed per pond
bpy.ops.harappa.add_waterfall(height=2.4, width=1.4)  # pool at the cursor, rocky knoll + stream + rocks + trees + outflow
fall.harappa_fall.flow = 1.5                  # per waterfall: flow (live), height / width / seed (rebuild it)
bpy.ops.harappa.add_rock(size=1.0, flat=0.65) # mossy rock on the ground under the cursor
rock.harappa_rock.moss = 0.3                  # per rock: size, flat, seed, moss
bpy.ops.harappa.add_fish(count=6)             # active pond: koi ("Harappa Fish" modifier: Count, Size, Speed,
                                              #   Leap Every = seconds between leaps, 0 = never)
bpy.ops.harappa.add_boat()                    # active pond: rowboat ("Harappa Float": Draft = buoyancy, Bob, Sway)
s.weather = "RAIN"                            # CLEAR CLOUDY RAIN STORM, a layer over the season (user colours kept)
s.rain_radius = 8; bpy.ops.harappa.rain_here()   # rain only around the cursor (s.rain_follow = True: over the camera)
s.rainbow = True; s.firefly_count = 200       # fireflies glow at GOLDEN / NIGHT (s.fireflies = glow)
s.dragonfly_count = 10                        # dragonflies hovering and darting over the water (daytime)
bpy.ops.harappa.stepping_stones()             # active stream: flat stones across it, nearest the 3D cursor
bpy.ops.harappa.freeze_banks(on=True)         # bake the dug banks: fast playback (Harappa re-bakes after its tools)
```
Nature's rules are built in: trees are not planted in water, lily pads grow only on water 0.2-1.6 m deep, reeds stand
in the shallows (not by a waterfall), pebbles lie on the bank.
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
| a pond, a lake, 池, 湖, 池塘 | `--pond X,Y` or `--pond X,Y,R` (radius in metres, default 2.5; repeatable) |
| a stream, a brook, a river, 小川, 川, 小溪, 小河 | `--stream X,Y:X,Y:…` (world points, upstream first; width `--stream-width 1.4`) |
| rain on the water, 雨の波紋, 雨点 | `--rain 0.4` |
| clear / blue / lotus / glacier / mountain / brown water, 澄んだ湖, 蓮池, 清澈的湖, 荷塘 | `--water-type CLEAR` (`SEASON CLEAR LOTUS GLACIER STREAM TEA`) |
| a waterfall, 滝, 瀑布 | `--waterfall X,Y` or `--waterfall X,Y,H` (pool at X,Y, height H, default 2.4 m) |
| a rock, a boulder, 岩, 石, 岩石 | `--rock X,Y` or `--rock X,Y,S` (size in metres; repeatable) |
| koi, fish, 鯉, 魚, 锦鲤, 鱼 | `--koi 6` (in every pond) |
| a boat, 小舟, ボート, 小船 | `--boat` (on the first pond) |
| cloudy, overcast, 曇り, くもり, 阴天 | `--weather CLOUDY` |
| rain, rainy, 雨, 下雨 | `--weather RAIN` (only in one place: `--rain-at X,Y,R`) |
| storm, 嵐, 暴風雨, 暴风雨 | `--weather STORM` |
| rainbow, 虹, 彩虹 | `--rainbow` (after rain: `--weather RAIN --rainbow`) |
| dragonflies, トンボ, 蜻蜓 | `--dragonflies 10` |
| fireflies, ホタル, 蛍, 萤火虫 | `--fireflies 200 --season NIGHT` (or `GOLDEN`) |
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
