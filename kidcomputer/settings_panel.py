"""The settings card: a glass panel opened by the top-right gear.

Holds About (version/build/update status), Sound, Log level, Effect intensity,
Theme, and Age mode. Each control reads its current value from the SettingsStore
and applies changes live via the ``on_change`` callback (which persists them).
An Exit button is a mouse-only backup to the Ctrl+Alt+Q combo.

Layout is computed once for the given UI rect (the primary monitor), so the card
is centered on one screen rather than across a dual-monitor seam.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

from kidcomputer import buildinfo
from kidcomputer.config import LOG_LEVELS, SettingsStore
from kidcomputer.modes import MODE_ORDER, get_mode
from kidcomputer.theme import THEME_ORDER, Theme, get_theme

_CARD_W = 460
_CARD_H = 580


def _segments(rect: pygame.Rect, count: int, gap: int = 6) -> list[pygame.Rect]:
    """Split a row into ``count`` equal pill rects."""
    inner = (rect.width - gap * (count - 1)) / count
    return [
        pygame.Rect(int(rect.x + i * (inner + gap)), rect.y, int(inner), rect.height)
        for i in range(count)
    ]


class SettingsPanel:
    def __init__(
        self,
        store: SettingsStore,
        get_active_theme: Callable[[], Theme],
        on_change: Callable[[str, object], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.store = store
        self._theme = get_active_theme
        self._on_change = on_change
        self._on_exit = on_exit
        self.open = False
        self.update_status = ""
        self._dragging = False
        self._card = pygame.Rect(0, 0, _CARD_W, _CARD_H)
        self._segs: dict[str, tuple[list[pygame.Rect], tuple[str, ...]]] = {}
        self._sound_rect = pygame.Rect(0, 0, 0, 0)
        self._slider = pygame.Rect(0, 0, 0, 0)
        self._exit_rect = pygame.Rect(0, 0, 0, 0)
        self._close_rect = pygame.Rect(0, 0, 0, 0)
        self._font_title = pygame.font.SysFont("Segoe UI,Arial", 26, bold=True)
        self._font = pygame.font.SysFont("Segoe UI,Arial", 18)
        self._font_small = pygame.font.SysFont("Segoe UI,Arial", 14)

    def toggle(self) -> None:
        self.open = not self.open

    def set_ui_rect(self, ui_rect: pygame.Rect) -> None:
        self._card = pygame.Rect(0, 0, _CARD_W, _CARD_H)
        self._card.center = ui_rect.center
        self._layout()

    def _layout(self) -> None:
        x = self._card.x + 28
        w = self._card.width - 56
        self._close_rect = pygame.Rect(self._card.right - 46, self._card.y + 18, 28, 28)
        y = self._card.y + 150  # below title + About block
        row_h = 36
        self._sound_rect = pygame.Rect(self._card.right - 90, y, 62, 28)
        y += 56
        self._segs["log_level"] = (
            _segments(pygame.Rect(x, y, w, row_h), len(LOG_LEVELS)),
            LOG_LEVELS,
        )
        y += 64
        self._slider = pygame.Rect(x, y, w, 8)
        y += 56
        self._segs["theme"] = (
            _segments(pygame.Rect(x, y, w, row_h), len(THEME_ORDER)),
            THEME_ORDER,
        )
        y += 64
        self._segs["age_mode"] = (
            _segments(pygame.Rect(x, y, w, row_h), len(MODE_ORDER)),
            MODE_ORDER,
        )
        y += 64
        self._exit_rect = pygame.Rect(x, y, w, 44)

    # --- input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the panel consumed the event (so the scene ignores it)."""
        if not self.open:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self._on_click(event.pos)
        if event.type == pygame.MOUSEMOTION and self._dragging:
            self._set_intensity_from_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP:
            self._dragging = False
        return self.open  # swallow other mouse events while open

    def _on_click(self, pos: tuple[int, int]) -> bool:
        if self._close_rect.collidepoint(pos):
            self.open = False
            return True
        if self._exit_rect.collidepoint(pos):
            self._on_exit()
            return True
        if self._sound_rect.collidepoint(pos):
            self._on_change("sound", not self.store.sound)
            return True
        if self._slider.inflate(0, 28).collidepoint(pos):
            self._dragging = True
            self._set_intensity_from_x(pos[0])
            return True
        if self._click_segments(pos):
            return True
        # Click anywhere outside the card closes it; inside is swallowed.
        if not self._card.collidepoint(pos):
            self.open = False
        return True

    def _click_segments(self, pos: tuple[int, int]) -> bool:
        for key, (rects, values) in self._segs.items():
            for rect, value in zip(rects, values, strict=True):
                if rect.collidepoint(pos):
                    self._on_change(key, value)
                    return True
        return False

    def _set_intensity_from_x(self, x: int) -> None:
        frac = (x - self._slider.x) / max(1, self._slider.width)
        self._on_change("intensity", max(0.0, min(1.0, frac)))

    # --- draw -----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        if not self.open:
            return
        theme = self._theme()
        scrim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, 120))
        surface.blit(scrim, (0, 0))
        self._draw_card(surface, theme)

    def _draw_card(self, surface: pygame.Surface, theme: Theme) -> None:
        pygame.draw.rect(surface, theme.panel_bg, self._card, border_radius=22)
        pygame.draw.rect(surface, theme.line, self._card, width=1, border_radius=22)
        x = self._card.x + 28
        self._blit(surface, self._font_title, "Settings", (x, self._card.y + 22), theme.text)
        self._draw_close(surface, theme)
        self._draw_about(surface, theme, x)
        self._draw_sound(surface, theme, x)
        self._draw_segments(surface, theme, x)
        self._draw_slider(surface, theme, x)
        self._draw_exit(surface, theme)

    def _draw_close(self, surface: pygame.Surface, theme: Theme) -> None:
        c = self._close_rect.center
        pygame.draw.line(surface, theme.text_dim, (c[0] - 6, c[1] - 6), (c[0] + 6, c[1] + 6), 3)
        pygame.draw.line(surface, theme.text_dim, (c[0] + 6, c[1] - 6), (c[0] - 6, c[1] + 6), 3)

    def _draw_about(self, surface: pygame.Surface, theme: Theme, x: int) -> None:
        y = self._card.y + 70
        self._blit(surface, self._font_small, "ABOUT", (x, y), theme.text_dim)
        self._blit(
            surface, self._font, f"Kid Computer  v{buildinfo.VERSION}", (x, y + 22), theme.text
        )
        detail = f"build {buildinfo.short_sha()}  -  {buildinfo.BUILD_TIME}"
        if self.update_status:
            detail += f"  -  {self.update_status}"
        self._blit(surface, self._font_small, detail, (x, y + 48), theme.text_dim)

    def _draw_sound(self, surface: pygame.Surface, theme: Theme, x: int) -> None:
        self._blit(surface, self._font, "Sound", (x, self._sound_rect.y + 2), theme.text)
        on = self.store.sound
        track = theme.accent if on else theme.line
        pygame.draw.rect(surface, track, self._sound_rect, border_radius=14)
        knob_x = self._sound_rect.right - 14 if on else self._sound_rect.x + 14
        pygame.draw.circle(surface, (255, 255, 255), (knob_x, self._sound_rect.centery), 11)

    def _draw_segments(self, surface: pygame.Surface, theme: Theme, x: int) -> None:
        labels = {
            "log_level": ("Log level", self.store.log_level, lambda v: v),
            "theme": ("Theme", self.store.theme, lambda v: get_theme(v).label),
            "age_mode": ("Age mode", self.store.age_mode, lambda v: get_mode(v).label),
        }
        for key, (rects, values) in self._segs.items():
            title, current, render_label = labels[key]
            self._blit(surface, self._font, title, (x, rects[0].y - 28), theme.text)
            for rect, value in zip(rects, values, strict=True):
                selected = value == current
                fill = theme.accent if selected else theme.panel_bg
                pygame.draw.rect(surface, fill, rect, border_radius=9)
                pygame.draw.rect(surface, theme.line, rect, width=1, border_radius=9)
                color = (20, 20, 30) if selected else theme.text_dim
                self._blit_centered(
                    surface, self._font_small, render_label(value), rect.center, color
                )

    def _draw_slider(self, surface: pygame.Surface, theme: Theme, x: int) -> None:
        self._blit(surface, self._font, "Effect intensity", (x, self._slider.y - 28), theme.text)
        pygame.draw.rect(surface, theme.line, self._slider, border_radius=4)
        filled = self._slider.copy()
        filled.width = int(self._slider.width * self.store.intensity)
        pygame.draw.rect(surface, theme.accent, filled, border_radius=4)
        knob_x = self._slider.x + filled.width
        pygame.draw.circle(surface, (255, 255, 255), (knob_x, self._slider.centery), 10)

    def _draw_exit(self, surface: pygame.Surface, theme: Theme) -> None:
        pygame.draw.rect(surface, (255, 93, 115), self._exit_rect, border_radius=12)
        self._blit_centered(
            surface, self._font, "Exit Kid Computer", self._exit_rect.center, (255, 255, 255)
        )

    def _blit(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        topleft: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        surface.blit(font.render(text, True, color), topleft)

    def _blit_centered(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        center: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        img = font.render(text, True, color)
        surface.blit(img, img.get_rect(center=center))
