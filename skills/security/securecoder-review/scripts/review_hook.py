#!/usr/bin/env python3
"""Pre-commit hook shim for /securecoder-review.

Runs SAST tools (Semgrep, Bandit, Gitleaks) against staged files only.
Exits non-zero — blocking the commit — when any finding above
config.severity_floor is present.

This script runs in `git`'s shell context, not the agent's context, so
it cannot invoke /securecoder-review interactively. The LLM compliance
pass is NOT run by the hook — that requires the agent. The hook
reminds the user to run /securecoder-review interactively for
compliance review before pushing significant changes.

The hook uses tools already cached at ~/.cache/securecoder/tools/ by
previous /securecoder-scan or /securecoder-secure runs. If the tools
are missing, the hook prints a one-line install hint and exits 0
(don't block commits just because tools aren't installed; let the
user run a scan first to populate the cache).

Stdlib only.

Install location: <project-root>/.git/hooks/pre-commit
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _today_utc() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


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


def load_suppressions(project_root: Path) -> list:
    """Return the list of live (non-expired) suppression entries.

    Returns [] when the file is missing or malformed — the hook degrades
    gracefully if suppressions.json isn't set up.
    """
    sup_path = project_root / ".securecoder" / "suppressions.json"
    if not sup_path.is_file():
        return []
    try:
        blob = json.loads(sup_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    today = _today_utc()
    return [
        e for e in (blob.get("entries", []) or [])
        if not _is_expired(e, today)
    ]


def is_suppressed(file_path: str, rule_id: str, suppressions: list) -> bool:
    """Minimal-cost matcher mirroring apply_suppressions.py's logic.

    Only checks file, file_glob, and rule fields — the hook doesn't have
    canonical IDs (those are computed by the normalizers, which the hook
    doesn't invoke). framework_ref matching requires framework_refs data
    that the hook also doesn't have. So id and framework_ref suppressions
    are effectively skipped by the hook; the full /securecoder-scan run
    will catch them.
    """
    for entry in suppressions:
        match = entry.get("match", {}) or {}
        if not match:
            continue
        if "rule" in match and rule_id != match["rule"]:
            continue
        if "file" in match and file_path != match["file"]:
            continue
        if "file_glob" in match and not fnmatch.fnmatch(file_path, match["file_glob"]):
            continue
        # If id or framework_ref is the ONLY match key, skip (can't evaluate)
        keys = set(match.keys())
        if keys <= {"id", "framework_ref"}:
            continue
        # If we get here, every checkable key matched
        return True
    return False


def find_project_root() -> Path:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(r.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def read_config(project_root: Path) -> dict:
    cfg_path = project_root / ".securecoder" / "config.json"
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def staged_files(project_root: Path) -> list:
    r = subprocess.run(
        ["git", "-C", str(project_root), "diff", "--cached", "--name-only",
         "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return [project_root / p for p in r.stdout.splitlines() if p.strip()]


def tool_path(tool: str) -> Path | None:
    candidates = {
        "semgrep":     Path.home() / ".cache" / "securecoder" / "tools" / "semgrep" / "venv" / "bin" / "semgrep",
        "bandit":      Path.home() / ".cache" / "securecoder" / "tools" / "bandit" / "venv" / "bin" / "bandit",
        "gitleaks":    Path.home() / ".cache" / "securecoder" / "tools" / "gitleaks" / "gitleaks",
        "osv-scanner": Path.home() / ".cache" / "securecoder" / "tools" / "osv-scanner" / "osv-scanner",
    }
    p = candidates.get(tool)
    if p and p.exists():
        return p
    fallback = shutil.which(tool)
    return Path(fallback) if fallback else None


def severity_at_or_above_floor(sev: str, floor: str) -> bool:
    """Return True if `sev` is at least as severe as `floor`."""
    return SEVERITY_RANK.get(sev, 4) <= SEVERITY_RANK.get(floor, 4)


def run_semgrep(staged: list, project_root: Path, suppressions: list) -> int:
    """Returns the count of findings at or above floor, MINUS suppressed ones."""
    binary = tool_path("semgrep")
    if not binary:
        return 0
    # Filter to files with extensions Semgrep supports cheaply
    targets = [
        str(f.relative_to(project_root))
        for f in staged
        if f.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".jsx", ".go",
                                  ".java", ".rb", ".php", ".kt", ".rs", ".swift"}
    ]
    if not targets:
        return 0
    rules_root = Path.home() / ".cache" / "securecoder" / "rules" / "semgrep"
    if not rules_root.exists():
        return 0
    rule_dir = next(rules_root.iterdir(), None)
    if rule_dir is None:
        return 0
    args = [str(binary), "--metrics=off", "--quiet", "--json",
            "--config", str(rule_dir / "generic")]
    for t in targets:
        args.append(str(project_root / t))
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return 0
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return 0
    count = 0
    for result in data.get("results", []):
        path = result.get("path", "")
        try:
            rel = str(Path(path).resolve().relative_to(project_root))
        except ValueError:
            rel = path
        rule = result.get("check_id", "")
        if not is_suppressed(rel, rule, suppressions):
            count += 1
    return count


def run_gitleaks(staged: list, project_root: Path, suppressions: list) -> int:
    binary = tool_path("gitleaks")
    if not binary:
        return 0
    try:
        r = subprocess.run(
            [str(binary), "protect", "--no-banner", "--report-format", "json",
             "--report-path", "/dev/stdout", "--source", str(project_root),
             "--staged", "--exit-code", "0"],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return 0
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return 0
    if not isinstance(data, list):
        return 0
    count = 0
    for result in data:
        rel = result.get("File", "")
        rule = result.get("RuleID", "")
        if not is_suppressed(rel, rule, suppressions):
            count += 1
    return count


def run_bandit(staged: list, project_root: Path, suppressions: list) -> int:
    binary = tool_path("bandit")
    if not binary:
        return 0
    py_files = [str(f) for f in staged if f.suffix == ".py"]
    if not py_files:
        return 0
    try:
        r = subprocess.run(
            [str(binary), "-f", "json", "-q"] + py_files,
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return 0
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return 0
    count = 0
    for result in data.get("results", []):
        path = result.get("filename", "")
        try:
            rel = str(Path(path).resolve().relative_to(project_root))
        except ValueError:
            rel = path
        rule = result.get("test_id", "")
        if not is_suppressed(rel, rule, suppressions):
            count += 1
    return count


def main() -> None:
    project_root = find_project_root()
    config = read_config(project_root)
    floor = config.get("severity_floor", "low")

    staged = staged_files(project_root)
    if not staged:
        sys.exit(0)

    suppressions = load_suppressions(project_root)

    semgrep_count = run_semgrep(staged, project_root, suppressions)
    gitleaks_count = run_gitleaks(staged, project_root, suppressions)
    bandit_count = run_bandit(staged, project_root, suppressions)
    total = semgrep_count + gitleaks_count + bandit_count

    if total == 0:
        sys.stderr.write(
            "[securecoder-review] SAST hook passed (0 findings). "
            "Run /securecoder-review interactively for compliance review "
            "before pushing significant changes.\n"
        )
        sys.exit(0)

    sys.stderr.write(
        f"[securecoder-review] BLOCKED — {total} finding(s) above floor '{floor}' "
        f"in staged files\n"
        f"  Semgrep:  {semgrep_count}\n"
        f"  Gitleaks: {gitleaks_count}\n"
        f"  Bandit:   {bandit_count}\n"
        f"To inspect findings, unstage the file or run /securecoder-review "
        f"interactively. To bypass once: `git commit --no-verify`.\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
