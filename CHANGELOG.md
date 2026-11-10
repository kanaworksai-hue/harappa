# Changelog

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
