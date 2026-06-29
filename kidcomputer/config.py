"""Application configuration.

No secrets live here. Runtime knobs come from environment variables (so a parent
can tweak behavior without editing code) and fall back to sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Public GitHub repo the auto-updater checks. Public means the running exe needs
# no embedded token to read releases or download assets.
GITHUB_REPO = "shmuelsash/kid-computer"

# The single secret way out: hold Ctrl+Alt+Q together for this long.
EXIT_HOLD_SECONDS = 2.0

# App data dir for logs (no display/console when frozen, so a file matters).
APP_DIR_NAME = "KidComputer"


def app_data_dir() -> Path:
    """Per-user data directory for logs and update downloads."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings."""

    log_level: str
    exit_hold_seconds: float
    sound_enabled: bool
    auto_update: bool
    fullscreen: bool

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            exit_hold_seconds=float(os.environ.get("EXIT_HOLD_SECONDS", EXIT_HOLD_SECONDS)),
            sound_enabled=_env_flag("KIDCOMPUTER_SOUND", True),
            auto_update=_env_flag("KIDCOMPUTER_AUTO_UPDATE", True),
            # Windowed mode is handy for development; fullscreen is the default.
            fullscreen=_env_flag("KIDCOMPUTER_FULLSCREEN", True),
        )
