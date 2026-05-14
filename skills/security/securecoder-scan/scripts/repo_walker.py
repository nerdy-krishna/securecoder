#!/usr/bin/env python3
"""Walk a project directory and produce a JSON file inventory.

Used by /securecoder-scan to determine which files to scan and which
language-specific Semgrep rule packs to apply.

Stdlib only.

Usage:
    python3 repo_walker.py <project-root> [--output <path>]

Output (to stdout or the given path) is a JSON document with shape:
    {
      "root": "/abs/path/to/project",
      "files": [
        {"path": "src/api/auth.py", "language": "python",
         "lines": 142, "bytes": 4831},
        ...
      ],
      "languages": {"python": 84, "typescript": 12},
      "total_files": 96,
      "total_lines": 5432
    }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


# Directory names pruned from the walk entirely (vendored / generated / hidden).
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", ".tox", "target", "out", "vendor",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".next", ".nuxt", "coverage", ".cache",
    ".sccap", ".securecoder",
}

# File extension → language label. Extensions not present here are skipped.
LANG_MAP = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash",
    ".sql": "sql",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".less": "css",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".tf": "terraform", ".hcl": "terraform",
    ".dockerfile": "dockerfile",
}

MAX_BYTES = 200 * 1024  # files > 200 KB are skipped


def is_text(path: Path) -> bool:
    """Heuristic: at least 70% of the first 2 KB must be printable bytes."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
    except OSError:
        return False
    if not chunk:
        return True
    printable = sum(1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13))
    return printable / len(chunk) >= 0.7


def language_for(path: Path) -> str | None:
    """Return the language label for a path, or None if not source code."""
    if path.name.lower() == "dockerfile" or path.name.lower().startswith("dockerfile."):
        return "dockerfile"
    return LANG_MAP.get(path.suffix.lower())


def walk(root: Path) -> list[dict]:
    """Walk `root` recursively, returning a list of file records."""
    records: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs and any dot-prefixed dirs (e.g. .git, .venv) in-place
        # so os.walk doesn't descend into them.
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for name in filenames:
            full = Path(dirpath) / name
            # Minified web assets are noise.
            if name.endswith(".min.js") or name.endswith(".min.css"):
                continue
            try:
                size = full.stat().st_size
            except OSError:
                continue
            if size > MAX_BYTES:
                continue
            lang = language_for(full)
            if lang is None:
                continue
            if not is_text(full):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    line_count = sum(1 for _ in f)
            except OSError:
                continue
            records.append({
                "path": str(full.relative_to(root)),
                "language": lang,
                "lines": line_count,
                "bytes": size,
            })
    records.sort(key=lambda r: r["path"])
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", help="Project root to walk")
    ap.add_argument(
        "--output", "-o",
        help="Write JSON here instead of stdout",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write(f"error: not a directory: {root}\n")
        sys.exit(2)

    files = walk(root)
    lang_counts: dict[str, int] = {}
    total_lines = 0
    for f in files:
        lang_counts[f["language"]] = lang_counts.get(f["language"], 0) + 1
        total_lines += f["lines"]

    out = {
        "root": str(root),
        "files": files,
        "languages": dict(sorted(lang_counts.items(), key=lambda kv: -kv[1])),
        "total_files": len(files),
        "total_lines": total_lines,
    }

    payload = json.dumps(out, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
