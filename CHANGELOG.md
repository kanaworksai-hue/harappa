# Changelog

## 1.1.1 — 2026-11-13

- **Blend Into Meadow:** your own models (a character, a building from any generator or store) no longer get
  pitch-black shadows in a Harappa scene. Select one and click *Blend Into Meadow* (shown under *Make Grass Avoid
  It*, also for an imported model's empty parent): it is painted the way the meadow is, with the season's light and
  shade colours, the Look, the colour strength and contrast, and the haze. Cut-outs and glow are kept. Its own
  materials stay in the file; *Original Look* brings them back. Agents: `--blend A,B` / `--unblend A,B`.
  Why the shadows were black: Harappa's materials paint their own light and shade, so the scene gives objects no
  ambient light, and an ordinary material was lit by the sun alone.

## 1.1.0 — 2026-11-12

A bigger, brighter meadow you can make your own. Works on Blender 5.0, 5.1, 5.2 LTS and 5.3.

**A new look**
- **Sky:** the deep top colour now reaches the frame, with a sun disc and glow, painted high cirrus and brushy
  bands that follow the camera (move or zoom the camera and the gradient refits itself).
- **Solid cumulus clouds:** every cloud is its own object (move, scale or delete it) with a lit top, blue shade and
  a flat base, a golden rim against the sun and moonlit edges at night; big, middle and small clouds in three
  layers that stay clear of tree crowns. *Active Cloud* panel: New Shape, Tower, Width, Bump Size.
- **Distant mountains:** three layers of ridges fading into the haze (*Distant Mountains*, 0–3 layers).
- **Vivid seasons:** all six seasons repainted for strong, clear anime colour; golden hour is backlit, the misty
  morning keeps its fog in the distance. *Vividness* and *Picture Contrast* on the main panel survive season
  changes.
- **Paint styles reach everything:** sky, clouds, mountains and leaf dabs change with the style (Crisp Cel: big
  blocks; Painterly: small broken dabs; Soft Pastel: airy sky).
- **Nine tree shapes:** cherry blossom, Japanese pine, willow and poplar join round, tall, wide, bush and conifer.
  Plant Trees puts a round focal tree on a third of the frame.
- **Detail Level:** Fast / Balanced / Best — less or more grass, flowers and cloud detail, and the render samples.

**Make it yours**
- **Paint the Meadow:** four brush layers painted with Blender's own brush — Grass (Make Path / Grow Grass),
  Flowers (dense flower beds / none), Grass Height (up to twice as tall / mown) and Colour (sunlit patches, dry
  spots…). Fill All, Erase All, Reset Layer and Ctrl+Z work; seasons, Shuffle and Reset keep what you painted.
  The viewport draws fewer blades while you paint. *Make Ground Finer* for your own coarse ground.
- **Avoid Objects:** *Make Grass Avoid It* on any selected mesh (or a character's armature): grass and flowers
  make room, grow up to just below objects that hang above them (benches, bridges) and never pop as things move.
  *Use Simple Box* for heavy models.
- **This Object's Colour:** hue, saturation and brightness shift and an own colour for any meadow, tree, cloud or
  mountain range; Shuffle keeps it. *Blossom on This Tree* makes a cherry tree in one step.
- **My Looks:** save the colours, light, sky and paint style as a small JSON file, apply it to any scene, import /
  export to share it.
- **Agent CLI:** `--paint`, `--fill`, `--clear`, `--avoid`, `--preset`, `--preset-file`, `--save-preset`.

**Under the hood**
- Rebuilding node groups keeps every value set on the modifiers; scenes from 1.0 open and upgrade with their
  colours.
- Customisation costs nothing until it is used: the default landscape renders as fast as before.
- Tests on Blender 5.0, 5.1, 5.2 LTS and 5.3 (two test files, every node link checked, pictures compared).

## 1.0.1 — 2026-11-10

Blender 5.3 compatibility.

- **Works on Blender 5.3.** 5.3 added a socket in front of the Vector Transform node's input. Harappa 1.0.0 picked
  some sockets by position, so *Make Anime Meadow* stopped with an error there, and the clouds would have lost
  their shading (plain white). Every socket is now looked up by name.
- **Scenes made with 1.0.0 keep their look.** The first Harappa action that touches the look in such a scene (a
  colour, a slider, a season, Make Anime Meadow, Add Clouds, a tree) brings all Harappa materials up to date at
  once, with your colours.
- **Small clouds:** the lit / shadow edge of clouds that are small in the frame no longer breaks into dark specks
  (most visible at night and at golden hour). Big clouds keep their puffy look.
- **Far hills:** the grass along the crest of the distant hills stood on the horizon as sparse dark tufts. The
  hills now face up, so that grass stands upright, and it takes the hill's own colour and haze: a soft fringe.
  (In a scene made with 1.0.0 the tufts only get the softer colour: the hills are built together with a new hill
  by Make Anime Meadow, an existing landscape keeps the ones it has.)
- A material or node group that could not be built completely (for example on a Blender newer than the add-on
  knows) is no longer kept as if it were finished: the next button that needs it builds it again.
- Tests: every node link, node setting and input value is checked on the Blender that runs the tests, the default
  landscape is rendered in all six seasons and compared with recorded pictures, and a scene from an older version
  is upgraded and rendered. Tested on Blender 5.2 LTS and 5.3.

## 1.0.0 — 2026-11-10

First release.

- **Make Anime Meadow:** grass + flowers on the selected meshes (or a new hill), anime sky, key sun, painted clouds,
  far hills and a camera in one click. Grass stays as instances (light), sways in a two-layer wind, and is shaded
  with a world-projected clump field so light and shadow fall in big painted clumps.
- **Paint Path / Paint Grass:** a vertex-colour mask decides where grass grows; path edges break up naturally.
- **Anime trees:** five shapes (round, tall, wide/cherry, bush, conifer), three leaf styles, camera-facing brush-dab
  leaves shaded from the canopy clumps, blossom bunches, live rebuild from shape / height / seed, Plant Trees.
- **Make Foliage:** turns any mesh into a bush or hedge of leaf dabs.
- **Add Clouds:** painted cumulus that keep clear of tree crowns and the frame edges.
- **6 seasons × 4 paint styles + Shuffle** (variation number re-rolls colours, tree shapes, clouds, flowers and sun).
- Aerial haze, moon and stars at night, rim light at golden hour.
- **Avoid:** a collection on the Harappa Grass / Harappa Flowers modifiers that the meadow grows around: nothing
  under those objects, shorter grass leaning away beside them (continuous, so nothing pops when a character moves).
- Leaf cards have their own low **Wind Flutter**, so close-up canopies sway without shimmering.
- UI in English, 日本語, 简体中文 and 한국어 (follows Blender's language; 🌐 menu to override).
- AI-agent support: `AGENTS.md` and `agent/harappa_agent.py`.
