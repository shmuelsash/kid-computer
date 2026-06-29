"""Self-update from GitHub Releases.

On launch (only when running as a built exe) the app asks the public GitHub API
for the latest release, compares versions, and if a newer build exists downloads
the new exe and relaunches into it via a tiny batch script. The repo is public,
so no token is embedded in the distributed exe.

Update failures are non-fatal: any network/HTTP/parse problem is logged at
WARNING and the current build keeps running. We never block a child's session
because GitHub is unreachable.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_API_TIMEOUT = 6.0
_DOWNLOAD_TIMEOUT = 120.0
_ASSET_NAME = "KidComputer.exe"
_CHUNK = 64 * 1024


@dataclass
class UpdateStatus:
    """Shared state between the update worker thread and the splash screen."""

    phase: str = "checking"  # checking | downloading | uptodate | relaunching | error | disabled
    progress: float = 0.0  # 0..1 during download
    target: str = ""  # tag being downloaded
    done: bool = False
    relaunch: bool = False  # True once the new exe has been launched


def _parse_version(tag: str) -> tuple[int, ...]:
    """Turn 'v1.0.42' or '1.0.42' into (1, 0, 42); junk parts become 0."""
    cleaned = tag.lstrip("vV").split("+")[0].split("-")[0]
    parts = cleaned.split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


def is_newer(latest_tag: str, current_version: str) -> bool:
    """True if ``latest_tag`` is a strictly higher version than the running one."""
    try:
        return _parse_version(latest_tag) > _parse_version(current_version)
    except (ValueError, AttributeError):
        return False


def fetch_latest_release(repo: str) -> dict | None:
    """Return the latest release JSON, or None on any failure."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        logger.warning("Update check failed (continuing on current build): %s", exc)
        return None


def _find_asset(release: dict) -> dict | None:
    for asset in release.get("assets", []):
        if asset.get("name") == _ASSET_NAME:
            return asset
    return None


def _find_asset_url(release: dict) -> str | None:
    asset = _find_asset(release)
    return asset.get("browser_download_url") if asset else None


def _download(url: str, dest: Path, on_progress: Callable[[float], None] | None = None) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT) as resp:  # noqa: S310
            total = int(resp.headers.get("Content-Length") or 0)
            read = 0
            with open(dest, "wb") as out:
                while chunk := resp.read(_CHUNK):
                    out.write(chunk)
                    read += len(chunk)
                    if on_progress and total:
                        on_progress(min(1.0, read / total))
        if total and read != total:
            logger.warning("Update download incomplete: %d of %d bytes.", read, total)
            return False
        if on_progress:
            on_progress(1.0)
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("Update download failed: %s", exc)
        return False


def _is_valid_exe(path: Path, expected_size: int = 0) -> bool:
    """Guard against swapping in a truncated/corrupt exe (the bug that bricked an
    install): require the PE 'MZ' magic, a sane size, and an exact size match to
    the published asset when we know it."""
    try:
        size = path.stat().st_size
        if expected_size and size != expected_size:
            logger.warning("Update size mismatch: %d != %d expected.", size, expected_size)
            return False
        if size < 1_000_000:
            return False
        with open(path, "rb") as handle:
            return handle.read(2) == b"MZ"
    except OSError:
        return False


def _old_path(current_exe: Path) -> Path:
    return current_exe.with_name(current_exe.name + ".old")


def cleanup_leftovers(exe_dir: Path) -> None:
    """Delete stale update files (.old from a prior swap, abandoned .new)."""
    for leftover in (exe_dir / f"{_ASSET_NAME}.old", exe_dir / f"{_ASSET_NAME}.new"):
        # The .old may briefly linger if AV holds it; ignore and retry next launch.
        with contextlib.suppress(OSError):
            leftover.unlink(missing_ok=True)


def _relaunch_with(new_exe: Path, current_exe: Path) -> bool:
    """Swap in the verified new exe and launch it. Returns True on success.

    Windows lets you *rename* a running exe (you just can't overwrite it), so we
    move the running file aside to ``.old``, atomically rename the verified new
    file into its place, then launch it. No batch script, no fixed sleep, no
    file-lock race - the class of bug that produced a truncated "Failed to load
    Python DLL" exe. The ``.old`` is cleaned up on the next launch.
    """
    old = _old_path(current_exe)
    try:
        old.unlink(missing_ok=True)
        os.replace(current_exe, old)  # rename the running exe out of the way
        os.replace(new_exe, current_exe)  # drop the verified new one in place
    except OSError as exc:
        logger.error("Update swap failed (%s); rolling back.", exc)
        _rollback(old, current_exe)
        return False
    try:
        subprocess.Popen(  # noqa: S603
            [str(current_exe)],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            close_fds=True,
            cwd=str(current_exe.parent),
            env=_child_env(),
        )
    except OSError as exc:
        logger.error("Could not launch updated exe: %s", exc)
        return False
    return True


