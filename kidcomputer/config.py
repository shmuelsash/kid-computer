"""Application configuration.

No secrets live here. Runtime knobs come from environment variables (so a parent
can tweak behavior without editing code) and fall back to sensible defaults.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from kidcomputer.modes import DEFAULT_MODE, MODES
from kidcomputer.theme import DEFAULT_THEME, THEMES

logger = logging.getLogger(__name__)

# Public GitHub repo the auto-updater checks. Public means the running exe needs
# no embedded token to read releases or download assets.
GITHUB_REPO = "shmuelsash/kid-computer"

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

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


class SettingsStore:
    """User-facing preferences, persisted to JSON so choices survive restarts.

    Defaults are seeded from env on first run; after that the file wins. Every
    setter validates and writes immediately, so the UI can change settings live.
    """

    FILENAME = "settings.json"

    def __init__(self, path: Path | None = None, defaults: dict | None = None) -> None:
        self._path = path or (app_data_dir() / self.FILENAME)
        self._data: dict = defaults or self._env_defaults()
        self._load()

    @staticmethod
    def _env_defaults() -> dict:
        return {
            "theme": DEFAULT_THEME,
            "age_mode": DEFAULT_MODE,
            "intensity": 0.6,
            "sound": _env_flag("KIDCOMPUTER_SOUND", True),
            "log_level": os.environ.get("LOG_LEVEL", "INFO").upper(),
        }

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Could not read settings, using defaults: %s", exc)
            return
        for key in self._data:
            if key in stored:
                self._data[key] = stored[key]
        self._validate()

    def _validate(self) -> None:
        if self._data["theme"] not in THEMES:
            self._data["theme"] = DEFAULT_THEME
        if self._data["age_mode"] not in MODES:
            self._data["age_mode"] = DEFAULT_MODE
        if self._data["log_level"] not in LOG_LEVELS:
            self._data["log_level"] = "INFO"
        self._data["intensity"] = max(0.0, min(1.0, float(self._data["intensity"])))
        self._data["sound"] = bool(self._data["sound"])

    def _save(self) -> None:
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as exc:
            logger.warning("Could not save settings: %s", exc)

    # Typed accessors -----------------------------------------------------
    @property
    def theme(self) -> str:
        return self._data["theme"]

    @property
    def age_mode(self) -> str:
        return self._data["age_mode"]

    @property
    def intensity(self) -> float:
        return self._data["intensity"]

    @property
    def sound(self) -> bool:
        return self._data["sound"]

    @property
    def log_level(self) -> str:
        return self._data["log_level"]

    def set(self, key: str, value: object) -> None:
        """Update one setting (validated) and persist immediately."""
        if key not in self._data:
            raise KeyError(key)
        self._data[key] = value
        self._validate()
        self._save()
