"""Theme and age-mode lookups must be total (never KeyError on bad input)."""

from kidcomputer.modes import DEFAULT_MODE, MODE_ORDER, MODES, get_mode
from kidcomputer.theme import DEFAULT_THEME, THEME_ORDER, THEMES, get_theme


def test_theme_order_matches_registry() -> None:
    assert set(THEME_ORDER) == set(THEMES)


def test_get_theme_known_and_fallback() -> None:
    assert get_theme("candy").key == "candy"
    assert get_theme("does-not-exist").key == DEFAULT_THEME


def test_mode_order_matches_registry() -> None:
    assert set(MODE_ORDER) == set(MODES)


def test_get_mode_known_and_fallback() -> None:
    assert get_mode("early").key == "early"
    assert get_mode("nope").key == DEFAULT_MODE


def test_only_early_has_kaleidoscope_symmetry() -> None:
    assert get_mode("toddler").symmetry == 1
    assert get_mode("preschool").symmetry == 1
    assert get_mode("early").symmetry > 1


def test_palettes_are_non_empty() -> None:
    for theme in THEMES.values():
        assert len(theme.palette) >= 3
