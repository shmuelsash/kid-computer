"""On-screen effects, redesigned for a softer, more sophisticated look.

Every effect implements ``update(dt)`` and ``draw(surface)`` and reports ``dead``
when it should be culled. Shapes are filled with a base color plus a lighter
highlight and wrapped in an additive bloom glow; motion uses spring easing.
Effects receive a pre-rendered glow sprite (see render.radial_glow) matching
their color so the bloom is cheap to draw.
"""

from __future__ import annotations

import math
import random

import pygame

from kidcomputer.render import draw_glow, lighten

Color = tuple[int, int, int]
Pos = tuple[int, int]
Glow = pygame.Surface


def ease_out_back(t: float) -> float:
    """Spring overshoot easing for a lively 'pop'."""
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


class Effect:
    """Base: subclasses set lifetime and override draw."""

    def __init__(self, lifetime: float) -> None:
        self.lifetime = lifetime
        self.age = 0.0

    @property
    def dead(self) -> bool:
        return self.age >= self.lifetime

    @property
    def t(self) -> float:
        return min(1.0, self.age / self.lifetime)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface) -> None:  # pragma: no cover
        raise NotImplementedError


def _polygon(
    center: tuple[float, float], radius: float, sides: int, angle: float
) -> list[tuple[float, float]]:
    cx, cy = center
    step = 2 * math.pi / sides
    return [
        (cx + radius * math.cos(angle + i * step), cy + radius * math.sin(angle + i * step))
        for i in range(sides)
    ]


def _star_points(
    center: tuple[float, float], radius: float, angle: float
) -> list[tuple[float, float]]:
    cx, cy = center
    out: list[tuple[float, float]] = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.45
        a = angle + i * math.pi / 5
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def _draw_filled(
    surface: pygame.Surface,
    kind: str,
    center: tuple[float, float],
    radius: float,
    color: tuple[int, ...],
    angle: float,
) -> None:
    if kind == "circle":
        pygame.draw.circle(surface, color, (int(center[0]), int(center[1])), int(radius))
    elif kind == "square":
        pygame.draw.polygon(surface, color, _polygon(center, radius, 4, angle))
    elif kind == "triangle":
        pygame.draw.polygon(surface, color, _polygon(center, radius, 3, angle))
    else:
        pygame.draw.polygon(surface, color, _star_points(center, radius, angle))


class GlowShape(Effect):
    """A glowing shape that springs in, holds, then fades."""

    KINDS = ("circle", "square", "triangle", "star")

    def __init__(
        self,
        pos: Pos,
        radius: float,
        color: Color,
        glow: Glow,
        *,
        kind: str | None = None,
        lifetime: float = 1.4,
    ) -> None:
        super().__init__(lifetime=lifetime)
        self.pos = pos
        self.radius = radius
        self.color = color
        self.glow = glow
        self.kind = kind or random.choice(self.KINDS)
        self.spin = random.uniform(-1.6, 1.6)

    def _scale(self) -> float:
        return ease_out_back(self.t / 0.28) if self.t < 0.28 else 1.0

    def _alpha(self) -> int:
        if self.t < 0.65:
            return 255
        return max(0, int(255 * (1.0 - (self.t - 0.65) / 0.35)))

    def draw(self, surface: pygame.Surface) -> None:
        scale = self._scale()
        alpha = self._alpha()
        radius = max(1.0, self.radius * scale)
        glow_size = int(radius * 2.7 * (0.45 + 0.55 * alpha / 255))
        draw_glow(surface, self.glow, self.pos, glow_size)
        self._draw_body(surface, radius, alpha)

    def _draw_body(self, surface: pygame.Surface, radius: float, alpha: int) -> None:
        angle = self.age * self.spin
        highlight = lighten(self.color, 0.45)
        hi_center = (self.pos[0] - radius * 0.18, self.pos[1] - radius * 0.22)
        if alpha >= 255:
            _draw_filled(surface, self.kind, self.pos, radius, self.color, angle)
            _draw_filled(surface, self.kind, hi_center, radius * 0.55, highlight, angle)
            return
        size = int(radius * 2 + 6)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size / 2, size / 2)
        hi = (c[0] - radius * 0.18, c[1] - radius * 0.22)
        _draw_filled(layer, self.kind, c, radius, (*self.color, alpha), angle)
        _draw_filled(layer, self.kind, hi, radius * 0.55, (*highlight, alpha), angle)
        surface.blit(layer, layer.get_rect(center=self.pos))


