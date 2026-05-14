#!/usr/bin/env python3
"""Normalize Semgrep JSON output into securecoder findings.jsonl (schema v1.0).

Reads the JSON output of `semgrep --json`, enriches each result with
framework references via the shipped CWE-to-framework lookup table, and
emits one finding object per line to stdout (or the given output path).

Stdlib only. Schema details: see docs/design.md § 4.

Usage:
    python3 normalize_semgrep.py <semgrep-json-file> \\
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
    extract_owasp_categories,
    humanize_rule_id,
    load_cwe_table,
    normalize_path,
    truncate,
    utc_now_iso,
)


# Rule-id substrings that escalate Semgrep ERROR severity to "critical"
# rather than "high". These are the patterns that, when triggered, tend
# to indicate exploitable conditions rather than merely risky patterns.
CRITICAL_RULE_PATTERNS = (
    "secret", "hardcoded", "private-key", "api-key",
    "sql-injection", "command-injection", "os-command",
    "ssrf", "xxe", "deserialization", "rce", "remote-code",
    "shell-injection", "code-injection",
)


def map_severity(semgrep_severity, rule_id: str, metadata: dict) -> str:
    """Map Semgrep ERROR/WARNING/INFO to the securecoder 5-level scale."""
    sev = (semgrep_severity or "").upper() if isinstance(semgrep_severity, str) else ""
    impact = str(metadata.get("impact") or "").upper()
    lower_id = (rule_id or "").lower()
    is_critical = (
        impact == "HIGH"
        or any(p in lower_id for p in CRITICAL_RULE_PATTERNS)
    )
    if sev == "ERROR":
        return "critical" if is_critical else "high"
    if sev == "WARNING":
        return "medium"
    if sev == "INFO":
        return "low"
    return "info"


def map_confidence(metadata: dict) -> str:
    """Map Semgrep confidence (or impact heuristic) to high/medium/low."""
    c = str(metadata.get("confidence") or "").upper()
    if c == "HIGH":
        return "high"
    if c == "LOW":
        return "low"
    return "medium"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("semgrep_json", help="Path to Semgrep --json output file")
    ap.add_argument("--cwe-table", required=True,
                    help="Path to cwe-to-framework.json")
    ap.add_argument("--repo-root", required=True,
                    help="Project root; used to normalize file paths")
    ap.add_argument("--output", "-o",
                    help="Write JSONL here instead of stdout")
    args = ap.parse_args()

    with open(args.semgrep_json, encoding="utf-8") as f:
        data = json.load(f)
    cwe_table = load_cwe_table(args.cwe_table)
    repo_root = Path(args.repo_root).resolve()
    now = utc_now_iso()

    findings: list = []

    for r in data.get("results", []):
        rel_path = normalize_path(r.get("path", ""), repo_root)
        rule_id = r.get("check_id", "") or ""
        start = r.get("start", {}) or {}
        end = r.get("end", {}) or {}
        extra = r.get("extra", {}) or {}
        metadata = extra.get("metadata", {}) or {}

        line_start = int(start.get("line", 0) or 0)
        line_end = int(end.get("line", line_start) or line_start)

        cwes = extract_cwes(metadata.get("cwe", []))
        owasp_cats = extract_owasp_categories(metadata.get("owasp", []))
        severity = map_severity(extra.get("severity"), rule_id, metadata)
        confidence = map_confidence(metadata)
        framework_refs = enrich_framework_refs(
            cwes,
            cwe_table,
            extra_refs=[
                {"framework": "owasp-top-10-2021", "category": cat}
                for cat in owasp_cats
            ],
        )

        tags_raw = metadata.get("technology", [])
        if isinstance(tags_raw, str):
            tags = [tags_raw]
        elif isinstance(tags_raw, list):
            tags = [str(t) for t in tags_raw]
        else:
            tags = []

        has_fix = bool(metadata.get("fix") or extra.get("fix"))
        fix_complexity = "low" if has_fix else "medium"

        finding = {
            "id": canonical_id(rel_path, line_start, rule_id),
            "file": rel_path,
            "lines": (
                {"start": line_start, "end": line_end}
                if line_start else None
            ),
            "source": "semgrep",
            "source_rule_id": rule_id,
            "category": "sast",
            "cwe": cwes,
            "framework_refs": framework_refs,
            "severity": severity,
            "confidence": confidence,
            "title": humanize_rule_id(rule_id),
            "description": truncate(extra.get("message", ""), 500),
            "evidence": truncate(extra.get("lines", ""), 500),
            "remediation_hint": truncate(
                metadata.get("fix") or extra.get("fix") or "", 500
            ),
            "fix_complexity": fix_complexity,
            "tags": tags,
            "detected_at": now,
            "status": "open",
            "history": [],
        }
        findings.append(finding)

    emit_findings(findings, args.output)


if __name__ == "__main__":
    main()
