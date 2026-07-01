"""Kiosk foreground guard: keep our full-screen window in front no matter what.

Touchpad multi-finger gestures - three-finger switch-apps, four-finger show-
desktop, the three-finger swipe-up to Task View - are produced by the touchpad
driver, not as keyboard events, so the keyboard hook (:mod:`keyboard_lock`) can't
see them. Disabling them in the registry (:mod:`touchpad`) is the durable fix,
but on most machines that only takes effect after a sign-out - useless in the
middle of a toddler's session. This guard closes that gap with no driver or
sign-out dependency: a background thread watches the foreground window and, the
instant something else steals it (or our window gets minimised by a show-desktop
gesture), snaps our window back on top and reclaims focus. The gesture still
animates, but the child lands right back on the fun within one poll (~100 ms).

Reliability note: Windows normally forbids a *background* thread from stealing
the foreground (``SetForegroundWindow`` returns success but does nothing). The
documented work-around is to briefly attach our input queue to the current
foreground thread's, which lifts the restriction; we do that and detach again.

Everything here FAILS OPEN: any error is logged and swallowed. A bug in the
guard must never freeze the machine, steal focus from the Ctrl+Alt+Del secure
screen (it can't - that lives on a separate desktop), or block the exit combo.
Like every WinAPI call in this project, each ctypes function declares argtypes
and restype so 64-bit window handles aren't truncated to 32 bits on Win64.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading

logger = logging.getLogger(__name__)

_POLL_SECONDS = 0.1

# SetWindowPos / ShowWindow constants (winuser.h).
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_SHOWWINDOW = 0x0040
_SW_RESTORE = 9


def should_reclaim(foreground_hwnd: int | None, our_hwnd: int | None) -> bool:
    """True if our window is not the foreground window and should grab it back.

    Pure and side-effect free so the decision can be unit-tested without touching
    the real desktop. A missing own-handle means the guard can't act; a foreground
    of 0/None (e.g. the secure desktop) still counts as "not us", and the reclaim
    attempt there simply no-ops.
    """
    if not our_hwnd:
        return False
    return foreground_hwnd != our_hwnd


def _configure_prototypes() -> None:
    """Declare argtypes/restype for every WinAPI call (see module docstring)."""
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = ctypes.c_void_p

    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.IsIconic.restype = wintypes.BOOL

    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL

    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
    user32.BringWindowToTop.restype = wintypes.BOOL

    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL

    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def _reclaim_foreground(hwnd: int, foreground_hwnd: int | None) -> None:
    """Restore, re-pin topmost, and take input focus back for ``hwnd``.

    Uses the AttachThreadInput work-around so the steal actually succeeds from a
    background thread. Best-effort throughout.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    if user32.IsIconic(hwnd):  # a show-desktop / minimise gesture hid us
        user32.ShowWindow(hwnd, _SW_RESTORE)
    # Re-pin topmost without moving or resizing the spanning window.
    user32.SetWindowPos(
        hwnd, _HWND_TOPMOST, 0, 0, 0, 0, _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW
    )

    our_thread = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None) if foreground_hwnd else 0
    attached = bool(fg_thread) and fg_thread != our_thread
    if attached:
        attached = bool(user32.AttachThreadInput(our_thread, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(our_thread, fg_thread, False)


class ForegroundGuard:
    """Keeps a window in the foreground while running, on a daemon watchdog thread."""

    def __init__(self, poll_seconds: float = _POLL_SECONDS) -> None:
        self._poll = poll_seconds
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._hwnd: int | None = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self, hwnd: int | None) -> bool:
        """Begin guarding ``hwnd``. Returns True on success, False if unsupported."""
        if sys.platform != "win32":
            logger.warning("Foreground guard is Windows-only; window not pinned.")
            return False
        if self._thread is not None:
            return self._active
        if not hwnd:
            logger.warning("Foreground guard: no window handle; window not pinned.")
            return False
        self._hwnd = hwnd
        _configure_prototypes()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="focus-guard", daemon=True)
        self._thread.start()
        self._active = True
        logger.info("Foreground guard active (window kept on top).")
        return True

    def stop(self) -> None:
        """Stop guarding. Safe to call more than once; must run before teardown so
        we aren't fighting the OS for focus while the app exits."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._active = False

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        hwnd = self._hwnd  # set in start(); never None once the thread is running
        if not hwnd:
            return
        # Event.wait doubles as the sleep and the stop signal: returns True the
        # moment stop() fires, so we exit promptly instead of after a full poll.
        while not self._stop.wait(self._poll):
            try:
                foreground = user32.GetForegroundWindow()
                if should_reclaim(foreground, hwnd):
                    _reclaim_foreground(hwnd, foreground)
            except Exception:  # noqa: BLE001 - never let the watchdog raise
                logger.exception("Foreground guard error; continuing.")
