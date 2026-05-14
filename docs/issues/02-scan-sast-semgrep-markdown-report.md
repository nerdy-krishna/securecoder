# 02 — `/securecoder-scan` SAST end-to-end with Semgrep + markdown report

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The smallest viable scan loop. Single SAST tool (Semgrep), single output format (markdown), no compliance pass. Establishes every cross-cutting mechanism the rest of the build relies on: tool installation, rule-pack fetching with allowlist, content-addressed cache, repo walker, SAST normalizer + findings schema v1.0, canonical-ID derivation, CWE-to-framework enricher (using shipped `references/cwe-to-framework.json`), run directory manager with `latest` pointer, manifest.json, and markdown report renderer.

The user runs `/securecoder-scan`, picks "SAST only" at the mode prompt, and gets `.securecoder/runs/<run-id>/findings.jsonl` + `report.md` + `manifest.json` + `log.md`. The skill installs Semgrep into `~/.cache/securecoder/tools/` on first run with the one-time consent gate; fetches `returntocorp/semgrep-rules` at the pinned tag into `~/.cache/securecoder/rules/`; walks the user's repo respecting standard excludes (`.git/`, `node_modules/`, `.venv/`, binaries, files > 200KB); runs Semgrep with the language-appropriate sub-packs; normalizes Semgrep JSON output into the v1.0 findings schema; enriches with framework_refs via the shipped CWE table; writes the run dir; maintains the `latest` symlink (or `latest.json` on Windows).

The mode picker shows token-warning text up front for each option per design.md §3.2 — even though SAST mode is "0 LLM tokens" the picker still appears (consistency, and for when slices 03 and 07 land).

The pre-flight cost estimate for SAST-only is trivially "$0, ~30s wall time" but the estimate flow runs anyway so future slices reuse the same gate.

## Acceptance criteria

- [ ] `/securecoder-scan` runs against a Python repo and produces a non-empty `findings.jsonl` covering at least the SQL injection / hardcoded password / unsafe deserialization patterns Semgrep's `p/owasp-top-ten` catches
- [ ] `findings.jsonl` lines conform exactly to the v1.0 schema (every required field present, severity in the 5-level set, confidence in the 3-level set, canonical IDs computed correctly)
- [ ] Findings include populated `framework_refs` via the shipped CWE-to-framework table
- [ ] `~/.cache/securecoder/tools/semgrep/installed.json` records the installed version + checksum; re-running `/securecoder-scan` does not reinstall when the pin matches
- [ ] Semgrep rule packs are cloned to `~/.cache/securecoder/rules/semgrep/<sha>/` content-addressed by the git SHA of the fetched tree; manifest records source / tag / SHA / fetch timestamp
- [ ] Re-running with a populated cache works offline (no network calls)
- [ ] Cold cache + no network fails loudly with the message described in design.md §6 ("Source X needs network access...")
- [ ] One-time consent gate appears on first tool install; consent recorded in `~/.cache/securecoder/manifest.json`; subsequent installs are silent
- [ ] `.securecoder/runs/<run-id>/` contains `findings.jsonl`, `manifest.json`, `report.md`, `log.md`; `latest` points to the new run
- [ ] `manifest.json` includes schema version, run id, repo SHA (if git), tool versions, rule pack SHAs, phase durations, findings count
- [ ] Markdown report has summary, severity breakdown, findings grouped by file, manifest footer
- [ ] Pre-flight cost estimate prints (even when $0 for SAST mode) and asks for approval — `proceed` / `abort` (no scan-only option since this slice has no fix phase yet)
- [ ] Tests cover: Semgrep findings normalizer (happy path + edge cases), canonical-ID stability and distinctness, CWE-to-framework enrichment, file relevance filter for Semgrep, repo walker exclusion rules, run directory manager `latest`-pointer invariant

## Blocked by

- 01 — Repo skeleton + plugin.json + `/securecoder-setup` minimal wizard
