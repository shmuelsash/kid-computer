"""Provenance helpers must work even without the CI-generated module."""

from kidcomputer import buildinfo


def test_version_present() -> None:
    assert isinstance(buildinfo.VERSION, str)
    assert buildinfo.VERSION


def test_short_sha_truncates() -> None:
    assert len(buildinfo.short_sha()) <= 40


def test_build_summary_mentions_version() -> None:
    summary = buildinfo.build_summary()
    assert buildinfo.VERSION in summary
