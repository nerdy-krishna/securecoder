"""Unit tests for apply_suppressions.py — the matcher + most-specific-wins
resolution + expiry handling. Stdlib + pytest only.

Covers:
- Each match-field type (id, rule, file, file_glob, framework_ref) in isolation
- Combined matchers (rule + file_glob, etc.) requiring AND-style fit
- Most-specific-wins tie-breaking (id beats rule+glob beats rule alone)
- Expired entries skipped at match time
- Empty match dict rejected
- No-suppressions case is a pass-through
"""
from __future__ import annotations

import datetime as dt

import apply_suppressions as aps


def make_finding(**overrides):
    base = {
        "id": "abc123",
        "file": "src/api/auth.py",
        "lines": {"start": 42, "end": 42},
        "source": "bandit",
        "source_rule_id": "B105",
        "category": "sast",
        "cwe": ["CWE-259"],
        "framework_refs": [{"framework": "asvs-v5", "control": "V11.6.1"}],
        "severity": "high",
        "confidence": "medium",
        "title": "Hardcoded password",
        "description": "...",
        "evidence": "PASSWORD='x'",
        "remediation_hint": "",
        "fix_complexity": "medium",
        "tags": ["python"],
        "detected_at": "2026-05-14T16:00:00+00:00",
        "status": "open",
        "history": [],
    }
    base.update(overrides)
    return base


# ─────────────────────────── matcher tests ────────────────────────────


def test_match_by_id():
    f = make_finding(id="abc123")
    entry = {"match": {"id": "abc123"}}
    assert aps._entry_matches_finding(entry, f)
    entry_no = {"match": {"id": "different"}}
    assert not aps._entry_matches_finding(entry_no, f)


def test_match_by_rule():
    f = make_finding(source_rule_id="B105")
    assert aps._entry_matches_finding({"match": {"rule": "B105"}}, f)
    assert not aps._entry_matches_finding({"match": {"rule": "B106"}}, f)


def test_match_by_file_exact():
    f = make_finding(file="src/api/auth.py")
    assert aps._entry_matches_finding({"match": {"file": "src/api/auth.py"}}, f)
    assert not aps._entry_matches_finding({"match": {"file": "src/api/users.py"}}, f)


def test_match_by_file_glob():
    f = make_finding(file="tests/fixtures/passwords.py")
    assert aps._entry_matches_finding({"match": {"file_glob": "tests/**"}}, f)
    assert aps._entry_matches_finding({"match": {"file_glob": "tests/fixtures/*.py"}}, f)
    assert not aps._entry_matches_finding({"match": {"file_glob": "src/**"}}, f)


def test_match_combined_rule_and_glob():
    f = make_finding(source_rule_id="B105", file="tests/fixtures/x.py")
    entry = {"match": {"rule": "B105", "file_glob": "tests/**"}}
    assert aps._entry_matches_finding(entry, f)
    # Rule matches but glob doesn't → no match
    f2 = make_finding(source_rule_id="B105", file="src/x.py")
    assert not aps._entry_matches_finding(entry, f2)
    # Glob matches but rule doesn't → no match
    f3 = make_finding(source_rule_id="B106", file="tests/fixtures/x.py")
    assert not aps._entry_matches_finding(entry, f3)


def test_match_by_lines_within_range():
    """Source-code annotation suppression — match by file + line range."""
    f = make_finding(file="src/api/auth.py", lines={"start": 42, "end": 42})
    # Exact line match
    e = {"match": {"file": "src/api/auth.py", "lines": {"start": 42, "end": 42}}}
    assert aps._entry_matches_finding(e, f)
    # Range match — finding's start within entry's range
    e2 = {"match": {"file": "src/api/auth.py", "lines": {"start": 40, "end": 45}}}
    assert aps._entry_matches_finding(e2, f)
    # Out of range (above)
    e3 = {"match": {"file": "src/api/auth.py", "lines": {"start": 50, "end": 60}}}
    assert not aps._entry_matches_finding(e3, f)
    # Out of range (below)
    e4 = {"match": {"file": "src/api/auth.py", "lines": {"start": 10, "end": 20}}}
    assert not aps._entry_matches_finding(e4, f)
    # Different file → mismatch even with matching lines
    e5 = {"match": {"file": "different.py", "lines": {"start": 42, "end": 42}}}
    assert not aps._entry_matches_finding(e5, f)


def test_match_by_framework_ref():
    f = make_finding(framework_refs=[{"framework": "asvs-v5", "control": "V1.2.1"}])
    assert aps._entry_matches_finding({"match": {"framework_ref": "asvs-v5/V1.2.1"}}, f)
    assert not aps._entry_matches_finding({"match": {"framework_ref": "asvs-v5/V99.9.9"}}, f)
    # Framework matches but control doesn't
    assert not aps._entry_matches_finding({"match": {"framework_ref": "masvs/V1.2.1"}}, f)


