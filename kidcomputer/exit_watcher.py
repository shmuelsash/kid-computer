"""The single secret way out: hold Ctrl+Alt+Q together.

A pure timing state machine with an injectable clock, so it can be unit-tested
without a real wall clock or a window. The UI reads :attr:`progress` to draw a
filling ring, and :attr:`triggered` to know when to quit.
"""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic


class ExitWatcher:
    """Tracks how long the exit combo has been held continuously.

    Call :meth:`update` every frame with the current key states. Progress climbs
    from 0 to 1 while the combo is held and snaps back to 0 the moment any key in
    the combo is released, so a brief accidental brush never builds toward exit.
    """

    def __init__(
        self,
        hold_seconds: float = 2.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._hold_seconds = max(hold_seconds, 0.001)
        self._clock = clock
        self._started_at: float | None = None
        self._progress = 0.0

    @property
    def progress(self) -> float:
        """0.0 to 1.0 - how far through the hold we are."""
        return self._progress

    @property
    def triggered(self) -> bool:
        """True once the combo has been held for the full duration."""
        return self._progress >= 1.0

    def reset(self) -> None:
        self._started_at = None
        self._progress = 0.0

    def update(self, *, ctrl: bool, alt: bool, q: bool) -> float:
        """Advance the state machine; return the new progress (0.0-1.0)."""
        combo_held = ctrl and alt and q
        if not combo_held:
            self.reset()
            return self._progress

        now = self._clock()
        if self._started_at is None:
            self._started_at = now
        elapsed = now - self._started_at
        self._progress = min(1.0, elapsed / self._hold_seconds)
        return self._progress
