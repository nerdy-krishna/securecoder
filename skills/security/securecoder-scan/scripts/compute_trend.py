#!/usr/bin/env python3
"""Compute new / resolved / persistent finding deltas vs the prior run.

Looks at sibling run directories under `.securecoder/runs/`, picks the
most recent run before the current one, and compares its findings to
the current run's findings by canonical ID.

Schema of emitted JSON:

    {
      "previous_run_id": "20260514T140000Z" | null,
      "new":         ["<id>", ...],
      "resolved":    ["<id>", ...],
      "persistent":  ["<id>", ...],
      "summary": {
        "new_count":        <int>,
        "resolved_count":   <int>,
        "persistent_count": <int>
      }
    }

When no prior run exists (first scan against this repo), `previous_run_id`
is `null` and all three lists are empty. The renderer interprets that as
"first run — no trend data yet."

Stdlib only.

Usage:
    python3 compute_trend.py <current-findings-jsonl> \\
        --runs-dir <path-to-.securecoder/runs/> \\
        --current-run-id <id> \\
        [--output <path>]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def load_finding_ids(path: Path) -> set:
    """Return the set of canonical IDs in a findings.jsonl file."""
    ids: set = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fid = obj.get("id")
                if fid:
                    ids.add(fid)
    except OSError:
        pass
    return ids


def find_prior_run(runs_dir: Path, current_run_id: str) -> str | None:
    """Return the run_id of the most recent run that's older than the
    current one and has a findings.jsonl. Returns None if no such run.
    """
    if not runs_dir.is_dir():
        return None
    candidates: list = []
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.is_symlink():
            continue  # ignore `latest` pointer
        name = entry.name
        if name == current_run_id:
            continue
        if not name[:1].isdigit():
            continue
        if not (entry / "findings.jsonl").is_file():
            continue
        candidates.append(name)
    candidates.sort()
    # Among candidates strictly less than current_run_id (lex sort matches
    # chronological order for ISO-like timestamps), pick the largest.
    prior_candidates = [c for c in candidates if c < current_run_id]
    return prior_candidates[-1] if prior_candidates else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("current_findings",
                    help="Path to the current run's findings.jsonl")
    ap.add_argument("--runs-dir", required=True,
                    help="Path to .securecoder/runs/")
    ap.add_argument("--current-run-id", required=True,
                    help="Run ID of the current run (e.g. 20260514T140000Z)")
    ap.add_argument("--output", "-o",
                    help="Write JSON here instead of stdout")
    args = ap.parse_args()

    current_path = Path(args.current_findings)
    runs_dir = Path(args.runs_dir)

    current_ids = load_finding_ids(current_path)
    prior_id = find_prior_run(runs_dir, args.current_run_id)

    if prior_id is None:
        result = {
            "previous_run_id": None,
            "new": [],
            "resolved": [],
            "persistent": [],
            "summary": {"new_count": 0, "resolved_count": 0, "persistent_count": 0},
        }
    else:
        prior_path = runs_dir / prior_id / "findings.jsonl"
        prior_ids = load_finding_ids(prior_path)

        new_ids = sorted(current_ids - prior_ids)
        resolved_ids = sorted(prior_ids - current_ids)
        persistent_ids = sorted(current_ids & prior_ids)

        result = {
            "previous_run_id": prior_id,
            "new": new_ids,
            "resolved": resolved_ids,
            "persistent": persistent_ids,
            "summary": {
                "new_count": len(new_ids),
                "resolved_count": len(resolved_ids),
                "persistent_count": len(persistent_ids),
            },
        }

    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
