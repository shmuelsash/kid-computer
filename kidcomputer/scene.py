"""The scene: turns key/mouse input into a live show of effects and sounds.

Owns the list of live effects, a gently shifting background, an always-visible
exit hint, and the exit-progress ring. Tuned for toddlers: big bold shapes, lots
of motion, soft (non-strobing) color washes, and cheerful pentatonic sounds.
"""

from __future__ import annotations

import colorsys
import random

import pygame

from kidcomputer.audio import SoundBank
from kidcomputer.buildinfo import build_summary
from kidcomputer.effects import (
    Effect,
    Firework,
    Glyph,
    PopWindow,
    Shape,
    Sparkle,
    random_color,
)

# Keep memory bounded no matter how fast the keys are mashed.
_MAX_EFFECTS = 240
# A soft, infrequent color wash - deliberately gentle, never a harsh strobe.
_FLASH_ALPHA = 70
_FLASH_LIFE = 0.35
_MOUSE_TRAIL_INTERVAL = 0.03
_IDLE_AMBIENT_INTERVAL = 2.5
_EXIT_HINT = "Grown-ups: hold  Ctrl + Alt + Q  to exit"


class Scene:
    def __init__(self, size: tuple[int, int], sounds: SoundBank) -> None:
        self.size = size
        self.sounds = sounds
        self.effects: list[Effect] = []
        self._bg_hue = random.random()
        self._flash: tuple[tuple[int, int, int], float] | None = None
        self._mouse_accum = 0.0
        self._idle_accum = 0.0
        short_side = min(size)
        self._max_radius = max(40, short_side // 8)
        self._glyph_font = pygame.font.SysFont("arialblack,arial", short_side // 4, bold=True)
        self._hint_font = pygame.font.SysFont("arial", max(16, short_side // 45))

    # --- input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._on_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_click(event.pos)

    def _random_pos(self) -> tuple[int, int]:
        margin = self._max_radius
        return (
            random.randint(margin, self.size[0] - margin),
            random.randint(margin, self.size[1] - margin),
        )

    def _on_key(self, event: pygame.event.Event) -> None:
        pos = self._random_pos()
        self._add(Shape(pos, self._max_radius))
        char = event.unicode
        if char and char.isprintable() and not char.isspace():
            self._add(Glyph(char.upper(), pos, self._glyph_font))
        self.sounds.play_note()
        roll = random.random()
        if roll < 0.18:
            self._add(PopWindow(self.size))
        if roll > 0.88:
            self._flash = (random_color(), 0.0)

    def _on_click(self, pos: tuple[int, int]) -> None:
        self._add(Firework(pos))
        self.sounds.play_chime()

    def _on_mouse_move(self, dt: float) -> None:
        self._mouse_accum += dt
        if self._mouse_accum < _MOUSE_TRAIL_INTERVAL:
            return
        self._mouse_accum = 0.0
        if pygame.mouse.get_focused():
            self._add(Sparkle(pygame.mouse.get_pos()))

    def _add(self, effect: Effect) -> None:
        self.effects.append(effect)
        if len(self.effects) > _MAX_EFFECTS:
            del self.effects[: len(self.effects) - _MAX_EFFECTS]

    # --- update ---------------------------------------------------------

    def update(self, dt: float) -> None:
        self._bg_hue = (self._bg_hue + dt * 0.02) % 1.0
        self._on_mouse_move(dt)
        self._update_ambient(dt)
        self._update_flash(dt)
        for effect in self.effects:
            effect.update(dt)
        self.effects = [e for e in self.effects if not e.dead]

    def _update_ambient(self, dt: float) -> None:
        # Keep something gently happening even when no one is pressing keys.
        self._idle_accum += dt
        if self._idle_accum >= _IDLE_AMBIENT_INTERVAL:
            self._idle_accum = 0.0
            spawn = (
                PopWindow(self.size)
                if random.random() < 0.5
                else Shape(self._random_pos(), self._max_radius)
            )
            self._add(spawn)

    def _update_flash(self, dt: float) -> None:
        if self._flash is None:
            return
        color, age = self._flash
        age += dt
        self._flash = None if age >= _FLASH_LIFE else (color, age)

    # --- draw -----------------------------------------------------------

    def _background_color(self) -> tuple[int, int, int]:
        # Dark, rich, slowly shifting hue so bright effects always pop on top.
        r, g, b = colorsys.hsv_to_rgb(self._bg_hue, 0.6, 0.18)
        return (int(r * 255), int(g * 255), int(b * 255))

    def draw(self, surface: pygame.Surface, exit_progress: float) -> None:
        surface.fill(self._background_color())
        for effect in self.effects:
            effect.draw(surface)
        self._draw_flash(surface)
        self._draw_hint(surface)
        if exit_progress > 0.0:
            self._draw_exit_ring(surface, exit_progress)

    def _draw_flash(self, surface: pygame.Surface) -> None:
        if self._flash is None:
            return
        color, age = self._flash
        fade = 1.0 - age / _FLASH_LIFE
        overlay = pygame.Surface(self.size, pygame.SRCALPHA)
        overlay.fill((*color, int(_FLASH_ALPHA * fade)))
        surface.blit(overlay, (0, 0))

    def _draw_hint(self, surface: pygame.Surface) -> None:
        hint = self._hint_font.render(_EXIT_HINT, True, (235, 235, 235))
        hint.set_alpha(150)
        rect = hint.get_rect(midbottom=(self.size[0] // 2, self.size[1] - 12))
        surface.blit(hint, rect)
        about = self._hint_font.render(build_summary(), True, (160, 160, 160))
        about.set_alpha(110)
        surface.blit(about, about.get_rect(bottomright=(self.size[0] - 10, self.size[1] - 10)))

    def _draw_exit_ring(self, surface: pygame.Surface, progress: float) -> None:
        import math

        cx, cy = self.size[0] // 2, self.size[1] // 2
        radius = min(self.size) // 8
        rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), radius, width=4)
        end = -math.pi / 2 + progress * 2 * math.pi
        pygame.draw.arc(surface, (80, 220, 120), rect, -math.pi / 2, end, width=10)
        label = self._hint_font.render("Keep holding to exit...", True, (255, 255, 255))
        surface.blit(label, label.get_rect(center=(cx, cy + radius + 24)))
