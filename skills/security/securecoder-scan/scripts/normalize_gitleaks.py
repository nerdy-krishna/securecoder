#!/usr/bin/env python3
"""Normalize Gitleaks JSON output into securecoder findings.jsonl (v1.0).

Gitleaks detects hardcoded secrets (API keys, passwords, tokens, etc.) in
source files. Its JSON output is a top-level array of detection objects.
We map every gitleaks finding to CWE-798 (hardcoded credentials) and a
severity of `critical` — the design.md guidance is that detected secrets
are always above any sensible severity floor.

Stdlib only.

Usage:
    python3 normalize_gitleaks.py <gitleaks-json-file> \\
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
    load_cwe_table,
    normalize_path,
    truncate,
    utc_now_iso,
)


# All gitleaks findings represent CWE-798 (Use of Hardcoded Credentials).
# We pin the CWE list rather than reading it from the tool because gitleaks
# doesn't emit CWE metadata in its JSON.
GITLEAKS_CWES = ["CWE-798"]


def redact_match(match: str, max_chars: int = 60) -> str:
    """Return a redacted preview of a secret match. Keeps the first and
    last few characters with the middle replaced by asterisks so the
    finding is identifiable without leaking the secret into the report.
    """
    s = (match or "").strip()
    if len(s) <= 12:
        return "*" * len(s)
    return f"{s[:4]}{'*' * (min(len(s), max_chars) - 8)}{s[-4:]}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gitleaks_json", help="Path to Gitleaks --report output file")
    ap.add_argument("--cwe-table", required=True,
                    help="Path to cwe-to-framework.json")
    ap.add_argument("--repo-root", required=True,
                    help="Project root; used to normalize file paths")
    ap.add_argument("--output", "-o",
                    help="Write JSONL here instead of stdout")
    args = ap.parse_args()

    with open(args.gitleaks_json, encoding="utf-8") as f:
        # Gitleaks may emit an empty file when no findings; tolerate that.
        text = f.read().strip()
    data = json.loads(text) if text else []
    if not isinstance(data, list):
        # Tolerate an unexpected wrapper object with "findings" key
        data = data.get("findings", []) if isinstance(data, dict) else []
    cwe_table = load_cwe_table(args.cwe_table)
    repo_root = Path(args.repo_root).resolve()
    now = utc_now_iso()

    findings: list = []

    for r in data:
        rel_path = normalize_path(r.get("File", ""), repo_root)
        rule_id = r.get("RuleID", "") or ""
        description = r.get("Description", "") or rule_id

        line_start = int(r.get("StartLine", 0) or 0)
        line_end = int(r.get("EndLine", line_start) or line_start)

        framework_refs = enrich_framework_refs(GITLEAKS_CWES, cwe_table)

        # Use Fingerprint when present (gitleaks's own dedup id) as a
        # secondary input to the canonical id so two findings on the same
        # line for different secrets are distinct.
        fingerprint = r.get("Fingerprint", "")
        rule_id_for_id = f"{rule_id}#{fingerprint}" if fingerprint else rule_id

        tags_raw = r.get("Tags") or []
        if isinstance(tags_raw, str):
            tags = [tags_raw]
        else:
            tags = [str(t) for t in tags_raw]
        tags.append("secret")

        finding = {
            "id": canonical_id(rel_path, line_start, rule_id_for_id),
            "file": rel_path,
            "lines": (
                {"start": line_start, "end": line_end}
                if line_start else None
            ),
            "source": "gitleaks",
            "source_rule_id": rule_id,
            "category": "sast",
            "cwe": list(GITLEAKS_CWES),
            "framework_refs": framework_refs,
            "severity": "critical",
            "confidence": "high",
            "title": description,
            "description": truncate(
                f"Hardcoded secret detected: {description}", 500
            ),
            "evidence": redact_match(r.get("Match", "")),
            "remediation_hint": (
                "Rotate the leaked credential immediately. Remove from source "
                "and load via environment variable, secret manager, or vault. "
                "Audit git history (`git log -S <secret>`) for prior exposure."
            ),
            "fix_complexity": "high",
            "tags": tags,
            "detected_at": now,
            "status": "open",
            "history": [],
        }
        findings.append(finding)

    emit_findings(findings, args.output)


if __name__ == "__main__":
    main()
