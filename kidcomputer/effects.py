"""On-screen effects: shapes, glyphs, fireworks, sparkles, pop-up windows.

Each effect implements ``update(dt)`` and ``draw(surface)`` and reports ``dead``
when it should be culled. The scene keeps a list of live effects and lets them
age out. Everything is drawn with pygame primitives - no image assets.
"""

from __future__ import annotations

import colorsys
import math
import random

import pygame

Color = tuple[int, int, int]


def random_color() -> Color:
    """A vivid, well-saturated color - bold and toddler-friendly."""
    hue = random.random()
    sat = random.uniform(0.7, 1.0)
    val = random.uniform(0.9, 1.0)
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return (int(r * 255), int(g * 255), int(b * 255))


class Effect:
    """Base class. Subclasses set ``self.life``/``self.age`` and override draw."""

    def __init__(self, lifetime: float) -> None:
        self.lifetime = lifetime
        self.age = 0.0

    @property
    def dead(self) -> bool:
        return self.age >= self.lifetime

    @property
    def t(self) -> float:
        """Normalized progress 0.0 -> 1.0 across the effect's life."""
        return min(1.0, self.age / self.lifetime)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface) -> None:  # pragma: no cover
        raise NotImplementedError


class Shape(Effect):
    """A big shape that pops in (scales up), holds, then fades out."""

    KINDS = ("circle", "square", "triangle", "star")

    def __init__(self, pos: tuple[int, int], max_radius: int) -> None:
        super().__init__(lifetime=1.4)
        self.pos = pos
        self.max_radius = max_radius
        self.color = random_color()
        self.kind = random.choice(self.KINDS)
        self.spin = random.uniform(-2.0, 2.0)

    def _radius(self) -> int:
        # Ease-out pop: quick grow in the first 25%, gentle settle after.
        grow = min(1.0, self.t / 0.25)
        eased = 1.0 - (1.0 - grow) ** 3
        return max(1, int(self.max_radius * eased))

    def _alpha(self) -> int:
        # Fully opaque until 60% of life, then fade.
        if self.t < 0.6:
            return 255
        return int(255 * (1.0 - (self.t - 0.6) / 0.4))

    def draw(self, surface: pygame.Surface) -> None:
        radius = self._radius()
        layer = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        center = (radius + 2, radius + 2)
        color = (*self.color, self._alpha())
        angle = self.age * self.spin
        _draw_kind(layer, self.kind, center, radius, color, angle)
        surface.blit(layer, (self.pos[0] - center[0], self.pos[1] - center[1]))


def _draw_kind(
    surface: pygame.Surface,
    kind: str,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int, int],
    angle: float,
) -> None:
    if kind == "circle":
        pygame.draw.circle(surface, color, center, radius)
    elif kind == "square":
        pygame.draw.polygon(surface, color, _polygon(center, radius, 4, angle))
    elif kind == "triangle":
        pygame.draw.polygon(surface, color, _polygon(center, radius, 3, angle))
    else:
        pygame.draw.polygon(surface, color, _star_points(center, radius, angle))


def _polygon(
    center: tuple[int, int], radius: int, sides: int, angle: float
) -> list[tuple[float, float]]:
    cx, cy = center
    step = 2 * math.pi / sides
    return [
        (cx + radius * math.cos(angle + i * step), cy + radius * math.sin(angle + i * step))
        for i in range(sides)
    ]


def _star_points(center: tuple[int, int], radius: int, angle: float) -> list[tuple[float, float]]:
    cx, cy = center
    points: list[tuple[float, float]] = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.45
        a = angle + i * math.pi / 5
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return points


class Glyph(Effect):
    """A big character that pops up where a key was pressed, then floats away."""

    def __init__(self, char: str, pos: tuple[int, int], font: pygame.font.Font) -> None:
        super().__init__(lifetime=1.6)
        self.pos = pos
        self.color = random_color()
        self._base = font.render(char, True, self.color)

    def draw(self, surface: pygame.Surface) -> None:
        scale = 0.5 + 1.2 * min(1.0, self.t / 0.3)
        img = pygame.transform.rotozoom(self._base, 0, scale)
        img.set_alpha(int(255 * (1.0 - self.t**2)))
        rect = img.get_rect(center=(self.pos[0], int(self.pos[1] - 60 * self.t)))
        surface.blit(img, rect)


class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "size")

    def __init__(self, x: float, y: float, vx: float, vy: float, color: Color, size: int) -> None:
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.color, self.size = color, size


class Firework(Effect):
    """A burst of particles that fly outward and fall under gravity."""

    GRAVITY = 420.0

    def __init__(self, pos: tuple[int, int], count: int = 60) -> None:
        super().__init__(lifetime=1.5)
        base = random_color()
        self.particles = [self._spawn(pos, base) for _ in range(count)]

    def _spawn(self, pos: tuple[int, int], base: Color) -> _Particle:
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(80, 360)
        color = base if random.random() < 0.6 else random_color()
        return _Particle(
            pos[0],
            pos[1],
            math.cos(angle) * speed,
            math.sin(angle) * speed,
            color,
            random.randint(3, 7),
        )

    def update(self, dt: float) -> None:
        super().update(dt)
        for p in self.particles:
            p.vy += self.GRAVITY * dt
            p.x += p.vx * dt
            p.y += p.vy * dt

    def draw(self, surface: pygame.Surface) -> None:
        alpha = int(255 * (1.0 - self.t))
        for p in self.particles:
            dot = pygame.Surface((p.size * 2, p.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*p.color, alpha), (p.size, p.size), p.size)
            surface.blit(dot, (int(p.x - p.size), int(p.y - p.size)))


class Sparkle(Effect):
    """A tiny short-lived dot for the mouse-move trail."""

    def __init__(self, pos: tuple[int, int]) -> None:
        super().__init__(lifetime=0.6)
        self.pos = pos
        self.color = random_color()
        self.size = random.randint(4, 10)

    def draw(self, surface: pygame.Surface) -> None:
        alpha = int(255 * (1.0 - self.t))
        size = max(1, int(self.size * (1.0 - self.t)))
        dot = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(dot, (*self.color, alpha), (size, size), size)
        surface.blit(dot, (self.pos[0] - size, self.pos[1] - size))


class PopWindow(Effect):
    """A little window that opens (scales up) and snaps closed - like apps
    opening and closing, but completely harmless."""

    def __init__(self, screen_size: tuple[int, int]) -> None:
        super().__init__(lifetime=1.8)
        w, h = screen_size
        self.full_w = random.randint(int(w * 0.18), int(w * 0.34))
        self.full_h = random.randint(int(h * 0.18), int(h * 0.32))
        self.cx = random.randint(self.full_w, w - self.full_w)
        self.cy = random.randint(self.full_h, h - self.full_h)
        self.body = random_color()
        self.bar = random_color()

    def _scale(self) -> float:
        # Open fast (first 25%), hold, then close in the last 20%.
        if self.t < 0.25:
            return self.t / 0.25
        if self.t > 0.8:
            return max(0.0, (1.0 - self.t) / 0.2)
        return 1.0

    def draw(self, surface: pygame.Surface) -> None:
        scale = self._scale()
        if scale <= 0.01:
            return
        w = int(self.full_w * scale)
        h = int(self.full_h * scale)
        x = self.cx - w // 2
        y = self.cy - h // 2
        bar_h = max(4, h // 6)
        pygame.draw.rect(surface, self.body, (x, y, w, h), border_radius=8)
        pygame.draw.rect(surface, self.bar, (x, y, w, bar_h), border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), (x, y, w, h), width=3, border_radius=8)
