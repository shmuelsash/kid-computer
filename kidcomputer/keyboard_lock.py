"""Low-level Windows keyboard lock.

Installs a WH_KEYBOARD_LL hook that swallows the system shortcuts a toddler can
use to escape or disrupt the session - Windows key, Alt+Tab, Alt+F4, Alt+Esc,
Ctrl+Esc, and the context-menu key. Ordinary keys pass straight through to the
focused full-screen window so they can drive the on-screen fun.

What CANNOT be blocked from a user-mode process, by Windows design:
  * Ctrl+Alt+Del (the Secure Attention Sequence) - a hardware-level safety key.
  * Win+L (lock workstation).
Both are OS safety features; neither can break anything, and Esc backs out of
the Ctrl+Alt+Del screen. Blocking them would require enterprise kiosk / Group
Policy lockdown, which is out of scope here.

The decision of *what* to block lives in :func:`should_block`, a pure function
that is unit-tested. Everything else is the ctypes plumbing to run the hook.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from ctypes import wintypes

logger = logging.getLogger(__name__)

# Virtual-key codes (winuser.h).
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_APPS = 0x5D
VK_F4 = 0x73

_WH_KEYBOARD_LL = 13
_WM_QUIT = 0x0012
_HC_ACTION = 0


def should_block(vk: int, *, alt_down: bool, ctrl_down: bool) -> bool:
    """Return True if this key event is a system shortcut we want to swallow.

    Pure and side-effect free so it can be unit-tested without installing a hook.
    """
    if vk in (VK_LWIN, VK_RWIN, VK_APPS):
        return True
    if alt_down and vk in (VK_TAB, VK_ESCAPE, VK_F4):
        return True
    return ctrl_down and vk == VK_ESCAPE


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    )


# Callback signature: LRESULT CALLBACK LowLevelKeyboardProc(int, WPARAM, LPARAM)
_HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KeyboardLock:
    """Installs and removes the low-level keyboard hook on its own thread.

    A low-level hook callback runs on the thread that installed it, and that
    thread must pump a message loop - so the hook lives in a dedicated thread
    with its own ``GetMessage`` loop.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook: int | None = None
        self._proc = _HOOKPROC(self._callback)  # keep a strong ref (no GC)
        self._ready = threading.Event()

    @property
    def active(self) -> bool:
        return self._hook is not None

    def start(self) -> bool:
        """Install the hook. Returns True on success, False if unsupported."""
        if sys.platform != "win32":
            logger.warning("Keyboard lock is Windows-only; running unlocked.")
            return False
        if self._thread is not None:
            return self.active
        self._thread = threading.Thread(target=self._run, name="kbd-lock", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        if not self.active:
            logger.error("Keyboard lock failed to install.")
        return self.active

    def stop(self) -> None:
        """Remove the hook and stop its thread. Safe to call more than once."""
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._thread_id = None

    # --- internals -------------------------------------------------------

    def _is_down(self, vk: int) -> bool:
        # High-order bit set => key currently down.
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

    def _callback(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code == _HC_ACTION:
            info = ctypes.cast(l_param, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
            alt_down = self._is_down(0x12)  # VK_MENU
            ctrl_down = self._is_down(0x11)  # VK_CONTROL
            if should_block(info.vkCode, alt_down=alt_down, ctrl_down=ctrl_down):
                return 1  # non-zero swallows the key
        return ctypes.windll.user32.CallNextHookEx(0, n_code, w_param, l_param)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        hook = user32.SetWindowsHookExW(
            _WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0
        )
        self._hook = hook or None
        self._ready.set()
        if not hook:
            return
        try:
            self._pump_messages(user32)
        finally:
            user32.UnhookWindowsHookEx(hook)
            self._hook = None
            logger.info("Keyboard lock removed.")

    def _pump_messages(self, user32: ctypes.WinDLL) -> None:
        msg = wintypes.MSG()
        # GetMessage returns 0 on WM_QUIT, -1 on error.
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
