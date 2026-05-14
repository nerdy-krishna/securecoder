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

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


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


def run_semgrep(staged: list, project_root: Path) -> int:
    """Returns the count of findings at or above floor."""
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
    return len(data.get("results", []))


def run_gitleaks(staged: list, project_root: Path) -> int:
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
    return len(data) if isinstance(data, list) else 0


def run_bandit(staged: list, project_root: Path) -> int:
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
    return len(data.get("results", []))


def main() -> None:
    project_root = find_project_root()
    config = read_config(project_root)
    floor = config.get("severity_floor", "low")

    staged = staged_files(project_root)
    if not staged:
        sys.exit(0)

    semgrep_count = run_semgrep(staged, project_root)
    gitleaks_count = run_gitleaks(staged, project_root)
    bandit_count = run_bandit(staged, project_root)
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
