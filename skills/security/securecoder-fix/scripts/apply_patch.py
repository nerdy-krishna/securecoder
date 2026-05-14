#!/usr/bin/env python3
"""Apply SEARCH/REPLACE blocks to a target file atomically.

Parses SEARCH/REPLACE blocks (asvs-shell precedent) from a patch text,
validates each block has exactly one match in the target file's current
content, and writes the file in one shot when every block applies
cleanly. If any block fails to match, no write happens and the script
reports which block(s) failed via stderr (and JSON when --json is set).

The agent uses this as the deterministic core of /securecoder-fix's
per-fix loop — the LLM produces the patch text, this script either
applies all blocks or none of them.

Block syntax (must match exactly, byte-for-byte on the delimiter lines):

    <<<<<<< SEARCH
    <existing code to find>
    =======
    <replacement code>
    >>>>>>> REPLACE

Multiple blocks in one patch text are valid; each is applied in order
to the post-previous-block content of the file (in memory).

Stdlib only.

Usage:
    python3 apply_patch.py <target-file> --patch <patch-file> [--json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Strict regex: SEARCH and REPLACE delimiters on their own lines, with
# arbitrary content (greedy across newlines) between them.
BLOCK_RE = re.compile(
    r"^<{7} SEARCH\s*\n(?P<search>.*?)\n={7}\s*\n(?P<replace>.*?)\n>{7} REPLACE\s*$",
    re.MULTILINE | re.DOTALL,
)


def parse_blocks(patch_text: str) -> list:
    """Return a list of {search, replace} dicts in document order."""
    return [
        {"search": m.group("search"), "replace": m.group("replace")}
        for m in BLOCK_RE.finditer(patch_text)
    ]


def apply_blocks(content: str, blocks: list) -> tuple:
    """Apply all blocks to `content` in order. Returns (new_content, details).

    `details` is a list of per-block status dicts; if any block has a
    status other than "ok", `new_content` matches the original (i.e. no
    partial application happens).
    """
    working = content
    details: list = []
    for i, block in enumerate(blocks):
        search = block["search"]
        replace = block["replace"]
        match_count = working.count(search)
        if match_count == 0:
            details.append({
                "block_index": i,
                "status": "no_match",
                "search_preview": search.splitlines()[0][:120] if search else "",
            })
            return content, details
        if match_count > 1:
            details.append({
                "block_index": i,
                "status": "multiple_match",
                "match_count": match_count,
                "search_preview": search.splitlines()[0][:120] if search else "",
            })
            return content, details
        working = working.replace(search, replace, 1)
        details.append({"block_index": i, "status": "ok"})
    return working, details


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="Path to the file to patch")
    ap.add_argument("--patch", required=True, help="Path to the patch text file")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON to stdout")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse + validate, but do not write")
    args = ap.parse_args()

    target = Path(args.target)
    patch_path = Path(args.patch)

    if not target.is_file():
        result = {"status": "target_missing", "target": str(target)}
        sys.stdout.write(json.dumps(result) if args.json else f"target not found: {target}\n")
        sys.exit(2)

    patch_text = patch_path.read_text(encoding="utf-8")
    blocks = parse_blocks(patch_text)

    if not blocks:
        result = {
            "status": "no_blocks",
            "target": str(target),
            "blocks_total": 0,
            "blocks_applied": 0,
            "details": [],
        }
        sys.stdout.write(
            json.dumps(result) if args.json
            else "no SEARCH/REPLACE blocks found in patch\n"
        )
        sys.exit(3)

    original = target.read_text(encoding="utf-8")
    new_content, details = apply_blocks(original, blocks)

    bad = [d for d in details if d["status"] != "ok"]
    applied_count = sum(1 for d in details if d["status"] == "ok")
    overall_status = "ok" if not bad else bad[0]["status"]

    result = {
        "status": overall_status,
        "target": str(target),
        "blocks_total": len(blocks),
        "blocks_applied": applied_count if overall_status == "ok" else 0,
        "details": details,
    }

    if overall_status == "ok" and not args.dry_run:
        target.write_text(new_content, encoding="utf-8")

    if args.json:
        sys.stdout.write(json.dumps(result, indent=2))
    elif overall_status != "ok":
        for d in details:
            if d["status"] != "ok":
                sys.stderr.write(
                    f"block {d['block_index']}: {d['status']}"
                    + (f" (preview: {d.get('search_preview', '')})\n"
                       if "search_preview" in d else "\n")
                )

    sys.exit(0 if overall_status == "ok" else 1)


if __name__ == "__main__":
    main()
