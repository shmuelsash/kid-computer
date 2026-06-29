"""Display setup: high-resolution, DPI-aware, spanning every monitor.

Two Windows-specific problems are solved here:

1. **Blurry / low resolution.** A process that isn't DPI-aware is lied to by
   Windows about the screen size (it reports a scaled-down resolution and then
   upscales the result), so everything looks soft and small. We declare
   per-monitor DPI awareness *before* creating the window so we render at native
   pixels.

2. **Only one screen covered.** ``pygame.FULLSCREEN`` covers the primary monitor
   only. We instead create a borderless, top-most window spanning the entire
   virtual desktop (all monitors combined), so the lockout covers every screen.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys

import pygame

logger = logging.getLogger(__name__)

_WINDOWED_SIZE = (1280, 800)

# GetSystemMetrics indices.
_SM_CXSCREEN = 0  # primary monitor width
_SM_CYSCREEN = 1  # primary monitor height
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79

# SetWindowPos: place the window above all non-topmost windows.
_HWND_TOPMOST = -1
_SWP_SHOWWINDOW = 0x0040


def make_dpi_aware() -> None:
    """Tell Windows we render at native resolution. Call before creating a window."""
    if sys.platform != "win32":
        return
    # Try the best API first, fall back for older Windows versions.
    if _try_set_dpi_context():
        return
    if _try_shcore_awareness():
        return
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as exc:  # noqa: BLE001 - DPI is best-effort
        logger.warning("Could not set DPI awareness: %s", exc)


def _try_set_dpi_context() -> bool:
    # PER_MONITOR_AWARE_V2 = -4 (Windows 10 1703+); correct for multi-monitor.
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return True
    except Exception:  # noqa: BLE001 - older Windows lacks this entry point
        return False


def _try_shcore_awareness() -> bool:
    # PROCESS_PER_MONITOR_DPI_AWARE = 2 (Windows 8.1+).
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except Exception:  # noqa: BLE001
        return False


def _virtual_desktop_rect() -> tuple[int, int, int, int]:
    """(x, y, width, height) of the bounding box around all monitors."""
    metrics = ctypes.windll.user32.GetSystemMetrics
    return (
        metrics(_SM_XVIRTUALSCREEN),
        metrics(_SM_YVIRTUALSCREEN),
        metrics(_SM_CXVIRTUALSCREEN),
        metrics(_SM_CYVIRTUALSCREEN),
    )


def _force_window_geometry(x: int, y: int, width: int, height: int) -> None:
    """Pin the SDL window to the exact virtual-desktop rect and make it topmost."""
    try:
        hwnd = pygame.display.get_wm_info().get("window")
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        user32.SetWindowPos.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        user32.SetWindowPos(
            ctypes.c_void_p(hwnd),
            ctypes.c_void_p(_HWND_TOPMOST),
            x,
            y,
            width,
            height,
            _SWP_SHOWWINDOW,
        )
    except Exception as exc:  # noqa: BLE001 - positioning is best-effort
        logger.warning("Could not force window geometry: %s", exc)


def create_surface(fullscreen: bool) -> tuple[pygame.Surface, pygame.Rect]:
    """Create the drawing surface and the primary-monitor rect (in surface coords).

    The ui_rect is where chrome (settings card, exit hint/ring) is placed so it
    lands on one screen instead of across a dual-monitor seam.
    """
    if not fullscreen:
        surface = pygame.display.set_mode(_WINDOWED_SIZE)
        return surface, surface.get_rect()

    if sys.platform == "win32":
        x, y, width, height = _virtual_desktop_rect()
        # SDL reads this env var at window-creation time.
        os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"
        surface = pygame.display.set_mode((width, height), pygame.NOFRAME)
        _force_window_geometry(x, y, width, height)
        logger.info("Display: %dx%d borderless spanning all monitors.", width, height)
        # Primary monitor is at Windows (0,0); in surface coords that is (-x,-y).
        metrics = ctypes.windll.user32.GetSystemMetrics
        ui_rect = pygame.Rect(-x, -y, metrics(_SM_CXSCREEN), metrics(_SM_CYSCREEN))
        return surface, ui_rect

    # Non-Windows fallback (dev only): primary-monitor fullscreen.
    surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    logger.info("Display: %dx%d fullscreen.", *surface.get_size())
    return surface, surface.get_rect()
