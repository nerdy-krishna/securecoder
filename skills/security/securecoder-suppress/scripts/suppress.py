#!/usr/bin/env python3
"""CLI for /securecoder-suppress — read and mutate .securecoder/suppressions.json.

Subcommands:
    show               list all current suppression entries
    show --stale       entries that didn't match anything in last scan
    show --expired     entries past their expires_at
    show --finding <id> which entry suppresses this finding (per last scan)
    add                append a new entry from a match expression + reason
    import             append a batch of entries from a JSON payload
    remove             delete one entry by index
    expire             remove entries past their expires_at (with confirm)

Each subcommand exits non-zero on usage errors or when the suppressions file
is missing for a mutate operation. `show` modes work on a missing file (treat
as zero entries).

Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path


SCHEMA_VERSION = "1.0"
SUP_PATH_REL = ".securecoder/suppressions.json"
LATEST_REL = ".securecoder/runs/latest"


def _today_utc() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _is_expired(entry: dict, today: dt.date) -> bool:
    raw = entry.get("expires_at")
    if not raw:
        return False
    try:
        if "T" in str(raw):
            exp = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        else:
            exp = dt.date.fromisoformat(str(raw))
    except ValueError:
        return False
    return exp < today


def _git_email(project_root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "config", "user.email"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "unknown@local"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown@local"


def _load_suppressions(path: Path) -> dict:
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "entries": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.stderr.write(f"warning: suppressions.json malformed ({e}); using empty\n")
        return {"schema_version": SCHEMA_VERSION, "entries": []}


def _save_suppressions(path: Path, blob: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob["schema_version"] = SCHEMA_VERSION
    path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")


def _parse_match_expr(expr: str) -> dict:
    """Parse `key=value and key=value ...` into a dict, or treat as JSON if it
    starts with '{'."""
    stripped = expr.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as e:
            raise ValueError(f"--match looked like JSON but failed to parse: {e}")
    out: dict = {}
    parts = re.split(r"\s+and\s+", stripped, flags=re.IGNORECASE)
    for p in parts:
        if "=" not in p:
            raise ValueError(f"--match expression term missing '=': {p!r}")
        k, _, v = p.partition("=")
        k = k.strip()
        v = v.strip().strip("'\"")
        if k not in {"id", "rule", "file", "file_glob", "framework_ref"}:
            raise ValueError(
                f"--match key {k!r} not recognized; allowed: "
                f"id, rule, file, file_glob, framework_ref"
            )
        out[k] = v
    if not out:
        raise ValueError("--match must specify at least one field")
    return out


def _entry_signature(entry: dict) -> str:
    """Stable string identifier for an entry — used for dedupe on import."""
    match = entry.get("match", {}) or {}
    parts = sorted(f"{k}={v}" for k, v in match.items())
    return "|".join(parts) + "::" + (entry.get("reason", "") or "")


def _resolve_paths():
    cwd = Path.cwd().resolve()
    # Walk up looking for .git or .securecoder
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").is_dir() or (parent / ".securecoder").is_dir():
            return parent
    return cwd


# ───────────────────────── subcommands ──────────────────────────


def cmd_show(args, project_root: Path) -> int:
    sup_path = project_root / SUP_PATH_REL
    blob = _load_suppressions(sup_path)
    entries = blob.get("entries", []) or []

    if args.finding:
        latest_findings = project_root / LATEST_REL / "findings.jsonl"
        if not latest_findings.is_file():
            sys.stderr.write(f"No latest scan run found at {latest_findings}\n")
            return 2
        target_id = args.finding
        with open(latest_findings, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                finding = json.loads(line)
                fid = finding.get("id", "")
                if fid == target_id or fid.startswith(target_id):
                    if finding.get("status") != "suppressed":
                        sys.stdout.write(
                            f"Finding {fid[:12]} is NOT suppressed (status: "
                            f"{finding.get('status', '?')})\n"
                        )
                        return 0
                    match_ref = finding.get("suppression_match", "")
                    reason = finding.get("suppression_reason", "(no reason)")
                    sys.stdout.write(
                        f"Finding {fid[:12]} is suppressed by {match_ref}\n"
                        f"  reason: {reason}\n"
                    )
                    # Look up the entry by index
                    idx = match_ref.split("#")[-1] if "#" in match_ref else ""
                    try:
                        idx_int = int(idx)
                        if 0 <= idx_int < len(entries):
                            sys.stdout.write(
                                f"  entry: {json.dumps(entries[idx_int], indent=2)}\n"
                            )
                    except ValueError:
                        pass
                    return 0
        sys.stdout.write(f"Finding {target_id} not found in latest scan.\n")
        return 0

    today = _today_utc()
    if args.expired:
        filtered = [
            (i, e) for i, e in enumerate(entries) if _is_expired(e, today)
        ]
        title = f"Expired suppression entries ({len(filtered)}):"
    elif args.stale:
        # Stale = entries with 0 matches in last run's manifest
        manifest_path = project_root / LATEST_REL / "manifest.json"
        if not manifest_path.is_file():
            sys.stderr.write(
                "No latest scan manifest; can't determine stale entries.\n"
            )
            return 2
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_entry = manifest.get("suppressed_by_entry", {}) or {}
        filtered = [
            (i, e) for i, e in enumerate(entries)
            if not _is_expired(e, today)
            and int(by_entry.get(str(i), 0)) == 0
        ]
        title = (
            f"Stale suppression entries ({len(filtered)} — matched nothing in "
            f"last scan):"
        )
    else:
        filtered = list(enumerate(entries))
        title = f"All suppression entries ({len(filtered)}):"

    sys.stdout.write(title + "\n\n")
    if not filtered:
        sys.stdout.write("  (none)\n")
        return 0
    for idx, entry in filtered:
        match_repr = " AND ".join(f"{k}={v!r}" for k, v in entry.get("match", {}).items())
        exp = entry.get("expires_at") or "(none)"
        sys.stdout.write(
            f"  [{idx}] {match_repr}\n"
            f"        reason:    {entry.get('reason', '(none)')}\n"
            f"        created:   {entry.get('created_at', '?')} by "
            f"{entry.get('created_by', '?')}\n"
            f"        expires:   {exp}\n\n"
        )
    return 0


def cmd_add(args, project_root: Path) -> int:
    try:
        match = _parse_match_expr(args.match)
    except ValueError as e:
        sys.stderr.write(f"error: {e}\n")
        return 2

    entry = {
        "match": match,
        "scope": args.scope,
        "reason": args.reason,
        "created_at": _now_utc_iso(),
        "created_by": args.created_by or _git_email(project_root),
        "expires_at": args.expires or None,
    }

    sup_path = project_root / SUP_PATH_REL
    blob = _load_suppressions(sup_path)
    entries = blob.setdefault("entries", [])

    sig = _entry_signature(entry)
    if any(_entry_signature(e) == sig for e in entries):
        sys.stderr.write(
            "warning: an entry with identical match + reason already exists; "
            "skipping add\n"
        )
        return 0

    entries.append(entry)
    _save_suppressions(sup_path, blob)
    sys.stdout.write(
        f"Added entry #{len(entries) - 1} to {sup_path}\n"
        f"  match:  {json.dumps(match)}\n"
        f"  reason: {entry['reason']}\n"
    )
    return 0


def cmd_import_(args, project_root: Path) -> int:
    payload = args.entries
    # Could be a path to a file or an inline JSON string
    text = payload
    if Path(payload).is_file():
        text = Path(payload).read_text(encoding="utf-8")
    try:
        incoming = json.loads(text)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"error: import payload not valid JSON ({e})\n")
        return 2
    if not isinstance(incoming, list):
        sys.stderr.write("error: import payload must be a JSON array\n")
        return 2

    sup_path = project_root / SUP_PATH_REL
    blob = _load_suppressions(sup_path)
    entries = blob.setdefault("entries", [])
    existing_sigs = {_entry_signature(e) for e in entries}

    added = 0
    skipped_dup = 0
    skipped_invalid = 0
    for raw in incoming:
        if not isinstance(raw, dict) or "match" not in raw:
            skipped_invalid += 1
            continue
        entry = {
            "match": raw["match"],
            "scope": raw.get("scope", "project"),
            "reason": raw.get("reason", "(no reason supplied)"),
            "created_at": raw.get("created_at") or _now_utc_iso(),
            "created_by": raw.get("created_by") or _git_email(project_root),
            "expires_at": raw.get("expires_at"),
        }
        sig = _entry_signature(entry)
        if sig in existing_sigs:
            skipped_dup += 1
            continue
        existing_sigs.add(sig)
        entries.append(entry)
        added += 1

    _save_suppressions(sup_path, blob)
    sys.stdout.write(
        f"Import to {sup_path}:\n"
        f"  added:           {added}\n"
        f"  skipped (dup):   {skipped_dup}\n"
        f"  skipped (bad):   {skipped_invalid}\n"
        f"  total entries:   {len(entries)}\n"
    )
    return 0


def cmd_remove(args, project_root: Path) -> int:
    sup_path = project_root / SUP_PATH_REL
    blob = _load_suppressions(sup_path)
    entries = blob.get("entries", []) or []
    idx = args.index
    if idx < 0 or idx >= len(entries):
        sys.stderr.write(
            f"error: index {idx} out of range (0..{len(entries) - 1})\n"
        )
        return 2
    removed = entries.pop(idx)
    _save_suppressions(sup_path, blob)
    sys.stdout.write(f"Removed entry #{idx}: {json.dumps(removed)}\n")
    return 0


def cmd_expire(args, project_root: Path) -> int:
    sup_path = project_root / SUP_PATH_REL
    blob = _load_suppressions(sup_path)
    entries = blob.get("entries", []) or []
    today = _today_utc()
    expired = [(i, e) for i, e in enumerate(entries) if _is_expired(e, today)]
    if not expired:
        sys.stdout.write("No entries past their expires_at. Nothing to do.\n")
        return 0

    sys.stdout.write(
        f"Will remove {len(expired)} expired entry/entries:\n\n"
    )
    for i, e in expired:
        sys.stdout.write(
            f"  [{i}] {json.dumps(e.get('match', {}))} (expired "
            f"{e.get('expires_at', '?')})\n"
        )
    sys.stdout.write("\n")

    if not args.yes:
        sys.stdout.write(
            "Re-run with --yes to apply, or use /securecoder-suppress remove "
            "<index> for specific entries.\n"
        )
        return 0

    blob["entries"] = [e for i, e in enumerate(entries) if not _is_expired(e, today)]
    _save_suppressions(sup_path, blob)
    sys.stdout.write(f"Removed {len(expired)} expired entries.\n")
    return 0


# ───────────────────────── main ──────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project-root", default=None,
                    help="Override project root (default: walk up from cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show")
    p_show.add_argument("--stale", action="store_true")
    p_show.add_argument("--expired", action="store_true")
    p_show.add_argument("--finding", help="Show entry that suppresses this finding ID")
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser("add")
    p_add.add_argument("--match", required=True,
                       help="Match expr: JSON or `key=value and key=value`")
    p_add.add_argument("--reason", required=True)
    p_add.add_argument("--scope", default="project")
    p_add.add_argument("--expires", default=None,
                       help="ISO date or full ISO-8601 timestamp (optional)")
    p_add.add_argument("--created-by", default=None,
                       help="Override author (default: git config user.email)")
    p_add.set_defaults(func=cmd_add)

    p_imp = sub.add_parser("import")
    p_imp.add_argument("--entries", required=True,
                       help="JSON array string OR path to file containing one")
    p_imp.set_defaults(func=cmd_import_)

    p_rem = sub.add_parser("remove")
    p_rem.add_argument("--index", type=int, required=True)
    p_rem.set_defaults(func=cmd_remove)

    p_exp = sub.add_parser("expire")
    p_exp.add_argument("--yes", action="store_true",
                       help="Skip confirmation and remove expired entries")
    p_exp.set_defaults(func=cmd_expire)

    args = ap.parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else _resolve_paths()

    sys.exit(args.func(args, project_root))


if __name__ == "__main__":
    main()
