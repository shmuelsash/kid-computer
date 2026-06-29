"""Low-level Windows keyboard lock.

Installs a WH_KEYBOARD_LL hook that swallows the system shortcuts a toddler can
use to escape or disrupt the session - the Windows key (Start menu, Win+Tab,
Win+D, etc.), Alt+Tab / Ctrl+Alt+Tab, Alt+Esc, Ctrl+Esc, Alt+F4, and the
context-menu key. Ordinary keys pass straight through to the focused full-screen
window so they can drive the on-screen fun.

CRITICAL (this bit us once): every WinAPI function MUST have ``argtypes`` and
``restype`` declared. Without them, ctypes assumes 32-bit ints and silently
truncates 64-bit handles (module handle, hook handle, LRESULT) on 64-bit
Windows - which makes ``SetWindowsHookExW`` fail and the lock never installs.
The prototypes in :func:`_configure_prototypes` are not optional.

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
VK_CONTROL = 0x11
VK_MENU = 0x12  # the Alt key
VK_ESCAPE = 0x1B
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_APPS = 0x5D
VK_F4 = 0x73

_WH_KEYBOARD_LL = 13
_WM_QUIT = 0x0012
_HC_ACTION = 0
_KEY_DOWN_BIT = 0x8000

# 64-bit-correct integer aliases for the WinAPI message types.
_LRESULT = ctypes.c_ssize_t
_LPARAM = ctypes.c_ssize_t
_WPARAM = ctypes.c_size_t


def should_block(vk: int, *, alt_down: bool, ctrl_down: bool) -> bool:
    """Return True if this key event is a system shortcut we want to swallow.

    Pure and side-effect free so it can be unit-tested without installing a hook.
    Blocking the Windows key on its own neutralizes every Win+<key> combo, since
    the combo can never start.
    """
    if vk in (VK_LWIN, VK_RWIN, VK_APPS):
        return True
    if alt_down and vk in (VK_TAB, VK_ESCAPE, VK_F4):
        return True
    # Ctrl+Esc opens Start; Ctrl+Shift+Esc opens Task Manager - both have Ctrl.
    return ctrl_down and vk == VK_ESCAPE


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    )


# Callback signature: LRESULT CALLBACK LowLevelKeyboardProc(int, WPARAM, LPARAM).
# The return type MUST be LRESULT (64-bit), not c_long, or the hook chain breaks.
_HOOKPROC = ctypes.CFUNCTYPE(_LRESULT, ctypes.c_int, _WPARAM, _LPARAM)


def _configure_prototypes() -> None:
    """Declare argtypes/restype for every WinAPI call we make (see module docstring)."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int,
        _HOOKPROC,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p

    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, _WPARAM, _LPARAM]
    user32.CallNextHookEx.restype = _LRESULT

    user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL

    user32.GetMessageW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = ctypes.c_int

    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short

    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, _WPARAM, _LPARAM]
    user32.PostThreadMessageW.restype = wintypes.BOOL

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p

    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD


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
        """Install the hook. Returns True on success, False if unsupported/failed."""
        if sys.platform != "win32":
            logger.warning("Keyboard lock is Windows-only; running unlocked.")
            return False
        if self._thread is not None:
            return self.active
        self._thread = threading.Thread(target=self._run, name="kbd-lock", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        if self.active:
            logger.info("Keyboard lock installed (system shortcuts blocked).")
        else:
            logger.error("Keyboard lock FAILED to install; keys are NOT blocked.")
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
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & _KEY_DOWN_BIT)

    def _callback(self, n_code: int, w_param: int, l_param: int) -> int:
        # Fail OPEN on any error: a bug here must never freeze the keyboard.
        try:
            if n_code == _HC_ACTION:
                info = ctypes.cast(l_param, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                alt_down = self._is_down(VK_MENU)
                ctrl_down = self._is_down(VK_CONTROL)
                if should_block(info.vkCode, alt_down=alt_down, ctrl_down=ctrl_down):
                    return 1  # non-zero swallows the key
        except Exception:  # noqa: BLE001 - never let the hook proc raise
            logger.exception("Keyboard hook callback error; passing key through.")
        return ctypes.windll.user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _run(self) -> None:
        _configure_prototypes()
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        hook = user32.SetWindowsHookExW(
            _WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0
        )
        self._hook = hook or None
        self._ready.set()
        if not hook:
            err = ctypes.get_last_error()
            logger.error("SetWindowsHookExW returned NULL (GetLastError=%s).", err)
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
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
