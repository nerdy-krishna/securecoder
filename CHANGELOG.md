# Changelog

All notable changes to securecoder ship here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [Unreleased]

## [1.2.0] — 2026-05-15

Six slices delivering the v1.2.0 roadmap items: version-check helper, source-code suppression annotations, smart-collapse virtualization, sample-assisted cluster review, plus 46 new pytest cases backfilling v0.x helper coverage. Brings the skill count to 9 and the test count to 83.

### Added

- **`/securecoder-update`** — the 9th skill. Reports installed vs latest GitHub release; surfaces the install command without auto-upgrading. Ships a `VERSION` file alongside its SKILL.md that the skills.sh installer carries into the host. Four exit codes (up-to-date / update-available / missing-VERSION / API-unreachable) and a `--json` mode.
- **Source-code suppression annotations.** `# securecoder: ignore [reason="..."] [expires="..."]` (and `// securecoder: ignore` for JS-style line comments) work as an alternative to config-file suppressions. The new `scan_annotations.py` helper walks the repo before `apply_suppressions.py` runs and emits ephemeral entries with `source: "annotation"` and `created_by: "<annotation>"`. Inline annotations apply to their own line; line-only annotations apply to the next non-blank code line.
- **`lines: {start, end}` match field** on suppression entries (specificity score 1 — just below `id`, above `rule + file`). A finding matches if its starting line is within the entry's range. Used by source-code annotations; available to manually-written entries too.
- **Smart-collapse virtualization** in the HTML report. When total findings > 500, file-groups render collapsed by default (`<details>` without the `open` attribute — browser skips article-card rendering inside). New `[Expand all visible] [Collapse all]` toolbar appears in large reports.
- **Sample-assisted cluster review.** New "Review samples" button on every cluster row. Opens a modal with 5 random samples; each has Keep/Suppress vote buttons. When all 5 are voted: if ≥80% suppress, the modal's "Suppress entire cluster" button is enabled and reuses the standard staging pipeline. Modal samples are pulled from the DOM by matching the cluster's rule + file_glob (regex-built from gitignore-style globs).
- **46 new pytest cases** across 7 new test files covering v0.x helpers: repo_walker (5), all four SAST normalizers (12), validate_coverage (4), compute_trend (7), diff_scoper (6), apply_patch (7), syntax_check (5). Plus 8 cases for scan_annotations and 1 new for apply_suppressions' `lines` match field.

### Changed

- **Suppression specificity ranking** updated to insert `file + lines` (score 1, annotation-style) between `id` (score 0) and `rule + file` (now score 2). Existing entries keep working — only the relative ordering between certain combinations shifts when both are present.
- **`apply_suppressions.py` CLI** gains `--annotations <path>` for the ephemeral-entries JSON array. When present, those entries are appended after persistent entries.
- **Scan SKILL.md** gains Phase A.7.3 (scan annotations) before A.7.5 (apply suppressions). The A.7.5 invocation conditionally includes `--annotations` when the annotations file is non-empty.

### Compatibility

- Backwards-compatible. Repos without annotations behave identically to v1.1.0; repos without `.securecoder/suppressions.json` behave identically to v1.0.0.
- No new pinned upstreams.
- No new external dependencies.

### Deferred to v1.3.0

- DOM-level virtualized rendering (smart-collapse is the workaround; ~100 LOC plain-JS virtual scroll remains future work).
- Block-comment annotation syntax (`/* securecoder: ignore */`). Line comments only for now.
- Live workflow YAML installation (still ships as a `scripts/ci/pinned-tag-bumps.yml.template` due to OAuth-scope limits on the install token).
- Windows end-to-end validation.
- Higher-coverage pytest backfill for the render functions and search helpers (currently smoke-tested via integration only).

## [1.1.0] — 2026-05-14

False-positive suppression. Eight slices covering the full feature: schema + matcher + scan integration + new skill + fix/review integration + HTML UI (per-finding + multi-select + cluster view + suppressions section) + advise integration + 22 pytest tests.

### Added

