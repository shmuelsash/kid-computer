"""Persisted settings must round-trip and reject bad values."""

from pathlib import Path

import pytest

from kidcomputer.config import SettingsStore


def _store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(path=tmp_path / "settings.json")


def test_roundtrip_persists_to_disk(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set("theme", "candy")
    store.set("age_mode", "early")
    reloaded = _store(tmp_path)
    assert reloaded.theme == "candy"
    assert reloaded.age_mode == "early"


def test_intensity_is_clamped(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set("intensity", 5.0)
    assert store.intensity == 1.0
    store.set("intensity", -2.0)
    assert store.intensity == 0.0


def test_invalid_choice_falls_back(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set("theme", "bogus")
    assert store.theme == "aurora"
    store.set("log_level", "LOUD")
    assert store.log_level == "INFO"


def test_unknown_key_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(KeyError):
        store.set("not_a_setting", 1)


def test_corrupt_file_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")
    store = SettingsStore(path=path)
    assert store.theme == "aurora"  # defaults, no crash
