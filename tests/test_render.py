"""Render helpers must produce surfaces of the requested size (the rest of the
code blits assuming exact dimensions)."""

from kidcomputer.render import (
    lighten,
    progress_ring,
    radial_glow,
    vertical_gradient,
    vignette,
)


def test_vertical_gradient_size() -> None:
    surf = vertical_gradient((40, 30), (0, 0, 0), (10, 10, 10), (20, 20, 20))
    assert surf.get_size() == (40, 30)


def test_radial_glow_is_square() -> None:
    assert radial_glow(64, (255, 0, 0)).get_size() == (64, 64)


def test_vignette_size_and_alpha() -> None:
    surf = vignette((50, 40), 120)
    assert surf.get_size() == (50, 40)


def test_progress_ring_size() -> None:
    assert progress_ring(80, 0.5, (0, 255, 0), (80, 80, 80)).get_size() == (80, 80)


def test_lighten_endpoints() -> None:
    assert lighten((0, 0, 0), 0.5) == (127, 127, 127)
    assert lighten((255, 255, 255), 0.5) == (255, 255, 255)
    assert lighten((100, 100, 100), 0.0) == (100, 100, 100)
