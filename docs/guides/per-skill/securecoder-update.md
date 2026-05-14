# `/securecoder-update` — usage guide

## What this skill does

Checks whether the installed securecoder is current versus the latest GitHub release. Read-only — never modifies anything, never auto-upgrades. Reports installed vs latest, days since release, release notes URL, and the exact install command to run if an upgrade is offered.

## When to invoke it

- **Periodically** (~monthly) as a habit
- **Before a substantive audit** — to make sure you're not missing fixes that affect the scan
- **After hearing about a new release** on the project's release feed
- **When `/securecoder-scan` behaves unexpectedly** — could be an older version

## When NOT to invoke it

- **Frequently in CI.** GitHub's unauthenticated API rate-limit is 60/hour per IP; running this on every PR will burn through that fast. Set `GITHUB_TOKEN` on the host if you want frequent CI integration.

## How to invoke

```text
/securecoder-update

# Or for tooling integration (machine-readable):
/securecoder-update --json
```

No arguments other than `--json`. The skill always runs unconditionally.

## What you'll see

### Up to date

```
You're up to date.
  Installed: v1.2.0
  Latest:    v1.2.0 (v1.2.0 - /securecoder-update + annotations + smart-collapse + sample review)
```

Exit code 0.

### Update available

```
Update available.
  Installed: v1.1.0
  Latest:    v1.2.0 (v1.2.0 - /securecoder-update + annotations + smart-collapse + sample review)
  Released:  2026-05-15T08:00:00Z (1 days ago)
  Notes:     https://github.com/nerdy-krishna/securecoder/releases/tag/v1.2.0

To upgrade:
  npx skills@latest add nerdy-krishna/securecoder

Your team-shared config (.securecoder/config.json), suppressions
(.securecoder/suppressions.json), and scan history (.securecoder/runs/)
are preserved across upgrades.
```

Exit code 1. Run the install command to upgrade — the skill won't do it for you.

### Couldn't reach GitHub

```
Installed: v1.2.0. Could not check for updates (network/API issue).
Try again later or browse https://github.com/nerdy-krishna/securecoder/releases manually.
```

Exit code 3. No problem — just retry later. Could also mean you're rate-limited (60 requests/hour without auth).

### Couldn't determine installed version

```
Could not determine installed version. The VERSION file is missing from this skill's
install dir. This may indicate a broken install — try `npx skills@latest add
nerdy-krishna/securecoder` to refresh.
```

Exit code 2. Usually means the installer didn't copy the `VERSION` file or you've manually edited the install dir. Re-install to fix.

## What the upgrade preserves

When you run the install command to upgrade, everything below survives:

- `.securecoder/config.json` — your team-shared per-project preferences
- `.securecoder/suppressions.json` — the false-positive ledger your team has built
- `.securecoder/runs/<id>/` — every previous scan + fix run, with backups
- `~/.cache/securecoder/tools/` — Semgrep/Bandit/Gitleaks/OSV binaries; re-checked against the new SKILL.md's pinned versions and only re-downloaded if pins changed
- `~/.cache/securecoder/rules/` — OWASP + Semgrep rule clones; same content-addressed reuse rules

Only the skill files themselves (SKILL.md and helper scripts) get rewritten.

## How it works internally

The helper at `<skill-dir>/scripts/check_version.py`:

1. Reads `<skill-dir>/VERSION` — a file the skills.sh installer copies alongside the SKILL.md when securecoder is installed.
2. Queries `https://api.github.com/repos/nerdy-krishna/securecoder/releases/latest`.
3. Parses both tags as `(major, minor, patch)` tuples so `v1.10.0 > v1.2.0` (string comparison would get this wrong).
4. Compares and reports.

No state is written, no auth tokens are sent, no telemetry. The single HTTPS request is anonymous to GitHub.

## Common pitfalls

- **The skill reports up-to-date but I know there's a newer commit on `main`.** Releases are tagged, not every commit. If you want bleeding-edge, install from `main` directly via `git pull` rather than tracking releases.
- **Rate-limited.** GitHub allows 60 unauthenticated requests per hour per IP. If you're running the check frequently or share an IP, set `GITHUB_TOKEN` on the host to get 5000/hour.
- **VERSION file out of date after manual edits.** If you've edited skill files directly and forgot the VERSION file, the check reports the old version. Re-install fixes it.
- **Pre-release tags are filtered out** by GitHub's "latest release" endpoint. If you're tracking pre-releases, browse the releases page manually.

## See also

- [Top-level README](../../../README.md)
- [docs/roadmap.md](../../../docs/roadmap.md) — what's coming next
- [CHANGELOG.md](../../../CHANGELOG.md) — full release history
