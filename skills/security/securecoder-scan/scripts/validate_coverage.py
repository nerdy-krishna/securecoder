#!/usr/bin/env python3
"""Validate that an LLM compliance response covers every expected control.

The architect prompt instructs the model to produce a coverage matrix with
one row per control in the relevant chapter. This script:

  1. Parses the chapter's source markdown to extract every control ID
     (matches `**X.y.z**` tokens — the convention OWASP/ASVS uses in
     control table rows).
  2. Parses the LLM response to find every control ID mentioned in its
     coverage matrix.
  3. Emits a JSON status indicating whether all controls are covered, and
     if not, which IDs are missing. The caller uses missing IDs to compose
     a single retry prompt.

Stdlib only.

Usage:
    python3 validate_coverage.py <chapter-md-path> <llm-response-path> [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Matches **N.M.L** tokens used in OWASP/ASVS chapter control table rows.
CONTROL_TOKEN_RE = re.compile(r"\*\*(\d+\.\d+\.\d+)\*\*")
# Also matches bare X.Y.Z when used in LLM response coverage matrix
# (model often emits `V1.1.1` or `1.1.1` rather than `**1.1.1**`).
# Note: ASVS uses `V<chapter>.<section>.<control>` where the V prefix
# applies to the whole control id, not just the leading number — so we
# allow an optional `V` (no following digits) immediately before the
# X.Y.Z capture.
RESPONSE_CONTROL_RE = re.compile(r"\bV?(\d+\.\d+\.\d+)\b")


def extract_chapter_controls(chapter_md: str) -> list:
    return sorted(set(CONTROL_TOKEN_RE.findall(chapter_md)))


def extract_response_controls(response: str) -> list:
    # Only look inside lines that look like coverage matrix rows
    # (markdown table cells, starting with `|`), to avoid picking up
    # control IDs in prose / chapter excerpts the model might quote back.
    found: set = set()
    for line in response.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        for m in RESPONSE_CONTROL_RE.finditer(stripped):
            found.add(m.group(1))
    return sorted(found)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("chapter_md", help="Path to the chapter markdown file")
    ap.add_argument("response", help="Path to the LLM response file")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON to stdout")
    args = ap.parse_args()

    chapter_text = Path(args.chapter_md).read_text(encoding="utf-8")
    response_text = Path(args.response).read_text(encoding="utf-8")

    expected = extract_chapter_controls(chapter_text)
    found = extract_response_controls(response_text)
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))

    result = {
        "status": "ok" if not missing else "incomplete",
        "expected_count": len(expected),
        "found_count": len(found),
        "missing": missing,
        "extra": extra,
    }

    if args.json:
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
    else:
        if missing:
            sys.stderr.write(
                f"coverage incomplete: missing {len(missing)} controls: "
                + ", ".join(missing[:10])
                + (" ..." if len(missing) > 10 else "")
                + "\n"
            )

    sys.exit(0 if not missing else 1)


if __name__ == "__main__":
    main()
