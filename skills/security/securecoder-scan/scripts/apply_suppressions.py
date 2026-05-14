#!/usr/bin/env python3
"""Apply `.securecoder/suppressions.json` to a findings.jsonl in-place.

For each finding, walks every suppression entry, collects matches, and
applies most-specific-wins to pick the winning entry. The winning entry's
reason becomes the finding's `suppression_reason`; a `suppressions.json#<index>`
pointer becomes its `suppression_match`. Stamps `status: "suppressed"`.

Runs as the FINAL step of `/securecoder-scan` Phase A — after per-tool
normalize + per-tool merge, before manifest write. Downstream skills
(`/securecoder-fix`, `/securecoder-review`, `/securecoder-advise`) check
`status` rather than re-running matching logic.

Side-channel output (--stats): a small JSON summary used to populate the
manifest's `totals.findings_active` / `totals.findings_suppressed` /
`suppressed_by_entry` fields.

Stdlib only.

Usage:
    python3 apply_suppressions.py <findings-jsonl> \\
        --suppressions <suppressions-json> \\
        [--output <findings-jsonl>] \\
        [--stats <stats-json>]

If --suppressions points at a missing file or empty entries, this script
is a no-op pass-through: every finding keeps its original status, and
the stats JSON reports 0 suppressed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import sys
from pathlib import Path


SCHEMA_VERSION = "1.0"


def _today_utc() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _is_expired(entry: dict, today: dt.date) -> bool:
    """True if entry has an expires_at past today."""
    raw = entry.get("expires_at")
    if not raw:
        return False
    try:
        # Accept either YYYY-MM-DD or full ISO-8601
        if "T" in str(raw):
            exp = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        else:
            exp = dt.date.fromisoformat(str(raw))
    except ValueError:
        return False
    return exp < today


def _entry_matches_finding(entry: dict, finding: dict) -> bool:
    """True iff every populated match-field in the entry matches the finding.

    The match-field set is: id, rule, file, file_glob, framework_ref.
    Empty `match` (no fields populated) matches nothing — we refuse to treat
    a match-all entry as valid; users must specify at least one field.
    """
    match = entry.get("match", {}) or {}
    if not match:
        return False

    # id — exact canonical-ID match
    if "id" in match and finding.get("id") != match["id"]:
        return False

    # rule — matches source_rule_id
    if "rule" in match and finding.get("source_rule_id") != match["rule"]:
        return False

    # file — exact relative path
    if "file" in match and finding.get("file") != match["file"]:
        return False

    # file_glob — gitignore-style glob
    if "file_glob" in match:
        if not fnmatch.fnmatch(finding.get("file", ""), match["file_glob"]):
            return False

    # framework_ref — matches any entry in the finding's framework_refs list
    if "framework_ref" in match:
        # Expected format: "<framework>/<control_or_category>"
        ref = match["framework_ref"]
        if "/" in ref:
            fw, ctrl = ref.split("/", 1)
        else:
            fw, ctrl = ref, ""
        refs = finding.get("framework_refs", []) or []
        ok = False
        for r in refs:
            if r.get("framework") == fw:
                # Match either control or category
                if not ctrl or r.get("control") == ctrl or r.get("category") == ctrl:
                    ok = True
                    break
        if not ok:
            return False

    return True


def _specificity_score(entry: dict) -> int:
    """Lower score = more specific. See design.md §3.9 ranking table.

    Score 0 (most specific):  id present
    Score 1:                  rule + file
    Score 2:                  rule + file_glob
    Score 3:                  rule alone, or framework_ref alone
    Score 4 (least specific): file_glob alone

    The order matters for tie-breaking when multiple entries match a finding.
    """
    match = entry.get("match", {}) or {}
    if "id" in match:
        return 0
    has_rule = "rule" in match
    has_file = "file" in match
    has_file_glob = "file_glob" in match
    has_fw_ref = "framework_ref" in match
    if has_rule and has_file:
        return 1
    if has_rule and has_file_glob:
        return 2
    if has_rule or has_fw_ref:
        return 3
    if has_file_glob:
        return 4
    return 5  # match-all — shouldn't pass _entry_matches_finding's empty check


def _load_findings(path: Path) -> list:
    findings: list = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            findings.append(json.loads(line))
    return findings


def _write_findings(path, findings: list) -> None:
    out_lines = [json.dumps(f) for f in findings]
    payload = "\n".join(out_lines) + ("\n" if out_lines else "")
    if path is None:
        sys.stdout.write(payload)
    else:
        Path(path).write_text(payload, encoding="utf-8")


def apply_suppressions(findings: list, entries: list) -> tuple:
    """Mutate findings in place. Returns (findings, stats_dict).

    Stats include suppressed_by_entry (entry-index → count) and overall
    active/suppressed totals.
    """
    today = _today_utc()
    # Pre-compute (index, entry) pairs, skipping expired
    live: list = []
    for i, entry in enumerate(entries):
        if _is_expired(entry, today):
            continue
        live.append((i, entry))

    suppressed_by_entry: dict = {i: 0 for i, _ in live}
    active_count = 0

    for finding in findings:
        # Find every matching entry, pick the most-specific (lowest score)
        matches = [(i, e) for i, e in live if _entry_matches_finding(e, finding)]
        if not matches:
            # Leave status as-is (typically "open" from the normalizer)
            active_count += 1
            continue

        # Sort: ascending specificity score, ascending entry index (first-defined)
        matches.sort(key=lambda pair: (_specificity_score(pair[1]), pair[0]))
        winner_idx, winner = matches[0]

        finding["status"] = "suppressed"
        finding["suppression_reason"] = winner.get("reason", "")
        finding["suppression_match"] = f"suppressions.json#{winner_idx}"
        suppressed_by_entry[winner_idx] = suppressed_by_entry.get(winner_idx, 0) + 1

    total = len(findings)
    stats = {
        "totals": {
            "findings": total,
            "findings_active": active_count,
            "findings_suppressed": total - active_count,
        },
        "suppressed_by_entry": {str(k): v for k, v in suppressed_by_entry.items()},
    }
    return findings, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("findings", help="Path to findings.jsonl")
    ap.add_argument("--suppressions", required=True,
                    help="Path to .securecoder/suppressions.json")
    ap.add_argument("--output",
                    help="Write enriched JSONL here (default: stdout)")
    ap.add_argument("--stats",
                    help="Also write the suppressed_by_entry + totals JSON here")
    args = ap.parse_args()

    findings_path = Path(args.findings)
    if not findings_path.is_file():
        sys.stderr.write(f"findings.jsonl not found: {findings_path}\n")
        sys.exit(2)

    findings = _load_findings(findings_path)

    entries: list = []
    sup_path = Path(args.suppressions)
    if sup_path.is_file():
        try:
            blob = json.loads(sup_path.read_text(encoding="utf-8"))
            entries = blob.get("entries", []) or []
            file_schema = blob.get("schema_version", SCHEMA_VERSION)
            if file_schema != SCHEMA_VERSION:
                sys.stderr.write(
                    f"warning: suppressions.json schema_version is {file_schema}, "
                    f"expected {SCHEMA_VERSION}; proceeding best-effort\n"
                )
        except json.JSONDecodeError as e:
            sys.stderr.write(
                f"warning: suppressions.json could not be parsed ({e}); "
                f"treating as empty\n"
            )

    findings, stats = apply_suppressions(findings, entries)

    out_path = args.output if args.output else None
    _write_findings(out_path, findings)

    if args.stats:
        Path(args.stats).write_text(
            json.dumps(stats, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
