"""Version comparison drives auto-update; a wrong answer ships a downgrade or
skips a real update."""

from pathlib import Path

import pytest

from kidcomputer.updater import (
    _ASSET_NAME,
    _child_env,
    _find_asset_url,
    _is_valid_exe,
    _old_path,
    _parse_version,
    check_and_update,
    cleanup_leftovers,
    is_newer,
)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.0.0", (1, 0, 0)),
        ("1.2.3", (1, 2, 3)),
        ("v2.10.5", (2, 10, 5)),
        ("1.0.0+dev", (1, 0, 0)),
        ("v1.0", (1, 0)),
    ],
)
def test_parse_version(tag: str, expected: tuple[int, ...]) -> None:
    assert _parse_version(tag) == expected


@pytest.mark.parametrize(
    ("latest", "current", "expected"),
    [
        ("v1.0.1", "1.0.0", True),
        ("v1.1.0", "1.0.9", True),
        ("v2.0.0", "1.9.9", True),
        ("v1.0.0", "1.0.0", False),
        ("v1.0.0", "1.0.1", False),
        ("v1.0.5", "1.0.42", False),
    ],
)
def test_is_newer(latest: str, current: str, expected: bool) -> None:
    assert is_newer(latest, current) is expected


def test_is_newer_handles_garbage() -> None:
    assert is_newer("not-a-version", "1.0.0") is False


def test_find_asset_url_matches_exe() -> None:
    release = {
        "assets": [
            {"name": "notes.txt", "browser_download_url": "http://x/notes.txt"},
            {"name": "KidComputer.exe", "browser_download_url": "http://x/KidComputer.exe"},
        ]
    }
    assert _find_asset_url(release) == "http://x/KidComputer.exe"


def test_find_asset_url_missing() -> None:
    assert _find_asset_url({"assets": []}) is None


def test_no_update_when_not_frozen() -> None:
    # In a dev run there is no single exe to swap, so it must never act.
    assert check_and_update("owner/repo", "1.0.0", is_frozen=False) is False


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_valid_exe_accepts_real_pe(tmp_path: Path) -> None:
    # 'MZ' magic + over the 1MB minimum + exact expected size.
    blob = b"MZ" + b"\x00" * (2_000_000 - 2)
    path = _write(tmp_path / "ok.exe", blob)
    assert _is_valid_exe(path, expected_size=len(blob)) is True


def test_valid_exe_rejects_truncated(tmp_path: Path) -> None:
    # The exact failure that bricked the install: a short/partial download.
    path = _write(tmp_path / "short.exe", b"MZ" + b"\x00" * 1000)
    assert _is_valid_exe(path) is False


def test_valid_exe_rejects_wrong_magic(tmp_path: Path) -> None:
    path = _write(tmp_path / "html.exe", b"<!DOCTYPE html>" + b"\x00" * 2_000_000)
    assert _is_valid_exe(path) is False


def test_valid_exe_rejects_size_mismatch(tmp_path: Path) -> None:
    blob = b"MZ" + b"\x00" * 2_000_000
    path = _write(tmp_path / "ok.exe", blob)
    assert _is_valid_exe(path, expected_size=len(blob) + 5) is False


def test_cleanup_removes_leftovers(tmp_path: Path) -> None:
    old = _write(tmp_path / f"{_ASSET_NAME}.old", b"x")
    new = _write(tmp_path / f"{_ASSET_NAME}.new", b"x")
    keep = _write(tmp_path / f"{_ASSET_NAME}", b"x")
    cleanup_leftovers(tmp_path)
    assert not old.exists()
    assert not new.exists()
    assert keep.exists()  # the live exe is never touched


def test_old_path_naming(tmp_path: Path) -> None:
    assert _old_path(tmp_path / "KidComputer.exe").name == "KidComputer.exe.old"


def test_child_env_strips_pyinstaller_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    # The relaunched exe must NOT inherit these, or it reuses the parent's temp
    # extraction and bricks when the parent deletes it ("Failed to load Python DLL").
    monkeypatch.setenv("_MEIPASS2", "C:/tmp/_MEI123")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "x")
    monkeypatch.setenv("KIDCOMPUTER_KEEPME", "yes")
    env = _child_env()
    assert "_MEIPASS2" not in env
    assert "_PYI_ARCHIVE_FILE" not in env
    assert env.get("KIDCOMPUTER_KEEPME") == "yes"
