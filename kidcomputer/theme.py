"""Visual themes (design tokens).

Three selectable palettes/moods, chosen in Settings. A theme defines the
background gradient, the shape palette, glow strength, and the UI chrome colors -
nothing hard-codes a color outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    bg_top: Color
    bg_mid: Color
    bg_bottom: Color
    palette: tuple[Color, ...]  # vivid fill colors for shapes/effects
    accent: Color  # progress ring, highlights
    glow_alpha: int  # base bloom strength, 0-255
    vignette_alpha: int  # corner darkening, 0-255
    # UI chrome (settings card, pills, gear).
    panel_bg: Color
    text: Color
    text_dim: Color
    line: Color


_AURORA = Theme(
    key="aurora",
    label="Aurora",
    bg_top=(11, 16, 38),
    bg_mid=(27, 19, 70),
    bg_bottom=(7, 5, 18),
    palette=(
        (63, 224, 200),
        (255, 138, 214),
        (155, 107, 255),
        (255, 179, 71),
        (127, 208, 255),
        (124, 240, 176),
    ),
    accent=(124, 240, 176),
    glow_alpha=150,
    vignette_alpha=130,
    panel_bg=(17, 21, 46),
    text=(243, 244, 255),
    text_dim=(154, 160, 207),
    line=(255, 255, 255),
)

_CANDY = Theme(
    key="candy",
    label="Candy",
    bg_top=(40, 22, 74),
    bg_mid=(70, 40, 122),
    bg_bottom=(24, 12, 46),
    palette=(
        (255, 71, 148),
        (0, 224, 200),
        (255, 214, 64),
        (124, 240, 80),
        (124, 156, 255),
        (255, 122, 71),
    ),
    accent=(255, 214, 64),
    glow_alpha=120,
    vignette_alpha=80,
    panel_bg=(48, 26, 84),
    text=(255, 250, 255),
    text_dim=(214, 196, 240),
    line=(255, 255, 255),
)

_MINIMAL = Theme(
    key="minimal",
    label="Minimal",
    bg_top=(12, 12, 20),
    bg_mid=(16, 16, 26),
    bg_bottom=(6, 6, 12),
    palette=(
        (236, 239, 244),
        (136, 226, 208),
        (245, 203, 138),
        (180, 165, 230),
    ),
    accent=(136, 226, 208),
    glow_alpha=70,
    vignette_alpha=60,
    panel_bg=(20, 20, 30),
    text=(236, 239, 244),
    text_dim=(150, 154, 170),
    line=(255, 255, 255),
)

THEMES: dict[str, Theme] = {t.key: t for t in (_AURORA, _CANDY, _MINIMAL)}
THEME_ORDER: tuple[str, ...] = ("aurora", "candy", "minimal")
DEFAULT_THEME = "aurora"


def get_theme(key: str) -> Theme:
    return THEMES.get(key, THEMES[DEFAULT_THEME])
