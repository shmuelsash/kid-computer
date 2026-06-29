"""Age-group visual modes.

Each mode is a bundle of behavior parameters that the scene reads when deciding
what to spawn on a key/click. Chosen in Settings. The three modes deliberately
feel different:

* toddler   - "Bubbles & Booms": one big thing per press, slow and gentle.
* preschool - "Letters & Friends": letters/numbers + counting dots + smiley shapes.
* early     - "Cosmic Maker": kaleidoscope symmetry, constellations, word building.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgeMode:
    key: str
    label: str
    age: str
    tagline: str
    max_effects: int  # cull cap (scaled by intensity)
    lifetime_scale: float  # how long effects linger
    speed_scale: float  # particle/motion speed
    glyph_fraction: float  # glyph size as a fraction of the short screen side
    always_glyph: bool  # show the pressed letter/number every time
    counting_dots: bool  # number keys spawn that many dots
    friend_chance: float  # chance a shape becomes a smiley "friend"
    symmetry: int  # mirror copies of each spawn (1 = none)
    constellation: bool  # clicks drop linked stars
    word_row: bool  # typed letters line up at the bottom
    ambient_interval: float  # seconds between idle ambient spawns
    firework_particles: int


_TODDLER = AgeMode(
    key="toddler",
    label="Toddler",
    age="1-3",
    tagline="Bubbles & Booms",
    max_effects=90,
    lifetime_scale=1.25,
    speed_scale=0.8,
    glyph_fraction=0.30,
    always_glyph=False,
    counting_dots=False,
    friend_chance=0.18,
    symmetry=1,
    constellation=False,
    word_row=False,
    ambient_interval=2.2,
    firework_particles=70,
)

_PRESCHOOL = AgeMode(
    key="preschool",
    label="Preschool",
    age="3-5",
    tagline="Letters & Friends",
    max_effects=150,
    lifetime_scale=1.0,
    speed_scale=1.0,
    glyph_fraction=0.26,
    always_glyph=True,
    counting_dots=True,
    friend_chance=0.4,
    symmetry=1,
    constellation=False,
    word_row=False,
    ambient_interval=2.6,
    firework_particles=85,
)

_EARLY = AgeMode(
    key="early",
    label="Early school",
    age="5-8",
    tagline="Cosmic Maker",
    max_effects=240,
    lifetime_scale=0.9,
    speed_scale=1.25,
    glyph_fraction=0.16,
    always_glyph=True,
    counting_dots=False,
    friend_chance=0.08,
    symmetry=6,
    constellation=True,
    word_row=True,
    ambient_interval=1.6,
    firework_particles=110,
)

MODES: dict[str, AgeMode] = {m.key: m for m in (_TODDLER, _PRESCHOOL, _EARLY)}
MODE_ORDER: tuple[str, ...] = ("toddler", "preschool", "early")
DEFAULT_MODE = "toddler"


def get_mode(key: str) -> AgeMode:
    return MODES.get(key, MODES[DEFAULT_MODE])
