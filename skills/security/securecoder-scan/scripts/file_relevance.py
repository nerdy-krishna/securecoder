#!/usr/bin/env python3
"""Determine which ASVS chapters apply to each file in a repo map.

Reads the chapter-relevance lookup table and a repo_map.json from the
walker, then emits the file × chapter dispatch list for the compliance
pass. A pair is included if:

  1. The chapter's `applies_to_languages` matches the file's language
     (or the chapter says `["all"]`).
  2. The file's language is not in the chapter's `excludes_languages`.
  3. If the chapter has `keyword_triggers`, at least one trigger appears
     in the file's content (case-insensitive substring). When the
     trigger list is empty, this check is skipped.

Pairs are emitted in the dispatch list as JSON; the SKILL.md flow
iterates over them and dispatches one LLM call per pair.

Stdlib only.

Usage:
    python3 file_relevance.py <repo-map.json> \\
        --chapter-relevance <path-to-chapter-relevance.json> \\
        --repo-root <path-to-project-root> \\
        [--chapters V1,V2,...] \\
        [--output <path>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def file_matches_chapter(file_record: dict, chapter: dict, content: str) -> bool:
    """True if (file, chapter) is a relevant pair to evaluate.

    Resolution order:
      1. excludes_languages — hard exclude, wins over everything.
      2. Unconditional fit — language in applies_to_languages (or "all"),
         optionally gated by keyword_triggers when that list is non-empty.
      3. Conditional fit — language in conditional_languages.languages AND
         the file contains one of conditional_languages.keyword_triggers.
         This is the FFI / unsafe escape hatch: a chapter that applies
         unconditionally to systems languages can still apply to a
         memory-managed language when that file does FFI or unsafe work.
    """
    lang = file_record.get("language", "")
    applies = chapter.get("applies_to_languages", []) or []
    excludes = chapter.get("excludes_languages", []) or []
    triggers = chapter.get("keyword_triggers", []) or []
    conditional = chapter.get("conditional_languages", {}) or {}

    # 1. Hard exclude
    if lang in excludes:
        return False

    haystack = content.lower()

    # 2. Unconditional fit
    if "all" in applies or lang in applies:
        # keyword_triggers, when present, gate even the unconditional set
        if triggers and not any(t.lower() in haystack for t in triggers):
            return False
        return True

    # 3. Conditional fit (escape hatch for languages outside applies_to)
    cond_langs = conditional.get("languages", []) or []
    cond_triggers = conditional.get("keyword_triggers", []) or []
    if lang in cond_langs and cond_triggers:
        if any(t.lower() in haystack for t in cond_triggers):
            return True

    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo_map", help="Path to repo_map.json from the walker")
    ap.add_argument("--chapter-relevance", required=True,
                    help="Path to chapter-relevance.json")
    ap.add_argument("--repo-root", required=True,
                    help="Project root; used to read file contents")
    ap.add_argument("--chapters",
                    help="Comma-separated chapter subset (e.g. V1,V11,V13). "
                         "Defaults to all chapters in the relevance table.")
    ap.add_argument("--output", "-o",
                    help="Write JSON here instead of stdout")
    args = ap.parse_args()

    with open(args.repo_map, encoding="utf-8") as f:
        repo_map = json.load(f)
    with open(args.chapter_relevance, encoding="utf-8") as f:
        relevance = json.load(f)
    chapters_table = relevance.get("_chapters", {})

    if args.chapters:
        chapter_subset = {c.strip().upper() for c in args.chapters.split(",")}
        chapters_table = {
            k: v for k, v in chapters_table.items() if k in chapter_subset
        }

    repo_root = Path(args.repo_root).resolve()
    pairs: list = []
    file_content_cache: dict = {}

    for file_record in repo_map.get("files", []):
        rel = file_record.get("path", "")
        full = repo_root / rel
        try:
            if rel not in file_content_cache:
                file_content_cache[rel] = full.read_text(
                    encoding="utf-8", errors="replace"
                )
        except OSError:
            continue
        content = file_content_cache[rel]

        for chap_id, chapter in chapters_table.items():
            if file_matches_chapter(file_record, chapter, content):
                pairs.append({
                    "file": rel,
                    "language": file_record.get("language", ""),
                    "lines": file_record.get("lines", 0),
                    "chapter_id": chap_id,
                    "chapter_title": chapter.get("title", ""),
                    "chapter_filename": chapter.get("filename", ""),
                })

    result = {
        "total_pairs": len(pairs),
        "total_files": repo_map.get("total_files", 0),
        "total_chapters_evaluated": len(chapters_table),
        "pairs": pairs,
    }

    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
