"""The scene: turns input into a themed, age-tuned show of effects and sounds.

Reads the active Theme (palette/mood), AgeMode (behavior), and intensity from the
SettingsStore. Owns the background, glow sprites, effects list, the top-left exit
hint, the auto-hiding gear, the anti-aliased exit ring, and the settings panel.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

import pygame

from kidcomputer.audio import SoundBank
from kidcomputer.config import SettingsStore
from kidcomputer.effects import (
    Bokeh,
    ConstellationStar,
    Effect,
    Firework,
    Friend,
    GlowShape,
    Glyph,
    Ripple,
    Sparkle,
)
from kidcomputer.modes import get_mode
from kidcomputer.render import draw_glow, progress_ring, radial_glow, vertical_gradient, vignette
from kidcomputer.settings_panel import SettingsPanel
from kidcomputer.theme import Theme, get_theme

_BASE_GLOW = 240
_MOUSE_TRAIL_INTERVAL = 0.03
_GEAR_IDLE_HIDE = 3.0
_EXIT_HINT = "Grown-ups: hold  Ctrl + Alt + Q  to exit"
_MAX_WORD = 14
_LINK_LIFE = 2.5
# Minimum gap between note triggers - stops a key-mash from stacking dozens of
# overlapping notes into a clipped, distorted wall of sound.
_NOTE_MIN_INTERVAL = 0.045


class Scene:
    def __init__(
        self,
        size: tuple[int, int],
        ui_rect: pygame.Rect,
        sounds: SoundBank,
        store: SettingsStore,
        on_exit: Callable[[], None],
    ) -> None:
        self.size = size
        self._ui = ui_rect
        self.sounds = sounds
        self.store = store
        self.effects: list[Effect] = []
        self._stars: list[list[float]] = []
        self._word: list[tuple[str, tuple[int, int, int]]] = []
        self._mouse_trail = 0.0
        self._mouse_idle = 0.0
        self._ambient = 0.0
        self._since_note = _NOTE_MIN_INTERVAL
        self._hint_font = pygame.font.SysFont("Segoe UI,Arial", max(16, min(ui_rect.size) // 45))
        self._panel = SettingsPanel(store, self._theme, self._apply_setting, on_exit)
        self._panel.set_ui_rect(ui_rect)
        self._apply_theme()
        self._apply_mode()

    # --- theming / settings ---------------------------------------------

    def _theme(self) -> Theme:
        return get_theme(self.store.theme)

    def _apply_theme(self) -> None:
        theme = self._theme()
        self._bg = vertical_gradient(self.size, theme.bg_top, theme.bg_mid, theme.bg_bottom)
        self._vignette = vignette(self.size, theme.vignette_alpha)
        self._palette = theme.palette
        self._glows = [radial_glow(_BASE_GLOW, c) for c in theme.palette]

    def _apply_mode(self) -> None:
        self.mode = get_mode(self.store.age_mode)
        frac = self.mode.glyph_fraction
        self._glyph_font = pygame.font.SysFont(
            "Arial Black,Arial", int(min(self._ui.size) * frac), bold=True
        )
        # Built once (not per frame); used for the early-mode word row.
        self._word_font = pygame.font.SysFont("Consolas,Arial", 56, bold=True)
        self._word.clear()
        self._stars.clear()

    def _apply_setting(self, key: str, value: object) -> None:
        """Apply a settings change live, then persist it."""
        self.store.set(key, value)
        if key == "theme":
            self._apply_theme()
        elif key == "age_mode":
            self._apply_mode()
        elif key == "sound":
            self.sounds.enabled = bool(value)
        elif key == "log_level":
            import logging

            logging.getLogger().setLevel(str(value))

    def set_update_status(self, text: str) -> None:
        self._panel.update_status = text

    # --- derived sizing --------------------------------------------------

    @property
    def _eff_max(self) -> int:
        return int(self.mode.max_effects * (0.5 + self.store.intensity))

    def _shape_radius(self) -> int:
        return max(12, int(min(self._ui.size) * self.mode.glyph_fraction * 0.5))

    def _random_pos(self) -> tuple[int, int]:
        m = self._shape_radius()
        return (random.randint(m, self.size[0] - m), random.randint(m, self.size[1] - m))

    def _pick(self) -> tuple[tuple[int, int, int], pygame.Surface]:
        i = random.randrange(len(self._palette))
        return self._palette[i], self._glows[i]

    # --- input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._panel.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self._gear_hit(event.pos):
                self._panel.toggle()
            else:
                self._on_click(event.pos)
        elif event.type == pygame.KEYDOWN:
            self._on_key(event)
        elif event.type == pygame.MOUSEMOTION:
            self._mouse_idle = 0.0

    def _gear_hit(self, pos: tuple[int, int]) -> bool:
        return math.dist(pos, self._gear_center()) <= 26

    def _gear_center(self) -> tuple[int, int]:
        return (self._ui.right - 44, self._ui.top + 44)

    def _on_key(self, event: pygame.event.Event) -> None:
        if self._panel.open:
            return
        base = self._random_pos()
        color, glow = self._pick()
        self._spawn_cluster(base, color, glow)
        # Only render plain A-Z / 0-9. Anything else (symbols, accented or
        # non-ASCII keys) is skipped rather than drawn as a "?" missing-glyph box.
        char = event.unicode.upper()
        renderable = len(char) == 1 and char.isascii() and char.isalnum()
        if renderable:
            if self.mode.always_glyph or random.random() < 0.5:
                self._add(Glyph(char, base, color, glow, self._glyph_font))
            if self.mode.word_row:
                self._push_word(char, color)
            if self.mode.counting_dots and char.isdigit() and char != "0":
                self._spawn_counting(int(char), base)
        if random.random() < 0.15:
            self._add(Ripple(base, color, max_radius=self._shape_radius() * 2.6))
        if self._since_note >= _NOTE_MIN_INTERVAL:
            self.sounds.play_note()
            self._since_note = 0.0

    def _spawn_cluster(
        self, base: tuple[int, int], color: tuple[int, int, int], glow: pygame.Surface
    ) -> None:
        if random.random() < self.mode.friend_chance:
            self._add(Friend(base, self._shape_radius(), color, glow))
            return
        for p in self._mirror_positions(base):
            self._add(
                GlowShape(
                    p, self._shape_radius(), color, glow, lifetime=1.4 * self.mode.lifetime_scale
                )
            )

    def _spawn_counting(self, count: int, base: tuple[int, int]) -> None:
        r = max(8, self._shape_radius() // 3)
        gap = r * 2.6
        start_x = base[0] - gap * (count - 1) / 2
        y = min(base[1] + self._shape_radius() + r * 2, self.size[1] - r)
        for i in range(count):
            color, glow = self._pick()
            self._add(
                GlowShape(
                    (int(start_x + i * gap), int(y)), r, color, glow, kind="circle", lifetime=1.6
                )
            )

    def _mirror_positions(self, pos: tuple[int, int]) -> list[tuple[int, int]]:
        n = self.mode.symmetry
        if n <= 1:
            return [pos]
        cx, cy = self._ui.center
        dx, dy = pos[0] - cx, pos[1] - cy
        out: list[tuple[int, int]] = []
        for k in range(n):
            a = k * 2 * math.pi / n
            ca, sa = math.cos(a), math.sin(a)
            out.append((int(cx + dx * ca - dy * sa), int(cy + dx * sa + dy * ca)))
        return out

    def _push_word(self, char: str, color: tuple[int, int, int]) -> None:
        self._word.append((char, color))
        if len(self._word) > _MAX_WORD:
            self._word.pop(0)

    def _on_click(self, pos: tuple[int, int]) -> None:
        color, glow = self._pick()
        if self.mode.constellation:
            self._add(ConstellationStar(pos, color, glow))
            self._stars.append([float(pos[0]), float(pos[1]), 0.0])
        count = int(self.mode.firework_particles * (0.5 + self.store.intensity))
        self._add(Firework(pos, color, glow, count=count, speed_scale=self.mode.speed_scale))
        self.sounds.play_chime()

    def _add(self, effect: Effect) -> None:
        self.effects.append(effect)
        if len(self.effects) > self._eff_max:
            del self.effects[: len(self.effects) - self._eff_max]

    # --- update ---------------------------------------------------------

    def update(self, dt: float) -> None:
        self._mouse_idle += dt
        self._since_note += dt
        self._update_trail(dt)
        self._update_ambient(dt)
        self._update_stars(dt)
        for effect in self.effects:
            effect.update(dt)
        self.effects = [e for e in self.effects if not e.dead]

    def _update_trail(self, dt: float) -> None:
        self._mouse_trail += dt
        if self._mouse_trail < _MOUSE_TRAIL_INTERVAL or self._panel.open:
            return
        self._mouse_trail = 0.0
        if pygame.mouse.get_focused():
            color, glow = self._pick()
            self._add(Sparkle(pygame.mouse.get_pos(), color, glow))

    def _update_ambient(self, dt: float) -> None:
        self._ambient += dt
        interval = self.mode.ambient_interval / (0.5 + self.store.intensity)
        if self._ambient < interval:
            return
        self._ambient = 0.0
        color, glow = self._pick()
        self._add(Bokeh(self._random_pos(), color, glow))

    def _update_stars(self, dt: float) -> None:
        for star in self._stars:
            star[2] += dt
        self._stars = [s for s in self._stars if s[2] < _LINK_LIFE][-8:]

    # --- draw -----------------------------------------------------------

    def draw(self, surface: pygame.Surface, exit_progress: float) -> None:
        surface.blit(self._bg, (0, 0))
        self._draw_links(surface)
        for effect in self.effects:
            effect.draw(surface)
        surface.blit(self._vignette, (0, 0))
        self._draw_word(surface)
        self._draw_hint(surface)
        self._draw_gear(surface)
        if exit_progress > 0.0:
            self._draw_exit_ring(surface, exit_progress)
        self._panel.draw(surface)

    def _draw_links(self, surface: pygame.Surface) -> None:
        if not self.mode.constellation or len(self._stars) < 2:
            return
        theme = self._theme()
        for a, b in zip(self._stars, self._stars[1:], strict=False):
            fade = max(0.0, 1.0 - max(a[2], b[2]) / _LINK_LIFE)
            color = tuple(int(c * fade) for c in theme.accent)
            pygame.draw.aaline(surface, color, (a[0], a[1]), (b[0], b[1]))

    def _draw_word(self, surface: pygame.Surface) -> None:
        if not self._word:
            return
        imgs = [self._glyph_render(ch, color) for ch, color in self._word]
        total = sum(i.get_width() for i in imgs) + 8 * (len(imgs) - 1)
        x = self._ui.centerx - total // 2
        y = self._ui.bottom - 90
        for img in imgs:
            surface.blit(img, (x, y))
            x += img.get_width() + 8

    def _glyph_render(self, char: str, color: tuple[int, int, int]) -> pygame.Surface:
        return self._word_font.render(char, True, color)

    def _draw_hint(self, surface: pygame.Surface) -> None:
        theme = self._theme()
        text = self._hint_font.render(_EXIT_HINT, True, theme.text)
        pad = 14
        pill = pygame.Surface(
            (text.get_width() + pad * 2 + 22, text.get_height() + pad), pygame.SRCALPHA
        )
        pill.fill((*theme.panel_bg, 150))
        pygame.draw.circle(pill, (*theme.accent, 230), (16, pill.get_height() // 2), 6)
        pill.blit(text, (28, pad // 2))
        surface.blit(pill, (self._ui.left + 24, self._ui.top + 22))

    def _draw_gear(self, surface: pygame.Surface) -> None:
        if self._panel.open or self._mouse_idle > _GEAR_IDLE_HIDE:
            return
        alpha = int(220 * max(0.0, 1.0 - max(0.0, self._mouse_idle - (_GEAR_IDLE_HIDE - 1.0))))
        theme = self._theme()
        chip = pygame.Surface((52, 52), pygame.SRCALPHA)
        c = (26, 26)
        pygame.draw.circle(chip, (*theme.panel_bg, 150), c, 26)
        pygame.draw.circle(chip, (*theme.text_dim, 255), c, 8, width=3)
        for k in range(8):
            a = k * math.pi / 4
            p1 = (c[0] + 12 * math.cos(a), c[1] + 12 * math.sin(a))
            p2 = (c[0] + 15 * math.cos(a), c[1] + 15 * math.sin(a))
            pygame.draw.line(chip, (*theme.text_dim, 255), p1, p2, 3)
        chip.set_alpha(alpha)
        surface.blit(chip, chip.get_rect(center=self._gear_center()))

    def _draw_exit_ring(self, surface: pygame.Surface, progress: float) -> None:
        theme = self._theme()
        diameter = int(min(self._ui.size) * 0.18)
        ring = progress_ring(diameter, progress, theme.accent, theme.text_dim)
        center = self._ui.center
        draw_glow(surface, self._glows[0], center, int(diameter * 0.7 * progress))
        surface.blit(ring, ring.get_rect(center=center))
        label = self._hint_font.render("keep holding to exit...", True, theme.text)
        surface.blit(label, label.get_rect(center=(center[0], center[1] + diameter // 2 + 28)))
