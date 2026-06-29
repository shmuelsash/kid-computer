"""The exit watcher is the single escape hatch - its timing must be exact."""

from kidcomputer.exit_watcher import ExitWatcher


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_no_progress_without_full_combo() -> None:
    watcher = ExitWatcher(hold_seconds=2.0, clock=FakeClock())
    assert watcher.update(ctrl=True, alt=True, q=False) == 0.0
    assert watcher.update(ctrl=True, alt=False, q=True) == 0.0
    assert watcher.update(ctrl=False, alt=True, q=True) == 0.0
    assert not watcher.triggered


def test_progress_builds_while_held() -> None:
    clock = FakeClock()
    watcher = ExitWatcher(hold_seconds=2.0, clock=clock)

    watcher.update(ctrl=True, alt=True, q=True)  # start the timer at t=0
    clock.now = 1.0
    assert watcher.update(ctrl=True, alt=True, q=True) == 0.5
    assert not watcher.triggered

    clock.now = 2.0
    assert watcher.update(ctrl=True, alt=True, q=True) == 1.0
    assert watcher.triggered


def test_releasing_resets_progress() -> None:
    clock = FakeClock()
    watcher = ExitWatcher(hold_seconds=2.0, clock=clock)

    watcher.update(ctrl=True, alt=True, q=True)
    clock.now = 1.5
    watcher.update(ctrl=True, alt=True, q=True)
    assert watcher.progress > 0.0

    # Let go for one frame: progress must snap back to zero.
    watcher.update(ctrl=True, alt=True, q=False)
    assert watcher.progress == 0.0

    # Re-grab: the timer starts fresh, not from where it left off.
    clock.now = 2.0
    assert watcher.update(ctrl=True, alt=True, q=True) == 0.0


def test_progress_caps_at_one() -> None:
    clock = FakeClock()
    watcher = ExitWatcher(hold_seconds=1.0, clock=clock)
    watcher.update(ctrl=True, alt=True, q=True)
    clock.now = 10.0
    assert watcher.update(ctrl=True, alt=True, q=True) == 1.0
