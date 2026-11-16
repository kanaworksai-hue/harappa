# Changelog

## Unreleased (1.1 "Waterside & Weather")

- **Grass Only in Camera View** (Meadow panel, off by default): grass and flowers grow only where the active
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
  one click. Selected Waterfall: Flow (live), Height, Width and Seed (rebuild).
- **Rocks:** Add Rock (rounded boulders, angular chunks and flat slabs, bedded into the ground on the low side of
  their footprint); Selected Rock: size, flatness, seed, moss. Steep bare faces of the meadow (terrace and bank
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
- **Fast Playback (Freeze Banks):** bakes the dug banks into the file (about 4x faster playback).
- Agent CLI: `--pond`, `--stream`, `--stream-width`, `--rain`, `--water-type`, `--waterfall`, `--rock`, `--koi`,
  `--boat`, `--weather`, `--rain-at`, `--rainbow`, `--fireflies`, `--dragonflies`.

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