- **`/securecoder-suppress` — the 8th skill.** Eight modes: `add` (with simple `key=value and key=value` match expression or JSON form), `import` (batch from HTML report), `show` (all / specific finding / stale / expired), `remove`, `expire`. Auto-populates `created_at` + `created_by` (from `git config user.email`). Dedupes by signature (match + reason).
- **`apply_suppressions.py`** — runs as Phase A.7.5 of `/securecoder-scan` (after merge, before manifest). Implements most-specific-wins resolution (id > rule+file > rule+file_glob > rule | framework_ref > file_glob). Stamps `status: "suppressed"`, `suppression_reason`, `suppression_match` (with `suppressions.json#<index>` pointer) on matching findings. Skips expired entries at match time. No-op pass-through when no suppressions file.
- **Manifest extensions.** `totals.findings_active`, `totals.findings_suppressed`, `suppressed_by_entry` (entry index → match count this run). Used by the HTML report's stale-suppression banner and by `/securecoder-suppress show stale`.
- **HTML report — multi-select.** Checkboxes on every finding card, sticky bar with select-all / select-filtered / suppress-N-selected / clear-selection. Multi-select bulk-suppress prompts for one reason, stages one entry per selected finding.
- **HTML report — per-finding suppress UI.** Three buttons per finding card (suppress this instance / rule here / rule project-wide). Inline form with required reason + optional expiry. Each entry can be added to the localStorage staging tray or copied as a single command immediately.
- **HTML report — cluster view.** Second view tab grouping by `(rule_id, file_path_prefix)`. Heuristic prefix discovery with 3-finding floor + 80% coverage ceiling, falling back to the longest prefix with ≥3 coverage when 80% rejected everything. Per-cluster "Suppress entire cluster" generates pattern-based entries.
- **HTML report — staging tray.** Sticky bottom banner with count, [Export to agent], [Clear], [Review]. localStorage-persisted per run id. Review modal lists staged entries with per-entry remove buttons. Export generates `/securecoder-suppress import [...]` and copies to clipboard with confirmation toast.
- **HTML report — show-suppressed toggle.** Body defaults to `class="hide-suppressed"` when any finding has `status: "suppressed"`. Checkbox in filters area flips the class. CSS uses `:has()` to collapse file groups whose findings are all suppressed.
- **HTML report — severity-floor advisory banner.** When any single severity exceeds 1000 findings, shows a banner suggesting raising `severity_floor` or switching to clusters view.
- **HTML report — stale suppressions banner.** When `suppressed_by_entry` has entries with 0 matches this run, lists up to 5 inline with a pointer to `/securecoder-suppress show stale`.
- **HTML report — Suppressions section.** Table at the bottom of every report: index, match expression, reason, created_at, created_by, expires_at, caught-this-run count.
- **Markdown report — Suppressed findings collapsed section.** Suppressed findings exit the main grouping and appear in a `<details>` block at the end with the reason + match pointer.
- **`/securecoder-fix` integration.** Severity-scope filter drops `status: "suppressed"` findings, recording each as `editor_skipped_suppressed` in `fix_log.jsonl` (distinct from `editor_skipped` which is user-skipped in interactive mode). Interactive one-by-one mode gains a `suppress` action alongside apply/skip/quit — prompts for reason, invokes `/securecoder-suppress add`, continues.
- **`/securecoder-review` integration.** Both the interactive flow (via the same findings stream) and the pre-commit hook respect suppressions. `review_hook.py` reads `.securecoder/suppressions.json` directly and filters tool outputs before computing its exit code. Hook's matcher is a minimal subset (rule + file + file_glob; not id or framework_ref since the hook doesn't compute canonical IDs).
- **`/securecoder-advise` integration.** New `suppressions` mode in the no-arg picker. Three natural-language intents recognized: "show all suppressions", "why is finding X suppressed?", "why is finding X still appearing?" — all answered from the static JSON data (no matching logic needed).
- **22 pytest unit tests.** First proper pytest suites in the project. Cover `apply_suppressions.py` (matchers, specificity, expiry, stats, pointer format) and `compute_clusters()` (under-three-findings, shared-prefix, diverging-paths, two-cluster ordering, suppressed counted, 80% ceiling fallback, sample ordering). All 22 pass on Python 3.9.6.
- **New per-skill guide** at `docs/guides/per-skill/securecoder-suppress.md`.
- **New scenario** "Triaging a 2,000-finding scan" in `docs/guides/scenarios.md`.

