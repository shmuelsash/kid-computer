"""Application entry point and main loop.

Wires together the updater, the keyboard lock, the sound bank, and the scene.
The keyboard lock is released in a ``finally`` block no matter how the loop ends
- a crash must never leave the real keyboard captured.
"""

from __future__ import annotations

import logging
import platform
import sys

import pygame

from kidcomputer import buildinfo
from kidcomputer.audio import SoundBank
from kidcomputer.config import GITHUB_REPO, Settings
from kidcomputer.exit_watcher import ExitWatcher
from kidcomputer.keyboard_lock import KeyboardLock
from kidcomputer.logging_setup import setup_logging
from kidcomputer.scene import Scene
from kidcomputer.updater import check_and_update, is_frozen

logger = logging.getLogger(__name__)

_WINDOWED_SIZE = (1280, 800)
_FPS = 60


def _create_screen(fullscreen: bool) -> pygame.Surface:
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode(_WINDOWED_SIZE)


def _read_exit_keys() -> tuple[bool, bool, bool]:
    mods = pygame.key.get_mods()
    pressed = pygame.key.get_pressed()
    ctrl = bool(mods & pygame.KMOD_CTRL)
    alt = bool(mods & pygame.KMOD_ALT)
    return ctrl, alt, pressed[pygame.K_q]


def _run_loop(screen: pygame.Surface, scene: Scene, settings: Settings) -> None:
    clock = pygame.time.Clock()
    exit_watcher = ExitWatcher(hold_seconds=settings.exit_hold_seconds)
    running = True
    while running:
        dt = clock.tick(_FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Window-manager close is normally blocked by the keyboard lock;
                # honoring it here is a harmless safety valve in windowed dev.
                running = False
            scene.handle_event(event)

        ctrl, alt, q = _read_exit_keys()
        exit_watcher.update(ctrl=ctrl, alt=alt, q=q)
        if exit_watcher.triggered:
            logger.info("Exit combo held; shutting down.")
            running = False

        scene.update(dt)
        scene.draw(screen, exit_watcher.progress)
        pygame.display.flip()


def _log_startup(settings: Settings) -> None:
    logger.info(
        "Kid Computer starting | %s | python %s on %s | log_level=%s fullscreen=%s sound=%s",
        buildinfo.build_summary(),
        platform.python_version(),
        platform.platform(),
        settings.log_level,
        settings.fullscreen,
        settings.sound_enabled,
    )


def main() -> int:
    settings = Settings.from_env()
    setup_logging(settings.log_level)
    _log_startup(settings)

    if settings.auto_update and check_and_update(
        GITHUB_REPO, buildinfo.VERSION, is_frozen=is_frozen()
    ):
        return 0  # an update was launched; exit so the swap can complete

    pygame.init()
    pygame.display.set_caption("Kid Computer")
    sounds = SoundBank(enabled=settings.sound_enabled)
    sounds.init()

    lock = KeyboardLock()
    try:
        screen = _create_screen(settings.fullscreen)
        pygame.event.set_grab(True)
        lock.start()
        scene = Scene(screen.get_size(), sounds)
        _run_loop(screen, scene, settings)
    finally:
        lock.stop()
        pygame.event.set_grab(False)
        pygame.quit()
        logger.info("Kid Computer stopped. Keyboard released.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
