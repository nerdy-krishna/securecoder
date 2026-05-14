# 14 — Maintenance CI: auto-PR for pinned-tag bumps

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

Operational, not user-facing. Wires automation that keeps the skill's pinned upstream versions current without manual upkeep.

The skill ships ten distinct pins that drift out of date if neglected:

- 6 rule-pack / framework pins (Semgrep rules + 5 OWASP repos)
- 4 tool version pins (Semgrep, Bandit, Gitleaks, OSV-scanner)

Without automation, the maintenance treadmill swamps a small team. This slice ships a GitHub Action that:

1. Runs on a weekly schedule (cron) plus on-demand via `workflow_dispatch`.
2. For each tracked upstream source, queries the GitHub API for the latest release tag.
3. Compares against the current pin (parsed from `SKILL.md` files and from `references/frameworks.json`).
4. For each mismatch, opens a PR against `main`:
   - Title: `chore: bump <source> pin to <new-tag>`
   - Body: links to upstream release notes; lists affected SKILL.md files / references files; tags the PR for automated securecoder self-test (slice 9's `/securecoder-secure` against a known-good fixture repo) to catch behavioral regressions from a new rule pack version.
   - Labels: `dependencies`, `auto-pr`
5. If a PR for the same source + new-tag already exists, no duplicate is opened.

The corresponding skill-version bump (minor for rule packs, patch for tools) is documented in the PR body so the human merging it knows what semver to tag.

**Where the action lives:** `.github/workflows/pinned-tag-bumps.yml`. Helper scripts (one for parsing current pins out of SKILL.md, one for querying GitHub release APIs, one for opening the PR) live in `scripts/ci/`. None of this is installed by skills.sh — it's repo infrastructure, not skill content.

## Acceptance criteria

- [ ] `.github/workflows/pinned-tag-bumps.yml` runs weekly via cron and on-demand via `workflow_dispatch`
- [ ] Action correctly enumerates all 10 tracked pins (6 rule / framework + 4 tool)
- [ ] For each pin, queries the GitHub API for the latest release and compares to the current pinned tag
- [ ] Mismatches trigger PR creation with the documented title / body / labels
- [ ] Existing matching PR (same source + new-tag) is detected; no duplicate PR opened
- [ ] PR body cites upstream release notes URL and lists which SKILL.md / references files would be updated
- [ ] PR body specifies the recommended skill semver bump (minor for rule / framework pin bumps, patch for tool version bumps)
- [ ] Helper scripts in `scripts/ci/` are not installed by skills.sh — only `skills/security/*/` content is installed
- [ ] Manual `workflow_dispatch` produces the same behavior as the cron run
- [ ] Tests cover: pin-parsing from SKILL.md (regex correctness), release-tag comparison (handles `v` prefix, RC tags ignored, pre-releases ignored), PR-body templating

## Blocked by

- 01 — Repo skeleton + plugin.json + `/securecoder-setup` minimal wizard
