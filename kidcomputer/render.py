"""Rendering helpers: gradients, bloom glow, and anti-aliased shapes.

pygame's primitives are aliased and flat, which is what made the first version
look crude. These helpers add the polish:

* ``vertical_gradient`` - numpy-built smooth background gradient.
* ``radial_glow`` / ``draw_glow`` - a soft additive bloom sprite (baked falloff,
  blitted with BLEND_RGB_ADD so it adds light like a real glow).
* ``progress_ring`` - a supersampled, anti-aliased dotted exit ring.
* ``blit_centered`` and small color utilities.

Glow sprites are pre-rendered once per palette color and just scaled per draw,
so the bloom is cheap even at 4K.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

Color = tuple[int, int, int]


def vertical_gradient(
    size: tuple[int, int], top: Color, mid: Color, bottom: Color
) -> pygame.Surface:
    """A smooth top->mid->bottom vertical gradient surface."""
    width, height = size
    ys = np.linspace(0.0, 1.0, height)
    column = np.empty((height, 3), dtype=np.float64)
    for channel in range(3):
        column[:, channel] = np.interp(
            ys, (0.0, 0.5, 1.0), (top[channel], mid[channel], bottom[channel])
        )
    field = np.repeat(column[np.newaxis, :, :], width, axis=0)  # (w, h, 3) for surfarray
    return pygame.surfarray.make_surface(field.astype(np.uint8))


def radial_glow(diameter: int, color: Color, falloff: float = 2.2) -> pygame.Surface:
    """An additive bloom sprite: color fading to black from center to edge.

    Blit with ``BLEND_RGB_ADD`` (the falloff is baked into RGB, so black edges
    add nothing). Returned as a plain RGB surface for fast additive blits.
    """
    radius = diameter / 2.0
    axis = np.arange(diameter) - radius + 0.5
    xx, yy = np.meshgrid(axis, axis)
    dist = np.sqrt(xx * xx + yy * yy) / radius
    mask = np.clip(1.0 - dist, 0.0, 1.0) ** falloff
    rgb = np.empty((diameter, diameter, 3), dtype=np.float64)
    for channel in range(3):
        rgb[:, :, channel] = color[channel] * mask
    return pygame.surfarray.make_surface(rgb.astype(np.uint8))


def vignette(size: tuple[int, int], alpha: int) -> pygame.Surface:
    """A transparent overlay that darkens the corners, deepening the mood."""
    width, height = size
    xx, yy = np.mgrid[0:width, 0:height]
    dist = np.sqrt(((xx - width / 2) / (width / 2)) ** 2 + ((yy - height / 2) / (height / 2)) ** 2)
    mask = (np.clip((dist - 0.6) / 0.5, 0.0, 1.0) * alpha).astype(np.uint8)
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)
    rgb[:] = 0
    del rgb
    pa = pygame.surfarray.pixels_alpha(surf)
    pa[:] = mask
    del pa
    return surf


def draw_glow(
    surface: pygame.Surface, sprite: pygame.Surface, center: tuple[int, int], size: int
) -> None:
    """Scale a glow sprite and add it to the scene as light."""
    if size < 2:
        return
    scaled = pygame.transform.smoothscale(sprite, (size, size))
    surface.blit(scaled, scaled.get_rect(center=center), special_flags=pygame.BLEND_RGB_ADD)


def lighten(color: Color, amount: float) -> Color:
    """Mix a color toward white by ``amount`` (0..1) - used for shape highlights."""
    return tuple(int(c + (255 - c) * amount) for c in color)  # type: ignore[return-value]


def blit_centered(dest: pygame.Surface, src: pygame.Surface, center: tuple[int, int]) -> None:
    dest.blit(src, src.get_rect(center=center))


def progress_ring(
    diameter: int,
    progress: float,
    accent: Color,
    track: Color,
    dots: int = 48,
    supersample: int = 3,
) -> pygame.Surface:
    """An anti-aliased dotted progress ring (drawn big, smooth-scaled down)."""
    big = max(8, diameter * supersample)
    surf = pygame.Surface((big, big), pygame.SRCALPHA)
    center = big // 2
    ring_radius = big * 0.42
    dot_radius = max(2, int(big * 0.028))

    lit = max(0, min(dots, round(progress * dots)))
    for i in range(dots):
        angle = -math.pi / 2 + (i / dots) * 2 * math.pi
        x = int(center + ring_radius * math.cos(angle))
        y = int(center + ring_radius * math.sin(angle))
        if i < lit:
            pygame.draw.circle(surf, (*accent, 255), (x, y), dot_radius)
        else:
            pygame.draw.circle(surf, (*track, 90), (x, y), max(1, dot_radius - 1))

    return pygame.transform.smoothscale(surf, (diameter, diameter))
