# Changelog

## 1.2.0 — 2026-11-16 "Waterside & Weather"

- **Panels:** Water and Weather show once there is a meadow; Active Water, Active Waterfall, Active Rock and Active
  Boat open by themselves for the selected thing, with the finer settings folded under More (like Active Meadow). A new
  pond added with the 3D cursor still at the world origin goes where the camera sees it.
- **Grass Only in Camera View** (Active Meadow panel, off by default): grass and flowers grow only where the active
  camera can see, with a 25 % margin, so big scenes get much lighter (about half to four fifths fewer tufts in our
  test shots). The render is pixel-identical, since off-screen grass casts no shadow; tufts never reshuffle as the
  camera moves.
- **Water follows the lie of the land:** a waterfall's plunge pool is dug into the slope and its water stands at
  the lowest point of its rim, where it spills out through a stone-lined notch; the outflow takes the steepest way
  down the meadow (into a pond when it meets one). Steep streams become step-pools (a calm pool, a short drop with a
  stone each side) instead of smooth chutes, and stay below their banks. Where a stream leaves or enters a pond, its
  shape, colour and flow lines hand over at the shore, so the water bodies read as one. Every pond fills to the
  lowest point of its own rim (never held up above the ground), and a stream drawn up to a pond's shore, or starting
  beside one, joins it by itself; Make Water from Curves and Drop Onto Meadow re-level the water after editing.
- **Water:** Add Pond / Add Stream / Make Water from Curves. A closed curve becomes a pond, an open curve a stream
  that follows the meadow downhill. Each water body digs its own bed into the meadow (a "Harappa Water Carve"
  modifier, first in the stack), raises a low bank where the ground is lower than the water, and fades the grass
  out over the bank, so grass, flowers and the path colour step back by themselves.
- **Toon water shader:** crisp shallow / mid / deep bands with organic shapes (the shelf is wide here, steep there),
  the bed showing through the shallows, a caustic web, real reflections of the scene (EEVEE screen-space ray
  tracing, broken by small ripples), a wobbly shore line, flow lines on streams that turn to white rapids where a
  stream runs downhill, rain ripples, glints, a moonlight path at night; follows all six seasons and Shuffle.
  Animated by scene time (scrub the timeline, no cache).
- **Contact:** a thin white water line and a lapping ring round lily pads and the boat; a foam collar round rocks
  standing in the water.
- **Six water types** (Season Colours, Clear Blue Lake, Lotus Pond, Glacier Lake, Mountain Stream, Tea-Brown Marsh)
  plus hue / saturation / brightness / clarity, pond scale and shoreline shape per pond.
- **Add Waterfall:** a raised rocky knoll with trees, a stream across it, a lip of bedded slabs, the falling sheet
  (toon bands, a white lip, two layers of strands, torn edges, ropes in the lower part, a darker sheet behind), a
  crown splash, churning white water and foam on the plunge pool, expanding impact rings, and an outflow stream, in
  one click. Active Waterfall: Flow (live), Height, Width and Seed (rebuild).
- **Rocks:** Add Rock (rounded boulders, angular chunks and flat slabs, bedded into the ground on the low side of
  their footprint); Active Rock: size, height ratio, seed, moss. Steep bare faces of the meadow (terrace and bank
  cliffs) are dressed with angular rock chunks. Add Stepping Stones across a
  stream. Waterfalls have spray mist at the foot (Mist on the Harappa Waterfall modifier).
- **Pond life:** lily pads and water-lily flowers (only where the water is 0.2-1.6 m deep), reeds and cattails in
  the shallows, pebbles on the bank, Add Koi (now and then one leaps out of the pond with a crown splash where it
  leaves and where it dives back in; Leap Every on the Harappa Fish modifier), Add Boat (Draft = buoyancy, Bob,
  Sway). In Autumn, leaves float on the ponds, gathering in rafts by the banks.
- **Weather:** Clear / Cloudy / Rain / Storm as a layer over the season (your colours are kept). Rain follows the
  camera or falls only where you put it (Rain Here, Rain Area circle); raindrop rings only inside it. Storm doubles
  the wind. Rainbow, fireflies by the water at dusk and night, dragonflies over the water by day.
- **Rules of nature:** trees are not planted in water (and new water clears trees that stood there; a tree up on a rock or block above the water stays), lilies only
  on it, no reeds by a waterfall.
- **Fixes:** rocks and trees no longer float a grass-height above the ground (the ground probe stopped on blade tips);
  a stream that enters a pond grades down gently instead of dropping in its last stretch.
- **Fast Playback** (Water panel): bakes the dug banks into the file (about 4x faster playback).
- Agent CLI: `--pond`, `--stream`, `--stream-width`, `--rain`, `--water-type`, `--waterfall`, `--rock`, `--koi`,
  `--boat`, `--weather`, `--rain-at`, `--rainbow`, `--fireflies`, `--dragonflies`.
## 1.1.2 — 2026-11-13

- **A meadow needs room.** Make Anime Meadow on Blender's plain plane (Add › Plane, under 10 m) used to grow a 2 m
  lawn the camera couldn't even see. Now the plane becomes the 40 m rolling hill, in place (same object; Ctrl+Z
  brings the plane back; *Small Plane to Hill* in the operator panel turns it off). Your own small grounds are never
  reshaped: the status bar and the Active Meadow panel say the meadow is only that big and to scale it to 30 m or more.
- README: one click makes the grass, flowers and sky; trees are one more click (the first line said "with one
  click" for trees too). The ground-size advice is in the FAQ.

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
