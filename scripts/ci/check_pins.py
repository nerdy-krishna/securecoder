#!/usr/bin/env python3
"""Check securecoder's pinned upstream versions against current releases.

Reads pinned versions out of the relevant SKILL.md files (Semgrep, Bandit,
Gitleaks, OSV-scanner) and out of frameworks.json (OWASP ASVS, MASVS,
Proactive Controls, Cheatsheets, Semgrep rules). Queries the GitHub
Releases / Tags API for each upstream and compares.

Output: a JSON report listing every pin and whether it's current, plus a
markdown summary suitable for use as a PR body when one or more pins are
outdated.

Used by the .github/workflows/pinned-tag-bumps.yml workflow on a weekly
schedule. Stdlib only; uses urllib.request for HTTP.

Usage:
    python3 check_pins.py [--json] [--markdown <path>]
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCAN_SKILL = REPO_ROOT / "skills" / "security" / "securecoder-scan" / "SKILL.md"
FRAMEWORKS_JSON = REPO_ROOT / "skills" / "security" / "securecoder-scan" / "references" / "frameworks.json"


# Pin extraction patterns for SKILL.md
TOOL_VERSION_PATTERNS = {
    "semgrep":     re.compile(r"\*\*`semgrep==(\d+\.\d+\.\d+)`\*\*"),
    "bandit":      re.compile(r"\*\*`(\d+\.\d+\.\d+)`\*\*\s*\n\n```bash\nBANDIT_VERSION"),
    "gitleaks":    re.compile(r"Gitleaks — pinned `(\d+\.\d+\.\d+)`"),
    "osv-scanner": re.compile(r"OSV-scanner — pinned `(\d+\.\d+\.\d+)`"),
}


def fetch_latest_github_release(repo: str) -> str | None:
    """Return the latest release tag for `owner/repo`, or None on failure."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            return tag.lstrip("v")
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def fetch_latest_default_branch_sha(repo: str, branch: str) -> str | None:
    """Return the latest commit SHA on `branch` for `owner/repo`."""
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("sha")
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def extract_tool_pin(skill_md_text: str, tool: str) -> str | None:
    pattern = TOOL_VERSION_PATTERNS.get(tool)
    if not pattern:
        return None
    m = pattern.search(skill_md_text)
    return m.group(1) if m else None


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON")
    ap.add_argument("--markdown",
                    help="Write markdown PR body summary here")
    args = ap.parse_args()

    skill_md = SCAN_SKILL.read_text(encoding="utf-8")
    frameworks = json.loads(FRAMEWORKS_JSON.read_text(encoding="utf-8"))

    pins: list = []

    # Tool pins
    tool_repos = {
        "semgrep":     "returntocorp/semgrep",
        "bandit":      "PyCQA/bandit",
        "gitleaks":    "gitleaks/gitleaks",
        "osv-scanner": "google/osv-scanner",
    }
    for tool, gh_repo in tool_repos.items():
        current = extract_tool_pin(skill_md, tool)
        latest = fetch_latest_github_release(gh_repo)
        pins.append({
            "kind": "tool",
            "name": tool,
            "github_repo": gh_repo,
            "current_pin": current,
            "latest_release": latest,
            "outdated": (current is not None and latest is not None and current != latest),
        })

    # Framework pins (branch-tracked; we check if the latest commit SHA differs)
    fw_table = frameworks.get("_frameworks", {})
    for fw_id, fw in fw_table.items():
        source = fw.get("source", "")
        branch = fw.get("branch", "")
        if not source.startswith("https://github.com/"):
            continue
        owner_repo = source.removeprefix("https://github.com/").removesuffix(".git")
        latest_sha = fetch_latest_default_branch_sha(owner_repo, branch)
        pins.append({
            "kind": "framework",
            "name": fw_id,
            "github_repo": owner_repo,
            "branch": branch,
            "latest_sha": latest_sha,
            "outdated": None,  # frameworks track-branch; outdated check is per-clone, not per-pin
        })

    outdated = [p for p in pins if p.get("outdated") is True]

    report = {
        "checked_at": "<runtime>",
        "total_pins": len(pins),
        "outdated_count": len(outdated),
        "pins": pins,
    }

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2) + "\n")

    if args.markdown:
        lines: list = []
        lines.append("# Pinned upstream version check\n")
        if not outdated:
            lines.append("All tool pins are current. No PR needed.\n")
        else:
            lines.append(f"Found {len(outdated)} outdated tool pin(s):\n")
            for p in outdated:
                lines.append(
                    f"- **{p['name']}**: pinned `{p['current_pin']}` → latest `{p['latest_release']}` "
                    f"([release notes](https://github.com/{p['github_repo']}/releases/tag/v{p['latest_release']}))"
                )
            lines.append("")
            lines.append("This PR is recommended for skill version `v0.x.y → v0.x.(y+1)` (patch bump for tool versions per design.md § 12).")
        Path(args.markdown).write_text("\n".join(lines), encoding="utf-8")

    sys.exit(0 if not outdated else 1)


if __name__ == "__main__":
    main()
