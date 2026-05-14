# Changelog

All notable changes to securecoder ship here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [Unreleased]

## [0.8.0] — 2026-05-14

`/securecoder-secure` becomes functional. The easy-button skill wires `/securecoder-scan` and `/securecoder-fix` into a 4-phase pipeline: SAST scan → SAST fix → compliance scan → compliance fix. One up-front approval covers the whole pipeline; a 50%-overrun mid-run gate offers a single safety bail.

### Added
- **`/securecoder-secure` four-phase pipeline** with single approval gate. Mode picker offers `proceed` (full pipeline), `scan-only` (Phases 1 and 3 only, no fixes), and `abort`.
- **50%-overrun mid-run gate.** After Phase 3 (compliance scan) completes, if actual token usage ≥ 1.5× the pre-flight estimate, the pipeline pauses and asks `continue` / `abort` before Phase 4. Skipped in `scan-only` mode.
- **Top-level pre-flight safety** — git clean-tree auto-stash, protected-branch auto-branch (no per-phase re-prompts). The easy-button mode doesn't make the user answer the same question twice.
- **Unified pipeline manifest** at `.securecoder/runs/<pipeline-run-id>/manifest.json` referencing every sub-run id, plus `estimate_vs_actual` token comparison.
- **Two `--restore`-able fix runs** (SAST fix + compliance fix) — the pipeline doesn't change the rollback story; each fix phase remains independently undoable.

### Compatibility
- Requires `/securecoder-scan` and `/securecoder-fix` installed alongside (declared in the skill description; the skill fails early with a clear message if either is missing).
- No new pinned upstreams.

## [0.7.0] — 2026-05-14

`/securecoder-fix` extends to handle compliance findings produced by the v0.6.0 ASVS pass. The full safety loop applies: backup, syntax check, re-scan with the originating mechanism, automatic rollback on failure. Compliance fixes that the model can't fully resolve in 3 tries land as `editor_failed`; those whose re-verification LLM call fails land as `applied_unverified`.

### Added
- **Compliance-finding handling in `/securecoder-fix`.** Findings with `category: "compliance"` now flow through the per-fix loop alongside SAST findings.
- **Compliance re-verification path.** After a compliance fix is applied, the architect prompt for the originating ASVS chapter is re-run against the patched file. The original failing control must no longer fail, and no new same-or-higher compliance failures may appear at that file × chapter, or the fix is rolled back.
- **`applied_unverified` status.** When the re-scan LLM call fails (3 tries), the patch stays applied but is flagged in the summary so the user can spot-check. Distinguished from `applied` (verified) and `editor_failed` (rolled back).
- **Specialized commit message for compliance fixes.** `fix(securecoder): <severity>/<title> [compliance <framework>/<control> <id-short>]` makes compliance fixes visually distinct from SAST fixes in git log.

### Compatibility
- Findings with `fix_complexity: "high"` or `lines: null` remain flagged `manual_review_required` regardless of category — these are architectural or location-ambiguous fixes the agent shouldn't auto-apply.
- No new pinned upstreams.

## [0.6.0] — 2026-05-14

`/securecoder-scan` gains the LLM-driven ASVS v5 compliance pass. Mode picker now offers SAST only / LLM compliance only / Both. Compliance findings merge into the same `findings.jsonl` as SAST findings; per-framework posture score appears in both markdown and HTML reports.

### Added
- **ASVS v5 compliance pass** as Phase B of `/securecoder-scan`. Fetches `OWASP/ASVS` at branch `master`, content-addressed by commit SHA. Dispatches one LLM call per file × chapter pair, validates coverage matrix is complete, retries once on incomplete coverage, normalizes findings.
- **`references/asvs-architect-prompt.md`** — the LLM prompt template that drives every compliance pair. HITL — changes deserve manual review since the wording shapes the whole compliance output.
- **`references/chapter-relevance.json`** — per-chapter applicability hints for ASVS V1–V17. Each chapter declares which languages apply, optional exclusions, and optional keyword triggers. Cuts the dispatch list aggressively to keep token cost down.
- **`scripts/file_relevance.py`** — builds the file × chapter dispatch list from the repo walker output and the relevance table.
- **`scripts/validate_coverage.py`** — parses chapter source for expected control IDs, parses the LLM response for found control IDs, emits a missing-controls list for retry composition. Same pattern as asvs-shell.
- **`scripts/normalize_compliance.py`** — extracts the LLM's findings JSON array (tolerant balanced-bracket scanner; works whether the array is in markdown fences or bare in the response), normalizes each entry to the v1.0 schema, adds canonical IDs and framework refs.
- **Compliance posture in the manifest.** `compliance_posture.<framework>` with `controls_evaluated`, `controls_passing`, `controls_with_findings`, `posture_score` (0.0–1.0). Reports display this in the compliance-posture section that was previously a placeholder.

