#!/usr/bin/env python3
"""Parse `git diff` unified output into per-file changed line ranges.

Emits a JSON document describing, for each touched file, the line ranges
of additions (post-image numbering) and a ±N-line context window around
each range. /securecoder-review uses this to:

  - Constrain Semgrep / Bandit / Gitleaks invocations to only changed files
  - Send only changed hunks + ±20 lines context to the compliance LLM
    (cost proportional to diff size, not repo size)

Stdlib only.

Usage:
    git diff --cached | python3 diff_scoper.py --repo-root <path> [--context 20] [--output <path>]
    git diff main...HEAD | python3 diff_scoper.py --repo-root <path>

Schema of emitted JSON:

    {
      "files": [
        {
          "path": "src/api/auth.py",
          "added_ranges": [{"start": 42, "end": 58}, ...],
          "context_windows": [{"start": 22, "end": 78}, ...],
          "added_line_count": 17,
          "removed_line_count": 3,
          "is_new": false,
          "is_deleted": false
        }
      ],
      "total_files": 3,
      "total_added_lines": 47,
      "total_removed_lines": 12
    }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Matches a hunk header: @@ -OLD_START,OLD_COUNT +NEW_START,NEW_COUNT @@
HUNK_HEADER_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)
# Matches a file header line: +++ b/path/to/file
FILE_HEADER_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
# Matches the alternate (old-side) file header: --- a/path
OLD_FILE_HEADER_RE = re.compile(r"^--- (?:b/)?(.+)$")
# `/dev/null` paths indicate new files or deletions
NEW_DELETE_MARKER = "/dev/null"


def parse_diff(text: str) -> list:
    """Parse a unified-format `git diff` and yield per-file records."""
    files: list = []
    current: dict | None = None
    is_new = False
    is_deleted = False
    line_iter = iter(text.splitlines())
    for line in line_iter:
        if line.startswith("diff --git"):
            if current is not None:
                files.append(current)
            current = None
            is_new = False
            is_deleted = False
            continue
        m_old = OLD_FILE_HEADER_RE.match(line)
        if m_old:
            if m_old.group(1).endswith(NEW_DELETE_MARKER):
                is_new = True
            continue
        m_new = FILE_HEADER_RE.match(line)
        if m_new:
            path = m_new.group(1)
            if path.endswith(NEW_DELETE_MARKER):
                is_deleted = True
                path = ""
            current = {
                "path": path,
                "added_ranges": [],
                "context_windows": [],
                "added_line_count": 0,
                "removed_line_count": 0,
                "is_new": is_new,
                "is_deleted": is_deleted,
            }
            continue
        m_hunk = HUNK_HEADER_RE.match(line)
        if m_hunk and current is not None:
            new_start = int(m_hunk.group(3))
            new_count = int(m_hunk.group(4) or "1")
            # Walk the hunk body to compute added/removed counts and the
            # post-image line ranges of *added* lines.
            cursor = new_start
            range_start: int | None = None
            range_end: int | None = None
            while True:
                try:
                    next_line = next(line_iter)
                except StopIteration:
                    break
                if next_line.startswith("@@") or next_line.startswith("diff --git"):
                    # End of this hunk; back-feed (we can't true peek without OOB
                    # state, so we accept that the outer loop continues with a
                    # missed line — re-process below).
                    if next_line.startswith("@@") and current is not None:
                        # Re-handle this hunk header in the outer loop logic
                        # by recursing manually.
                        m2 = HUNK_HEADER_RE.match(next_line)
                        if m2:
                            # Flush any open range first.
                            if range_start is not None:
                                current["added_ranges"].append({
                                    "start": range_start, "end": range_end or range_start
                                })
                            new_start = int(m2.group(3))
                            cursor = new_start
                            range_start = None
                            range_end = None
                            continue
                    elif next_line.startswith("diff --git"):
                        # New file — flush and stop hunk
                        if range_start is not None:
                            current["added_ranges"].append({
                                "start": range_start, "end": range_end or range_start
                            })
                            range_start = None
                            range_end = None
                        files.append(current)
                        current = None
                        is_new = False
                        is_deleted = False
                        break
                if next_line.startswith("+") and not next_line.startswith("+++"):
                    current["added_line_count"] += 1
                    if range_start is None:
                        range_start = cursor
                        range_end = cursor
                    else:
                        range_end = cursor
                    cursor += 1
                elif next_line.startswith("-") and not next_line.startswith("---"):
                    current["removed_line_count"] += 1
                    # Removed lines don't advance the new-side cursor.
                elif next_line.startswith(" ") or next_line == "":
                    # Context — flush open range
                    if range_start is not None:
                        current["added_ranges"].append({
                            "start": range_start, "end": range_end or range_start
                        })
                        range_start = None
                        range_end = None
                    cursor += 1
                else:
                    # Unknown line type; stop this hunk
                    break
            if range_start is not None:
                current["added_ranges"].append({
                    "start": range_start, "end": range_end or range_start
                })
    if current is not None:
        files.append(current)
    return [f for f in files if f.get("path") and not f.get("is_deleted")]


def add_context_windows(files: list, context: int) -> None:
    """Merge overlapping or adjacent ±context windows around each
    added-range and store the merged spans on the file record."""
    for f in files:
        windows: list = []
        for r in f["added_ranges"]:
            windows.append({
                "start": max(1, r["start"] - context),
                "end": r["end"] + context,
            })
        # Merge overlapping windows
        windows.sort(key=lambda w: w["start"])
        merged: list = []
        for w in windows:
            if merged and w["start"] <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], w["end"])
            else:
                merged.append(dict(w))
        f["context_windows"] = merged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", required=True,
                    help="Project root (for context-window line capping)")
    ap.add_argument("--context", type=int, default=20,
                    help="Lines of context around each changed range (default 20)")
    ap.add_argument("--output", "-o",
                    help="Write JSON here instead of stdout")
    args = ap.parse_args()

    text = sys.stdin.read()
    files = parse_diff(text)
    add_context_windows(files, args.context)

    result = {
        "files": files,
        "total_files": len(files),
        "total_added_lines": sum(f["added_line_count"] for f in files),
        "total_removed_lines": sum(f["removed_line_count"] for f in files),
    }

    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
