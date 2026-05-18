#!/usr/bin/env python3
"""Reconcile the project-root `.gitignore` with securecoder's scan-output policy.

securecoder writes scan results under `.securecoder/runs/` and review results
under `.securecoder/reviews/`. Those directories hold the full vulnerability
picture of the codebase — sensitive, per-developer, and not meant to be pushed
to a shared remote. `.securecoder/config.json` and `.securecoder/suppressions.json`,
by contrast, are deliberately team-shared and stay tracked.

This script maintains a sentinel-fenced block in the project-root `.gitignore`
so the ignore rule is visible where developers actually look, idempotent across
re-runs, and removable cleanly. The strategy is driven by `git.gitignore_strategy`
in `.securecoder/config.json`:

    runs-and-reviews  — ignore `.securecoder/runs/` + `.securecoder/reviews/`
                        (sensitive output ignored, team config still shared)
    whole-folder      — ignore the entire `.securecoder/` directory
    none              — no managed block; remove it if present

A nested `.securecoder/.gitignore` (written by /securecoder-scan step A.12.a)
remains the always-on backstop; this root block is the visible layer on top.

Emitted JSON:

    {
      "strategy": "runs-and-reviews",
      "action": "created" | "updated" | "unchanged" | "removed" | "skipped_not_git",
      "gitignore_path": "/abs/path/.gitignore" | null,
      "tracked_files": ["..."],          # whole-folder only; already-tracked paths
      "tracked_warning": "<text>" | null
    }

Stdlib only.

Usage:
    python3 manage_gitignore.py <project-root> \\
        --strategy <runs-and-reviews|whole-folder|none> \\
        [--output <path>]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

#: Sentinel lines that fence the securecoder-managed region of the .gitignore.
BEGIN = "# >>> securecoder >>>"
END = "# <<< securecoder <<<"

STRATEGIES = ("runs-and-reviews", "whole-folder", "none")

#: Human-readable preamble written inside the fenced block.
_COMMENT = (
    "# securecoder scan output — local vulnerability data, not for commit.\n"
    "# Managed by securecoder; change via git.gitignore_strategy in "
    ".securecoder/config.json.\n"
)


def block_body(strategy: str) -> str:
    """Return the ignore lines for a strategy (no fence)."""
    if strategy == "runs-and-reviews":
        return ".securecoder/runs/\n.securecoder/reviews/\n"
    if strategy == "whole-folder":
        return ".securecoder/\n"
    raise ValueError(f"strategy {strategy!r} has no block body")


def render_block(strategy: str) -> str:
    """Full sentinel-fenced block, newline-terminated."""
    return f"{BEGIN}\n{_COMMENT}{block_body(strategy)}{END}\n"


def strip_block(text: str) -> tuple[str, bool]:
    """Remove an existing securecoder block. Returns (new_text, found).

    Matches the first BEGIN sentinel and the first END sentinel after it. A
    single blank separator line immediately preceding the block is dropped too,
    so repeated add/remove cycles don't accumulate blank lines.
    """
    lines = text.splitlines(keepends=True)
    start = end = None
    for i, line in enumerate(lines):
        if line.strip() == BEGIN and start is None:
            start = i
        elif line.strip() == END and start is not None:
            end = i
            break
    if start is None or end is None:
        return text, False
    before = lines[:start]
    after = lines[end + 1:]
    if before and before[-1].strip() == "":
        before = before[:-1]
    return "".join(before) + "".join(after), True


def apply_strategy(gitignore_path: Path, strategy: str) -> str:
    """Write the strategy into the gitignore. Returns the action taken.

    One of: "created", "updated", "unchanged", "removed".
    """
    existed = gitignore_path.exists()
    original = gitignore_path.read_text(encoding="utf-8") if existed else ""
    stripped, had_block = strip_block(original)

    if strategy == "none":
        if not had_block:
            return "unchanged"
        if stripped.strip() == "":
            # The block was the file's only content — remove the empty file.
            gitignore_path.unlink()
        else:
            gitignore_path.write_text(stripped, encoding="utf-8")
        return "removed"

    new_block = render_block(strategy)
    if stripped.strip() == "":
        new_text = new_block
    else:
        sep = "" if stripped.endswith("\n") else "\n"
        new_text = stripped + sep + "\n" + new_block

    if new_text == original:
        return "unchanged"
    gitignore_path.write_text(new_text, encoding="utf-8")
    return "updated" if existed else "created"


def is_git_repo(project_root: Path) -> bool:
    """True when project_root is inside a git working tree."""
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def tracked_securecoder_files(project_root: Path) -> list[str]:
    """Files under `.securecoder/` that git already tracks (sorted, may be empty)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "--", ".securecoder"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return sorted(ln for ln in r.stdout.splitlines() if ln.strip())


def emit(result: dict, output: str | None) -> None:
    payload = json.dumps(result, indent=2) + "\n"
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Reconcile the root .gitignore with securecoder's scan-output policy.")
    ap.add_argument("project_root", help="Project root (the git toplevel)")
    ap.add_argument("--strategy", required=True, choices=STRATEGIES,
                    help="gitignore strategy: runs-and-reviews | whole-folder | none")
    ap.add_argument("--output", "-o",
                    help="Write the JSON result here instead of stdout")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    gitignore_path = project_root / ".gitignore"

    result: dict = {
        "strategy": args.strategy,
        "action": None,
        "gitignore_path": str(gitignore_path),
        "tracked_files": [],
        "tracked_warning": None,
    }

    if not is_git_repo(project_root):
        # No git working tree — a root .gitignore would be meaningless.
        result["action"] = "skipped_not_git"
        result["gitignore_path"] = None
        emit(result, args.output)
        return

    result["action"] = apply_strategy(gitignore_path, args.strategy)

    if args.strategy == "whole-folder":
        tracked = tracked_securecoder_files(project_root)
        if tracked:
            result["tracked_files"] = tracked
            result["tracked_warning"] = (
                f"{len(tracked)} file(s) under .securecoder/ are already tracked "
                "by git and will keep being committed despite this ignore rule "
                "(.gitignore only affects untracked files). To untrack them run: "
                "git rm --cached -r .securecoder/ — note this also drops the "
                "team-shared config.json and suppressions.json from version control."
            )

    emit(result, args.output)


if __name__ == "__main__":
    main()
