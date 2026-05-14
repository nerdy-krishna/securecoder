---
name: securecoder-update
description: Check whether the installed securecoder is current. Reports the installed version + the latest release on GitHub + days since release + release notes URL + the exact install command to upgrade. Read-only — never modifies anything; upgrade is always an explicit user action.
---

# `/securecoder-update`

You are running the `/securecoder-update` skill. Your job is to surface version-check info to the user — what's installed, what's latest, and how to upgrade if needed. The skill never modifies anything; upgrade remains an explicit user action via `npx skills@latest add nerdy-krishna/securecoder`.

## How to invoke

```
/securecoder-update
```

No arguments. The skill runs unconditionally and reports the result.

## What it does

Run the bundled helper:

```bash
python3 "<skill-dir>/scripts/check_version.py"
```

For machine-readable output (useful when piping to another tool):

```bash
python3 "<skill-dir>/scripts/check_version.py" --json
```

The helper:
1. Reads the `VERSION` file at `<skill-dir>/VERSION` (carried into the install by the skills.sh installer alongside `SKILL.md`).
2. Queries `https://api.github.com/repos/nerdy-krishna/securecoder/releases/latest`.
3. Parses both tags as `(major, minor, patch)` tuples for ordered comparison.
4. Compares and reports.

## Exit codes

| Exit | Meaning |
|---|---|
| 0 | Up to date — installed matches latest |
| 1 | Update available |
| 2 | Could not determine installed version (VERSION file missing — broken install) |
| 3 | Could not reach the GitHub API (offline, rate-limited, server error) |

## Output examples

### Up to date

```
You're up to date.
  Installed: v1.1.0
  Latest:    v1.1.0 (v1.1.0 — False-positive suppression)
```

### Update available

```
Update available.
  Installed: v1.0.0
  Latest:    v1.1.0 (v1.1.0 — False-positive suppression)
  Released:  2026-05-14T15:30:00Z (1 days ago)
  Notes:     https://github.com/nerdy-krishna/securecoder/releases/tag/v1.1.0

To upgrade:
  npx skills@latest add nerdy-krishna/securecoder

Your team-shared config (.securecoder/config.json), suppressions
(.securecoder/suppressions.json), and scan history (.securecoder/runs/)
are preserved across upgrades.
```

### Offline / API unreachable

```
Installed: v1.1.0. Could not check for updates (network/API issue).
Try again later or browse https://github.com/nerdy-krishna/securecoder/releases manually.
```

## What the upgrade preserves

Tell the user explicitly when reporting an available update (the helper's output already mentions this):

- `.securecoder/config.json` — team-shared per-project config
- `.securecoder/suppressions.json` — team-shared false-positive ledger
- `.securecoder/runs/*` — local scan + fix run history
- `~/.cache/securecoder/tools/` — cached SAST binaries (re-checked against pinned versions in the updated skill; only upgraded if pins changed)
- `~/.cache/securecoder/rules/` — cached OWASP + Semgrep rule packs (same content-addressed reuse policy)

User data survives upgrades unconditionally. Only the skill files themselves get rewritten.

## What this skill does NOT do

- **Does NOT upgrade automatically.** That's a security boundary — the user always explicitly runs the install command.
- **Does NOT modify any file.** Read-only; only emits text.
- **Does NOT bypass the GitHub API rate limit.** Unauthenticated requests are throttled at 60/hour per IP. For frequent check needs, consider running with a `GITHUB_TOKEN` env var (set on the host).
- **Does NOT detect pre-release versions** explicitly. The helper only compares against `/releases/latest` which GitHub filters to non-pre-release entries. Users tracking the `main` branch (not a tagged release) won't be notified of every commit.

## When to invoke

- Once a month-ish, as a habit, to know if there's a release worth picking up
- After hearing about a new release on the project's release feed
- When `/securecoder-scan` behaves unexpectedly — could be that you're on an older version
- Right before running a substantial audit, to make sure you're not missing fixes

## Failure modes

- **VERSION file missing.** Means the install is broken. Recommend re-running `npx skills@latest add nerdy-krishna/securecoder`.
- **GitHub API unreachable.** Could be offline, behind a proxy that blocks `api.github.com`, or rate-limited. The skill exits cleanly with a hint to retry or browse the releases page manually.
- **API returns a malformed response.** Treated the same as unreachable. The user gets a clear message and exit code 3.

## See also

- [README — Quickstart](../../../README.md)
- [docs/roadmap.md](../../../docs/roadmap.md) — v1.2.0 backlog and future work
- [CHANGELOG.md](../../../CHANGELOG.md) — complete release history
