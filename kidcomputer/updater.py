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

import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_API_TIMEOUT = 6.0
_DOWNLOAD_TIMEOUT = 120.0
_ASSET_NAME = "KidComputer.exe"


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


def _find_asset_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        if asset.get("name") == _ASSET_NAME:
            return asset.get("browser_download_url")
    return None


def _download(url: str, dest: Path) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT) as resp:  # noqa: S310
            dest.write_bytes(resp.read())
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("Update download failed: %s", exc)
        return False


def _relaunch_with(new_exe: Path, current_exe: Path) -> None:
    """Write a batch script that swaps in the new exe and relaunches it.

    The running exe can't overwrite itself, so a detached cmd waits for this
    process to exit, copies the download over the current file, restarts it, and
    deletes itself.
    """
    script = current_exe.parent / "_kidcomputer_update.bat"
    script.write_text(
        "@echo off\r\n"
        "ping 127.0.0.1 -n 2 >nul\r\n"
        f'move /y "{new_exe}" "{current_exe}" >nul\r\n'
        f'start "" "{current_exe}"\r\n'
        'del "%~f0"\r\n',
        encoding="ascii",
    )
    subprocess.Popen(  # noqa: S603
        ["cmd", "/c", str(script)],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        close_fds=True,
    )


def check_and_update(repo: str, current_version: str, *, is_frozen: bool) -> bool:
    """Check for and apply an update. Returns True if an update was launched
    (caller should exit so the swap can happen).

    No-ops in a dev (non-frozen) run - there's no single exe to replace.
    """
    if not is_frozen:
        logger.info("Dev run: skipping self-update.")
        return False

    release = fetch_latest_release(repo)
    if release is None:
        return False

    latest_tag = release.get("tag_name", "")
    if not is_newer(latest_tag, current_version):
        logger.info("Already up to date (running v%s).", current_version)
        return False

    asset_url = _find_asset_url(release)
    if asset_url is None:
        logger.warning("Release %s has no %s asset.", latest_tag, _ASSET_NAME)
        return False

    logger.info("Updating from v%s to %s ...", current_version, latest_tag)
    current_exe = Path(sys.executable)
    download = current_exe.parent / f"{_ASSET_NAME}.new"
    if not _download(asset_url, download):
        return False

    _relaunch_with(download, current_exe)
    logger.info("Update downloaded; relaunching into %s.", latest_tag)
    return True


def is_frozen() -> bool:
    """True when running as a PyInstaller-built exe."""
    return bool(getattr(sys, "frozen", False)) or os.environ.get("KIDCOMPUTER_FROZEN") == "1"
