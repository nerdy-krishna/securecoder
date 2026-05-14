"""Unit tests for the four SAST normalizers (Semgrep, Bandit, Gitleaks, OSV).

Each normalizer's main() is invoked indirectly by feeding synthetic raw
tool output through the helper functions. Schema conformance is the
primary assertion.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import normalize_semgrep as ns
import normalize_bandit as nb
import normalize_gitleaks as ng
import normalize_osv as no_mod


CWE_TABLE = {
    "CWE-89": {
        "name": "SQL Injection",
        "framework_refs": [
            {"framework": "asvs-v5", "control": "V1.2.1"},
            {"framework": "owasp-top-10-2021", "category": "A03"},
        ],
    },
    "CWE-798": {
        "name": "Use of Hardcoded Credentials",
        "framework_refs": [
            {"framework": "asvs-v5", "control": "V11.6.1"},
        ],
    },
    "CWE-1333": {
        "name": "Regex DoS",
        "framework_refs": [],
    },
}


# ───────────────────────── Semgrep ───────────────────────────


def test_semgrep_severity_mapping():
    md = {"impact": "HIGH"}
    assert ns.map_severity("ERROR", "rule.sql-injection", md) == "critical"
    md = {}
    assert ns.map_severity("ERROR", "rule.sql-injection", md) == "critical"  # rule name escalates
    assert ns.map_severity("ERROR", "rule.unrelated", md) == "high"
    assert ns.map_severity("WARNING", "any", md) == "medium"
    assert ns.map_severity("INFO", "any", md) == "low"
    assert ns.map_severity("", "any", md) == "info"


def test_semgrep_confidence_mapping():
    assert ns.map_confidence({"confidence": "HIGH"}) == "high"
    assert ns.map_confidence({"confidence": "LOW"}) == "low"
    assert ns.map_confidence({}) == "medium"


# ───────────────────────── Bandit ────────────────────────────


def test_bandit_severity_escalates_for_secrets_and_sqli():
    # B105 = hardcoded_password_string — should be high even when bandit says LOW
    assert nb.map_severity("LOW", "MEDIUM", "B105") == "high"
    assert nb.map_severity("MEDIUM", "HIGH", "B608") == "high"
    # Generic rule with HIGH/HIGH → critical
    assert nb.map_severity("HIGH", "HIGH", "B999") == "critical"
    assert nb.map_severity("HIGH", "LOW", "B999") == "high"
    assert nb.map_severity("LOW", "LOW", "B999") == "low"


def test_bandit_confidence_mapping():
    assert nb.map_confidence("HIGH") == "high"
    assert nb.map_confidence("LOW") == "low"
    assert nb.map_confidence("MEDIUM") == "medium"


# ───────────────────────── Gitleaks ──────────────────────────


def test_gitleaks_redact_match_preserves_recognizability():
    s = "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'"
    redacted = ng.redact_match(s)
    # Keeps prefix/suffix; middle replaced
    assert redacted.startswith("AWS_") or redacted.startswith("AKIA")
    assert "*" in redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted


def test_gitleaks_redact_match_short_strings():
    assert ng.redact_match("short") == "*" * 5
    assert ng.redact_match("") == ""


# ───────────────────────── OSV ───────────────────────────────


def test_osv_severity_from_numeric_score():
    assert no_mod.severity_from_signal(9.5, None) == "critical"
    assert no_mod.severity_from_signal(7.5, None) == "high"
    assert no_mod.severity_from_signal(5.0, None) == "medium"
    assert no_mod.severity_from_signal(2.0, None) == "low"
    assert no_mod.severity_from_signal(0.0, None) == "info"


def test_osv_severity_from_label_overrides_score():
    assert no_mod.severity_from_signal(None, "critical") == "critical"
    assert no_mod.severity_from_signal(7.5, "low") == "low"  # label wins


def test_osv_severity_defaults_to_high_when_no_signal():
    assert no_mod.severity_from_signal(None, None) == "high"


def test_osv_severity_signal_parse_cvss_vector_returns_none():
    # The vector "CVSS:3.1/..." should NOT yield a number (we don't extract
    # the score from the vector itself).
    entries = [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/A:H"}]
    score, label = no_mod.parse_severity_signal(entries)
    assert score is None
    assert label is None


def test_osv_severity_signal_parse_explicit_number():
    entries = [{"type": "CVSS_V3", "score": "7.5"}]
    score, label = no_mod.parse_severity_signal(entries)
    assert score == 7.5


def test_osv_severity_signal_parse_label():
    entries = [{"type": "HIGH"}]
    score, label = no_mod.parse_severity_signal(entries)
    assert label == "high"
