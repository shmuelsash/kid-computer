"""The guard must reclaim the foreground whenever our window loses it - that is
what stops a touchpad gesture from stranding the child in another app."""

from kidcomputer.focus_guard import ForegroundGuard, should_reclaim


def test_reclaims_when_another_window_is_foreground() -> None:
    # A switch-apps / show-desktop gesture made some other window foreground.
    assert should_reclaim(foreground_hwnd=999, our_hwnd=42) is True


def test_no_reclaim_when_we_are_foreground() -> None:
    assert should_reclaim(foreground_hwnd=42, our_hwnd=42) is False


def test_reclaims_when_no_foreground_window() -> None:
    # GetForegroundWindow returns NULL (0) when focus is nowhere useful; grab back.
    assert should_reclaim(foreground_hwnd=0, our_hwnd=42) is True
    assert should_reclaim(foreground_hwnd=None, our_hwnd=42) is True


def test_no_reclaim_without_our_handle() -> None:
    # Without our own window handle the guard cannot act and must stay passive.
    assert should_reclaim(foreground_hwnd=999, our_hwnd=None) is False
    assert should_reclaim(foreground_hwnd=999, our_hwnd=0) is False


def test_start_without_handle_is_inactive() -> None:
    # No handle -> the guard declines to run rather than pinning the wrong window.
    guard = ForegroundGuard()
    assert guard.start(None) is False
    assert guard.active is False


def test_stop_is_idempotent() -> None:
    # Exit runs stop() in a finally; calling it when never started must be safe.
    guard = ForegroundGuard()
    guard.stop()
    guard.stop()
    assert guard.active is False
