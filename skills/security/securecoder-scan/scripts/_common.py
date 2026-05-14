#!/usr/bin/env python3
"""Shared utilities for securecoder SAST normalizers.

Imported by normalize_semgrep.py, normalize_bandit.py, normalize_gitleaks.py,
and normalize_osv.py. Stdlib only.

This module ships inside the /securecoder-scan skill directory; each
normalizer prepends its parent dir to sys.path before importing so the
scripts work regardless of how the agent invokes them.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path


# Matches CWE identifiers like "CWE-89", "cwe-89", "CWE 89" in arbitrary text.
CWE_TOKEN_RE = re.compile(r"\bCWE[-\s]?(\d+)\b", re.IGNORECASE)

# Matches OWASP Top 10 category prefixes like "A03", "A1", "A10".
OWASP_CAT_RE = re.compile(r"\b(A(?:0?\d|1[0-2]))\b")


def canonical_id(file: str, line_start: int, rule_id: str) -> str:
    """SAST canonical ID per design.md §4 — sha256(file|line_start|rule_id).

    Stable across runs: same (file, line_start, rule_id) → same ID. Lets
    /securecoder-fix and the report renderer match findings across runs
    for trend tracking and history carry-over.
    """
    h = hashlib.sha256()
    h.update(f"{file}|{line_start}|{rule_id}".encode("utf-8"))
    return h.hexdigest()


def truncate(s, n: int) -> str:
    """Return s clipped to n characters with an ellipsis if truncated."""
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def humanize_rule_id(rule_id: str) -> str:
    """Convert `python.django.security.xss-raw` to `Xss Raw`."""
    if not rule_id:
        return ""
    tail = rule_id.rsplit(".", 1)[-1] if "." in rule_id else rule_id
    words = tail.replace("_", "-").split("-")
    return " ".join(w.capitalize() for w in words if w)


def extract_cwes(value) -> list:
    """Pull canonical CWE-N tokens from a CWE field that may be a string,
    list of strings, list of dicts with `id`, or arbitrary nested junk."""
    found: list = []
    items = value if isinstance(value, list) else [value]
    for item in items:
        if isinstance(item, dict):
            cwe_id = item.get("id")
            if cwe_id is not None:
                tok = f"CWE-{cwe_id}" if not str(cwe_id).upper().startswith("CWE") else str(cwe_id).upper()
                if tok not in found:
                    found.append(tok)
            continue
        for m in CWE_TOKEN_RE.finditer(str(item or "")):
            tok = f"CWE-{m.group(1)}"
            if tok not in found:
                found.append(tok)
    return found


def extract_owasp_categories(value) -> list:
    """Pull OWASP Top 10 category tokens (A01-A12) from arbitrary text."""
    items = value if isinstance(value, list) else [value]
    found: list = []
    for item in items:
        for m in OWASP_CAT_RE.finditer(str(item or "")):
            tok = m.group(1)
            if len(tok) == 2:  # "A1" → "A01"
                tok = "A0" + tok[1]
            if tok not in found:
                found.append(tok)
    return found


def enrich_framework_refs(cwes: list, cwe_table: dict, extra_refs=None) -> list:
    """Merge framework refs from the CWE table with any extras the caller
    provides. Dedupes by (framework, control|category) tuple while
    preserving insertion order.
    """
    refs: list = []
    seen: set = set()

    def add(ref: dict) -> None:
        key = (ref.get("framework"), ref.get("control") or ref.get("category"))
        if key not in seen:
            seen.add(key)
            refs.append(dict(ref))

    for cwe in cwes:
        entry = cwe_table.get(cwe)
        if not entry:
            continue
        for r in entry.get("framework_refs", []):
            add(r)

    if extra_refs:
        for r in extra_refs:
            add(r)

    return refs


def normalize_path(raw_path, repo_root: Path) -> str:
    """Convert a tool's reported path to a project-root-relative path.

    If the path cannot be resolved relative to repo_root (e.g. it's in a
    different directory tree), return it unchanged.
    """
    if not raw_path:
        return ""
    try:
        return str(Path(raw_path).resolve().relative_to(repo_root))
    except ValueError:
        return str(raw_path)


def utc_now_iso() -> str:
    """ISO-8601 UTC timestamp at seconds precision (no microseconds)."""
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_cwe_table(path: str) -> dict:
    """Load and lightly validate the CWE-to-framework lookup table."""
    with open(path, encoding="utf-8") as f:
        table = json.load(f)
    return {k: v for k, v in table.items() if not k.startswith("_")}


def emit_findings(findings: list, output: str | None) -> None:
    """Write findings as JSONL to the given path, or stdout if None."""
    import sys
    payload = "\n".join(json.dumps(f) for f in findings)
    if findings:
        payload += "\n"
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
