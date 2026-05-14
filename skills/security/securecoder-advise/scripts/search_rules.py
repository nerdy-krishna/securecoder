#!/usr/bin/env python3
"""Keyword search across cached securecoder framework markdown.

Scans files under ~/.cache/securecoder/rules/frameworks/ and returns the
top-N matching sections (sections are delimited by markdown headings).
A match is scored by:
  - keyword occurrences in section body (heavy weight)
  - keyword occurrences in section heading (medium weight)
  - control IDs near matches (light bonus)

Used by /securecoder-advise to ground answers in the actual framework
text rather than the host LLM's training-time recollection.

Stdlib only.

Usage:
    python3 search_rules.py "<query>" [--framework asvs-v5] \\
        [--top 5] [--cache-root <path>] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


# Markdown heading detector — captures level + heading text.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# ASVS-style control token (e.g. V1.2.1, V12.3.4)
CONTROL_RE = re.compile(r"\b(V\d+\.\d+\.\d+)\b")


def default_cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "securecoder" / "rules" / "frameworks"
    return Path.home() / ".cache" / "securecoder" / "rules" / "frameworks"


def split_sections(content: str) -> list:
    """Split markdown into sections delimited by headings."""
    lines = content.splitlines()
    sections: list = []
    current_heading = ""
    current_level = 1
    current_lines: list = []
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            # Flush previous
            if current_lines or current_heading:
                sections.append({
                    "heading": current_heading,
                    "level": current_level,
                    "body": "\n".join(current_lines).strip(),
                })
            current_heading = m.group(2).strip()
            current_level = len(m.group(1))
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines or current_heading:
        sections.append({
            "heading": current_heading,
            "level": current_level,
            "body": "\n".join(current_lines).strip(),
        })
    return sections


def score_section(section: dict, terms: list) -> float:
    body = section["body"].lower()
    heading = section["heading"].lower()
    score = 0.0
    for t in terms:
        score += body.count(t) * 1.0
        score += heading.count(t) * 3.0
    # Bonus for sections containing control IDs (they're more
    # actionable than chapter-prose sections without controls)
    if CONTROL_RE.search(section["body"]):
        score += 0.5
    return score


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("query", help="Search query (space-separated terms)")
    ap.add_argument("--framework",
                    help="Restrict to a single framework (e.g. asvs-v5)")
    ap.add_argument("--top", type=int, default=5,
                    help="Number of results to return (default 5)")
    ap.add_argument("--cache-root",
                    help="Override the cache root (default per-OS)")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON")
    args = ap.parse_args()

    cache_root = Path(args.cache_root or default_cache_root())
    if not cache_root.is_dir():
        sys.stderr.write(
            f"No framework cache at {cache_root}. Run /securecoder-scan "
            "with a compliance mode to populate it.\n"
        )
        sys.exit(2)

    framework_dirs: list = []
    if args.framework:
        # Look for any subdir starting with the framework token, e.g.
        # asvs/<sha>/ → use the deepest dir under asvs/ that exists.
        roots = list((cache_root / args.framework.replace("-v5", "")).glob("*"))
        for r in roots:
            if r.is_dir():
                framework_dirs.append(r)
    else:
        for top in cache_root.iterdir():
            if top.is_dir():
                for sub in top.iterdir():
                    if sub.is_dir():
                        framework_dirs.append(sub)

    if not framework_dirs:
        sys.stderr.write("No framework directories found under cache root.\n")
        sys.exit(2)

    terms = [t.lower() for t in args.query.split() if t.strip()]
    if not terms:
        sys.exit(0)

    results: list = []
    for fw_dir in framework_dirs:
        for md_file in fw_dir.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for section in split_sections(text):
                score = score_section(section, terms)
                if score > 0:
                    controls = CONTROL_RE.findall(section["body"])
                    results.append({
                        "file": str(md_file.relative_to(cache_root)),
                        "heading": section["heading"],
                        "level": section["level"],
                        "score": score,
                        "controls": sorted(set(controls)),
                        "body_preview": section["body"][:400],
                    })

    results.sort(key=lambda r: -r["score"])
    top_results = results[: args.top]

    if args.json:
        sys.stdout.write(json.dumps({
            "query": args.query,
            "total_matches": len(results),
            "results": top_results,
        }, indent=2) + "\n")
    else:
        if not top_results:
            sys.stdout.write(f"No matches for: {args.query}\n")
            return
        sys.stdout.write(f"Top {len(top_results)} matches for: {args.query}\n\n")
        for r in top_results:
            sys.stdout.write(f"### {r['heading']}  (score {r['score']:.1f})\n")
            sys.stdout.write(f"_File:_ `{r['file']}`\n")
            if r["controls"]:
                sys.stdout.write(f"_Controls:_ {', '.join(r['controls'])}\n")
            sys.stdout.write("\n" + r["body_preview"] + "\n\n---\n\n")


if __name__ == "__main__":
    main()