### Compatibility

- **Backwards-compatible.** Repos without `.securecoder/suppressions.json` behave exactly like v1.0.0 — `apply_suppressions.py` is a pass-through; the HTML report's suppression UI still appears but stages to localStorage only.
- **No new pinned upstreams.** No new tool installs.
- **Schema version of `suppressions.json` is `1.0`**, separate from `config.json`'s `schema_version`.

### Deferred to v1.2.0

- **DOM-level virtualized rendering** of the flat findings list (~100 LOC plain-JS virtual scroll). For now, the cluster view (already shipped) is the recommended triage path for 1000+ finding repos.
- **Source-code comment annotations** (`# securecoder: ignore`) as an alternative suppression input layer.
- **Sampling-assisted review** for very large clusters ("review 5 random, suppress all if all FP").

## [1.0.0] — 2026-05-14

The stable initial release. All seven skills functional, all 10 pinned upstreams documented, multi-framework compliance, CI bumper template, and end-to-end smoke tests across every helper script.

### Stabilization
- **All seven skills functional and shipped** since v0.11.0; v0.12.0 added the multi-framework breadth on top.
- **Smoke-tested every helper script** end-to-end with synthetic inputs in the v1.0.0 release commit. Each Python helper parses cleanly under Python 3.9+. Each normalizer produces v1.0-schema-conformant findings. Each renderer produces the documented output shape.
- **One fix during stabilization:** `validate_coverage.py`'s regex was correctly catching chapter-source control IDs (`**1.1.1**`) but missing the V-prefixed form in LLM responses (`V1.1.1`). The regex now allows `V` as a bare prefix on the control ID rather than treating it as needing its own digit suffix. This is a bug fix; no schema changes.
- **CHANGELOG complete back to v0.1.0** documenting every behavior decision and every pinned upstream version bump.

### Where to start
1. Install: `npx skills@latest add nerdy-krishna/securecoder`.
2. From any project: `/securecoder-setup`.
3. Audit: `/securecoder-scan` (SAST + ASVS).
4. Remediate: `/securecoder-fix` (or `/securecoder-secure` for the whole pipeline).
5. Pre-commit gate: `/securecoder-review` (install the hook for SAST-only blocking).
6. While coding: `/securecoder-build` to wrap the session in ASVS supervision.
7. Q&A: `/securecoder-advise`.

### The skill set, final shape
- `/securecoder-setup` — config wizard
- `/securecoder-scan` — SAST (Semgrep, Bandit, Gitleaks, OSV-scanner) + LLM compliance (ASVS v5, MASVS, Proactive Controls) + markdown + HTML report + cross-run trend
- `/securecoder-fix` — SAST and compliance findings with full safety loop + restore
- `/securecoder-secure` — easy-button 4-phase pipeline with one approval
- `/securecoder-review` — diff-scoped pre-commit gate + hook installer
- `/securecoder-build` — persistent ASVS supervision mode
- `/securecoder-advise` — grounded Q&A

### Pinned upstreams (current as of v1.0.0)
- Semgrep: `1.91.0`
- Bandit: `1.7.10`
- Gitleaks: `8.18.4`
- OSV-scanner: `1.9.2`
- `returntocorp/semgrep-rules`: branch `main`, content-addressed by SHA
- `OWASP/ASVS`: branch `master`, content-addressed by SHA
- `OWASP/owasp-masvs`: branch `master`, content-addressed by SHA
- `OWASP/www-project-proactive-controls`: branch `master`, content-addressed by SHA
- `OWASP/CheatSheetSeries`: branch `master`, content-addressed by SHA

### What's NOT in v1.0.0 (deferred)
- Unit tests for the helper scripts. Manual smoke-testing covered every helper end-to-end before each release. Adding proper pytest suites is the v1.1.0 priority.
- The CI workflow YAML is shipped as a template at `scripts/ci/pinned-tag-bumps.yml.template` — needs to be moved to `.github/workflows/` and committed with a workflow-scoped token. The pin-checker Python script is fully functional.
- Windows end-to-end validation. Path handling is implemented but only macOS + Linux validated during development.

