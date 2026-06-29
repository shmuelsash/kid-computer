# 0004 - Three-axis visual design + in-app settings

## Status
Accepted

## Context
The first visuals looked crude (flat aliased shapes, literal "pop-up windows")
and there was no way to tune the experience. We wanted a more sophisticated look,
distinct experiences per age group, and selectable moods - without shipping any
art assets.

## Decision
Model the experience as **three independent axes**, all chosen in an in-app
settings card and persisted to `settings.json`:

1. **Age mode** (`modes.py`) - *behavior*: what spawns on key/click. Toddler
   (big/slow/simple), Preschool (letters, counting dots, smiley "friends"), Early
   (kaleidoscope symmetry, constellations, word building).
2. **Theme** (`theme.py`) - *palette/mood*: Aurora, Candy, Minimal. Background
   gradient, shape palette, glow strength, UI chrome.
3. **Intensity** - a scalar that scales effect count and ambient rate.

Rendering quality comes from `render.py`: a numpy vertical-gradient background, a
numpy radial **bloom glow** sprite (pre-rendered per palette color, blitted
additively), and a supersampled **anti-aliased** progress ring. Shapes get a
lighter highlight + spring easing. No image/audio assets are shipped (see
[0002](0002-procedural-audio-and-graphics.md)).

UI chrome moved off the screen seam for multi-monitor: the exit hint is a
top-left pill, the gear/settings card and exit ring are centered on the *primary*
monitor (`display.create_surface` returns a `ui_rect`). The auto-update now shows
a splash with progress, driven by a worker thread (`updater.run_update`).

## Consequences
- Settings are live and persistent; `LOG_LEVEL`/`KIDCOMPUTER_SOUND` env vars now
  only seed first-run defaults.
- New behavior/palette = a new entry in `modes.py`/`theme.py`, nothing else.
- Glow/gradient/ring math is pure and unit-tested by output size; behavior configs
  and the settings store are unit-tested directly.
