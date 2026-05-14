"""Unit tests for check_version.py — the version-comparison helpers.

Network-dependent paths (fetch_latest_release, full main()) are covered by
manual smoke-testing rather than pytest, since they hit a live GitHub API.
"""
from __future__ import annotations

import sys
from pathlib import Path

# This script lives under a different skill dir than apply_suppressions /
# render_html / review_hook, so add its scripts dir to the path.
REPO_ROOT = Path(__file__).resolve().parent.parent
UPDATE_SCRIPTS = REPO_ROOT / "skills" / "security" / "securecoder-update" / "scripts"
sys.path.insert(0, str(UPDATE_SCRIPTS))

import check_version as cv


def test_parse_version_tuple_basic():
    assert cv.parse_version_tuple("v1.1.0") == (1, 1, 0)
    assert cv.parse_version_tuple("1.1.0") == (1, 1, 0)
    assert cv.parse_version_tuple("v0.1.0") == (0, 1, 0)


def test_parse_version_tuple_with_pre_release_suffix():
    # We strip any -rc.1 / -beta / etc. suffix so a v1.2.0-rc.1 vs v1.2.0
    # comparison doesn't crash on int() of "0-rc"
    assert cv.parse_version_tuple("v1.2.0-rc.1") == (1, 2, 0)
    assert cv.parse_version_tuple("v2.0.0-beta") == (2, 0, 0)


def test_parse_version_tuple_handles_invalid():
    assert cv.parse_version_tuple("") == ()
    assert cv.parse_version_tuple("not-a-version") == ()
    assert cv.parse_version_tuple("v1.x.0") == ()  # x is not an int


def test_parse_version_tuple_handles_two_components():
    # Tolerant: a tag like v1.0 should still parse rather than failing
    assert cv.parse_version_tuple("v1.0") == (1, 0)


def test_version_ordering_is_lexicographic_on_tuples():
    # Critical: ensures v1.10.0 > v1.2.0 (string comparison would give
    # the wrong answer)
    assert cv.parse_version_tuple("v1.10.0") > cv.parse_version_tuple("v1.2.0")
    assert cv.parse_version_tuple("v2.0.0") > cv.parse_version_tuple("v1.99.99")


def test_find_installed_version_reads_version_file():
    """The function reads from VERSION relative to its module location.
    We can't easily fake the location, but we can verify the function
    runs without error on the real repo (which has a VERSION file we just
    created) and returns a parseable string.
    """
    version = cv.find_installed_version()
    # VERSION file exists in the actual repo (v1.2.0 sprint shipping)
    assert version is not None
    # Should look like a version tag
    assert version.startswith("v")
    parsed = cv.parse_version_tuple(version)
    assert parsed != ()  # parseable
