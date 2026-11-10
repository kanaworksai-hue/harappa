# Changelog

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