## [0.12.0] — 2026-05-14

Multi-framework compliance and maintenance CI. The compliance pass now extends to MASVS (mobile) and OWASP Proactive Controls; Cheatsheets become available as remediation reference. A GitHub Action checks all pinned upstreams weekly and opens a PR when releases advance.

### Added (slice 13 — multi-framework)
- **Framework registry** at `skills/security/securecoder-scan/references/frameworks.json` listing every supported framework with source repo, branch, chapter directory, control-ID regex, and per-framework relevance file. ASVS v5, MASVS, Proactive Controls, Cheatsheets.
- **`references/relevance-masvs.json`** — applicability hints for the 8 MASVS chapters (STORAGE / CRYPTO / AUTH / NETWORK / PLATFORM / CODE / RESILIENCE / PRIVACY) with mobile-stack language matchers + keyword triggers.
- **`references/relevance-proactive-controls.json`** — applicability for the 10 Proactive Controls (C1-C10), broadly backend-language scoped.
- **Mobile-stack auto-detection** — `frameworks.json` declares `_mobile_stack_signals` globs (iOS / Android / RN / Flutter). When `/securecoder-scan` Phase B starts, it auto-enables MASVS if any matching files are present.
- **Cheatsheets as remediation context** for `/securecoder-fix` — when a SAST or compliance finding maps to a CheatSheet (via CWE or rule-id heuristic), the relevant cheatsheet section is included in the fix-LLM prompt. Improves fix quality without changing the fix flow.
- The `cwe-to-framework.json` table gains a placeholder for cheatsheet refs (CWE → cheatsheet file basename), enabling enriched remediation hints.
- Renamed: `chapter-relevance.json` → `relevance-asvs-v5.json` to match the per-framework naming convention. The SKILL.md path references updated.

### Added (slice 14 — maintenance CI)
- **`scripts/ci/check_pins.py`** — reads current pinned versions out of SKILL.md and `frameworks.json`, queries the GitHub Releases API for each upstream (Semgrep, Bandit, Gitleaks, OSV-scanner, OWASP/ASVS, OWASP/owasp-masvs, OWASP/www-project-proactive-controls, OWASP/CheatSheetSeries), compares, and produces JSON + Markdown reports.
- **`scripts/ci/pinned-tag-bumps.yml.template`** — drop-in GitHub Actions workflow. Runs weekly on Mondays at 09:00 UTC plus `workflow_dispatch` on demand. Opens a `chore: pinned upstream version bumps` PR (labels: `dependencies`, `auto-pr`) when any tool pin is outdated; duplicate-detects existing open PRs on the same branch. **Install:** move to `.github/workflows/pinned-tag-bumps.yml` and commit with a token that has the `workflow` scope. Shipped as a template so the package install via skills.sh doesn't require additional GitHub permissions.