### Pinned upstream versions
- OWASP ASVS: branch `master` (no v5 tag yet on the OWASP repo), content-addressed by commit SHA in the per-framework manifest.
- Other pins unchanged from v0.5.0.

### Compatibility
- MASVS / Proactive Controls / Cheatsheets are not yet supported by the compliance pass. They land in slice 13 (v0.12.0). Selecting them in `/securecoder-setup` doesn't break v0.6.0 — they're recorded but skipped with `status: "skipped_not_yet_implemented"`.

### Tests
- Deferred. The pipeline is well-typed end-to-end (relevance filter → prompt compose → host LLM → validate → normalize → merge); each helper smoke-tested in isolation with synthetic inputs.

## [0.5.0] — 2026-05-14

`/securecoder-fix` becomes functional. Reads findings from the latest (or specified) scan run, asks the user which severities to fix, then runs a per-fix loop with mandatory pre-flight safeguards, automatic rollback on verification failure, and one git commit per successful fix.

### Added
- **`/securecoder-fix` SAST-finding remediation** with the full safety loop: pre-flight (git clean-tree check, protected-branch warning + auto-branch, backup capture, cost estimate, approval) → per-fix loop (LLM SEARCH/REPLACE → patch apply → syntax check → re-scan → commit + push per strategy) → up to 3 retries per finding with named-failure retry context → post-flight (push accumulated, write manifest, print summary).
- **Severity-multi-select mode picker.** All / Critical / High / Medium / Low / Critical+High (Recommended) / Critical+High+Medium / Custom subset / Interactive one-by-one / By specific finding IDs.
- **`scripts/apply_patch.py`** — atomic SEARCH/REPLACE block parser. Validates each block has exactly one match before any write happens; either every block lands or the file is untouched. Emits structured JSON status for the agent to act on.
- **`scripts/syntax_check.py`** — language-agnostic syntax check dispatcher. Resolves the right checker by file extension (`python3 -m py_compile`, `node --check`, `gofmt -e`, `ruby -c`, `php -l`, `bash -n`, stdlib `json.load` for JSON). Falls back to a UTF-8 validity probe when no checker is on PATH.
- **`--restore <run-id>` mode** for rolling back a previous fix run. Shows diff between current files and backups, asks for confirmation, restores from `backups/`, optionally also `git revert`s the corresponding commits, and writes `restore_log.md`. Works on non-git repos via backups alone.
- **Push-strategy honoring** from `.securecoder/config.json`. `push-each` pushes after each commit, `commit-local-push-at-end` (default) batches the push to post-flight, `commit-local-never-push` skips push entirely.
- **Manual-review gating.** Findings with `fix_complexity: "high"` or `lines: null` are marked `manual_review_required` and skipped. Compliance findings (`category: "compliance"`) are also marked `manual_review_required` for now; full handling lands in v0.7.0.

### Compatibility
- No new pinned upstreams. Re-uses the cached SAST tool binaries from v0.2.0–0.4.0 for re-scan verification.
- Python: 3.9+. Helper scripts use stdlib only.

### Tests
- Deferred. Manual smoke-tested `apply_patch.py` happy path, no-match path, and `syntax_check.py` on a Python file end-to-end.

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

[Unreleased]: https://github.com/nerdy-krishna/securecoder/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.8.0
[0.7.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.7.0
[0.6.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.6.0
[0.5.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.5.0
[0.4.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.4.0
[0.3.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.3.0
[0.2.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.2.0
[0.1.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.1.0
