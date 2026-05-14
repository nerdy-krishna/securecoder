# PRD — securecoder v1

- **Status:** ready-for-agent
- **Date:** 2026-05-13
- **Companion design doc:** [`docs/design.md`](./design.md) — full specs for every decision summarized here

## Problem Statement

Developers using AI coding agents (Claude Code, Cursor, Codex, Cline, Copilot, Windsurf, Gemini, etc.) want to write secure code, but they lack a portable, agent-native way to audit existing code for vulnerabilities or stay aligned to compliance frameworks like OWASP ASVS while building. The existing options are heavy: SCCAP itself is a server-side platform (Postgres, RabbitMQ, FastAPI, multi-agent LangGraph), Snyk and similar SaaS tools require accounts and integration, and standalone SAST tools don't carry framework knowledge or remediation guidance. None of these fit naturally into a slash-command agent workflow. The result is that security gets bolted on later (or skipped), and agents produce code that satisfies the visible feature but silently violates ASVS controls or contains injection / secret / dependency vulnerabilities.

## Solution

A collection of seven composable agent skills, distributed via skills.sh (`npx skills@latest add nerdy-krishna/securecoder`), that any modern coding agent can install. The skills fetch SAST tools (Semgrep, Bandit, Gitleaks, OSV-scanner) and OWASP framework markdown (ASVS, MASVS, Cheatsheets, Proactive Controls) at runtime from an allowlisted set of sources, cache them content-addressed under the user's home cache, and orchestrate scan/fix/compliance/build workflows by emitting plain-English instructions for the host agent to follow.

The seven skills:

- `/securecoder-setup` — one-time team config writing `.securecoder/config.json`
- `/securecoder-scan` — audit existing code; modes: SAST only / LLM compliance only / both
- `/securecoder-fix` — remediate findings; modes: by severity multi-select / by ID / interactive
- `/securecoder-secure` — easy-button end-to-end pipeline with one up-front cost approval
- `/securecoder-review` — diff-scoped pre-commit gate
- `/securecoder-build` — persistent ASVS policy layer for in-flight builds
- `/securecoder-advise` — Q&A grounded in fetched framework markdown + latest findings

Inter-skill communication is filesystem-only (run dirs, config files, cache). No host-specific primitives are used. Skills install once and work across every supported agent host.

## User Stories

