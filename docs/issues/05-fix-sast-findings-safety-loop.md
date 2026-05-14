# 05 — `/securecoder-fix` for SAST findings (safety loop + commit-per-fix)

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The highest-risk slice. Implements `/securecoder-fix` end-to-end against the safety model in design.md §8 and prd.md "Auto-fix safety". Modifies the user's source files; correctness here matters more than throughput.

The user invokes `/securecoder-fix`, picks a severity scope (any combination — All / Critical / High / Medium / Low / Critical+High / Custom multi-select / Interactive one-by-one / By ID), and the skill applies fixes one finding at a time against `.securecoder/runs/latest/findings.jsonl`.

**Pre-flight (mandatory):**
- Git clean-tree check; if dirty, ask stash / abort / proceed
- Protected-branch warning (`main`, `master`, `release/*`) with offer to create `securecoder-fix/<run-id>` branch
- Backup every file slated for edit to `.securecoder/runs/<run-id>/backups/<path>`
- Cost estimate based on `findings_to_fix × ~4K tokens`; one approval

**Per-fix loop:**
1. Locate target line range
2. LLM emits SEARCH/REPLACE block
3. Validate SEARCH appears exactly once; zero or many = `editor_failed`, skip
4. Apply replace
5. **Language-agnostic syntax check.** Detect language from extension. Use the cached or system-available checker per design.md §3.3 (`python3 -m py_compile`, `node --check`, `gofmt -e -l`, `php -l`, `ruby -c`, etc.). Install the right checker on demand into `~/.cache/securecoder/tools/` if not present (same consent gate as slice 02 already taken). UTF-8-validity fallback when no checker exists.
6. Re-scan the fixed file with the originating SAST tool; verify finding is gone and no new finding of equal-or-higher severity introduced
7. On any failure → restore from backup, mark `editor_failed`, log reason, move on
8. On success → `git commit` with message `fix(securecoder): <severity>/<title> [<finding-id-short>]` whose body includes finding source / rule ID / CWE / original lines; mark `applied`
9. Push policy per `config.git.push_strategy`: `push-each` / `commit-local-push-at-end` (default) / `commit-local-never-push`
10. Up to 3 LLM tries per finding with named-failure retry context

**Post-flight:**
- Summary: applied / editor_failed / manual_review_required counts
- `git diff --stat` if git
- Print restore instructions ("to roll back: `/securecoder-fix --restore <run-id>` or natural-language ask")
- Never auto-commit the run summary

**One-by-one mode** pauses before step 4 to show the proposed SEARCH/REPLACE and ask `apply / skip / quit`.

Compliance findings (`category: "compliance"`) are out of scope for this slice — they're handled in slice 08. SAST findings with `fix_complexity: "high"` are flagged `manual_review_required` and skipped.

The asvs-shell project at `/Users/overlord/Projects/asvs-shell` already has a working SEARCH/REPLACE patch loop with 3-tries semantics — lift its parse regex and retry pattern.

## Acceptance criteria

- [ ] `/securecoder-fix` with default scope (`critical + high`) reads `.securecoder/runs/latest/findings.jsonl` and applies fixes for matching findings
- [ ] Severity picker supports all listed modes; multi-select supports any combination
- [ ] Pre-flight refuses to start on a dirty tree unless user explicitly accepts; offers branch creation when on `main` / `master` / `release/*`
- [ ] Every file slated for edit is backed up to `.securecoder/runs/<run-id>/backups/<path>` before any edit
- [ ] Failed fixes restore from backup; the file ends up byte-identical to its pre-fix state
- [ ] Successful fixes produce one git commit each, with the documented message format
- [ ] Syntax check is language-agnostic: works on Python, JavaScript, Go, Ruby, PHP at minimum; falls back to UTF-8 check for unsupported languages
- [ ] Syntax checker installs on demand into `~/.cache/securecoder/tools/` without re-prompting consent
- [ ] Re-scan after each fix uses the originating SAST tool only (not the full tool stack) and verifies finding is gone + no new same-or-higher severity finding
- [ ] Push strategy honored: `push-each` pushes after every commit, `commit-local-push-at-end` pushes once in post-flight, `commit-local-never-push` never pushes
- [ ] One-by-one mode pauses with apply/skip/quit prompt for each fix
- [ ] Up to 3 LLM tries per finding; retry context includes the named failure mode
- [ ] After 3 failed tries, finding marked `editor_failed` with reason logged; batch continues
- [ ] Post-flight summary + `git diff --stat` + restore instructions
- [ ] Non-git repos: backups still work; commit/push steps skipped with informational message
- [ ] Tests cover: patch applier (happy path, zero-match, multi-match, multi-block-per-response), backup-restore round-trip (file → edit → restore = original), syntax checker dispatcher (per-language and UTF-8 fallback), git wrapper (clean-tree, branch, commit-per-fix, push-strategy dispatch)

## Blocked by

- 02 — `/securecoder-scan` SAST end-to-end with Semgrep + markdown report
