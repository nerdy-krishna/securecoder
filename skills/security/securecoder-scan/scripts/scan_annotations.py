#!/usr/bin/env python3
"""Walk a project for in-source suppression annotations and emit ephemeral
suppression entries that `apply_suppressions.py` merges with the persistent
`.securecoder/suppressions.json` ledger at match time.

Annotation syntax (v1.2.0):

    # securecoder: ignore
    # securecoder: ignore reason="dev-only path"
    # securecoder: ignore reason="..." expires="2027-01-01"

Same with `//` for JS/TS/Go/etc. Block comments (`/* ... */`) are NOT
recognized in v1.2.0 — only line comments.

Target-line resolution:
    - **Inline annotation** (code + annotation on the same line) →
      applies to that line.
    - **Comment-only line** annotation (whole line is just the
      comment) → applies to the NEXT non-blank, non-comment line.

The emitted entries use the `file + lines` match shape (specificity 1,
just below `id`). Each entry is tagged with `source: "annotation"` so
the report can distinguish them from config-file suppressions.

Stdlib only.

Usage:
    python3 scan_annotations.py <project-root> [--output <path>]

Output: JSON array of suppression entries (same shape as
`.securecoder/suppressions.json`'s `entries` array). When no
annotations are found, emits `[]`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path


# Matches a line-only annotation (just whitespace + comment + securecoder
# directive). The leading-whitespace group lets us know it's not inline.
LINE_ONLY_RE = re.compile(
    r"^\s*(?:#|//)\s*securecoder:\s*ignore\b(.*?)\s*$",
    re.IGNORECASE,
)

# Matches an inline annotation anywhere on a line.
INLINE_RE = re.compile(
    r"(?:#|//)\s*securecoder:\s*ignore\b(.*?)$",
    re.IGNORECASE,
)

# Parses key="value" pairs out of the annotation's trailing text.
KV_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


# Skip these dirs entirely (same set as repo_walker.py).
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", ".tox", "target", "out", "vendor",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".next", ".nuxt", "coverage", ".cache",
    ".sccap", ".securecoder",
}

# Extensions whose comment markers we recognize.
RECOGNIZED_EXTS = {
    ".py", ".rb", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml",
    ".tf", ".hcl", ".dockerfile", ".pl",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs",
    ".java", ".kt", ".kts", ".cs", ".swift", ".c", ".cpp", ".h",
    ".hpp", ".php", ".sql",
}


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _find_next_code_line(lines: list, after_idx: int) -> int | None:
    """Return the 1-based line number of the next non-blank, non-comment line
    after the 0-based `after_idx`, or None if there is none."""
    for j in range(after_idx + 1, len(lines)):
        s = lines[j].strip()
        if not s:
            continue
        # Skip lines that are entirely comment markers
        if s.startswith(("#", "//", "/*")):
            continue
        return j + 1
    return None


def _parse_attrs(text: str) -> dict:
    """Extract `reason=...` and `expires=...` from the trailing portion of
    the annotation."""
    return {k.lower(): v for k, v in KV_RE.findall(text or "")}


def scan_file(rel_path: str, content: str) -> list:
    """Return a list of ephemeral suppression entries for one file."""
    lines = content.splitlines()
    entries: list = []
    for i, line in enumerate(lines):
        # Try line-only first
        m = LINE_ONLY_RE.match(line)
        if m:
            attrs = _parse_attrs(m.group(1))
            target = _find_next_code_line(lines, i)
            if target is None:
                continue  # annotation at end of file
            entries.append({
                "match": {
                    "file": rel_path,
                    "lines": {"start": target, "end": target},
                },
                "scope": "project",
                "reason": attrs.get("reason", "(in-source annotation)"),
                "created_at": _now_iso(),
                "created_by": "<annotation>",
                "expires_at": attrs.get("expires") or None,
                "source": "annotation",
            })
            continue
        # Inline annotation — only valid if there's code before the marker.
        inline_m = INLINE_RE.search(line)
        if not inline_m:
            continue
        # Distinguish inline from line-only by checking what comes before the
        # comment marker. Line-only would have been caught above; inline means
        # the line has non-whitespace content before the marker.
        marker_pos = inline_m.start()
        before = line[:marker_pos]
        if not before.strip():
            continue  # actually line-only, already handled
        attrs = _parse_attrs(inline_m.group(1))
        line_no = i + 1  # 1-based
        entries.append({
            "match": {
                "file": rel_path,
                "lines": {"start": line_no, "end": line_no},
            },
            "scope": "project",
            "reason": attrs.get("reason", "(in-source annotation)"),
            "created_at": _now_iso(),
            "created_by": "<annotation>",
            "expires_at": attrs.get("expires") or None,
            "source": "annotation",
        })
    return entries


def walk_project(root: Path) -> list:
    """Walk the project tree and scan every recognized-extension file."""
    all_entries: list = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for name in filenames:
            full = Path(dirpath) / name
            ext = full.suffix.lower()
            # Also recognize Dockerfile by name
            if ext not in RECOGNIZED_EXTS and name.lower() != "dockerfile":
                continue
            try:
                # Don't read huge files (> 200 KB)
                if full.stat().st_size > 200 * 1024:
                    continue
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(full.relative_to(root))
            entries = scan_file(rel, text)
            all_entries.extend(entries)
    return all_entries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", help="Project root to scan")
    ap.add_argument("--output", "-o",
                    help="Write JSON array here instead of stdout")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write(f"error: not a directory: {root}\n")
        sys.exit(2)

    entries = walk_project(root)
    payload = json.dumps(entries, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
