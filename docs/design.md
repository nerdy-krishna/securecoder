# securecoder — Design Document

- **Status:** v1 spec, ready to implement
- **Date:** 2026-05-13
- **Author:** Krishna (`krishna.worklife@gmail.com`)
- **Source-of-truth for:** repo layout, skill behaviors, schemas, safety model, build order

## 1. Overview

`securecoder` is an installable collection of agent skills for secure coding. It distills the OWASP-driven scan/fix/compliance workflow from the [SCCAP platform](https://github.com/nerdy-krishna/ai-secure-coding-compliance-platform) into a portable set of markdown instructions that any modern coding agent (Claude Code, Cursor, Codex, Cline, Copilot, Windsurf, Gemini, etc.) can read and execute.

The skill ships **no SCCAP backend dependency**. Detection runs through standard SAST tools the agent installs locally; compliance review uses framework markdown the agent fetches from public OWASP repositories at runtime. The host agent's LLM does all orchestration and reasoning.

Two user journeys are first-class:

- **Audit an existing codebase** — find vulnerabilities and remediate them.
- **Build a new codebase securely** — wrap the agent's ongoing work in a persistent ASVS-driven policy layer.

Distribution is via [skills.sh](https://skills.sh): `npx skills@latest add nerdy-krishna/securecoder`. The installer handles dropping skills into each supported host's skill directory.

## 2. Architectural Principles

The following are non-negotiable constraints that shaped every downstream decision. New contributions must respect them.

1. **Pure agent skill.** Skills are markdown instructions (`SKILL.md`) plus small helper scripts (Python stdlib only). No daemon, no server, no MCP. The host agent reads the instructions and executes.
2. **Language-agnostic via runtime fetching.** The skill ships no Semgrep rule packs and no framework controls. The agent fetches OWASP and Semgrep repos at runtime, pinned to allowlist-controlled tags, cached content-addressed under `~/.cache/securecoder/`.
3. **Lowest-common-denominator multi-tool.** Drop Claude-Code-specific primitives: no `Agent` subagents, no `AskUserQuestion`, no model pinning. Skills phrase asks in plain English; each host implements its own prompt mechanism. Parallelism lives in the SAST tools, not in the agent.
4. **Filesystem is the inter-skill interface.** `/securecoder-fix` doesn't take a `--findings-file` argument; it reads `.securecoder/runs/latest/findings.jsonl`. Slash-command arg parsing varies too much across hosts to rely on.
5. **Audit-first with explicit cost gates.** No paid work runs without a token estimate shown and an approval taken.
6. **Safety over throughput.** Auto-fixes always pre-flight, syntax-check, re-scan, and back up before they apply. A single failed fix never blocks the rest of the batch but is logged loudly.

## 3. The Seven Skills

`/securecoder-setup`, `/securecoder-scan`, `/securecoder-fix`, `/securecoder-secure`, `/securecoder-review`, `/securecoder-build`, `/securecoder-advise`.

| Skill | Purpose | Reads | Writes |
|---|---|---|---|
| `/securecoder-setup` | One-time team config | (none) | `.securecoder/config.json` |
| `/securecoder-scan` | Audit existing code | rules cache, optional config | `.securecoder/runs/<id>/` |
| `/securecoder-fix` | Remediate findings | a run's `findings.jsonl` | working tree + `.securecoder/runs/<id>/backups/` |
| `/securecoder-secure` | End-to-end "easy button" | config | `.securecoder/runs/<id>/`, working tree |
| `/securecoder-review` | Diff-scoped security review | git diff | `.securecoder/reviews/<id>/` |
| `/securecoder-build` | Persistent secure-build mode | active frameworks | (chat-resident policy block) |
| `/securecoder-advise` | Q&A grounded in frameworks + findings | frameworks, latest findings | (chat output only) |

Behavior details follow.

### 3.1 `/securecoder-setup`

One-time configuration. Subsequent skills run with defaults if `.securecoder/config.json` doesn't exist and tell the user to invoke `/securecoder-setup` to customize. Not mandatory before first use.

**Wizard questions (asked one at a time, defaults pre-selected):**

| # | Question | Options | Default |
|---|---|---|---|
| 1 | Compliance overlay frameworks (multi-select) | ASVS v5 / MASVS / Proactive Controls / Cheatsheets / None | ASVS v5 only |
| 2 | Severity floor (findings below this are recorded as info, never block) | critical / high / medium / low / info | low |
| 3 | Default fix scope for `/securecoder-secure` | critical only / critical+high / critical+high+medium / all | critical+high |
| 4 | Git push strategy after each fix | push each / commit local push at end / commit local never push | commit local push at end |
| 5 | Scan-output gitignore policy for the project-root `.gitignore` | runs-and-reviews / whole-folder / none | runs-and-reviews |
| 6 | Auto-detected primary languages — override? | accept / provide list | accept |
| 7 | Customize rule source pins (advanced) | use defaults / override per source | use defaults |
| 8 | Use system-installed tools instead of cached? | use cached / override per tool | use cached |
| 9 | Custom rule sources beyond allowlist (advanced; warns on supply chain) | none / add sources | none |
| 10 | Framework fit threshold + baseline enable (advanced) | default 15% / custom; baseline on / off | 15%, baseline on |

**Output (`.securecoder/config.json` v1.1 schema):**

```json
{
  "schema_version": "1.1",
  "frameworks": ["asvs-v5"],
  "severity_floor": "low",
  "default_fix_scope": ["critical", "high"],
  "git": {
    "push_strategy": "commit-local-push-at-end",
    "gitignore_strategy": "runs-and-reviews"
  },
  "languages": ["python", "typescript"],
  "rule_pins": {},
  "tools": {},
  "custom_sources": [],
  "framework_fit": { "poor_fit_threshold_pct": 15 },
  "baseline_enabled": true
}
```

`git.gitignore_strategy` (added v1.3.1) governs how `/securecoder-scan` reconciles the **project-root `.gitignore`** with its scan output. `runs-and-reviews` ignores `.securecoder/runs/` + `.securecoder/reviews/` (keeping `config.json` / `suppressions.json` team-shared); `whole-folder` ignores all of `.securecoder/`; `none` leaves the root `.gitignore` untouched. `/securecoder-setup` records the value only — `/securecoder-scan` applies it (see §3.2). A config without the key is read as unset: `/securecoder-scan` prompts once and persists the answer.

**Refresh actions surfaced separately**, not in the wizard: `/securecoder-setup --refresh-rules`, `--refresh-tools`. Re-running the wizard loads existing config as pre-selected defaults.

### 3.2 `/securecoder-scan`

Scan-only — produces findings, never modifies code.

**Internal mode picker (asked at runtime with explanation + token warning):**

- **SAST only** — Semgrep, Bandit, Gitleaks, OSV. ~30s wall time. $0 LLM cost.
- **LLM compliance only** — Run active frameworks (ASVS etc.) against relevant files × applicable chapters. Slow and LLM-heavy.
- **Both (recommended)** — SAST first, then compliance pass merges into the same `findings.jsonl`.

**Phase A — Deterministic SAST (always-on when SAST mode selected):**

1. Pre-flight: ensure tools installed (Q9 install spec), refresh tools if version mismatch.
2. Build repo map: walk working tree, skip `node_modules/`, `dist/`, `.venv/`, etc., files > 200 KB, binary files.
3. Fetch / refresh per-language Semgrep rule packs based on detected languages.
4. Run tools:
   - `semgrep --config <cached-packs> --json` over repo
   - `bandit -r <python-files> -f json`
   - `gitleaks detect --report-format json`
   - `osv-scanner --json <lockfiles>` if dep manifests present
5. Normalize each tool's output into the unified findings schema (§4).
6. Append findings to `findings.jsonl`.

**Phase B — LLM compliance (when compliance mode selected):**

1. Load active frameworks from `.securecoder/config.json`.
2. For each file in repo map, run relevance filter (`scripts/file_relevance.py`) against each framework chapter — produces the dispatch list of (file, chapter) pairs that matter.
3. For each pair (sequential, no subagent fan-out):
   - Compose architect-style prompt with chapter content + file content (line-numbered) + repo context excerpt.
   - LLM emits coverage matrix (every control ID has exactly one row) + JSON findings array.
   - Validate coverage matrix completeness against the chapter source. One retry if incomplete.
   - Append findings to `findings.jsonl`.
4. Compute compliance posture per framework: `controls_passing / controls_evaluated`.

**Output written to `.securecoder/runs/<run-id>/`:**

- `findings.jsonl` — canonical findings (§4)
- `manifest.json` — run metadata: schema version, repo SHA, tool versions, rule pack SHAs, scan duration, token totals, model used (if known)
- `report.md` and `report.html` — rendered reports (§9)
- `log.md` — per-phase progress (asvs-shell-style runlog)
- A `latest` symlink (or `latest.json` on Windows) at `.securecoder/runs/latest` points to this run.

**gitignore reconcile.** Pre-flight resolves `git.gitignore_strategy` from config; when it's unset and the project is a git repo, `/securecoder-scan` prompts once and persists the choice. On every run it (a) writes the nested `.securecoder/.gitignore` backstop, and (b) reconciles a sentinel-fenced block in the **project-root `.gitignore`** to match the strategy — idempotent, replaced on a strategy change, removed for `none`. This is the only file securecoder maintains outside `.securecoder/`. See §5.

### 3.3 `/securecoder-fix`

Reads `.securecoder/runs/latest/findings.jsonl` by default; takes an explicit run id via natural-language ask.

**Internal mode picker:**

- All severities
- Critical only / High only / Medium only / Low only
- Critical + High
- Critical + High + Medium
- Custom multi-select (any combination)
- Interactive one-by-one (review each fix)
- By specific finding IDs

**Pre-flight (before any fix):**

1. **Git check.** If git repo + dirty working tree → ask: stash and continue / abort / proceed anyway. If not git → warn that there's no commit-based rollback.
2. **Branch check.** If git + on `main` / `master` / `release/*` → ask: create `securecoder-fix/<run-id>` branch?
3. **Backup capture.** For every file slated for edit, copy to `.securecoder/runs/<run-id>/backups/<path>` before any edit.
4. **Cost estimate.** `findings_to_fix × ~4K tokens per fix`. One approval.

**Per-fix loop (for each finding in scope):**

1. Locate the target line range in the current file.
2. LLM emits a SEARCH/REPLACE block.
3. Validate SEARCH appears exactly once. If zero or many matches → `editor_failed`, skip.
4. Apply the replace.
5. **Language-agnostic syntax check.** Detect language from extension. Use cached or system-available checker (`python3 -m py_compile`, `node --check`, `gofmt -e -l`, `rustc --emit=metadata`, `php -l`, `ruby -c`, etc.). If the right checker isn't installed, the agent installs it under `~/.cache/securecoder/tools/` (same consent gate as Q9). Fall back to "did SEARCH/REPLACE apply cleanly + is file valid UTF-8" when no checker is available.
6. **Re-scan.** Run the originating SAST tool against just the fixed file. Verify the finding is gone; check no new finding of equal-or-higher severity was introduced.
7. **On failure:** restore from backup, mark `editor_failed`, log reason, move on.
8. **On success:** `git commit` with message `fix(securecoder): <severity>/<title> [<finding-id-short>]` whose body includes finding source, rule ID, CWE, original lines. Mark `applied`.
9. **Push policy** per `config.git.push_strategy`:
   - `push-each` → `git push` after every successful commit
   - `commit-local-push-at-end` (default) → push once at post-flight
   - `commit-local-never-push` → no push
10. Up to 3 LLM tries per finding (retry context tells the LLM what failed). 4th try never happens.

**Compliance-finding handling:**

- `fix_complexity: "high"` or `lines: null` → marked `manual_review_required`, NOT auto-fixed. User must apply manually with the report's remediation hint.
- `fix_complexity: "low"` or `"medium"` and a defined location → auto-fix candidate.

**Post-flight:**

1. Show summary: applied / editor_failed / manual_review_required counts.
2. Show `git diff --stat` if git.
3. Print restore instructions: "to roll back this run, run `/securecoder-fix --restore <run-id>` or natural-language equivalent."
4. Never auto-commit summary itself.

**One-by-one mode** pauses before step 4 to show the proposed SEARCH/REPLACE and ask `apply / skip / quit`.

### 3.4 `/securecoder-secure`

Easy-button. Internally: `/securecoder-scan` (SAST) → `/securecoder-fix` (default scope from config, typically critical+high) → `/securecoder-scan` (compliance) → `/securecoder-fix` again → report. **Requires `/securecoder-scan` and `/securecoder-fix` installed** (declared in its description).

**Flow:**

1. Pre-flight (clean tree + branch checks).
2. **Cost estimate up front, covering the entire pipeline.** Token-first reporting (§9). One approval. User may exit to **scan-only** at this gate.
3. Run straight through — no further user prompts between SAST and compliance.
4. **50%-overrun mid-run gate.** If compliance phase exceeds estimated tokens by ≥ 50%, pause before fix phase and ask: continue / abort.
5. Post-flight: report + summary + `git diff --stat`.

Fix scope defaults to the value in `config.default_fix_scope` (typically `["critical", "high"]`).

### 3.5 `/securecoder-review`

Diff-scoped, fast (seconds, not minutes). Pre-commit gate.

**Scope picker:** staged / staged+unstaged / branch-vs-base / specific commit range. Default staged-only.

**Phases:**

1. Extract changed files + hunks from `git diff`.
2. **Scoped SAST:** Semgrep `--include=<file>` over changed files; Bandit on changed Python; Gitleaks on changed; OSV if dep manifest changed.
3. **Scoped LLM compliance:** for each changed file, run relevance filter; send only changed hunks + ±20 lines of context to the LLM. Cost proportional to diff size, not repo size.
4. **Output:**
   - Terse chat verdict: `OK to commit` / `N issues found — review before committing`
   - Findings to `.securecoder/reviews/<run-id>/findings.jsonl` (separate from `.securecoder/runs/`, keeps scan history clean)
5. **No auto-fix in review.** User invokes `/securecoder-fix` against the review findings file to remediate.

**Pre-commit hook installation (optional):**

- User can ask "install /securecoder-review as a pre-commit hook".
- Hook calls `scripts/review_hook.py` — **SAST-only**, no LLM. Git hooks run in shell, not agent context, so can't invoke slash commands.
- Exit code: non-zero if any finding above `severity_floor` exists, blocking commit.
- Hook output reminds user to run `/securecoder-review` interactively for compliance pass before pushing significant changes.

### 3.6 `/securecoder-build`

Persistent ASVS-driven secure-build mode. Not a scaffold generator — a session-scoped policy layer.

**Mechanism.** Skill emits a structured instruction block to the conversation. The host agent's context retention keeps the block alive across subsequent turns. Every code-producing task the user gives the agent flows through the protocol.

**On invocation:**

1. **Optional minimal bootstrap.** Ask "existing project or starting fresh?" If fresh: short interview (app type + stack), then generate just enough to start coding — secure-default config, deps pinned, pre-commit hook installed, `.securecoder/config.json` seeded. Not a full app scaffold.
2. **Activate secure-build mode** — emit the policy block:
   - Mode declaration: "Secure Build Mode is active until you say `end secure build mode` or context drops it."
   - Active frameworks (default: ASVS v5 from `.securecoder/config.json`).
   - Pointer to fetched framework markdown in `~/.cache/securecoder/rules/frameworks/asvs/<version>/` for on-demand reading.
   - **Pre-task protocol:** identify applicable framework chapters before writing code; plan with those controls in mind; state which controls apply at the top of the response.
   - **Post-task self-check:** review output against applicable controls. For each: `satisfied` / `partial` / `unknown / n/a`. Iterate until all relevant are `satisfied` or `n/a`, OR surface unresolved items explicitly.
   - **Escalation rule:** if a control conflicts with what the user asked for, surface the conflict rather than silently overriding either side.
   - **Adjunct hint:** "Run `/securecoder-review` after substantive changes for real SAST + LLM verification on the diff."

3. **Mode deactivation.** Explicit user signal ("end secure build mode") OR natural context drop. No persistent state on disk.

**Scope discipline:** `/securecoder-build` references only the configured compliance frameworks (typically ASVS). It does not run SAST. SAST is for finished code; `/securecoder-build` supervises in-flight code.

### 3.7 `/securecoder-advise`

Q&A grounded in fetched framework markdown and (optionally) the latest scan's findings. Read-only — never modifies code.

**Invocation:** `/securecoder-advise <question>` or just `/securecoder-advise` (skill asks for a question).

**Context loading on first turn:**

- Read `.securecoder/config.json` to know active frameworks.
- Read framework markdown from `~/.cache/securecoder/rules/frameworks/`.
- If `.securecoder/runs/latest/findings.jsonl` exists, read it.
- Print the list of loaded surfaces once at the top of the response.

**Mode picker (only if invoked without a question):**

- General Q&A (frameworks only)
- Findings-grounded Q&A (uses last scan)
- Specific finding deep-dive (user picks an ID)
- Framework lookup (e.g., "explain ASVS V1.2.1" — verbatim quote + plain-language interpretation)

**Response format (always):**

- Quote framework text verbatim before interpreting (no paraphrase-as-citation).
- Cite by control ID + version: `ASVS v5.0.0 V1.2.1`.
- When grounding in user findings, cite by finding ID + file:line.
- Suggest related controls / cheatsheets at the end.

**Helper:** `scripts/search_rules.py` performs keyword/concept search across cached framework markdown; returns top-N matching sections with control IDs. Agent invokes internally; user can ask directly ("search the ASVS for SSRF").

### 3.8 `/securecoder-suppress` (v1.1.0)

Marks findings as false positives — the source of truth for what `/securecoder-fix`, `/securecoder-review`, and `/securecoder-secure` should ignore. Read-only in `show` modes; mutates `.securecoder/suppressions.json` for `add`, `import`, `remove`, and `expire` modes.

**Command modes:**

```text
/securecoder-suppress <finding-id> "reason"          shortcut for instance suppression
/securecoder-suppress import <json>                  batch import (HTML report's export button)
/securecoder-suppress add "<match-expr>" "reason"    e.g. add "rule=B105 and file_glob=tests/**" "test fixtures"
/securecoder-suppress show                           list all current suppressions
/securecoder-suppress show <finding-id>              which entry suppresses a given finding
/securecoder-suppress show stale                     entries that didn't match anything in last scan
/securecoder-suppress show expired                   entries past their expires_at
/securecoder-suppress remove <entry-index>           delete one entry
/securecoder-suppress expire                         purge entries past expires_at (with confirmation)
```

Natural-language equivalents work via the agent's interpretation. The eight modes are not separate skills — they're branches inside one SKILL.md.

**What this skill does NOT do:** it does not re-run any scan or compute suppression effects against existing findings. Effects materialize the next time `/securecoder-scan` runs, when `apply_suppressions.py` (§ 3.9) stamps `status: "suppressed"` on matching findings.

## 3.9 Suppression model (v1.1.0)

A separate concern that touches every skill. Marking findings as false positives or known-acceptable so they don't pollute reports and don't get auto-fixed.

### Storage

Team-shared file at `.securecoder/suppressions.json` (checked in alongside `config.json`). Schema v1.0:

```json
{
  "schema_version": "1.0",
  "entries": [
    {
      "match": {
        "id": "5823722d…",
        "rule": "B105",
        "file": "tests/fixtures/passwords.py",
        "file_glob": "tests/**",
        "framework_ref": "asvs-v5/V1.2.1"
      },
      "scope": "project",
      "reason": "Hardcoded passwords in test fixtures are intentional",
      "created_at": "2026-05-14T15:30:00Z",
      "created_by": "krishna@example.com",
      "expires_at": null
    }
  ]
}
```

Inside `match`, every populated field is ANDed. Fields: `id` (exact canonical-ID — fragile by design, shifts with line numbers), `rule` (matches `source_rule_id`), `file` (exact path), `file_glob` (gitignore-style glob), `lines` (`{start, end}` range; a finding matches if its line falls within), `framework_ref` (e.g. `"asvs-v5/V1.2.1"` — matches any of the finding's framework_refs).

### Source-code annotations (v1.2.0)

In addition to the persistent `.securecoder/suppressions.json`, suppressions can also come from in-source comment annotations:

```python
# securecoder: ignore reason="validated upstream"
return db.execute(query)

PASSWORD = "x"  # securecoder: ignore reason="dev-only" expires="2027-01-01"
```

`scan_annotations.py` walks the project before `apply_suppressions.py` runs and emits ephemeral entries that use the `file + lines` match shape (specificity score 1, just below `id`). Ephemeral entries get `source: "annotation"` and `created_by: "<annotation>"` to distinguish them from config-file entries in audit views. Block comments (`/* ... */`) and JSX-style braces aren't yet recognized — line comments only (`#` and `//`).

### Most-specific-wins resolution

| Specificity score | Match shape |
|---|---|
| 0 (most specific) | `id` present |
| 1 | `rule` + `file` |
| 2 | `rule` + `file_glob` |
| 3 | `rule` alone, or `framework_ref` alone |
| 4 (least specific) | `file_glob` alone |

Among entries at the same specificity, the first-defined wins. The winner's reason becomes the finding's `suppression_reason` field; a `suppressions.json#<index>` pointer becomes its `suppression_match`.

### Expiry

`expires_at` is optional ISO-8601 date. Null = never expires. Past-date entries stay in the file (audit trail) but match-time logic ignores them. `/securecoder-suppress expire` removes them with confirmation. Default new entries have `expires_at: null`; teams that prefer expiry-by-default set `config.suppression_defaults.expires_after_days`.

### Cross-skill integration

- **`/securecoder-scan`** runs `apply_suppressions.py` as Phase A's final step (after merge, before manifest). Findings matching a suppression get `status: "suppressed"`, `suppression_reason`, `suppression_match`.
- **`/securecoder-fix`** filters out `status: "suppressed"` in its severity-scope step. Fix log captures `editor_skipped_suppressed` for visibility.
- **`/securecoder-review`** interactive flow inherits the filter via the same finding stream. The pre-commit hook `review_hook.py` reads `.securecoder/suppressions.json` directly and filters tool outputs before computing exit code.
- **`/securecoder-secure`** inherits through its sub-skills.
- **`/securecoder-build`** does not see suppressions for v1.1.0.
- **`/securecoder-advise`** gains new query modes — "show all currently active suppressions" and "why is finding X suppressed?"

### HTML report — UI affordances

- Per-finding action row with three scope buttons: `[ Suppress this instance ]  [ Suppress rule here ]  [ Suppress rule project-wide ]`
- Inline expand: reason textarea (required), optional expiry date picker, `[ Add to batch ]` and `[ Copy single command ]`
- Multi-select checkboxes per finding + sticky bar with `[ Select all ]  [ Select all matching filter ]  [ Suppress N selected ]`
- Cluster view tab — groups by `(rule_id, file_path_prefix)`; prefix discovered heuristically (longest common prefix with 3-finding floor and 80% coverage ceiling). Per-cluster suppress generates pattern-based entries.
- Staging tray sticky banner: "N suppressions staged. [Export to agent] [Clear] [Review]" — localStorage-persisted per run
- Export-to-agent produces `/securecoder-suppress import [{...}, ...]` (clipboard-copied with confirmation toast)
- Show-suppressed toggle reveals dimmed suppressed findings inline
- Severity-floor advisory banner when one severity dominates (>1000 findings of a single severity)
- Suppressions section at bottom listing every active entry with reason / created_at / created_by / expires_at, click-through to "show findings this matched"
- Virtualized rendering (plain JS, ~100 LOC) keeps DOM lightweight for 2000+ findings

### Manifest additions

```json
{
  "totals": {
    "findings": 2047,
    "findings_active": 800,
    "findings_suppressed": 1247
  },
  "suppressed_by_entry": {
    "0": 1247,
    "1": 0,
    "2": 18
  }
}
```

`suppressed_by_entry` maps suppressions.json entry index → count of findings caught this run. Entries with 0 count are stale candidates surfaced by the report banner and `/securecoder-suppress show stale`.

### What's intentionally NOT in v1.1.0

- **Source-code comment annotations** (e.g., `# securecoder: ignore`). Config-file model is source of truth; in-source annotations duplicate without adding meaningful value. *(Added in v1.2.0.)*
- **Sampling-assisted review** of large clusters. The cluster view's "expand to see 3 samples" covers most of the value. *(Added in v1.2.0.)*
- **`scope: "review-only"`** (suppress in `/securecoder-review` but not in full scans). Single global scope keeps the model simple.
- **ML-assisted false-positive prediction.** Needs training data not yet available.

## 3.10 Framework fit + the secure-coding-essentials baseline (v1.3.0)

ASVS, MASVS, and Proactive Controls are all web/mobile-shaped. When `/securecoder-scan` runs the compliance pass over non-web code — C kernel routines, embedded firmware, Rust systems code, Go CLIs, ML pipelines, libraries — most controls evaluate to N/A and the run burns LLM tokens for little signal. v1.3.0 closes this gap with two coupled mechanisms.

### Baseline-plus-overlay model

Frameworks split into two `layer`s:

- **`baseline`** — universal concerns present in *every* codebase regardless of domain. Always runs (unless explicitly opted out). v1.3.0 ships exactly one: `secure-coding-essentials`.
- **`overlay`** — domain-specialized controls layered on top. ASVS v5 (web), MASVS (mobile), and — from v1.4.0 — CERT C (systems). Subject to fit-detection.

A web-app scan runs `secure-coding-essentials` + `asvs-v5`. A C kernel scan runs `secure-coding-essentials` alone, with `asvs-v5` flagged poor-fit. The `frameworks` list in `config.json` governs *overlays only*; the baseline runs implicitly.

### `secure-coding-essentials` framework

Bundled in the skill repo (not fetched — sidesteps the SEI-wiki / paywalled-MISRA fetchability problem that rules out CERT C and MISRA as `git clone` targets). Lives at `skills/security/securecoder-scan/references/frameworks/secure-coding-essentials/` as chapter markdown. Its `frameworks.json` entry carries `source: "bundled"` + `bundled_path` instead of a git URL; Phase B.1's fetcher branches on `source: "bundled"` and points `CHAPTERS_DIR` straight at the in-repo path, skipping the clone.

Nine chapters, each a markdown control table with CWE cross-references. Control IDs follow the `SCE-<AREA>-<n>` pattern (mirrors MASVS's `MASVS-STORAGE-1`):

| Chapter | Code | CWE clusters |
|---|---|---|
| Memory Safety | `SCE-MEM` | CWE-119/125/787/416/415/476 |
| Integer Handling | `SCE-INT` | CWE-190/191/192/197 |
| Input Validation & Untrusted Data | `SCE-INPUT` | CWE-20/1284 |
| Injection Prevention | `SCE-INJECT` | CWE-77/78/94/22/89 |
| Error & Exception Handling | `SCE-ERR` | CWE-252/391/755 |
| Resource Management | `SCE-RES` | CWE-401/404/770/772 |
| Concurrency & Races | `SCE-CONC` | CWE-362/364/367 |
| Cryptography & Secrets | `SCE-CRYPTO` | CWE-327/328/330/798/200/532 |
| Access Control & Privilege | `SCE-ACCESS` | CWE-285/269/250 |

The existing architect prompt, coverage-matrix validator, and compliance normalizer all work unchanged once `validate_coverage.py` reads `control_id_regex` per-framework from `frameworks.json` (the field already exists; it was hardcoded to the ASVS three-number form).

### Essentials relevance filter

`relevance-secure-coding-essentials.json` uses the same machinery as the ASVS / MASVS relevance files. Seven chapters are `applies_to_languages: ["all"]`. `SCE-MEM` and `SCE-INT` are **keyword-triggered**: they apply unconditionally to memory-unsafe / fixed-width-int languages (C, C++, Rust, Zig, assembly), and to memory-managed languages *only when* the file contains FFI / `unsafe` signals (`ctypes`, `cffi`, `unsafe`, `JNI`, `cgo`, `Marshal`). This keeps the two language-dependent chapters from firing guaranteed-N/A pairs while preserving the FFI escape hatch.

### Fit-detection

A pre-flight step in `/securecoder-scan`, before the cost estimate. The `fit_check.py` helper scores each `overlay` framework by language-profile overlap:

```
fit_pct = (count of repo source files whose language ∈ framework.target_languages)
          / (total repo source files) × 100
```

`frameworks.json` gains three fields per entry: `target_languages` (or `["all"]`), `layer` (`baseline` | `overlay`), and `signal_globs` (file patterns that rescue a borderline case — a mostly-C repo with a `package.json` is a Node C-extension; ASVS still relevant).

When an overlay's `fit_pct` falls below `config.framework_fit.poor_fit_threshold_pct` (default 15, configurable), the scan warns before the cost estimate and offers three choices:

- `recommended` — drop the poor-fit overlay for this run only (does not rewrite `config.json`)
- `as-configured` — run everything anyway
- `abort`

The warning also surfaces *non-enabled* frameworks that would fit better ("this looks like a mobile project — consider enabling MASVS"). `baseline`-layer frameworks skip fit-detection entirely.

### Config additions

```json
{
  "framework_fit": { "poor_fit_threshold_pct": 15 },
  "baseline_enabled": true
}
```

`baseline_enabled` defaults true — `secure-coding-essentials` runs on every compliance scan. Existing `config.json` files (no `baseline_enabled` key) are treated as `true`, so upgrading installs get the baseline automatically; the `frameworks` list continues to govern overlays. The rare team wanting overlay-only sets `baseline_enabled: false`.

### What's intentionally NOT in v1.3.0

- **CERT C / C++ and other domain standards as overlays.** Committed to v1.4.0 — they need a wiki-scraping ingestion path since they aren't clean `git clone` markdown targets.
- **MISRA.** Paywalled; not viable as a bundled or fetched framework.
- **Auto-rewrite of `config.json` from the fit warning.** The warning advises and can drop-for-this-run; permanent changes stay `/securecoder-setup`'s job — config mutation should be deliberate.
- **Project-type detection beyond language profile.** "Is this a kernel module vs a C web server" needs deeper signals than v1.3.0's language + glob heuristic. Language profile + `signal_globs` covers the common cases.

## 4. Findings Schema

JSONL — one finding per line. Schema version 1.0.

**SAST finding example:**

```json
{
  "id": "sha256-hex-of-canonical-key",
  "file": "src/api/auth.py",
  "lines": { "start": 42, "end": 47 },
  "source": "semgrep",
  "source_rule_id": "python.django.security.injection.sql-injection",
  "category": "sast",
  "cwe": ["CWE-89"],
  "framework_refs": [
    { "framework": "asvs-v5", "control": "V1.2.1" },
    { "framework": "owasp-top-10-2021", "category": "A03" }
  ],
  "severity": "high",
  "confidence": "high",
  "title": "Raw SQL query allows injection",
  "description": "User input concatenated into a raw SQL query without parameterization.",
  "evidence": "cursor.execute('SELECT * FROM users WHERE id = ' + request.GET['id'])",
  "remediation_hint": "Use parameterized queries.",
  "fix_complexity": "low",
  "tags": ["sql-injection", "django"],
  "detected_at": "2026-05-13T14:00:00Z",
  "status": "open",
  "history": []
}
```

**Compliance finding example:**

Same shape with `category: "compliance"`, `source: "asvs-v5"`, `source_rule_id: "V1.1.1"`, `lines` may be `null`, `cwe` often empty, `framework_refs` always populated.

**Field semantics:**

- **`id` — canonical, content-derived.** SAST: `sha256(file + line_start + source_rule_id)`. Compliance: `sha256(file + framework + control_id)`. Same finding across runs → same `id`, enabling history tracking.
- **`severity`: 5-level** — `critical` / `high` / `medium` / `low` / `info`. Each SAST tool's native severity maps to this scale via a per-tool table in the scan SKILL.md. Compliance findings emitted by LLM with explicit severity + rationale.
- **`confidence`: 3-level** — `high` / `medium` / `low`. Bandit's H/M/L maps directly. Most other SAST tools default to `high` (deterministic rules).
- **`framework_refs`** — SAST findings enriched via shipped `references/cwe-to-framework.json`; compliance findings carry their framework reference natively.
- **`fix_complexity`** — `low` (mechanical patch) / `medium` (small refactor) / `high` (architectural; flagged `manual_review_required` in `/securecoder-fix`).
- **`status`** — `open` (default), `applied` (fixed), `editor_failed`, `manual_review_required`, `suppressed` (via config patterns).

**`manifest.json` alongside `findings.jsonl`** captures run metadata so `/securecoder-fix` and the report don't need to parse every line:

```json
{
  "schema_version": "1.0",
  "run_id": "20260513T140000Z",
  "started_at": "2026-05-13T14:00:00Z",
  "finished_at": "2026-05-13T14:25:00Z",
  "repo_sha": "<commit hash if git>",
  "tools": { "semgrep": "1.50.0", "bandit": "1.7.7", "gitleaks": "8.18.0", "osv-scanner": "1.7.0" },
  "rule_packs": { "semgrep/p-owasp-top-ten": "<sha>", "semgrep/p-python": "<sha>" },
  "frameworks": { "asvs-v5": "v5.0.0" },
  "phases": {
    "sast":       { "duration_s": 28,    "findings": 14, "input_tokens": 0,        "output_tokens": 0 },
    "compliance": { "duration_s": 1860,  "findings": 47, "input_tokens": 3200000,  "output_tokens": 960000 }
  },
  "totals": { "findings": 61, "duration_s": 1888 }
}
```

**Shipped `references/cwe-to-framework.json`** maps CWE → list of framework control refs. Curated from OWASP's published mappings, refined manually, updated on skill releases. Used to enrich SAST findings with `framework_refs`.

## 5. State & Filesystem Layout

Split between **in-repo project state** (team-shared and per-run history) and **user-global cache** (shared across projects).

### In the user's repo

```
<user-project>/
├── .gitignore                   # securecoder maintains a sentinel-fenced block
│                                #   here per git.gitignore_strategy (see below)
└── .securecoder/
    ├── config.json              # from /securecoder-setup. CHECKED IN.
    ├── .gitignore               # nested backstop: ignores runs/ and reviews/,
    │                            #   keeps config.json. Always written.
    ├── runs/
    │   ├── 20260513T140000Z/
    │   │   ├── findings.jsonl
    │   │   ├── manifest.json
    │   │   ├── report.md
    │   │   ├── report.html
    │   │   ├── log.md
    │   │   └── backups/<file paths copied before any /securecoder-fix edits>
    │   └── latest -> 20260513T140000Z/   # symlink; on Windows: latest.json
    └── reviews/                  # /securecoder-review writes here, NOT in runs/
        └── 20260513T144500Z/
            ├── findings.jsonl
            ├── report.md
            └── log.md
```

`.securecoder/config.json` is intentionally checked in — teams share the same framework choices and severity floor. `runs/` and `reviews/` are gitignored: large, per-developer, transient — and *sensitive*, since they hold the full vulnerability picture of the codebase.

Two `.gitignore` layers enforce that:

1. **Nested `.securecoder/.gitignore`** — always written by `/securecoder-scan` (step A.12.a). Ignores `runs/` and `reviews/`, never `config.json`. The unconditional backstop.
2. **Project-root `.gitignore`** — a sentinel-fenced (`# >>> securecoder >>>` … `# <<< securecoder <<<`) block, reconciled by `/securecoder-scan` (step A.12.b) per `git.gitignore_strategy`: `runs-and-reviews` ignores `.securecoder/runs/` + `.securecoder/reviews/`; `whole-folder` ignores all of `.securecoder/`; `none` removes the block. The visible layer, where developers actually look. Under `whole-folder`, files already tracked under `.securecoder/` keep being committed until `git rm --cached`-ed — the scan warns about this rather than mutating the index.

### In the user's home

OS-appropriate cache (macOS `~/Library/Caches/securecoder/`, Linux `~/.cache/securecoder/`, Windows `%LOCALAPPDATA%\securecoder\`):

```
~/.cache/securecoder/
├── manifest.json                 # what's cached + integrity hashes + consent record
├── tools/
│   ├── semgrep/                  # pipx-managed or venv-managed
│   ├── bandit/
│   ├── gitleaks/                 # static binary
│   └── osv-scanner/              # static binary
└── rules/
    ├── semgrep/
    │   ├── p-owasp-top-ten/<sha>/
    │   ├── p-python/<sha>/
    │   └── p-javascript/<sha>/
    └── frameworks/
        ├── asvs/v5.0.0/
        ├── masvs/<tag>/
        ├── proactive-controls/<tag>/
        └── cheatsheets/<tag>/
```

Cache dirs are content-addressed by git SHA so multiple versions coexist without conflict and integrity is verifiable.

### Inter-skill contract

Filesystem only. No reliance on slash-command argv parsing across hosts. `/securecoder-fix` reads `.securecoder/runs/latest/findings.jsonl`; the user can target a specific run by natural-language ask, which the agent interprets against SKILL.md instructions.

## 6. Rule & Framework Fetching

The skill never embeds rules. It fetches at runtime from a hardcoded **allowlist** and caches content-addressed.

### Default sources (v1)

| Source | Repo | Tag (initial pin) | Purpose |
|---|---|---|---|
| Semgrep rules | `returntocorp/semgrep-rules` | latest stable tag | Per-language SAST patterns; agent selects sub-packs by detected languages |
| OWASP ASVS | `OWASP/ASVS` | `v5.0.0` | Web app compliance |
| OWASP MASVS | `OWASP/owasp-masvs` | latest | Mobile app compliance (used if mobile stack detected) |
| OWASP Proactive Controls | `OWASP/www-project-proactive-controls` | latest | Optional defensive design checklist |
| OWASP Cheatsheets | `OWASP/CheatSheetSeries` | latest | Remediation reference; used by `/securecoder-fix` and `/securecoder-advise` |
| Gitleaks rules | bundled with tool | — | Secret detection |
| Bandit rules | bundled with tool | — | Python SAST |
| OSV | `api.osv.dev` (online API query) | — | Dependency CVE lookup; no fetch |

### Mechanism

- `git clone --depth 1 --branch <tag> <repo> ~/.cache/securecoder/rules/<source>/<sha>/`
- Cache key is the git SHA of the fetched tree.
- `manifest.json` records source URL, tag, SHA, fetch timestamp.
- **No TTL.** Same `(source, tag)` always reuses the cached SHA.
- Skill releases bump default pinned tags.
- `/securecoder-setup --refresh-rules` (or natural-language ask) force-refetches.

### Trust model

- **Allowlist of orgs** hardcoded in each scan-related SKILL.md: `OWASP/*` and `returntocorp/*`. Anything else requires explicit one-time user confirmation before first use.
- **Pinned tags** make supply chain reproducible and auditable.
- **Integrity verification** on reuse: if cached SHA differs from manifest's recorded SHA, the skill refuses to run and reports tampering.
- **Custom user sources** in `config.custom_sources` print a warning and require confirmation on first use.

### Offline mode

- Cache hit → works offline.
- Cache miss + no network → fail loudly: "Source X (cached version Y missing) needs network access. Either connect or remove X from `.securecoder/config.json` to skip."

## 7. Tool Installation

Skill-managed `~/.cache/securecoder/tools/`. Never global. Never project-local.

### Per-tool install method

| Tool | Type | Install | Pinned by |
|---|---|---|---|
| Semgrep | Python | `pipx install semgrep==X.Y.Z` → fallback venv | SKILL.md |
| Bandit | Python | Same pattern | SKILL.md |
| Gitleaks | Go binary | Download release matching OS+arch from `github.com/gitleaks/gitleaks/releases`, extract, chmod +x | SKILL.md |
| OSV-scanner | Go binary | Same pattern from `github.com/google/osv-scanner/releases` | SKILL.md |
| Syntax checkers (post-fix) | varies | Installed lazily by `/securecoder-fix` for whatever language is being patched; agent figures out the command | — |

### Pre-flight check on every invocation

1. Read `~/.cache/securecoder/tools/<tool>/installed.json` (version + checksum).
2. If matches SKILL.md pin → use cached.
3. Otherwise → install path.

### Consent

The very first time *any* tool needs installing, the skill asks once:

> securecoder needs these tools (~150MB total): Semgrep, Bandit, Gitleaks, OSV-scanner. They'll be installed under `~/.cache/securecoder/tools/` and never touch your system Python or PATH. Proceed?

Approval recorded in `~/.cache/securecoder/manifest.json`. Future installs (version bumps from new skill releases, lazy syntax-checker installs during fixes) are silent — consent is for "the skill manages its own tool cache," not per-version.

### System-tool override

By default, the skill ignores system-installed tools for reproducibility. Override per-tool in `.securecoder/config.json`:

```json
{ "tools": { "semgrep": { "path": "/usr/local/bin/semgrep" } } }
```

### Failure modes

- pipx absent → install via `python3 -m pip install --user pipx`, else plain venv.
- No `python3` on PATH → fail with pointer to Python install.
- No network during fresh install → fail with "Offline scans only work if `~/.cache/securecoder/tools/` is already populated."

### Per-tool disable

```json
{ "tools": { "osv-scanner": { "enabled": false } } }
```

## 8. Auto-fix Safety Model

Highest-risk surface. In-place edits to the user's repo, with mandatory pre-flight + per-fix verify + automatic rollback. Detailed flow is in §3.3. Invariants summarized here:

- **Always back up before editing.** `.securecoder/runs/<id>/backups/<path>` is the ground truth restore source, independent of git state.
- **Syntax check is language-agnostic.** Detect from extension; install checker via cache if needed; fall back to clean-application + UTF-8 validity check if no checker is available.
- **Re-scan after every fix.** Run the originating SAST tool against just the fixed file; verify finding is gone and no new equal-or-higher finding was introduced.
- **Rollback any fix that fails verification.** Mark `editor_failed`, log reason, move on. Other fixes proceed.
- **One git commit per successful fix.** Message format: `fix(securecoder): <severity>/<title> [<finding-id-short>]`. Push policy per `config.git.push_strategy`.
- **Never auto-commit the run summary itself.** User reviews and commits manually.
- **Compliance findings with `fix_complexity: "high"` or `lines: null` are never auto-fixed.** Flagged `manual_review_required` with remediation hint in the report.
- **3 LLM tries per finding maximum.** Retry context tells the LLM what failed (parse error / wrong location / syntax fail / finding still present / new finding introduced). 4th try never happens.

**Restore command** — natural-language ask "restore run X" or `/securecoder-fix --restore <run-id>` — copies backups back over the working tree.

## 9. Cost Estimation, Reporting

### Pre-flight estimate (deterministic, no LLM call)

For each phase:

- **SAST:** 0 LLM cost. ~30s wall time per 100 files (rough).
- **Compliance:** for each `(file, applicable_chapter)` pair, `input_tokens ≈ chars / 4` (chapter + line-numbered file + repo excerpt). `output_tokens ≈ input × 0.30` (calibrated from asvs-shell observed ratio).
- **Fix:** `findings_to_fix × ~3K input + ~1K output` average.

### Reporting

Token-first, model-agnostic. Reference price table shipped in the relevant SKILL.md, updated on skill releases:

```
/securecoder-secure estimate for this repo:
  Files in scope:       142
  SAST phase:           ~30s wall time, $0 LLM cost
  Compliance phase:     ~890 LLM calls, ~3.2M input tokens, ~960K output tokens
  Fix phase (est.):     ~50 fix calls, ~150K input tokens, ~50K output tokens

Approximate cost at common rates:
  Claude Opus 4.7:    $60.30
  Claude Sonnet 4.6:  $12.10
  Claude Haiku 4.5:   $ 3.40
  GPT-5 (typical):    $20.50
  Gemini 2.5 Pro:     $14.80

Wall time estimate (sequential, no subagent parallelism): ~25-40 min
```

### Approval gate options at the estimate prompt

- **Proceed** with full run
- **Scan-only** — ends after SAST + compliance, skipping fix phase
- **Abort**

### 50%-overrun mid-run gate

After compliance phase completes (in `/securecoder-secure`), compare actual tokens to estimate. If exceeded by ≥ 50%, pause before fix phase: continue / abort. Single safety valve for mis-calibrated heuristics.

### Report format

Markdown + HTML, both written to every run dir.

- `report.md` — for terminal / agent reading
- `report.html` — self-contained, opens in browser; inlined CSS, no external scripts or assets

Content (same in both, different presentation):

- **Summary** — counts, severity breakdown, total cost, wall time
- **Compliance posture** — per active framework: controls evaluated, controls passing, controls with findings, posture score
- **Findings** — grouped by file (default); HTML filterable by severity / framework / source
- **Trend** — comparison to previous run if `.securecoder/runs/` history has prior runs. Diff of new / resolved / persistent findings (matched by canonical `id`)
- **Manifest footer** — tool versions, rule pack SHAs, repo commit SHA, runtime, model used (if known)

## 10. Privacy & Data Egress

The skill ships strong defaults but the user should know what crosses the network.

**The skill itself never sends source code anywhere.** It performs:

- `git clone` over HTTPS against OWASP / returntocorp repos (and any explicit custom sources)
- HTTPS POST to `api.osv.dev` with dep package names + versions (no source code)
- HTTPS download of Gitleaks / OSV-scanner release binaries
- `git push` only if the user chose `push-each` or after-end push, against their configured remote

**LLM calls send code to the host agent's model provider.** This is the user's existing relationship with Anthropic / OpenAI / Google / etc. — the skill doesn't introduce a new vendor, but compliance scans and fixes inherently include source in prompts.

The `/securecoder-setup` wizard surfaces this explicitly. The README has a `Privacy` section reiterating it.

## 11. Repo Layout

Single-category `security/` since all skills are security-themed.

```
securecoder/                            # GitHub repo root
├── .claude-plugin/
│   └── plugin.json                      # lists the 7 skill paths
├── README.md                            # quickstart, supported hosts, privacy section
├── CHANGELOG.md                         # per-tag release notes
├── LICENSE                              # OSS, matches SCCAP main repo's license
├── docs/
│   ├── design.md                        # this document
│   ├── findings-schema.md               # detailed schema reference
│   └── adding-a-framework.md            # contributor guide
├── scripts/                             # repo-level dev tooling, NOT installed
│   └── ci/                              # GitHub Actions helpers for tag bumps
└── skills/
    └── security/
        ├── securecoder-setup/
        │   └── SKILL.md
        ├── securecoder-scan/
        │   ├── SKILL.md
        │   ├── references/
        │   │   ├── cwe-to-framework.json
        │   │   └── chapter-relevance.json
        │   └── scripts/
        │       ├── file_relevance.py
        │       └── search_rules.py
        ├── securecoder-fix/
        │   ├── SKILL.md
        │   └── scripts/
        │       └── apply_patch.py
        ├── securecoder-secure/
        │   └── SKILL.md                 # references /securecoder-scan + /securecoder-fix
        ├── securecoder-review/
        │   ├── SKILL.md
        │   └── scripts/
        │       └── review_hook.py
        ├── securecoder-build/
        │   ├── SKILL.md
        │   └── references/
        │       └── secure-build-policy.md
        └── securecoder-advise/
            ├── SKILL.md
            └── scripts/
                └── search_rules.py       # duplicate of securecoder-scan's; acceptable
```

`plugin.json`:

```json
{
  "name": "securecoder",
  "skills": [
    "./skills/security/securecoder-setup",
    "./skills/security/securecoder-scan",
    "./skills/security/securecoder-fix",
    "./skills/security/securecoder-secure",
    "./skills/security/securecoder-review",
    "./skills/security/securecoder-build",
    "./skills/security/securecoder-advise"
  ]
}
```

Each skill dir is fully self-contained. `/securecoder-secure` declares "requires `/securecoder-scan` and `/securecoder-fix`" in its description (mattpocock pattern).

## 12. Versioning & Compatibility

- **Repo-wide semver via git tags** (`v0.1.0`, `v0.2.0`, ...). Mattpocock's plugin.json doesn't carry a version; skills.sh resolves to git ref.
- **CHANGELOG.md required for every tag.** Sections: skill behavior changes / rule pin bumps / tool pin bumps / breaking changes.

### Breaking-change rules (require major bump)

- `findings.jsonl` schema change (breaks `/securecoder-fix` reading old runs)
- `.securecoder/config.json` schema change (breaks team-shared configs)
- Removal or rename of a skill

### Bump cadence

- **Rule pack pinned tags** bump on **minor** releases (e.g., ASVS v5.0.0 → v5.1.0 = skill v0.4.0 → v0.5.0).
- **Tool pinned versions** bump on **patch** releases (Semgrep 1.50.0 → 1.51.0 = v0.5.0 → v0.5.1).

### Migrations

A migration script per breaking change ships in `scripts/migrations/`. The skill detects schema mismatch on startup, names the older version it found, and offers to run the migration before continuing.

### Maintenance automation

Wire a GitHub Action that opens PRs when:

- Any pinned rule-pack source has a new upstream tag
- Any pinned tool has a new upstream release

Without this, six rule pins + four tool pins drift out of date quickly.

## 13. Build Order (V1)

Recommended slice ordering — each step exercises a new layer of the architecture and gives a working artifact.

1. **`/securecoder-setup` + `/securecoder-scan` (SAST-only path).**
   Smallest viable loop. Validates: cache dir creation, tool install consent + execution, rule-pack fetching, repo walking, SAST normalization to `findings.jsonl`, manifest writing, markdown report.
2. **`/securecoder-fix`.**
   Now there are real findings to fix. Validates: pre-flight checks, backup capture, per-fix loop (SEARCH/REPLACE → syntax check → re-scan → commit → push policy), restore command. Most safety-critical of the seven.
3. **`/securecoder-scan` compliance path.**
   Adds the LLM pass on top of SAST. Validates: framework fetching, relevance filter, architect-style prompts, coverage-matrix validation, compliance posture computation, HTML report.
4. **`/securecoder-secure`.**
   Wires existing skills with the cost-estimate gate and 50%-overrun mid-run gate. Mostly new prompt + orchestration logic, no new mechanisms.
5. **`/securecoder-review`.**
   Diff-scoped variant of `/securecoder-scan`. Validates: git-diff extraction, scoped SAST flags, `±20` line context for LLM, separate `.securecoder/reviews/` directory, pre-commit hook shim.
6. **`/securecoder-build` and `/securecoder-advise`.**
   Different shape from the pipeline skills. Build once the core is stable. `/securecoder-build` validates persistent-policy-block ergonomics across hosts; `/securecoder-advise` validates verbatim-citation discipline and search helper.

Ship each as its own minor-version tag (v0.1.0 = setup+scan-SAST, v0.2.0 = fix, etc.) so users can adopt incrementally.

## Appendix: Decisions Log

Locked decisions from the design grilling session (2026-05-13):

1. **Architecture:** Pure agent skill, no SCCAP backend dependency.
2. **Granularity:** Multiple composable skills (mattpocock-style), not one monolith.
3. **Scope:** Language-agnostic with runtime ruleset fetching, not Python-only / Python+TS / language-specific.
4. **Scan paths:** Both deterministic SAST and LLM-driven compliance, merged into a unified `findings.jsonl`.
5. **Skill set:** Seven skills (`/securecoder-setup`, `/securecoder-scan`, `/securecoder-fix`, `/securecoder-secure`, `/securecoder-review`, `/securecoder-build`, `/securecoder-advise`); modes asked inside skills with explanations + token warnings; `/securecoder-secure` runs straight through with one up-front approval.
6. **Multi-tool LCD:** Drop subagent parallelism, drop model pinning, ask in plain English instructions, stdlib-only Python helpers.
7. **State storage:** In-repo `.securecoder/` for project state + ~/.cache/securecoder/ for shared tools and rules; run history with `latest` pointer.
8. **Rule fetching:** Allowlist (OWASP/*, returntocorp/*); pinned-tag content-addressed cache; no TTL.
9. **Tool installation:** `~/.cache/securecoder/tools/`; pipx for Python, GitHub release binaries for native; one-time consent; ignore system tools by default.
10. **Findings:** 5-level severity, 3-level confidence, sha256-keyed dedup, shipped CWE-to-framework table; `/securecoder-fix` supports any-combination severity multi-select.
11. **Auto-fix safety:** Pre-flight + per-fix syntax-check (language-agnostic, installed on demand) + re-scan + automatic rollback + one git commit per successful fix + push strategy chosen up front.
12. **Cost estimation:** Token-first multi-model reference table; scan-only exit option at approval; 50%-overrun mid-run gate.
13. **`/securecoder-setup`:** 8-question wizard with defaults; defaults work without setup; re-running loads current values.
14. **`/securecoder-build`:** Persistent ASVS-policy block + optional minimal bootstrap + pre/post-task self-check protocol + `/securecoder-review` recommended adjunct + natural mode-end on context drop. Not a scaffold generator.
15. **`/securecoder-review`:** Scope picker + scoped SAST + scoped LLM compliance + separate `.securecoder/reviews/` dir + no auto-fix + SAST-only pre-commit hook shim.
16. **`/securecoder-advise`:** Invocation with/without question + 4-mode picker for no-arg + verbatim-cite-then-interpret response + `search_rules.py` helper + no code mutation.
17. **Repo layout / reports / versioning:** Single `security/` category; both markdown and HTML reports per run; repo-wide semver with migration scripts on breaking changes.

End of document.