1. As a solo developer, I want to install one skill collection that works in my coding agent of choice, so that I don't need a separate security service.
2. As a developer auditing an unfamiliar repo, I want to invoke `/securecoder-scan` and get a list of vulnerabilities, so I know what's wrong before changing anything.
3. As a developer with a quick-fix mindset, I want `/securecoder-secure` to do scan + fix + compliance review + fix with one approval, so I don't have to chain commands.
4. As a cost-conscious user, I want to see an estimated token spend before any LLM call runs, so I can decide if the run is worth it.
5. As a developer who picked the wrong scan mode, I want a `scan-only` exit option at the cost-approval gate, so I can abort the fix phase.
6. As a developer on a tight budget, I want the skill to pause mid-run if the compliance phase exceeds estimated tokens by 50%, so I can stop a runaway cost.
7. As a developer who wants only critical fixes, I want to pick severities in `/securecoder-fix` (any combination, not just preset bundles), so I'm not editing low-severity issues I don't care about.
8. As a careful developer, I want to apply fixes one-by-one with review, so I can vet each change.
9. As a confident developer, I want to apply all fixes in one batch with a summary at the end, so I save time.
10. As a developer whose fix went wrong, I want to roll back the run from filesystem backups, so I can recover even if git operations failed.
11. As a git user, I want each successful fix to land as its own commit, so I can `git revert` individual fixes if needed.
12. As a CI-aware developer, I want to choose whether each commit pushes immediately, batches at end, or stays local, so I can match my team's workflow.
13. As a developer on `main`, I want the skill to warn me and offer to create a `securecoder-fix/<run-id>` branch, so I don't accidentally rewrite history.
14. As a developer with uncommitted changes, I want the skill to ask before running fixes, so my work isn't entangled with auto-edits.
15. As a developer on a non-Python codebase, I want the syntax checker for my language to be installed on demand, so I get the same verify-loop safety as Python users.
16. As a developer working in JS / Go / Rust / Ruby / etc., I want the skill to detect my language and fetch the right Semgrep rules, so I don't need to configure anything manually.
17. As a developer who edits a file mid-run, I want the patch applier to refuse to apply if the SEARCH text appears zero or many times, so I don't silently get wrong changes.
18. As a developer reviewing fixes, I want a `git diff --stat` summary at the end, so I can see scope at a glance.
19. As a team lead, I want `.securecoder/config.json` to be checked into git, so framework choices and severity floors are shared across the team.
20. As a developer new to a repo, I want the skill to use sensible defaults if no config exists, so I can run a scan without going through setup first.
21. As a returning user, I want `/securecoder-setup` to load my current config as pre-selected defaults, so I'm not re-answering every question.
22. As a compliance officer, I want to see per-framework posture scores (X of Y controls passing), so I can report on coverage.
23. As a team adopting ASVS, I want OWASP/ASVS markdown fetched at a pinned tag, so all team members see the same controls.
24. As a security engineer, I want pinned rule packs locked by content-addressed SHA, so I know an attacker can't poison the rule set silently.
25. As a paranoid user, I want only OWASP and Semgrep's official orgs on the allowlist, so I'm not pulling rules from arbitrary repos.
26. As an advanced user, I want to add custom rule sources, so I can extend coverage with my own rules.
27. As a developer adding a custom source, I want a one-time confirmation prompt before first use, so I don't accidentally trust a typo'd URL.
28. As an offline user (plane, train), I want cached rules and tools to work without network, so my flight time is productive.
29. As an offline user with a cold cache, I want a clear error message, so I know I need network access first.
30. As a developer on a fresh machine, I want one-time consent before the skill installs ~150MB of tools, so I'm not surprised by disk usage.
31. As a developer who already has Semgrep installed system-wide, I want to override the cached version with my system install via config, so I don't waste disk space.
32. As a developer with no dependency manifest, I want to disable OSV-scanner, so I'm not running irrelevant tools.
33. As a developer running pre-commit checks, I want a fast SAST-only review on my staged changes, so commits don't slow down.
34. As a developer about to push, I want to invoke `/securecoder-review` interactively for full LLM compliance review on the diff, so I catch design issues before push.
35. As a developer with a large diff, I want compliance review scoped to changed hunks + ±20 lines of context, so cost stays proportional to the change size.
36. As a developer starting a new project, I want `/securecoder-build` to install a persistent ASVS policy layer in my chat, so all subsequent agent work is supervised.
37. As a developer in secure-build mode, I want the agent to identify applicable ASVS controls before writing code, so security is planned not retrofitted.
38. As a developer in secure-build mode, I want the agent to self-check its output against applicable controls, so issues are caught before they hit disk.
39. As a developer starting from an empty repo, I want an optional minimal bootstrap from `/securecoder-build`, so I get secure defaults wired up before I start.
40. As a developer ending secure-build mode, I want it to deactivate on explicit signal or natural context drop, so I don't need session cleanup.
41. As a developer needing a quick reference, I want `/securecoder-advise` to answer questions grounded in cached framework markdown, so my agent doesn't hallucinate controls.
42. As a developer reviewing a specific finding, I want `/securecoder-advise` to deep-dive on a finding ID, so I get framework refs + remediation guidance for that exact issue.
43. As a developer learning ASVS, I want verbatim-cited control text before any interpretation, so I trust the source.
44. As a developer searching for "SSRF", I want a search helper that scans cached framework markdown for matches, so I find the relevant controls quickly.
45. As an open-source maintainer, I want to install only the skills I need (e.g., just `/securecoder-review`), so my agent isn't cluttered.
46. As a contributor to the skill, I want each skill dir to be self-contained, so I can refactor one without breaking others.
47. As a contributor, I want shipped `cwe-to-framework.json` curated in git, so cross-framework mappings are reviewable.
48. As a tools maintainer, I want pinned tool versions bumped on patch releases, so security updates flow through quickly.
49. As a tools maintainer, I want a CI action that opens PRs when upstream tags update, so I'm not manually checking releases.
50. As an early adopter, I want each skill released as a separate semver bump, so I can adopt incrementally.
51. As a developer migrating from skill v0.X to v1.0, I want migration scripts to handle schema changes, so my old runs and configs don't break.
52. As a developer running on Windows, I want the skill to use `%LOCALAPPDATA%\securecoder\` for cache, so paths follow OS conventions.
53. As a developer running on macOS, I want the cache at `~/Library/Caches/securecoder/`, so it's correctly excluded from Time Machine by default.
54. As a developer on a sandboxed host (Codex web), I want the skill to fall back to sequential execution gracefully when subagent parallelism isn't available, so it doesn't crash.
55. As a developer worried about privacy, I want a clear statement of what data leaves my machine, so I can make informed choices.
56. As a developer using a self-hosted LLM, I want the skill to work without phoning home, so my source code stays internal.
57. As a developer reviewing run history, I want every run preserved in `.securecoder/runs/<id>/`, so I can compare scans over time.
58. As a developer comparing runs, I want the report to show new / resolved / persistent findings, so I track remediation progress.
59. As a developer reading reports, I want both markdown and HTML formats, so I can choose terminal or browser.
60. As a developer reading reports offline, I want HTML to be self-contained (no CDN deps), so reports work on a plane.
61. As a developer on a private repo, I want the skill to never publish my code anywhere, so I retain confidentiality.
62. As a developer with a non-git project, I want `/securecoder-fix` to use file backups instead of git history, so rollback still works.
63. As a developer with a small team, I want the skill to work without CI integration, so I don't need to set up automation upfront.
64. As a developer whose auto-fix broke a file, I want the fix to roll back automatically, so my repo isn't left in a broken state.
65. As a developer dealing with `editor_failed`, I want a clear log of why the fix failed, so I can fix it manually.
66. As a developer using a stack the skill doesn't know, I want a generic fallback for `/securecoder-build`, so I still get value.
67. As a developer where the LLM failed 3 times on one finding, I want the skill to give up gracefully and move to the next finding, so one bad fix doesn't block the batch.
68. As a developer who wants to suppress noisy findings, I want to set a `severity_floor` in config, so low findings don't clutter reports.
69. As a developer who wants per-folder exclusions, I want to set excludes either in config or interactively at scan time, so vendor and generated dirs are skipped.
70. As a developer running the same scan twice, I want canonical IDs to be stable, so findings dedupe correctly across runs and the trend view works.
71. As a developer reading a finding, I want `framework_refs` populated even on SAST-detected findings, so I can see which ASVS controls a SQL injection violates.
72. As a developer running the skill on a repo without git, I want the warning to be informational rather than a hard fail, so I can still scan and fix.
73. As a developer extending the skill, I want a documented `findings.jsonl` schema, so I can write my own tooling against it.

## Implementation Decisions

### Architectural

- **Pure agent skill.** SKILL.md instructions plus small Python-stdlib helper scripts. No daemon, server, MCP, or persistent process. The host agent orchestrates everything.
- **Language-agnostic via runtime fetching.** Skill ships no rules and no framework controls; both are fetched at runtime from allowlisted sources.
- **Lowest-common-denominator multi-tool.** Skills do not use Claude-Code-specific primitives (`Agent`, `AskUserQuestion`, model pinning). SKILL.md describes asks in plain English; each host implements its own prompt mechanism.
- **Filesystem as inter-skill interface.** No slash-command argv reliance. `/securecoder-fix` reads `.securecoder/runs/latest/findings.jsonl`. Targeting a specific run is via natural-language ask interpreted against SKILL.md.
- **Audit-first with explicit cost gates.** No paid work runs without a deterministic token estimate shown and approval taken.
- **Safety over throughput in fix loops.** Pre-flight + per-fix verify + automatic rollback are mandatory, not optional.

### Modules (directional — to be refined during implementation)

Eighteen module surfaces grouped by depth and purpose. The interface contract for each is "small, single-responsibility, file-or-data in → file-or-data out where possible."

**Pure-transform modules (deeply testable):**
- Findings normalizers — one per SAST tool (Semgrep, Bandit, Gitleaks, OSV-scanner). Input: tool's native JSON output. Output: list of findings conforming to the v1.0 schema.
- Canonical-ID computer. Input: finding fields. Output: stable sha256-derived ID.
- CWE-to-framework enricher. Input: CWE list + shipped table. Output: framework_refs list.
- Coverage matrix validator. Input: chapter source markdown + LLM response. Output: missing-control list (empty if valid), used to drive retry-with-context.
- File relevance filter. Input: file metadata (path, language, role hint) + chapter applicability rules. Output: boolean dispatch decision + rationale.
- Cost estimator. Input: repo map + framework selections + tool plan. Output: per-phase token + wall-time estimate.
- Report renderer. Input: findings + manifest. Output: markdown + self-contained HTML.
- Diff scoper. Input: `git diff` text. Output: per-file changed line ranges + ±20-line context windows.
- Search helper. Input: keyword/concept + cached framework markdown dir. Output: ranked top-N matching sections with control IDs.

**Safety-critical modules (deep + must-test):**
- Patch applier. Parses SEARCH/REPLACE blocks; validates single-match; applies; supports rollback. Pure function over text inputs; integrates with file I/O at the edges only.
- Syntax-checker dispatcher. Extension → checker command resolution; install-on-demand into `~/.cache/securecoder/tools/`; invoke and parse pass/fail; UTF-8-validity fallback when no checker exists.
- Rule-pack fetcher. Allowlist gating, `git clone --depth 1 --branch <tag>`, content-address by SHA, integrity verify on reuse, offline-fail with clear message.

**Filesystem state managers (less deep, integration-tested):**
- Run directory manager. Creates `.securecoder/runs/<id>/`, writes manifest, maintains `latest` symlink invariant.
- Config loader. Reads `.securecoder/config.json`, validates against v1.0 schema, runs migrations on schema mismatch.
- Cache directory manager. Owns `~/.cache/securecoder/` layout, tracks consent record in `manifest.json`.

**Fetchers / installers (platform-heavy, integration-tested):**
- Tool installer. pipx-or-venv for Python tools; GitHub-release-binary download for natives; OS+arch detection; one-time consent gate.

**Compute helpers:**
- Repo walker. Filter rules (binary heuristic, size limit, ignore dirs), language detection by extension table, exclusion globs.

**Standalone shim (no agent dependency):**
- Pre-commit hook script. SAST-only review on staged files; exit code non-zero if any finding above `severity_floor`.

**Git operations wrapper.** Thin subprocess wrapper for clean-tree check, branch ops, commit-per-fix, push-strategy dispatch.

### Schema

- **`findings.jsonl` schema v1.0.** Per-finding fields: `id`, `file`, `lines`, `source`, `source_rule_id`, `category` (sast / compliance), `cwe`, `framework_refs`, `severity` (critical / high / medium / low / info), `confidence` (high / medium / low), `title`, `description`, `evidence`, `remediation_hint`, `fix_complexity` (low / medium / high), `tags`, `detected_at`, `status` (open / applied / editor_failed / manual_review_required / suppressed), `history`.
- **Canonical-ID derivation.** SAST: `sha256(file + line_start + source_rule_id)`. Compliance: `sha256(file + framework + control_id)`. Stable across runs to support trend tracking.
- **`manifest.json` per run.** Schema version, run_id, repo_sha, tool versions, rule-pack SHAs, framework versions, per-phase duration + token totals, findings count.
- **`.securecoder/config.json` v1.0.** Eight fields: `frameworks`, `severity_floor`, `default_fix_scope`, `git.push_strategy`, `languages`, `rule_pins`, `tools`, `custom_sources`.

### State and filesystem

- In-repo `.securecoder/` holds `config.json` (checked in, team-shared), `runs/<id>/` (gitignored), `reviews/<id>/` (gitignored, separate from runs).
- User cache `~/.cache/securecoder/` (OS-appropriate: `~/Library/Caches/securecoder/` on macOS, `%LOCALAPPDATA%\securecoder\` on Windows) holds `tools/`, `rules/`, and a global `manifest.json` recording consent + integrity hashes.
- `latest` pointer: symlink on Unix, `latest.json` JSON fallback on Windows.

### Network and supply chain

- **Allowlist:** `OWASP/*` and `returntocorp/*` orgs only for automatic fetches. Custom sources in config require one-time confirmation before first use.
- **Pinned tags + content-addressed cache.** Cache key is the git SHA of the fetched tree; integrity verified on every reuse.
- **No TTL.** Cache hit means cache hit until explicit refresh (`/securecoder-setup --refresh-rules`).
- **OSV is online-API-queried** (no fetch); Gitleaks and Bandit ship their own rules (no fetch).
- **Skill releases bump default pinned tags.** Maintenance burden mitigated by a CI action that opens PRs on upstream tag bumps.

### Auto-fix safety

- **Pre-flight:** git clean-tree check (stash/abort/proceed); protected-branch warning with offer to create `securecoder-fix/<run-id>` branch; per-file backup capture to `.securecoder/runs/<id>/backups/`; cost estimate; one approval.
- **Per-fix loop:** locate → LLM SEARCH/REPLACE → single-match validation → apply → language-detected syntax check → re-scan with originating SAST tool → on success commit; on any failure restore from backup and mark `editor_failed`.
- **Up to 3 LLM tries per finding** with retry context that names what failed (parse error / wrong match count / syntax failure / finding still present / new finding introduced).
- **Commit-per-fix.** Message format: `fix(securecoder): <severity>/<title> [<finding-id-short>]` with finding source / rule ID / CWE / original lines in body.
- **Push strategy** from `config.git.push_strategy`: `push-each` / `commit-local-push-at-end` (default) / `commit-local-never-push`.
- **Compliance findings with `fix_complexity: "high"` or `lines: null`** are never auto-fixed; marked `manual_review_required`.
- **Restore command.** Natural-language ask or `/securecoder-fix --restore <run-id>` copies backups back over the working tree.

### Cost estimation

- **Pre-flight is deterministic** — no LLM call needed. Token math: `input_tokens ≈ chars / 4` for compliance prompts; `output_tokens ≈ input × 0.30` calibrated from asvs-shell.
- **Token-first reporting** with a multi-model reference rate table shipped in SKILL.md (Opus, Sonnet, Haiku, GPT, Gemini). Host model is unknowable, so dollars are illustrative.
- **Approval gate options:** proceed / scan-only (skip fix phase) / abort.
- **50%-overrun mid-run gate.** After compliance phase in `/securecoder-secure`, if actual tokens exceed estimate by ≥ 50%, pause before fix phase and ask continue/abort.

### Reports

- Markdown + self-contained HTML per run. HTML inlines CSS, no external scripts or assets.
- Sections: summary (counts, severity breakdown, cost, wall time), compliance posture per framework, findings grouped by file (default; HTML filterable by severity / framework / source), trend (new / resolved / persistent vs prior runs matched by canonical ID), manifest footer.

### Distribution and versioning

- **skills.sh installer** via mattpocock-style `.claude-plugin/plugin.json` listing skill paths. Each skill dir fully self-contained.
- **Single `security/` category** in repo layout. `/securecoder-secure` declares "requires `/securecoder-scan` + `/securecoder-fix` installed" in its description.
- **Repo-wide semver** via git tags. `CHANGELOG.md` required per tag.
- **Breaking changes (major bump):** `findings.jsonl` or `.securecoder/config.json` schema changes, removal or rename of a skill. Migration scripts ship for every breaking change.
- **Minor bumps:** rule-pack pin updates. **Patch bumps:** tool version pin updates.

### Per-skill specifics

- **`/securecoder-setup`:** 8-question wizard. Defaults work without setup. Re-running loads current config as pre-selected.
- **`/securecoder-scan`:** internal mode picker (SAST / compliance / both) with explanations + token warnings. Both modes merge into one `findings.jsonl`.
- **`/securecoder-fix`:** severity-multi-select picker (any combination), plus by-ID and interactive-one-by-one modes.
- **`/securecoder-secure`:** one up-front approval covering whole pipeline; runs straight through; fix scope defaults from config.
- **`/securecoder-review`:** scope picker (staged / staged+unstaged / branch-vs-base / specific range); scoped SAST + scoped LLM compliance on hunks + context; output to `.securecoder/reviews/<id>/`; no auto-fix. Pre-commit hook shim is SAST-only.
- **`/securecoder-build`:** emits persistent ASVS-policy block into chat; optional minimal bootstrap for empty repos; pre-task + post-task self-check protocol; mode ends on explicit signal or context drop.
- **`/securecoder-advise`:** invocation with or without question; 4-mode picker for no-arg case; verbatim-cite-then-interpret response format; search helper available.

### Decisions explicitly inherited from the design grilling

The 17 locked decisions from the design session — architecture, granularity, scope, scan paths, skill set + modes, multi-tool LCD, state layout, rule fetching, tool installation, findings schema, auto-fix safety, cost estimation, setup wizard, secure-build policy block, review specifics, advise specifics, repo+reports+versioning — are summarized in `docs/design.md` §Appendix. PRs implementing this PRD must not silently change any of those decisions; changes require a design-doc update first.

## Testing Decisions

### What makes a good test

- **Test external behavior, not implementation details.** A normalizer test asserts "Semgrep JSON X produces findings Y," not "the normalizer calls method Z internally."
- **Prefer fixtures over mocks.** Capture real Semgrep / Bandit / Gitleaks / OSV-scanner JSON outputs to `tests/fixtures/` and assert against them. Refresh fixtures when tool versions bump.
- **Property-based tests for invariants.** Canonical-ID stability (same input → same ID), findings JSONL roundtrip (parse + serialize is identity), backup-restore round-trip (write, edit, restore = original).
- **Tests should run offline at the unit layer.** Rule-pack fetcher tested with local fixture repos served via `file://` URLs; tool installer integration-tested separately and gated by an env var.
- **Assertion messages must name what failed.** A diff scoper test that fails should say "expected hunks at lines 42-47 but got 41-46," not just "expected != actual."

### Modules covered (safety-critical + pure-transform per Q&A confirmation)

- Patch applier — happy path, zero-match SEARCH failure, multi-match SEARCH failure, rollback after syntax fail, rollback after re-scan reveals new finding, multi-block within one response.
- Syntax-checker dispatcher — extension-to-checker mapping table coverage, on-demand install path, UTF-8 fallback for unsupported languages, parse-error output handling.
- Rule-pack fetcher — allowlist enforcement, integrity-verify happy path, integrity-mismatch refuses run, offline-with-cache-hit succeeds, offline-with-cache-miss fails cleanly.
- Coverage matrix validator — complete coverage accepted, missing rows produce retry context, malformed table rejected.
- Findings normalizers — one happy-path test per SAST tool plus edge cases per tool (no findings, malformed output, partial output).
- Canonical-ID computer — stability across identical inputs, distinctness across different inputs, version compatibility across schema versions.
- CWE-to-framework enricher — single-CWE lookup, multi-CWE merge, unknown CWE handled.
- File relevance filter — positive applicability, negative applicability, unknown-language fallback, role-hint application.
- Cost estimator — known-input expected-output regression tests, scaling tests (estimate grows with repo size linearly).
- Report renderer — markdown + HTML structural assertions (sections present, severity counts match input), self-contained HTML (no external `<link>` or `<script>` with external src).
- Diff scoper — single-file diff, multi-file diff, additions-only / deletions-only / mixed, large diff stays scoped.
- Run directory manager — `latest` pointer invariant after concurrent creates (best-effort), backup-capture invariant before any edit.

### Modules not tested at the unit layer (v1)

Tool installer (platform-heavy, integration-tested with env-var gate), config loader (thin JSON I/O), cache directory manager (thin filesystem ops), repo walker (well-covered by integration tests via fetcher + scan), search helper (small, covered via `/securecoder-advise` integration), git operations wrapper (thin subprocess wrapping), pre-commit hook script (covered via integration test with a temp git repo).

### Prior art

- **asvs-shell** at `/Users/overlord/Projects/asvs-shell` already implements the coverage-matrix validation pattern (parse expected control IDs from chapter source, assert exact-once presence in LLM response, retry with named-missing context). Reuse the validation logic and tests as a baseline.
- **asvs-shell's SEARCH/REPLACE patch loop** is the prior art for the patch applier; lift its parse regex and retry pattern.
- Standard Python testing tooling (`pytest`, `hypothesis` for property tests). No bespoke harness.

## Out of Scope

The following are explicitly deferred and must not block v1:

- CI integration (GitHub Actions workflow file for running scans on PRs)
- SARIF / JUnit / SPDX export formats
- A hosted dashboard or web UI for reports
- Multi-service / monorepo scaffolds in `/securecoder-build`
- Cloud-specific scaffolds (AWS Lambda, GCP Cloud Run, Cloudflare Workers) in `/securecoder-build`
- Curated per-stack secure-scaffold guides (dropped from `/securecoder-build` per Q14 redo)
- Fetching maintained secure-starter repos from GitHub for scaffolding
- Real-time live cost ticker during runs (asvs-shell style)
- Multi-environment config profiles (dev vs CI vs prod)
- Per-folder severity overrides in config
- Automatic re-run of compliance pass on fixed files
- Conflict resolution when the user edits files mid-run beyond the single-match SEARCH check
- TypeScript-strict syntax check via `tsc` (best-effort UTF-8 fallback in v1)
- Slack / email / Discord notifications
- Running the project's test suite after fixes
- SCCAP backend integration of any kind (MCP, REST, OAuth)
- Subagent parallelism (Claude Code only — dropped per multi-tool LCD)
- Model pinning (host-specific — dropped per multi-tool LCD)
- Git hooks beyond pre-commit (pre-push, commit-msg, post-merge)
- A review-against-PR mode (`/securecoder-review --pr <number>`)
- Per-skill independent semver versioning
- Bundling SAST tools inside the skill repo (download-only, no embedding)
- Docker fallback for tool installation
- Auto-upgrade of tools or rules outside of skill version bumps
- Custom Semgrep rules authored in `.securecoder/rules/` (no in-repo rule authoring in v1)
- Subscribing to the semgrep.dev registry packs that require authentication
- A "compare framework X vs Y" mode in `/securecoder-advise`
- Saving conversation history to `.securecoder/` from `/securecoder-advise`
- A web-search mode for `/securecoder-advise`

## Further Notes

- **The design doc is the source of truth for behavior.** This PRD summarizes; `docs/design.md` is the long form. If they disagree, the design doc wins until updated.
- **Recommended v1 build order is in design.md §13.** Slice 1: `/securecoder-setup` + `/securecoder-scan` SAST-only path; Slice 2: `/securecoder-fix`; Slice 3: `/securecoder-scan` compliance path; Slice 4: `/securecoder-secure`; Slice 5: `/securecoder-review`; Slice 6: `/securecoder-build` + `/securecoder-advise`. Each ships as its own minor semver tag so users can adopt incrementally.
- **Maintenance treadmill.** Six pinned-tag rule packs plus four pinned-version tools means manual upkeep gets neglected fast. Wire a CI action that opens PRs against this repo when any pinned upstream has a new release. This is a v0.1.0 setup task, not a future optimization.
- **Privacy surface to surface in README.** The skill never sends source code anywhere itself, but LLM calls flow source to whatever provider the host agent uses (Anthropic, OpenAI, Google, etc.). The `/securecoder-setup` wizard surfaces this explicitly the first time the user enables compliance mode.
- **Reference implementation.** The asvs-shell prototype (`/Users/overlord/Projects/asvs-shell`) is the closest functional precedent. Its 3-stage pipeline (summarizer → architect → editor) maps to the new skill's SAST-or-compliance → fix flow. The new skill drops asvs-shell's Claude-Code-specific machinery (subagents, AskUserQuestion, model pinning) per the multi-tool LCD constraint, and adds the SAST path that asvs-shell doesn't have.
- **No published GitHub repo yet.** The skill's home will be a new repo (proposed: `nerdy-krishna/securecoder`) — create it before tagging v0.1.0 so skills.sh installs work.
