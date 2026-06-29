# 0002 - Procedural audio and graphics (no bundled assets)

## Status
Accepted

## Context
The app needs lots of varied sounds and visuals. Shipping audio/image files
means licensing questions, a bigger exe, and PyInstaller data-bundling config.

## Decision
Generate everything at runtime:
- **Audio**: numpy synthesizes notes from a **C-major pentatonic** scale (random
  presses always sound musical, never dissonant) plus a two-note "win" chime,
  rendered into pygame sounds at startup. See `audio.py`.
- **Graphics**: all effects are drawn with pygame primitives (circles, polygons,
  stars, particle bursts, pop-up "windows"), colored via HSV for consistently
  bold, well-saturated tones. See `effects.py`.

## Consequences
- No asset files, no licensing, a smaller exe, and infinite variety for free.
- The only "asset" dependency is a system font for the big letter/number glyphs
  (`pygame.font.SysFont` with a fallback list), which is always available.
- `make_tone` and the effect math are pure/deterministic, so they're unit-tested
  without a display or audio device.

## Safety note
Color "flashes" are deliberately soft (low alpha) and infrequent - a gentle wash,
not a high-contrast strobe - to avoid any photosensitivity risk for a child.
