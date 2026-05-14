# Changelog

All notable changes to securecoder ship here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [Unreleased]

## [0.4.0] — 2026-05-14

Every `/securecoder-scan` run now produces both a markdown and a self-contained HTML report, plus a cross-run trend section that compares the current findings to the most recent prior run.

### Added
- **HTML report renderer** (`scripts/render_html.py`). Self-contained: inlined CSS in a `<style>` block, inlined client-side filtering JS in a `<script>` block, no external `<link>` / `<script src=>` / `<img src=>`. Opens correctly in any modern browser with networking disabled.
- **Interactive filtering** on the HTML report: severity, source (semgrep / bandit / gitleaks / osv-scanner), framework (asvs-v5 / owasp-top-10-2021 / etc.), plus a free-text search across file path / title / description / evidence. File groups with no visible findings auto-collapse.
- **Trend computer** (`scripts/compute_trend.py`). Walks sibling run directories under `.securecoder/runs/`, picks the most recent run before the current one, and emits JSON describing the new / resolved / persistent finding buckets by canonical ID.
- **`trend` field in `manifest.json`** populated by every scan. Both renderers read it; first-run reports correctly say "First run — no trend data yet."
- **HTML supports light and dark color scheme** via `@media (prefers-color-scheme)`.

### Changed
- `render_markdown.py` trend section now shows the prior-run ID + new / resolved / persistent counts, or "First run — no trend data yet" when no prior exists.
- SKILL.md flow extended: A.8 (compute trend) → A.9 (write manifest with trend) → A.10 (render markdown + HTML) → A.11 (latest pointer) → A.12 (gitignore) → A.13 (summary).

### Compatibility
- No new pinned upstreams. No new external dependencies.
- Python: 3.9+. HTML uses modern CSS (custom properties, `prefers-color-scheme`, `display: flex/grid`) and ES5 JS for broad browser support.

### Tests
- Deferred. Manual smoke-testing covered: compute_trend in three scenarios (first run, identical-prior, mixed prior); markdown trend rendering with and without trend data; HTML rendering plus a self-containment grep verifying zero external resource references.

## [0.3.0] — 2026-05-14

`/securecoder-scan` becomes multi-tool. Bandit, Gitleaks, and OSV-scanner join Semgrep in the SAST pipeline. Findings from all four tools merge into one `findings.jsonl`. Per-tool soft-failure policy means one crashing tool doesn't break the whole scan.

### Added
- **Bandit normalizer** (`scripts/normalize_bandit.py`). Maps Bandit HIGH/MEDIUM/LOW severity × HIGH/MEDIUM/LOW confidence to the securecoder 5-level scale; escalates hardcoded-secret / SQL-injection rule IDs to at-least-high. Extracts CWE from `issue_cwe.id`.
- **Gitleaks normalizer** (`scripts/normalize_gitleaks.py`). Every detection is `critical` severity, CWE-798, with the secret value redacted in the emitted evidence so reports don't leak credentials.
- **OSV-scanner normalizer** (`scripts/normalize_osv.py`). One finding per (package, vulnerability). Severity derived from CVSS score with safe fallback to `high` when the score isn't recoverable. Adds OWASP A06 to every finding's `framework_refs`. CVE aliases from advisories become tags.
- **Shared helpers** (`scripts/_common.py`). Canonical-ID computation, CWE / OWASP token extraction, framework-ref enrichment with dedup, path normalization, output emission. Imported by every normalizer.
- **OSV auto-skip** when no dependency manifest is present in the repo. Looks for npm, pip, poetry, pipenv, go, cargo, gem, composer, dart, mix lockfiles up to 3 levels deep.
- **Per-tool status reporting in `manifest.json`**. `phases.sast.per_tool.<tool>.{status, duration_s, findings}` lets reports and downstream skills know which tools ran, which were skipped, and which failed.
- **Bandit, Gitleaks, OSV-scanner installers** in the SKILL.md flow. Bandit via venv (same pattern as Semgrep). Gitleaks and OSV-scanner via GitHub release-binary download with per-OS / per-arch asset selection.

### Refactored
- `normalize_semgrep.py` now imports from `_common.py`; output is byte-equivalent to v0.2.0's. The Semgrep-specific severity heuristic (escalate injection / secret rules to critical) stays in `normalize_semgrep.py`.
- `SKILL.md` for `/securecoder-scan` restructured around four tools instead of one. Phase A now: A.0 enabled-tools resolution → A.1 OS/arch detection → A.2 install (a-d, one per tool) → A.3 Semgrep rule fetch → A.4 walk → A.5 run (a-d) → A.6 normalize → A.7 merge → A.8 manifest → A.9 report → A.10 latest pointer → A.11 gitignore → A.12 summary.

### Pinned upstream versions
- Semgrep: `1.91.0` (unchanged from v0.2.0)
- Bandit: `1.7.10`
- Gitleaks: `8.18.4`
- OSV-scanner: `1.9.2`

