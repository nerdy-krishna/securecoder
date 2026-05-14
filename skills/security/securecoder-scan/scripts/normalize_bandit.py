#!/usr/bin/env python3
"""Normalize Bandit JSON output into securecoder findings.jsonl (schema v1.0).

Bandit is a Python-specific SAST tool. `bandit -r <path> -f json` emits a
JSON document with a `results` array. Each result includes a CWE id (often
populated), severity and confidence labels (HIGH/MEDIUM/LOW), and line
range.

Stdlib only.

Usage:
    python3 normalize_bandit.py <bandit-json-file> \\
        --cwe-table <path-to-cwe-to-framework.json> \\
        --repo-root <path-to-project-root> \\
        [--output <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    canonical_id,
    emit_findings,
    enrich_framework_refs,
    extract_cwes,
    humanize_rule_id,
    load_cwe_table,
    normalize_path,
    truncate,
    utc_now_iso,
)


def map_severity(issue_severity: str, issue_confidence: str, test_id: str) -> str:
    """Map Bandit (severity, confidence, test_id) → securecoder 5-level.

    Bandit emits HIGH/MEDIUM/LOW for both severity and confidence. Cross
    multiply with a small rule-id heuristic to catch test_ids that flag
    inherently critical conditions (hardcoded secrets, SQL injection
    patterns) regardless of Bandit's own classification.
    """
    sev = (issue_severity or "").upper()
    conf = (issue_confidence or "").upper()
    lower_id = (test_id or "").lower()

    # B105 (hardcoded_password_string), B106 (hardcoded_password_funcarg),
    # B107 (hardcoded_password_default), B608 (hardcoded_sql_expressions) —
    # always at least 'high' regardless of Bandit's per-instance severity.
    always_at_least_high = lower_id in {"b105", "b106", "b107", "b608"}

    if sev == "HIGH":
        return "critical" if conf == "HIGH" else "high"
    if sev == "MEDIUM":
        if always_at_least_high:
            return "high"
        return "medium"
    if sev == "LOW":
        if always_at_least_high:
            return "high"
        return "low"
    return "info"


def map_confidence(issue_confidence: str) -> str:
    c = (issue_confidence or "").upper()
    if c == "HIGH":
        return "high"
    if c == "LOW":
        return "low"
    return "medium"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bandit_json", help="Path to Bandit -f json output file")
    ap.add_argument("--cwe-table", required=True,
                    help="Path to cwe-to-framework.json")
    ap.add_argument("--repo-root", required=True,
                    help="Project root; used to normalize file paths")
    ap.add_argument("--output", "-o",
                    help="Write JSONL here instead of stdout")
    args = ap.parse_args()

    with open(args.bandit_json, encoding="utf-8") as f:
        data = json.load(f)
    cwe_table = load_cwe_table(args.cwe_table)
    repo_root = Path(args.repo_root).resolve()
    now = utc_now_iso()

    findings: list = []

    for r in data.get("results", []):
        rel_path = normalize_path(r.get("filename", ""), repo_root)
        test_id = r.get("test_id", "") or ""
        test_name = r.get("test_name", "") or ""

        line_start = int(r.get("line_number", 0) or 0)
        line_range = r.get("line_range") or [line_start]
        line_end = int(line_range[-1]) if line_range else line_start

        cwes = extract_cwes(r.get("issue_cwe"))
        severity = map_severity(
            r.get("issue_severity", ""),
            r.get("issue_confidence", ""),
            test_id,
        )
        confidence = map_confidence(r.get("issue_confidence", ""))
        framework_refs = enrich_framework_refs(cwes, cwe_table)

        finding = {
            "id": canonical_id(rel_path, line_start, test_id),
            "file": rel_path,
            "lines": (
                {"start": line_start, "end": line_end}
                if line_start else None
            ),
            "source": "bandit",
            "source_rule_id": test_id,
            "category": "sast",
            "cwe": cwes,
            "framework_refs": framework_refs,
            "severity": severity,
            "confidence": confidence,
            "title": humanize_rule_id(test_name) or humanize_rule_id(test_id),
            "description": truncate(r.get("issue_text", ""), 500),
            "evidence": truncate(r.get("code", ""), 500),
            "remediation_hint": truncate(r.get("more_info", ""), 500),
            "fix_complexity": "medium",
            "tags": ["python"],
            "detected_at": now,
            "status": "open",
            "history": [],
        }
        findings.append(finding)

    emit_findings(findings, args.output)


if __name__ == "__main__":
    main()
