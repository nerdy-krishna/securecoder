#!/usr/bin/env python3
"""Normalize an LLM compliance response into findings.jsonl (schema v1.0).

The architect prompt instructs the model to emit a JSON array of finding
objects (only `Fail` rows from the coverage matrix). This script extracts
that JSON array from the response, validates each entry, enriches with
canonical IDs and framework refs, and emits one finding per line.

The JSON array can be embedded in markdown fences, prose, or anywhere
else in the response — we find it via a balanced-bracket scan that
prefers the largest candidate array containing valid finding objects.

Stdlib only.

Usage:
    python3 normalize_compliance.py <llm-response-path> \\
        --framework asvs-v5 \\
        --chapter-id V1 \\
        --cwe-table <path-to-cwe-to-framework.json> \\
        --repo-root <path-to-project-root> \\
        [--output <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


# Matches plausible JSON arrays in the response — used as candidate
# starting points for the balanced-bracket scan.
ARRAY_CANDIDATE_RE = re.compile(r"\[")


def find_findings_array(response_text: str) -> list:
    """Extract the model's emitted findings array from arbitrary response
    text. Strategy: try each `[` in the text as a starting point, scan
    for a balanced closing bracket, attempt to parse the slice as JSON.
    Return the longest valid array containing at least one dict with a
    `control` key (the architect prompt's required shape).
    """
    best: list = []
    for start_match in ARRAY_CANDIDATE_RE.finditer(response_text):
        start = start_match.start()
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(response_text[start:], start):
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    candidate = response_text[start:i + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if (
                        isinstance(parsed, list)
                        and parsed
                        and isinstance(parsed[0], dict)
                        and "control" in parsed[0]
                    ):
                        if len(parsed) > len(best):
                            best = parsed
                    break
        # else: depth never returned to 0; abandon this candidate
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("response", help="Path to the LLM response file")
    ap.add_argument("--framework", required=True,
                    help="Framework identifier (e.g. asvs-v5)")
    ap.add_argument("--chapter-id", required=True,
                    help="Chapter identifier (e.g. V1)")
    ap.add_argument("--cwe-table", required=True,
                    help="Path to cwe-to-framework.json")
    ap.add_argument("--repo-root", required=True,
                    help="Project root; used to normalize file paths")
    ap.add_argument("--output", "-o",
                    help="Write JSONL here instead of stdout")
    args = ap.parse_args()

    response_text = Path(args.response).read_text(encoding="utf-8")
    findings_raw = find_findings_array(response_text)
    cwe_table = load_cwe_table(args.cwe_table)
    repo_root = Path(args.repo_root).resolve()
    now = utc_now_iso()

    findings: list = []
    for raw in findings_raw:
        if not isinstance(raw, dict):
            continue
        control = str(raw.get("control") or "").strip()
        if not control:
            continue
        # Normalize control IDs like "1.2.1" → "V1.2.1" if the chapter
        # prefix is missing.
        if not control.upper().startswith("V"):
            control = f"{args.chapter_id}.{control}" if "." in control else f"{args.chapter_id}.{control}"
        elif "." not in control[1:].split(".", 1)[0]:
            # Already has V prefix, leave it
            pass

        rel_path = normalize_path(raw.get("file", ""), repo_root)
        lines = raw.get("lines") or {}
        if not isinstance(lines, dict):
            lines = {}
        line_start = lines.get("start") if lines else None
        line_end = lines.get("end") if lines else line_start

        severity = str(raw.get("severity", "medium")).lower()
        if severity not in ("critical", "high", "medium", "low", "info"):
            severity = "medium"
        confidence = str(raw.get("confidence", "medium")).lower()
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        fix_complexity = str(raw.get("fix_complexity", "medium")).lower()
        if fix_complexity not in ("low", "medium", "high"):
            fix_complexity = "medium"

        # framework_refs always includes the explicit framework+control
        framework_refs = enrich_framework_refs(
            [],  # compliance findings don't have CWEs from the LLM by default
            cwe_table,
            extra_refs=[{"framework": args.framework, "control": control}],
        )

        finding = {
            "id": canonical_id(rel_path, 0, f"{args.framework}|{control}"),
            "file": rel_path,
            "lines": (
                {"start": int(line_start), "end": int(line_end or line_start)}
                if line_start else None
            ),
            "source": args.framework,
            "source_rule_id": control,
            "category": "compliance",
            "cwe": [],
            "framework_refs": framework_refs,
            "severity": severity,
            "confidence": confidence,
            "title": truncate(raw.get("title", control), 200),
            "description": truncate(raw.get("description", ""), 500),
            "evidence": truncate(raw.get("evidence", ""), 500),
            "remediation_hint": truncate(raw.get("remediation_hint", ""), 500),
            "fix_complexity": fix_complexity,
            "tags": [args.framework, args.chapter_id, "compliance"],
            "detected_at": now,
            "status": "open",
            "history": [],
        }
        findings.append(finding)

    emit_findings(findings, args.output)


if __name__ == "__main__":
    main()
