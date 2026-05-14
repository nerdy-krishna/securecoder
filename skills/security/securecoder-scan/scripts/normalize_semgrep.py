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
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path


# Rule-id substrings that escalate Semgrep ERROR severity to "critical"
# rather than "high". These are the patterns that, when triggered, tend
# to indicate exploitable conditions rather than risky patterns.
CRITICAL_RULE_PATTERNS = (
    "secret", "hardcoded", "private-key", "api-key",
    "sql-injection", "command-injection", "os-command",
    "ssrf", "xxe", "deserialization", "rce", "remote-code",
    "shell-injection", "code-injection",
)

# Matches CWE identifiers like "CWE-89", "cwe-89", "CWE 89", embedded in
# arbitrary text Semgrep metadata sometimes uses.
CWE_TOKEN_RE = re.compile(r"\bCWE[-\s]?(\d+)\b", re.IGNORECASE)

# Matches OWASP Top 10 category prefixes like "A03", "A1", "A10".
OWASP_CAT_RE = re.compile(r"\b(A(?:0?\d|1[0-2]))\b")


def canonical_id(file: str, line_start: int, rule_id: str) -> str:
    """SAST canonical ID per design.md §4 — sha256(file|line|rule_id)."""
    h = hashlib.sha256()
    h.update(f"{file}|{line_start}|{rule_id}".encode("utf-8"))
    return h.hexdigest()


def map_severity(semgrep_severity: str, rule_id: str, metadata: dict) -> str:
    """Map Semgrep ERROR/WARNING/INFO to the securecoder 5-level scale."""
    sev = (semgrep_severity or "").upper()
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


def extract_cwes(metadata: dict) -> list[str]:
    """Extract canonical CWE-N tokens from Semgrep's varied metadata shapes."""
    raw = metadata.get("cwe", [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raw = []
    found: list[str] = []
    for item in raw:
        for m in CWE_TOKEN_RE.finditer(str(item)):
            tok = f"CWE-{m.group(1)}"
            if tok not in found:
                found.append(tok)
    return found


def extract_owasp_categories(metadata: dict) -> list[str]:
    """Extract OWASP Top 10 category tokens (e.g., 'A03') from metadata."""
    raw = metadata.get("owasp", [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raw = []
    found: list[str] = []
    for item in raw:
        for m in OWASP_CAT_RE.finditer(str(item)):
            tok = m.group(1)
            # Normalize A1 → A01 so categories sort consistently
            if len(tok) == 2:
                tok = "A0" + tok[1]
            if tok not in found:
                found.append(tok)
    return found


def enrich_framework_refs(
    cwes: list[str], cwe_table: dict, extra_owasp_cats: list[str]
) -> list[dict]:
    """Merge CWE-derived framework refs with any OWASP categories present in
    Semgrep metadata directly. Deduplicates by (framework, control|category).
    """
    refs: list[dict] = []
    seen: set[tuple] = set()

    def add(ref: dict) -> None:
        key = (ref["framework"], ref.get("control") or ref.get("category"))
        if key not in seen:
            seen.add(key)
            refs.append(ref)

    for cwe in cwes:
        entry = cwe_table.get(cwe)
        if not entry:
            continue
        for r in entry.get("framework_refs", []):
            add(dict(r))

    for cat in extra_owasp_cats:
        add({"framework": "owasp-top-10-2021", "category": cat})

    return refs


def humanize_rule_id(rule_id: str) -> str:
    """Turn `python.django.security.sql-injection-raw-query` into something
    closer to a human-readable title."""
    tail = rule_id.rsplit(".", 1)[-1] if "." in rule_id else rule_id
    words = tail.replace("_", "-").split("-")
    return " ".join(w.capitalize() for w in words if w)


def truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("semgrep_json", help="Path to Semgrep --json output file")
    ap.add_argument("--cwe-table", required=True,
                    help="Path to cwe-to-framework.json")
    ap.add_argument("--repo-root", required=True,
                    help="Project root path; used to normalize file paths")
    ap.add_argument("--output", "-o",
                    help="Write JSONL here instead of stdout")
    args = ap.parse_args()

    with open(args.semgrep_json, encoding="utf-8") as f:
        data = json.load(f)
    with open(args.cwe_table, encoding="utf-8") as f:
        cwe_table = json.load(f)

    repo_root = Path(args.repo_root).resolve()
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    out_lines: list[str] = []

    for r in data.get("results", []):
        # Path normalization — Semgrep returns absolute or relative paths
        # depending on invocation; we always emit the path relative to
        # repo_root for stable canonical IDs across machines.
        raw_path = r.get("path", "")
        try:
            rel_path = str(Path(raw_path).resolve().relative_to(repo_root))
        except ValueError:
            rel_path = raw_path

        rule_id = r.get("check_id", "") or ""
        start = r.get("start", {}) or {}
        end = r.get("end", {}) or {}
        extra = r.get("extra", {}) or {}
        metadata = extra.get("metadata", {}) or {}

        line_start = int(start.get("line", 0) or 0)
        line_end = int(end.get("line", line_start) or line_start)

        cwes = extract_cwes(metadata)
        owasp_cats = extract_owasp_categories(metadata)
        severity = map_severity(extra.get("severity"), rule_id, metadata)
        confidence = map_confidence(metadata)
        framework_refs = enrich_framework_refs(cwes, cwe_table, owasp_cats)

        tags_raw = metadata.get("technology", [])
        if isinstance(tags_raw, str):
            tags = [tags_raw]
        elif isinstance(tags_raw, list):
            tags = [str(t) for t in tags_raw]
        else:
            tags = []

        # fix_complexity is a coarse hint for /securecoder-fix's gating
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
                str(metadata.get("fix") or extra.get("fix") or ""), 500
            ),
            "fix_complexity": fix_complexity,
            "tags": tags,
            "detected_at": now_iso,
            "status": "open",
            "history": [],
        }

        out_lines.append(json.dumps(finding))

    payload = "\n".join(out_lines) + ("\n" if out_lines else "")
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
