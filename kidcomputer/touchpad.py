"""Disable precision-touchpad multi-finger gestures while the app runs.

Three/four-finger swipes (Task View, show desktop, switch apps) are produced by
the touchpad driver, not as keyboard events, so the keyboard hook can't catch
them. Windows exposes them as per-user settings under the PrecisionTouchPad
registry key; we set them to "nothing" on start and restore the originals on
exit. This touches only HKCU (the current user's prefs) and is fully reverted.

Best-effort: if the machine has no precision touchpad (key absent) or the write
fails, we log and carry on. Note: on some systems the change applies to new
gestures immediately; on others it may need a sign-out to fully take effect.
"""

from __future__ import annotations

import contextlib
import logging
import sys

logger = logging.getLogger(__name__)

_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad"
# 0 = "Nothing" for each of these gesture settings.
_GESTURE_VALUES = (
    "ThreeFingerSlideEnabled",
    "FourFingerSlideEnabled",
    "ThreeFingerTapEnabled",
    "FourFingerTapEnabled",
)


class TouchpadGestureLock:
    """Disables multi-finger touchpad gestures and restores them on stop."""

    def __init__(self) -> None:
        # name -> (value, type) it had before, or None if it didn't exist.
        self._saved: dict[str, tuple[int, int] | None] = {}
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _KEY_PATH, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
            ) as key:
                for name in _GESTURE_VALUES:
                    self._saved[name] = _read_value(winreg, key, name)
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 0)
            self._active = True
            _broadcast_setting_change()
            logger.info("Touchpad multi-finger gestures disabled.")
            return True
        except OSError as exc:
            logger.warning("Could not disable touchpad gestures: %s", exc)
            return False

    def stop(self) -> None:
        if not self._active:
            return
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _KEY_PATH, 0, winreg.KEY_SET_VALUE
            ) as key:
                for name, saved in self._saved.items():
                    _restore_value(winreg, key, name, saved)
            _broadcast_setting_change()
            logger.info("Touchpad gestures restored.")
        except OSError as exc:
            logger.warning("Could not restore touchpad gestures: %s", exc)
        finally:
            self._active = False


def _broadcast_setting_change() -> None:
    """Nudge Windows to re-read settings so the change applies without a sign-out.

    Best-effort: WM_SETTINGCHANGE to all top-level windows. Some setups still need
    a sign-out for touchpad gesture changes to fully take effect.
    """
    import ctypes

    try:
        hwnd_broadcast = 0xFFFF
        wm_settingchange = 0x001A
        smto_abortifhung = 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            hwnd_broadcast,
            wm_settingchange,
            0,
            "PrecisionTouchPad",
            smto_abortifhung,
            200,
            ctypes.byref(result),
        )
    except Exception as exc:  # noqa: BLE001 - purely a hint to the OS
        logger.debug("WM_SETTINGCHANGE broadcast failed: %s", exc)


def _read_value(winreg, key, name: str) -> tuple[int, int] | None:  # type: ignore[no-untyped-def]
    try:
        value, value_type = winreg.QueryValueEx(key, name)
        return (value, value_type)
    except FileNotFoundError:
        return None


def _restore_value(winreg, key, name: str, saved: tuple[int, int] | None) -> None:  # type: ignore[no-untyped-def]
    if saved is None:
        with contextlib.suppress(FileNotFoundError):
            winreg.DeleteValue(key, name)
        return
    winreg.SetValueEx(key, name, 0, saved[1], saved[0])