class Friend(Effect):
    """A round glowing 'friend' with eyes and a smile (preschool mode)."""

    def __init__(
        self, pos: Pos, radius: float, color: Color, glow: Glow, *, lifetime: float = 1.8
    ) -> None:
        super().__init__(lifetime=lifetime)
        self.pos = pos
        self.radius = radius
        self.color = color
        self.glow = glow

    def _scale(self) -> float:
        return ease_out_back(self.t / 0.3) if self.t < 0.3 else 1.0

    def draw(self, surface: pygame.Surface) -> None:
        fade = 1.0 if self.t < 0.7 else max(0.0, 1.0 - (self.t - 0.7) / 0.3)
        r = max(2.0, self.radius * self._scale())
        cx, cy = self.pos
        draw_glow(surface, self.glow, self.pos, int(r * 2.7 * (0.4 + 0.6 * fade)))
        pygame.draw.circle(surface, self.color, (int(cx), int(cy)), int(r))
        eye_dx, eye_dy, eye_r = r * 0.32, r * 0.12, max(2, int(r * 0.18))
        for sign in (-1, 1):
            ex = int(cx + sign * eye_dx)
            pygame.draw.circle(surface, (255, 255, 255), (ex, int(cy - eye_dy)), eye_r)
            pygame.draw.circle(surface, (34, 34, 51), (ex, int(cy - eye_dy)), max(1, eye_r // 2))
        smile = pygame.Rect(0, 0, int(r * 0.8), int(r * 0.6))
        smile.center = (int(cx), int(cy + r * 0.18))
        pygame.draw.arc(surface, (34, 34, 51), smile, math.pi, 2 * math.pi, max(2, int(r * 0.08)))


class Glyph(Effect):
    """A big glowing character that pops up and floats away."""

    def __init__(
        self,
        char: str,
        pos: Pos,
        color: Color,
        glow: Glow,
        font: pygame.font.Font,
        *,
        lifetime: float = 1.6,
    ) -> None:
        super().__init__(lifetime=lifetime)
        self.pos = pos
        self.glow = glow
        self._base = font.render(char, True, color)

    def draw(self, surface: pygame.Surface) -> None:
        scale = 0.5 + 1.1 * min(1.0, self.t / 0.3)
        rise = self.pos[1] - 70 * self.t
        center = (self.pos[0], int(rise))
        draw_glow(surface, self.glow, center, int(self._base.get_width() * scale * 1.1))
        img = pygame.transform.rotozoom(self._base, 0, scale)
        img.set_alpha(int(255 * (1.0 - self.t**2)))
        surface.blit(img, img.get_rect(center=center))


class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "size")

    def __init__(self, x: float, y: float, vx: float, vy: float, size: int) -> None:
        self.x, self.y, self.vx, self.vy, self.size = x, y, vx, vy, size


class Firework(Effect):
    """A glowing burst that flies out and falls under gravity."""

    GRAVITY = 420.0

    def __init__(
        self,
        pos: Pos,
        color: Color,
        glow: Glow,
        *,
        count: int = 80,
        speed_scale: float = 1.0,
        lifetime: float = 1.5,
    ) -> None:
        super().__init__(lifetime=lifetime)
        self.color = color
        self.glow = glow
        self.particles = [self._spawn(pos, speed_scale) for _ in range(count)]

    def _spawn(self, pos: Pos, speed_scale: float) -> _Particle:
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(90, 380) * speed_scale
        return _Particle(
            pos[0], pos[1], math.cos(angle) * speed, math.sin(angle) * speed, random.randint(3, 7)
        )

    def update(self, dt: float) -> None:
        super().update(dt)
        for p in self.particles:
            p.vy += self.GRAVITY * dt
            p.x += p.vx * dt
            p.y += p.vy * dt

    def draw(self, surface: pygame.Surface) -> None:
        fade = 1.0 - self.t
        for p in self.particles:
            center = (int(p.x), int(p.y))
            draw_glow(surface, self.glow, center, int(p.size * 4 * fade))
            pygame.draw.circle(surface, self.color, center, max(1, int(p.size * fade)))


class Sparkle(Effect):
    """A tiny glowing dot for the mouse-move trail."""

    def __init__(self, pos: Pos, color: Color, glow: Glow, *, lifetime: float = 0.6) -> None:
        super().__init__(lifetime=lifetime)
        self.pos = pos
        self.color = color
        self.glow = glow
        self.size = random.randint(4, 9)

    def draw(self, surface: pygame.Surface) -> None:
        fade = 1.0 - self.t
        draw_glow(surface, self.glow, self.pos, int(self.size * 3 * fade))
        pygame.draw.circle(surface, self.color, self.pos, max(1, int(self.size * fade)))


class Ripple(Effect):
    """Expanding concentric rings - a calm replacement for the old pop-windows."""

    def __init__(
        self, pos: Pos, color: Color, *, max_radius: float = 220, lifetime: float = 1.6
    ) -> None:
        super().__init__(lifetime=lifetime)
        self.pos = pos
        self.color = color
        self.max_radius = max_radius

    def draw(self, surface: pygame.Surface) -> None:
        fade = 1.0 - self.t
        size = int(self.max_radius * 2 + 8)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        for k in range(3):
            r = int(self.max_radius * self.t) - k * 26
            if r > 2:
                alpha = int(120 * fade * (1.0 - k * 0.3))
                pygame.draw.circle(layer, (*self.color, max(0, alpha)), c, r, width=3)
        surface.blit(layer, layer.get_rect(center=self.pos))


class Bokeh(Effect):
    """A soft glowing orb that drifts slowly upward and fades - ambient depth."""

    def __init__(self, pos: Pos, color: Color, glow: Glow, *, lifetime: float = 4.5) -> None:
        super().__init__(lifetime=lifetime)
        self.x, self.y = float(pos[0]), float(pos[1])
        self.glow = glow
        self.size = random.randint(80, 180)
        self.vx = random.uniform(-12, 12)
        self.vy = random.uniform(-26, -10)

    def update(self, dt: float) -> None:
        super().update(dt)
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surface: pygame.Surface) -> None:
        fade = math.sin(self.t * math.pi)  # fade in then out
        draw_glow(
            surface, self.glow, (int(self.x), int(self.y)), int(self.size * (0.4 + 0.6 * fade))
        )


class ConstellationStar(Effect):
    """A bright star point (early mode). The scene links recent stars with lines."""

    def __init__(self, pos: Pos, color: Color, glow: Glow, *, lifetime: float = 2.6) -> None:
        super().__init__(lifetime=lifetime)
        self.pos = pos
        self.color = color
        self.glow = glow

    def draw(self, surface: pygame.Surface) -> None:
        fade = 1.0 if self.t < 0.6 else max(0.0, 1.0 - (self.t - 0.6) / 0.4)
        draw_glow(surface, self.glow, self.pos, int(34 * (0.5 + 0.5 * fade)))
        pygame.draw.circle(surface, self.color, self.pos, max(2, int(6 * (0.6 + 0.4 * fade))))
