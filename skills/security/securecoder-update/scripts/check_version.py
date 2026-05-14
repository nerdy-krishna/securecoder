#!/usr/bin/env python3
"""Check whether the installed securecoder is current vs the latest release.

Reads the installed version from a VERSION file shipped alongside the
skill's SKILL.md (carried into the host's skill directory by the
skills.sh installer). Queries the GitHub Releases API for the latest
release tag and compares.

This script never modifies anything — it only surfaces version info and
the install command the user should run to upgrade. Security boundary:
upgrade is always an explicit user action, never automatic.

Stdlib only.

Usage:
    python3 check_version.py [--json]

Exit codes:
    0   — up to date
    1   — update available
    2   — could not determine version (missing VERSION file, etc.)
    3   — could not reach GitHub API (offline, rate-limited)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


GITHUB_REPO = "nerdy-krishna/securecoder"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def find_installed_version() -> str | None:
    """Locate the VERSION file relative to this script's own location.

    Expected layout in the installed skill dir:
        securecoder-update/
        ├── SKILL.md
        ├── VERSION              ← we read this
        └── scripts/
            └── check_version.py ← __file__
    """
    here = Path(__file__).resolve().parent  # scripts/
    skill_dir = here.parent  # securecoder-update/
    version_file = skill_dir / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    return None


def fetch_latest_release() -> dict | None:
    """Query the GitHub Releases API. Returns the JSON blob, or None on
    network / rate-limit / parsing failure.
    """
    req = urllib.request.Request(
        RELEASES_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "securecoder-update-check",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.stderr.write(
            f"GitHub API returned {e.code}: {e.reason}. "
            f"(rate-limited, server error, or no releases yet)\n"
        )
        return None
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        sys.stderr.write(f"Could not reach GitHub API: {e}\n")
        return None


def parse_version_tuple(tag: str) -> tuple:
    """Parse 'v1.1.0' → (1, 1, 0). Lenient; returns () on parse failure.
    Used for ordered comparison so 'v1.2.0' > 'v1.10.0' doesn't bite.
    """
    s = (tag or "").lstrip("v").split("-", 1)[0]  # strip any pre-release suffix
    parts = s.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return ()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON to stdout")
    args = ap.parse_args()

    installed = find_installed_version()
    if not installed:
        msg = (
            "Could not determine installed version. The VERSION file is "
            "missing from this skill's install dir. This may indicate a "
            "broken install — try `npx skills@latest add nerdy-krishna/"
            "securecoder` to refresh."
        )
        if args.json:
            sys.stdout.write(json.dumps({"status": "unknown", "message": msg}))
        else:
            sys.stderr.write(msg + "\n")
        sys.exit(2)

    release = fetch_latest_release()
    if release is None:
        msg = (
            f"Installed: {installed}. Could not check for updates "
            f"(network/API issue). Try again later or browse "
            f"https://github.com/{GITHUB_REPO}/releases manually."
        )
        if args.json:
            sys.stdout.write(json.dumps({
                "status": "unreachable",
                "installed": installed,
                "message": msg,
            }))
        else:
            sys.stderr.write(msg + "\n")
        sys.exit(3)

    latest_tag = release.get("tag_name", "")
    latest_url = release.get("html_url", "")
    latest_name = release.get("name", latest_tag)
    published = release.get("published_at", "")

    days_since = None
    try:
        pub_date = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
        days_since = (dt.datetime.now(dt.timezone.utc) - pub_date).days
    except (ValueError, AttributeError):
        pass

    installed_tup = parse_version_tuple(installed)
    latest_tup = parse_version_tuple(latest_tag)

    if installed_tup and latest_tup and installed_tup >= latest_tup:
        status = "up_to_date"
        message = (
            f"You're up to date.\n"
            f"  Installed: {installed}\n"
            f"  Latest:    {latest_tag} ({latest_name})"
        )
        exit_code = 0
    elif installed == latest_tag:
        status = "up_to_date"
        message = (
            f"You're up to date.\n"
            f"  Installed: {installed}\n"
            f"  Latest:    {latest_tag}"
        )
        exit_code = 0
    else:
        status = "update_available"
        age = f" ({days_since} days ago)" if days_since is not None else ""
        message = (
            f"Update available.\n"
            f"  Installed: {installed}\n"
            f"  Latest:    {latest_tag} ({latest_name})\n"
            f"  Released:  {published}{age}\n"
            f"  Notes:     {latest_url}\n"
            f"\n"
            f"To upgrade:\n"
            f"  npx skills@latest add {GITHUB_REPO}\n"
            f"\n"
            f"Your team-shared config (.securecoder/config.json), suppressions\n"
            f"(.securecoder/suppressions.json), and scan history "
            f"(.securecoder/runs/) are preserved across upgrades."
        )
        exit_code = 1

    if args.json:
        sys.stdout.write(json.dumps({
            "status": status,
            "installed": installed,
            "latest": latest_tag,
            "latest_name": latest_name,
            "released_at": published,
            "days_since_release": days_since,
            "notes_url": latest_url,
            "upgrade_command": f"npx skills@latest add {GITHUB_REPO}",
            "message": message,
        }, indent=2))
    else:
        sys.stdout.write(message + "\n")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
