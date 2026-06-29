"""Settings panel: segment geometry and click routing."""

from pathlib import Path

import pygame

from kidcomputer.config import SettingsStore
from kidcomputer.settings_panel import SettingsPanel, _segments
from kidcomputer.theme import get_theme


def test_segments_split_evenly() -> None:
    rects = _segments(pygame.Rect(0, 0, 360, 36), 4)
    assert len(rects) == 4
    assert rects[0].x == 0
    assert rects[-1].right <= 360


def _panel(tmp_path: Path) -> tuple[SettingsPanel, list, list]:
    pygame.init()
    store = SettingsStore(path=tmp_path / "settings.json")
    changes: list = []
    exits: list = []
    panel = SettingsPanel(
        store,
        lambda: get_theme(store.theme),
        lambda k, v: changes.append((k, v)),
        lambda: exits.append(True),
    )
    panel.set_ui_rect(pygame.Rect(0, 0, 1280, 800))
    panel.open = True
    return panel, changes, exits


def _click(panel: SettingsPanel, pos: tuple[int, int]) -> bool:
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)
    return panel.handle_event(event)


def test_clicking_theme_segment_emits_change(tmp_path: Path) -> None:
    panel, changes, _ = _panel(tmp_path)
    rects, values = panel._segs["theme"]
    assert _click(panel, rects[1].center) is True
    assert ("theme", values[1]) in changes


def test_clicking_exit_invokes_callback(tmp_path: Path) -> None:
    panel, _, exits = _panel(tmp_path)
    assert _click(panel, panel._exit_rect.center) is True
    assert exits == [True]


def test_closed_panel_ignores_events(tmp_path: Path) -> None:
    panel, changes, _ = _panel(tmp_path)
    panel.open = False
    assert _click(panel, panel._exit_rect.center) is False
    assert changes == []