### Compatibility
- Host agents: any reading SKILL.md markdown.
- OS: macOS (arm64, amd64) and Linux (amd64, arm64) validated for the binary-tool install logic via asset-name mapping tables. Windows asset names included but the install path is not yet validated end-to-end.
- Python: 3.9+. All normalizers use `from __future__ import annotations` so PEP 604 syntax is parse-only.

### Tests
- Deferred. Manual smoke-testing covered each normalizer with synthetic tool output (Bandit B608+B105, Gitleaks aws+generic-api-key, OSV GHSA), plus the merged-findings-plus-render end-to-end path with all four sources represented. Unit tests follow in a subsequent commit.

## [0.2.0] — 2026-05-14

`/securecoder-scan` becomes functional for the Semgrep SAST path. Establishes every cross-cutting mechanism the rest of the skill bundle relies on: tool installation with one-time consent, content-addressed rule cache, repo walker with language detection, SAST findings normalization, CWE-to-framework enrichment, run directory management, and markdown report rendering.

### Added
- `/securecoder-scan` SAST mode (Semgrep only). Mode picker prompts for SAST-only / LLM-compliance-only / Both; the last two are gracefully not-yet-implemented stubs.
- Helper scripts under `skills/security/securecoder-scan/scripts/`:
  - `repo_walker.py` — walks the project tree, prunes vendored / generated / hidden dirs, detects language per file by extension, emits a JSON inventory.
  - `normalize_semgrep.py` — parses Semgrep `--json` output into the v1.0 findings schema. Computes canonical IDs (`sha256(file|line_start|rule_id)`), maps severity with rule-id heuristics, enriches with framework refs.
  - `render_markdown.py` — renders `findings.jsonl` + `manifest.json` as a markdown report. Sections: summary, severity breakdown, phases, findings grouped by file, manifest footer. Compliance posture and trend sections are placeholders for slices 04 and 07.
- Curated `references/cwe-to-framework.json` covering 39 CWE → framework-ref mappings. Each entry links to relevant ASVS v5 controls and OWASP Top 10 2021 categories.
- Run directory layout under `.securecoder/runs/<run-id>/` containing `findings.jsonl`, `manifest.json`, `report.md`, `repo_map.json`, `log.md`, and raw Semgrep output for debugging.
- `latest` pointer (symlink on POSIX; `latest.json` fallback for Windows) so downstream skills like `/securecoder-fix` can find the most recent run without arg parsing.

### Pinned upstream versions
- Semgrep tool: `1.91.0`. Installed into `~/.cache/securecoder/tools/semgrep/venv/` via `python3 -m venv` + `pip install`; no pipx required.
- `returntocorp/semgrep-rules`: branch `main`, content-addressed by the resulting commit SHA recorded in `~/.cache/securecoder/rules/semgrep/<sha>/manifest.json`. Per-language rule subdirs are selected by the walker's detected languages.

### Compatibility
- Host agents: any reading SKILL.md markdown; instructions use plain English flow plus explicit bash commands, no host-specific primitives.
- OS: macOS, Linux. Windows path handling implemented but not yet validated end-to-end.
- Python: 3.9+. Helper scripts use `from __future__ import annotations` so PEP 604 syntax is parse-only.

### Tests
- Deferred to a separate slice. The acceptance criteria for unit tests in `docs/issues/02-scan-sast-semgrep-markdown-report.md` remain open and will be added in a follow-up commit. Manual smoke-testing of all three helper scripts validated the pipeline end-to-end with synthetic Semgrep output before this release.

## [0.1.0] — 2026-05-14

The foundation release. Establishes the repo as a skills.sh-installable agent skill collection.

### Added
- `.claude-plugin/plugin.json` listing all seven skills.
- `/securecoder-setup` — full 8-question configuration wizard. Writes `.securecoder/config.json` to the user's project root; surfaces a privacy notice when a compliance framework is selected; pre-selects existing values when re-run.
- Stub `SKILL.md` for the six skills landing in later slices: `/securecoder-scan`, `/securecoder-fix`, `/securecoder-secure`, `/securecoder-review`, `/securecoder-build`, `/securecoder-advise`. Each stub describes the intended behavior, links to its tracking issue, and tells the host agent the skill is not yet implemented.
- README with quickstart, privacy section, and pointers to the design document, PRD, and issue backlog.
- MIT license.

### Pinned upstream versions
- None — first release ships only the configuration surface. Tool and rule pack pins land in 0.2.0 alongside `/securecoder-scan`.

### Compatibility
- Host agents: any reading `SKILL.md` markdown. Validated against Claude Code in this release; broader host coverage tracked as a v0.x stability item.
- OS: macOS, Linux. Windows path handling implemented but not yet validated end-to-end.
- Python: 3.9+ for helper scripts (`/securecoder-setup` is pure SKILL.md and needs no Python).

[Unreleased]: https://github.com/nerdy-krishna/securecoder/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.4.0
[0.3.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.3.0
[0.2.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.2.0
[0.1.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.1.0