def test_empty_match_dict_rejected():
    f = make_finding()
    assert not aps._entry_matches_finding({"match": {}}, f)
    assert not aps._entry_matches_finding({}, f)


# ──────────────────────── specificity tests ───────────────────────────


def test_specificity_ranking():
    # New v1.2.0 ranking: file+lines (annotation) inserted at score 1
    assert aps._specificity_score({"match": {"id": "x"}}) == 0
    assert aps._specificity_score({"match": {"file": "y", "lines": {"start": 5, "end": 5}}}) == 1
    assert aps._specificity_score({"match": {"rule": "X", "file": "y"}}) == 2
    assert aps._specificity_score({"match": {"rule": "X", "file_glob": "y/**"}}) == 3
    assert aps._specificity_score({"match": {"rule": "X"}}) == 4
    assert aps._specificity_score({"match": {"framework_ref": "f/c"}}) == 4
    assert aps._specificity_score({"match": {"file_glob": "y/**"}}) == 5


def test_most_specific_wins():
    f = make_finding(id="abc123", source_rule_id="B105", file="tests/fixtures/x.py")
    entries = [
        {"match": {"rule": "B105", "file_glob": "tests/**"}, "reason": "broad rule+glob"},
        {"match": {"id": "abc123"}, "reason": "exact id"},  # most specific
        {"match": {"rule": "B105"}, "reason": "rule alone"},
    ]
    findings, stats = aps.apply_suppressions([f], entries)
    # The id-match (specificity 0) should win
    assert findings[0]["status"] == "suppressed"
    assert findings[0]["suppression_reason"] == "exact id"
    # And the per-entry count should attribute to entry index 1
    assert stats["suppressed_by_entry"]["1"] == 1
    assert stats["suppressed_by_entry"]["0"] == 0


# ──────────────────────────── expiry tests ────────────────────────────


def test_expired_entry_ignored():
    f = make_finding(source_rule_id="B105")
    entries = [
        {
            "match": {"rule": "B105"},
            "reason": "expired",
            "expires_at": "2020-01-01",
        }
    ]
    findings, _ = aps.apply_suppressions([f], entries)
    # Entry is expired (date in the past) → finding remains open
    assert findings[0]["status"] == "open"


def test_future_expiry_does_not_affect():
    f = make_finding(source_rule_id="B105")
    far_future = (dt.date.today().replace(year=dt.date.today().year + 5)).isoformat()
    entries = [
        {
            "match": {"rule": "B105"},
            "reason": "valid",
            "expires_at": far_future,
        }
    ]
    findings, _ = aps.apply_suppressions([f], entries)
    assert findings[0]["status"] == "suppressed"


def test_no_expiry_treated_as_never():
    f = make_finding(source_rule_id="B105")
    entries = [{"match": {"rule": "B105"}, "reason": "forever", "expires_at": None}]
    findings, _ = aps.apply_suppressions([f], entries)
    assert findings[0]["status"] == "suppressed"


# ─────────────────────── apply_suppressions tests ─────────────────────


def test_no_entries_is_passthrough():
    f1 = make_finding(id="a", status="open")
    f2 = make_finding(id="b", status="open")
    findings, stats = aps.apply_suppressions([f1, f2], [])
    assert all(f["status"] == "open" for f in findings)
    assert stats["totals"]["findings_active"] == 2
    assert stats["totals"]["findings_suppressed"] == 0


def test_stats_count_per_entry():
    f1 = make_finding(id="a", source_rule_id="B105", file="tests/x.py")
    f2 = make_finding(id="b", source_rule_id="B105", file="tests/y.py")
    f3 = make_finding(id="c", source_rule_id="B608", file="src/q.py")
    entries = [
        {"match": {"rule": "B105", "file_glob": "tests/**"}, "reason": "test fixtures"},
        {"match": {"rule": "B608"}, "reason": "sql builder"},
        {"match": {"rule": "B999"}, "reason": "stale — nothing matches"},
    ]
    findings, stats = aps.apply_suppressions([f1, f2, f3], entries)
    assert findings[0]["status"] == "suppressed"
    assert findings[1]["status"] == "suppressed"
    assert findings[2]["status"] == "suppressed"
    assert stats["suppressed_by_entry"]["0"] == 2
    assert stats["suppressed_by_entry"]["1"] == 1
    assert stats["suppressed_by_entry"]["2"] == 0  # stale


def test_suppression_match_pointer():
    f = make_finding(source_rule_id="B105")
    entries = [
        {"match": {"rule": "B999"}, "reason": "nope"},
        {"match": {"rule": "B105"}, "reason": "yep"},
    ]
    findings, _ = aps.apply_suppressions([f], entries)
    # Pointer should reference entry index 1
    assert findings[0]["suppression_match"] == "suppressions.json#1"
    assert findings[0]["suppression_reason"] == "yep"
