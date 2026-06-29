"""Sound is procedurally generated; verify the array shape/dtype contract that
pygame's sndarray depends on."""

import numpy as np

from kidcomputer.audio import SAMPLE_RATE, make_chime, make_tone


def test_make_tone_shape_and_dtype() -> None:
    duration = 0.2
    tone = make_tone(440.0, duration=duration)
    assert tone.dtype == np.int16
    assert tone.ndim == 2
    assert tone.shape[1] == 2  # stereo
    assert tone.shape[0] == int(SAMPLE_RATE * duration)


def test_make_tone_within_int16_range() -> None:
    tone = make_tone(440.0, volume=1.0)
    assert tone.max() <= 32767
    assert tone.min() >= -32768


def test_make_tone_is_deterministic() -> None:
    assert np.array_equal(make_tone(523.25), make_tone(523.25))


def test_make_chime_is_two_notes_long() -> None:
    chime = make_chime()
    assert chime.dtype == np.int16
    assert chime.shape[1] == 2
    # Concatenation of a 0.18s and a 0.30s note.
    assert chime.shape[0] == int(SAMPLE_RATE * 0.18) + int(SAMPLE_RATE * 0.30)
