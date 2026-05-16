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

Per-framework control-ID formats are supported via --chapter-regex and
--response-regex. Both default to the OWASP/ASVS three-number form, so
existing ASVS callers need no change. For frameworks with a different
ID shape (MASVS `MASVS-STORAGE-1`, secure-coding-essentials
`SCE-MEM-1`, etc.), the caller passes that framework's regexes — read
from `control_id_regex` / `control_id_response_regex` in frameworks.json.

Stdlib only.

Usage:
    python3 validate_coverage.py <chapter-md-path> <llm-response-path> \\
        [--chapter-regex <re>] [--response-regex <re>] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Defaults — OWASP/ASVS three-number form. The chapter form is bolded
# (**1.2.1**); the response form is lenient (allows an optional V prefix
# since the model often emits `V1.2.1`).
DEFAULT_CHAPTER_REGEX = r"\*\*(\d+\.\d+\.\d+)\*\*"
DEFAULT_RESPONSE_REGEX = r"\bV?(\d+\.\d+\.\d+)\b"


def extract_chapter_controls(chapter_md: str, chapter_regex: str = DEFAULT_CHAPTER_REGEX) -> list:
    return sorted(set(re.compile(chapter_regex).findall(chapter_md)))


def extract_response_controls(response: str, response_regex: str = DEFAULT_RESPONSE_REGEX) -> list:
    # Only look inside lines that look like coverage matrix rows
    # (markdown table cells, starting with `|`), to avoid picking up
    # control IDs in prose / chapter excerpts the model might quote back.
    compiled = re.compile(response_regex)
    found: set = set()
    for line in response.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        for m in compiled.finditer(stripped):
            found.add(m.group(1))
    return sorted(found)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("chapter_md", help="Path to the chapter markdown file")
    ap.add_argument("response", help="Path to the LLM response file")
    ap.add_argument("--chapter-regex", default=DEFAULT_CHAPTER_REGEX,
                    help="Regex with one capture group for control IDs in "
                         "chapter source. Default: OWASP/ASVS three-number form.")
    ap.add_argument("--response-regex", default=DEFAULT_RESPONSE_REGEX,
                    help="Regex with one capture group for control IDs in the "
                         "LLM response coverage matrix.")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON to stdout")
    args = ap.parse_args()

    chapter_text = Path(args.chapter_md).read_text(encoding="utf-8")
    response_text = Path(args.response).read_text(encoding="utf-8")

    expected = extract_chapter_controls(chapter_text, args.chapter_regex)
    found = extract_response_controls(response_text, args.response_regex)
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