### Compatibility
- The compliance pass still works with just `asvs-v5` enabled (the default). New frameworks are opt-in (or auto-enabled in MASVS's case).
- The CI workflow needs `contents: write` and `pull-requests: write` permissions — already declared in the YAML.

### Tests
- Deferred. The new relevance files are JSON data; the per-framework Phase B logic reuses the existing tested machinery. The CI check_pins.py script is best validated by running it against the live GitHub API, which the workflow itself does on the schedule.

## [0.11.0] — 2026-05-14

`/securecoder-advise` becomes functional. Interactive Q&A grounded in cached framework markdown and the latest scan's findings. Read-only — never modifies code.

### Added
- **`/securecoder-advise`** with 4-mode picker (general / findings-grounded / specific finding deep-dive / framework lookup). Default invocation: `/securecoder-advise <question>`. No-arg invocation presents the mode picker.
- **`scripts/search_rules.py`** — keyword search across cached framework markdown. Splits by markdown headings, scores by keyword occurrences in body (1.0) / heading (3.0), bonus for sections containing control IDs. Returns top-N matching sections with snippet previews. Available to the agent and invokable by users directly ("search the ASVS for SSRF").
- **Verbatim-cite-then-interpret response format.** Every answer quotes framework text in a blockquote first, citing `<framework> <version> <control-id>`, then interprets in plain language, then cross-references user findings when applicable.
- **Loaded-context summary** on first turn so the user sees what's grounding the answers (framework versions, finding counts, severity floor).

### Compatibility
- Reads framework cache populated by `/securecoder-scan` Phase B. If empty, the skill answers with an explicit ungrounded disclaimer and recommends running a scan.
- Skill is fully offline-capable once the cache is populated.

## [0.10.0] — 2026-05-14

`/securecoder-build` becomes functional. The skill emits a persistent secure-build policy block into the chat session that supervises every subsequent code-producing task. Optional minimal bootstrap for empty repos. ASVS-only by default.

### Added
- **`/securecoder-build` persistent policy block** — emitted once to chat, the host agent's context retention keeps it alive across turns. Pre-task / post-task protocol with a SATISFIED / PARTIAL / UNKNOWN / N/A classification rubric. Escalation rule for when a control conflicts with what the user asked for. Adjunct hint to run `/securecoder-review` after substantive changes.
- **"Controls applied" reporting template** that the agent appends to every code-producing response — verbatim control IDs, classification, one-line interpretation.
- **Optional minimal bootstrap** for empty repos. Generates `.securecoder/config.json`, `.gitignore`, `.env.example`, and installs the pre-commit hook from `/securecoder-review`. Deliberately minimal — does NOT generate per-stack scaffolds (FastAPI app structure, etc.), since the agent's general knowledge plus the ASVS reference is sufficient for one-off tasks.
- **Explicit + implicit deactivation.** `end secure build mode` / `/securecoder-build --end` deactivates explicitly; long-session context eviction deactivates implicitly. No on-disk state to clean up either way.

### Compatibility
- Requires ASVS markdown cached at `~/.cache/securecoder/rules/frameworks/asvs/<sha>/`. The skill fetches it on first use if missing (same fetch flow as `/securecoder-scan` Phase B.1).
- Offline mode works with reduced grounding — the agent still applies the protocol but can't read chapter source verbatim.

### HITL note
- The policy block wording is high-leverage. Future edits to this skill's SKILL.md should go through manual review before merge — the literal text shapes every agent response for the rest of the user's session.

## [0.9.0] — 2026-05-14

`/securecoder-review` becomes functional. Diff-scoped security review — SAST + scoped LLM compliance on changed hunks only. Cost proportional to diff size, not repo size. Optional pre-commit hook installation for SAST-only blocking-mode in `git`'s shell context.

### Added
- **`/securecoder-review`** with 4 scope modes: staged / staged+unstaged / branch-vs-base / specific commit range. Default: staged.
- **`scripts/diff_scoper.py`** — unified-diff parser. Outputs per-file added line ranges plus ±20-line context windows. Tolerates hunk boundaries, file renames, new files, deletions.
- **`scripts/review_hook.py`** — standalone pre-commit shim. Runs SAST tools against staged files only (no LLM call, no agent dependency). Blocks the commit when any finding above `config.severity_floor` is present. Reminds the user to run `/securecoder-review` interactively for compliance review before pushing.
- **Diff-scope filtering** for both SAST and compliance findings — findings in unchanged regions of touched files are dropped from the review report. The full scan output is still available via `/securecoder-scan`.
- **`.securecoder/reviews/<id>/`** directory layout — separate from `.securecoder/runs/<id>/`, so review history doesn't pollute the cross-run trend baseline.
- **Optional hook installation** with automatic backup of any pre-existing `.git/hooks/pre-commit` — `before-securecoder-<timestamp>` suffix.

### Compatibility
- Hook reuses cached SAST binaries from `~/.cache/securecoder/tools/`. If they're missing, the hook prints a hint and exits 0 (doesn't block commits just because the cache is empty).
- Bypassable per-commit via `git commit --no-verify`.

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

[Unreleased]: https://github.com/nerdy-krishna/securecoder/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v1.2.0
[1.1.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v1.1.0
[1.0.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v1.0.0
[0.12.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.12.0
[0.11.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.11.0
[0.10.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.10.0
[0.9.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.9.0
[0.8.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.8.0
[0.7.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.7.0
[0.6.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.6.0
[0.5.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.5.0
[0.4.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.4.0
[0.3.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.3.0
[0.2.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.2.0
[0.1.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.1.0