def _child_env() -> dict[str, str]:
    """Environment for the relaunched exe with PyInstaller's onefile vars removed.

    THE fix for the update-bricking bug: a child spawned from a onefile exe
    inherits ``_MEIPASS2`` / ``_PYI_*``, which tell it to REUSE the parent's temp
    extraction. When the parent then exits it deletes that folder, and the child's
    python DLL/base_library.zip vanish mid-run ("Failed to load Python DLL").
    Stripping these vars forces the child to extract its own fresh copy.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not (key.startswith("_MEIPASS") or key.startswith("_PYI"))
    }


def _rollback(old: Path, current_exe: Path) -> None:
    if old.exists() and not current_exe.exists():
        try:
            os.replace(old, current_exe)
        except OSError:
            logger.error("Rollback failed; current exe may be at %s", old)


def check_and_update(repo: str, current_version: str, *, is_frozen: bool) -> bool:
    """Check for and apply an update. Returns True if an update was launched
    (caller should exit so the swap can happen).

    No-ops in a dev (non-frozen) run - there's no single exe to replace.
    """
    if not is_frozen:
        logger.info("Dev run: skipping self-update.")
        return False

    current_exe = Path(sys.executable)
    cleanup_leftovers(current_exe.parent)
    release = fetch_latest_release(repo)
    if release is None:
        return False

    latest_tag = release.get("tag_name", "")
    if not is_newer(latest_tag, current_version):
        logger.info("Already up to date (running v%s).", current_version)
        return False

    asset = _find_asset(release)
    if asset is None:
        logger.warning("Release %s has no %s asset.", latest_tag, _ASSET_NAME)
        return False

    logger.info("Updating from v%s to %s ...", current_version, latest_tag)
    download = current_exe.parent / f"{_ASSET_NAME}.new"
    if not _download(asset.get("browser_download_url", ""), download):
        return False
    if not _is_valid_exe(download, int(asset.get("size", 0))):
        logger.warning("Update verification failed; keeping current build.")
        download.unlink(missing_ok=True)
        return False

    if not _relaunch_with(download, current_exe):
        return False
    logger.info("Update downloaded; relaunching into %s.", latest_tag)
    return True


def run_update(repo: str, current_version: str, status: UpdateStatus, *, is_frozen: bool) -> None:
    """Worker (run in a thread): drive the update and report progress via status.

    Mutates ``status`` so the splash screen can animate. Fails open - on any
    problem it sets an error/uptodate phase and returns; the app keeps running.
    """
    if not is_frozen:
        status.phase = "disabled"
        status.done = True
        return
    cleanup_leftovers(Path(sys.executable).parent)
    release = fetch_latest_release(repo)
    if release is None:
        _finish(status, "error")
        return
    tag = release.get("tag_name", "")
    if not is_newer(tag, current_version):
        _finish(status, "uptodate")
        return
    asset = _find_asset(release)
    if asset is None:
        logger.warning("Release %s has no %s asset.", tag, _ASSET_NAME)
        _finish(status, "error")
        return
    _download_and_relaunch(asset, tag, current_version, status)


def _download_and_relaunch(
    asset: dict, tag: str, current_version: str, status: UpdateStatus
) -> None:
    status.phase = "downloading"
    status.target = tag
    current_exe = Path(sys.executable)
    dest = current_exe.parent / f"{_ASSET_NAME}.new"

    def report(fraction: float) -> None:
        status.progress = fraction

    logger.info("Updating from v%s to %s ...", current_version, tag)
    ok = _download(asset.get("browser_download_url", ""), dest, report)
    if not ok or not _is_valid_exe(dest, int(asset.get("size", 0))):
        logger.warning("Update verification failed; keeping current build.")
        dest.unlink(missing_ok=True)
        _finish(status, "error")
        return
    if _relaunch_with(dest, current_exe):
        status.relaunch = True
        _finish(status, "relaunching")
    else:
        _finish(status, "error")


def _finish(status: UpdateStatus, phase: str) -> None:
    status.phase = phase
    status.done = True


def is_frozen() -> bool:
    """True when running as a PyInstaller-built exe."""
    return bool(getattr(sys, "frozen", False)) or os.environ.get("KIDCOMPUTER_FROZEN") == "1"
