"""Version and build provenance.

These defaults describe a local dev build. The CI release workflow writes
``kidcomputer/_generated_buildinfo.py`` with the real values (version, git SHA,
build time) and bakes it into the exe, so a running build can always answer
"what version is this, and where did it come from?" - surfaced in the startup
log and the on-screen About line.
"""

from __future__ import annotations

VERSION: str = "0.0.0+dev"
GIT_SHA: str = "unknown"
BUILD_TIME: str = "unknown"
CHANNEL: str = "dev"

# CI overwrites these via a generated module (gitignored). Import is best-effort
# so dev runs and tests work without it.
try:
    from kidcomputer import _generated_buildinfo as _gen  # type: ignore[attr-defined]

    VERSION = _gen.VERSION
    GIT_SHA = _gen.GIT_SHA
    BUILD_TIME = _gen.BUILD_TIME
    CHANNEL = _gen.CHANNEL
except ImportError:
    pass


def short_sha() -> str:
    """Return the first 7 chars of the git SHA, or the full value if shorter."""
    return GIT_SHA[:7] if GIT_SHA and GIT_SHA != "unknown" else GIT_SHA


def build_summary() -> str:
    """One-line provenance string for logs and the on-screen About text."""
    return f"v{VERSION} ({short_sha()}) built {BUILD_TIME} [{CHANNEL}]"
