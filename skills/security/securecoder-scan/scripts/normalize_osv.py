#!/usr/bin/env python3
"""Normalize OSV-scanner JSON output into securecoder findings.jsonl (v1.0).

OSV-scanner reads dependency lockfiles (package.json, requirements.txt,
go.sum, Cargo.lock, etc.) and queries osv.dev for known vulnerabilities.
Output: per source-file, a list of packages, each with a list of
vulnerabilities. We emit one finding per (package, vulnerability) pair.

Severity comes from the vulnerability's CVSS score when present;
otherwise defaults to "high" (vulnerable dependency, severity unknown,
conservative default). All OSV findings are tagged with CWE-1104 (Use
of Unmaintained Third Party Components) and OWASP A06 (Vulnerable and
Outdated Components).

Stdlib only.

Usage:
    python3 normalize_osv.py <osv-scanner-json-file> \\
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
    load_cwe_table,
    normalize_path,
    truncate,
    utc_now_iso,
)


def parse_severity_signal(severity_entries) -> tuple:
    """Extract a usable severity signal from OSV's `severity` array.

    Returns (numeric_score_or_None, label_or_None).

    OSV's severity entries come in several shapes:
      - {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/.../A:H"}  ← vector only
      - {"type": "CVSS_V3", "score": "7.5"}                    ← bare number
      - {"type": "HIGH"}                                       ← bare label
    We avoid trying to parse a number out of the CVSS vector string
    because the "3.1" in "CVSS:3.1/..." is the CVSS version, not the
    score. When no number or recognized label is present, return both
    Nones; the caller falls back to "high" (conservative default for
    a known-vulnerable dependency).
    """
    if not severity_entries:
        return None, None
    if not isinstance(severity_entries, list):
        severity_entries = [severity_entries]
    for entry in severity_entries:
        if isinstance(entry, dict):
            type_field = (entry.get("type") or "").upper()
            if type_field in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
                return None, type_field.lower()
            score_field = entry.get("score") or entry.get("value") or ""
        else:
            score_field = entry
        try:
            v = float(str(score_field).strip())
            if 0.0 <= v <= 10.0:
                return v, None
        except (TypeError, ValueError):
            pass
    return None, None


def severity_from_signal(score, label) -> str:
    """Map a CVSS 0–10 score or explicit label to securecoder's 5-level scale."""
    if label is not None:
        return label
    if score is None:
        return "high"  # vulnerable dep, severity unknown → conservative
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "info"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("osv_json", help="Path to OSV-scanner --json output file")
    ap.add_argument("--cwe-table", required=True,
                    help="Path to cwe-to-framework.json")
    ap.add_argument("--repo-root", required=True,
                    help="Project root; used to normalize file paths")
    ap.add_argument("--output", "-o",
                    help="Write JSONL here instead of stdout")
    args = ap.parse_args()

    with open(args.osv_json, encoding="utf-8") as f:
        text = f.read().strip()
    data = json.loads(text) if text else {}
    cwe_table = load_cwe_table(args.cwe_table)
    repo_root = Path(args.repo_root).resolve()
    now = utc_now_iso()

    findings: list = []

    # A06 is the canonical OWASP Top 10 mapping for OSV findings, so
    # we always include it as an extra ref even when the per-CWE table
    # doesn't fire.
    extra_owasp = [{"framework": "owasp-top-10-2021", "category": "A06"}]

    for source_result in data.get("results", []):
        source = source_result.get("source", {}) or {}
        source_path_raw = source.get("path", "") or ""
        rel_source_path = normalize_path(source_path_raw, repo_root)

        for pkg_entry in source_result.get("packages", []):
            pkg = pkg_entry.get("package", {}) or {}
            pkg_name = pkg.get("name", "") or ""
            pkg_version = pkg.get("version", "") or ""
            ecosystem = pkg.get("ecosystem", "") or ""

            for vuln in pkg_entry.get("vulnerabilities", []):
                vuln_id = vuln.get("id", "") or ""
                summary = vuln.get("summary", "") or vuln_id
                details = vuln.get("details", "") or summary
                aliases = vuln.get("aliases", []) or []
                db_specific = vuln.get("database_specific", {}) or {}
                cwes = extract_cwes(db_specific.get("cwe_ids", []))

                # If no CWE provided, fall back to CWE-1104.
                if not cwes:
                    cwes = ["CWE-1104"]

                score, label = parse_severity_signal(vuln.get("severity"))
                severity = severity_from_signal(score, label)

                framework_refs = enrich_framework_refs(
                    cwes, cwe_table, extra_refs=extra_owasp,
                )

                evidence = f"{pkg_name}@{pkg_version} ({ecosystem})"
                remediation = (
                    f"Upgrade `{pkg_name}` past `{pkg_version}`. "
                    f"See https://osv.dev/vulnerability/{vuln_id} for the "
                    f"advisory and patched versions."
                )

                rule_id = vuln_id or f"{pkg_name}@{pkg_version}"

                finding = {
                    "id": canonical_id(rel_source_path, 0, f"{pkg_name}#{rule_id}"),
                    "file": rel_source_path,
                    "lines": None,
                    "source": "osv-scanner",
                    "source_rule_id": rule_id,
                    "category": "sast",
                    "cwe": cwes,
                    "framework_refs": framework_refs,
                    "severity": severity,
                    "confidence": "high",
                    "title": truncate(summary, 200),
                    "description": truncate(details, 500),
                    "evidence": evidence,
                    "remediation_hint": truncate(remediation, 500),
                    "fix_complexity": "medium",
                    "tags": [ecosystem, "dependency", "cve"]
                    + [a for a in aliases if a.startswith("CVE-")],
                    "detected_at": now,
                    "status": "open",
                    "history": [],
                }
                findings.append(finding)

    emit_findings(findings, args.output)


if __name__ == "__main__":
    main()
