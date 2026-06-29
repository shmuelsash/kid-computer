"""Structured logging per the house LOGGING.md standard.

Logs to stdout (12-factor) and to a rotating file in the per-user app dir,
because a frozen windowed build has no console to read. ``LOG_LEVEL`` controls
verbosity; nothing hard-codes a level.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from kidcomputer.config import app_data_dir

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging once. Safe to call again (clears old handlers)."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric)

    # Reset so repeated calls (tests, restarts) don't duplicate handlers.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    # A file handler is best-effort: never let a logging problem crash the app.
    try:
        log_path = app_data_dir() / "kid-computer.log"
        file_handler = RotatingFileHandler(
            log_path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover - filesystem edge case
        root.warning("Could not open log file, continuing with stdout only: %s", exc)
