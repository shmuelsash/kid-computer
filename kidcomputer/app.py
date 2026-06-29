"""Application entry point and main loop.

Flow: declare DPI awareness -> create the spanning window -> show an animated
update splash (frozen builds only) -> lock the keyboard -> run the scene. The
keyboard lock is released in a ``finally`` block no matter how the loop ends - a
crash must never leave the real keyboard captured.
"""

from __future__ import annotations

import logging
import platform
import sys
import threading

import pygame

from kidcomputer import buildinfo
from kidcomputer.audio import SoundBank
from kidcomputer.config import GITHUB_REPO, Settings, SettingsStore
from kidcomputer.display import create_surface, make_dpi_aware
from kidcomputer.exit_watcher import ExitWatcher
from kidcomputer.keyboard_lock import KeyboardLock
from kidcomputer.logging_setup import setup_logging
from kidcomputer.scene import Scene
from kidcomputer.theme import Theme, get_theme
from kidcomputer.touchpad import TouchpadGestureLock
from kidcomputer.updater import UpdateStatus, is_frozen, run_update

logger = logging.getLogger(__name__)

_FPS = 60


def _read_exit_keys() -> tuple[bool, bool, bool]:
    mods = pygame.key.get_mods()
    pressed = pygame.key.get_pressed()
    ctrl = bool(mods & pygame.KMOD_CTRL)
    alt = bool(mods & pygame.KMOD_ALT)
    return ctrl, alt, pressed[pygame.K_q]


def _run_loop(screen: pygame.Surface, scene: Scene, settings: Settings, state: dict) -> None:
    clock = pygame.time.Clock()
    exit_watcher = ExitWatcher(hold_seconds=settings.exit_hold_seconds)
    while state["running"]:
        dt = clock.tick(_FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                state["running"] = False
            scene.handle_event(event)

        ctrl, alt, q = _read_exit_keys()
        exit_watcher.update(ctrl=ctrl, alt=alt, q=q)
        if exit_watcher.triggered:
            logger.info("Exit combo held; shutting down.")
            state["running"] = False

        scene.update(dt)
        scene.draw(screen, exit_watcher.progress)
        pygame.display.flip()


# --- update splash ------------------------------------------------------


def _status_text(status: UpdateStatus) -> str:
    return {"uptodate": "up to date", "error": "update check failed"}.get(status.phase, "")


def _run_update_splash(
    screen: pygame.Surface, ui_rect: pygame.Rect, theme: Theme
) -> tuple[bool, str]:
    """Animate a splash while the update worker runs. Returns (relaunching, status)."""
    status = UpdateStatus()
    worker = threading.Thread(
        target=run_update,
        args=(GITHUB_REPO, buildinfo.VERSION, status),
        kwargs={"is_frozen": True},
        daemon=True,
    )
    worker.start()
    clock = pygame.time.Clock()
    elapsed = 0.0
    while not status.done:
        elapsed += clock.tick(_FPS) / 1000.0
        pygame.event.pump()
        _draw_splash(screen, ui_rect, theme, status, elapsed)
        pygame.display.flip()
    worker.join(timeout=2.0)
    return status.relaunch, _status_text(status)


def _splash_message(status: UpdateStatus) -> str:
    if status.phase == "downloading":
        return f"Downloading update {status.target}  {int(status.progress * 100)}%"
    return "Checking for updates..."


def _draw_splash(
    screen: pygame.Surface, ui_rect: pygame.Rect, theme: Theme, status: UpdateStatus, elapsed: float
) -> None:
    screen.fill(theme.bg_mid)
    cx, cy = ui_rect.center
    title_font = pygame.font.SysFont(
        "Arial Black,Arial", max(28, min(ui_rect.size) // 16), bold=True
    )
    body_font = pygame.font.SysFont("Segoe UI,Arial", max(16, min(ui_rect.size) // 48))
    title = title_font.render("Kid Computer", True, theme.text)
    screen.blit(title, title.get_rect(center=(cx, cy - 80)))

    # Pulsing accent dots.
    import math

    for i in range(3):
        phase = math.sin(elapsed * 4 - i * 0.6) * 0.5 + 0.5
        r = int(6 + 6 * phase)
        pygame.draw.circle(screen, theme.accent, (cx - 26 + i * 26, cy), r)

    msg = body_font.render(_splash_message(status), True, theme.text_dim)
    screen.blit(msg, msg.get_rect(center=(cx, cy + 60)))
    if status.phase == "downloading":
        _draw_progress_bar(
            screen, (cx, cy + 100), min(ui_rect.width // 2, 480), status.progress, theme
        )


def _draw_progress_bar(
    screen: pygame.Surface, center: tuple[int, int], width: int, progress: float, theme: Theme
) -> None:
    bar = pygame.Rect(0, 0, width, 8)
    bar.center = center
    pygame.draw.rect(screen, theme.text_dim, bar, border_radius=4)
    filled = bar.copy()
    filled.width = int(width * progress)
    pygame.draw.rect(screen, theme.accent, filled, border_radius=4)


# --- main ---------------------------------------------------------------


def _log_startup(store: SettingsStore) -> None:
    logger.info(
        "Kid Computer starting | %s | python %s on %s | log_level=%s theme=%s mode=%s",
        buildinfo.build_summary(),
        platform.python_version(),
        platform.platform(),
        store.log_level,
        store.theme,
        store.age_mode,
    )


def main() -> int:
    settings = Settings.from_env()
    store = SettingsStore()
    setup_logging(store.log_level)
    _log_startup(store)

    make_dpi_aware()  # before any window, or Windows reports a scaled resolution
    pygame.init()
    pygame.display.set_caption("Kid Computer")
    screen, ui_rect = create_surface(settings.fullscreen)
    theme = get_theme(store.theme)

    update_status = ""
    if settings.auto_update and is_frozen():
        relaunching, update_status = _run_update_splash(screen, ui_rect, theme)
        if relaunching:
            pygame.quit()
            return 0  # exit so the swap can complete

    sounds = SoundBank(enabled=store.sound)
    sounds.init()
    state = {"running": True}
    lock = KeyboardLock()
    touchpad = TouchpadGestureLock()
    try:
        pygame.event.set_grab(True)
        lock.start()
        touchpad.start()
        scene = Scene(
            screen.get_size(), ui_rect, sounds, store, on_exit=lambda: state.update(running=False)
        )
        scene.set_update_status(update_status)
        _run_loop(screen, scene, settings, state)
    finally:
        lock.stop()
        touchpad.stop()
        pygame.event.set_grab(False)
        pygame.quit()
        logger.info("Kid Computer stopped. Input restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
