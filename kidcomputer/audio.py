"""Procedurally generated sound - no audio files to ship or license.

Every sound is synthesized with numpy at startup: a bank of pleasant pentatonic
notes (so random presses always sound musical, never dissonant) plus a few
playful effect sounds for clicks and "wins". :func:`make_tone` is pure and
unit-tested; the :class:`SoundBank` wraps pygame's mixer.
"""

from __future__ import annotations

import logging
import random
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100

# C major pentatonic across two octaves - cheerful and never clashing.
_PENTATONIC_HZ = (
    261.63,
    293.66,
    329.63,
    392.00,
    440.00,
    523.25,
    587.33,
    659.25,
    783.99,
    880.00,
)


def make_tone(
    freq: float,
    duration: float = 0.32,
    volume: float = 0.22,
    *,
    sample_rate: int = SAMPLE_RATE,
    harmonics: tuple[float, ...] = (1.0, 0.35, 0.15),
) -> np.ndarray:
    """Synthesize one note as a stereo int16 array shaped (n_samples, 2).

    Adds a couple of quiet harmonics for a warmer, less buzzy tone and applies a
    short attack / smooth decay envelope so notes don't click on/off. Pure: given
    the same args it always returns the same array.
    """
    n_samples = int(sample_rate * duration)
    t = np.linspace(0.0, duration, n_samples, endpoint=False)

    wave = np.zeros(n_samples, dtype=np.float64)
    for i, amp in enumerate(harmonics, start=1):
        wave += amp * np.sin(2.0 * np.pi * freq * i * t)
    wave /= sum(harmonics)

    envelope = _envelope(n_samples, sample_rate)
    mono = wave * envelope * volume
    samples = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)
    return np.column_stack((samples, samples))


def _envelope(n_samples: int, sample_rate: int) -> np.ndarray:
    """Quick attack, exponential-ish decay; avoids clicks at note edges."""
    env = np.ones(n_samples, dtype=np.float64)
    attack = min(int(0.01 * sample_rate), n_samples)
    if attack > 0:
        env[:attack] = np.linspace(0.0, 1.0, attack)
    decay = np.linspace(1.0, 0.0, n_samples) ** 1.5
    return env * decay


def make_chime(volume: float = 0.34) -> np.ndarray:
    """A short two-note 'win' chime for mouse clicks / fireworks."""
    low = make_tone(_PENTATONIC_HZ[4], duration=0.18, volume=volume)
    high = make_tone(_PENTATONIC_HZ[7], duration=0.30, volume=volume)
    return np.concatenate((low, high))


class SoundBank:
    """Owns the pygame mixer and a pre-rendered set of sounds."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        # pygame Sound objects; typed Any because pygame is imported lazily.
        self._notes: list[Any] = []
        self._chime: Any = None

    def init(self) -> None:
        """Initialize the mixer and render the sound bank. Fails soft."""
        if not self.enabled:
            return
        try:
            import pygame

            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
            # Cap simultaneous voices: many notes summing past int16 clips/distorts.
            # When all are busy, a new note simply doesn't play (no overload).
            pygame.mixer.set_num_channels(8)
            self._notes = [pygame.sndarray.make_sound(make_tone(hz)) for hz in _PENTATONIC_HZ]
            self._chime = pygame.sndarray.make_sound(make_chime())
            logger.info("Audio ready: %d notes + chime.", len(self._notes))
        except Exception as exc:  # noqa: BLE001 - audio is non-essential
            logger.warning("Audio unavailable, continuing silently: %s", exc)
            self.enabled = False

    def play_note(self, index: int | None = None) -> None:
        """Play a note - a specific one by index, or a random one."""
        if not self.enabled or not self._notes:
            return
        note = (
            self._notes[index % len(self._notes)]
            if index is not None
            else random.choice(self._notes)
        )
        note.play()

    def play_chime(self) -> None:
        if self.enabled and self._chime is not None:
            self._chime.play()
