# 10 — `/securecoder-review` diff-scoped + pre-commit hook shim

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The pre-commit-gate skill. Different ergonomics from `/securecoder-scan`: operates on `git diff` instead of the whole repo, must complete in seconds for staged-only mode, has no auto-fix step.

**Flow:**

1. **Scope picker.** Single-select: staged / staged+unstaged / branch-vs-base (`git diff main...HEAD`) / specific commit range. Default staged.
2. **Diff scoper.** Pure function: `git diff` text → per-file changed line ranges + ±20 lines of context windows. Shipped as a helper script; testable in isolation.
3. **Scoped SAST.** Semgrep `--include=<file>` over changed files; Bandit on changed Python; Gitleaks on changed; OSV only if dep manifest changed. Each tool already present from slices 02 + 03.
4. **Scoped LLM compliance.** For each changed file, run the slice 07 relevance filter against active frameworks. For each `(file, chapter)` pair, send only the changed hunks + ±20 lines context to the LLM rather than the whole file. Cost proportional to diff size, not repo size.
5. **Output.** Terse verdict in chat: `OK to commit` / `N issues found — review before committing`. Findings written to `.securecoder/reviews/<run-id>/findings.jsonl` (separate from `.securecoder/runs/` so review history doesn't pollute scan trend). Markdown report only (no HTML for reviews — the chat output is the primary surface).
6. **No auto-fix.** If the user wants to fix what `/securecoder-review` flagged, they invoke `/securecoder-fix` against `.securecoder/reviews/<run-id>/findings.jsonl` (the fixer accepts an explicit findings file via natural-language ask).

**Pre-commit hook shim** (`scripts/review_hook.py` inside the `securecoder-review` skill dir):

- Standalone Python script; no agent dependency.
- Runs SAST tools only (Semgrep + Bandit + Gitleaks + OSV) on staged files.
- Exit code non-zero if any finding above `config.severity_floor` is present; blocks the commit.
- Output reminds user: "SAST passed. Run `/securecoder-review` interactively for compliance review before pushing."
- User installs via natural-language ask ("install /securecoder-review as a pre-commit hook"); skill writes `.git/hooks/pre-commit` invoking the shim.

## Acceptance criteria

- [ ] `/securecoder-review` with default staged scope runs SAST + LLM compliance scoped to staged changes and produces a verdict in under 30s for typical small diffs
- [ ] Scope picker offers all four documented modes; selecting branch-vs-base or specific range correctly identifies changed files
- [ ] Diff scoper produces correct per-file ranges + ±20 lines context for additions, deletions, and mixed hunks
- [ ] Scoped SAST runs each tool with file-list restriction (not full repo scan)
- [ ] Scoped LLM compliance sends only hunks + context to the LLM (verified by token count being proportional to diff size, not repo size)
- [ ] Findings written to `.securecoder/reviews/<run-id>/findings.jsonl`, separate from `.securecoder/runs/`
- [ ] Chat output is terse: `OK to commit` or count + severity breakdown
- [ ] Markdown report written to the review dir; no HTML
- [ ] `/securecoder-fix` against a review findings file works (no regression from slices 05 + 08)
- [ ] Pre-commit hook shim installs via natural-language ask; writes `.git/hooks/pre-commit` that invokes `scripts/review_hook.py`
- [ ] Hook exit code blocks the commit when findings above `severity_floor` are present
- [ ] Hook output reminds user to run `/securecoder-review` interactively for compliance pass
- [ ] Hook runs SAST-only (no LLM); does not require agent context
- [ ] Tests cover: diff scoper (additions / deletions / mixed / multi-file diffs), scoped SAST flag construction, scoped LLM hunk extraction, hook script exit code logic, hook install + uninstall path

## Blocked by

- 02 — `/securecoder-scan` SAST end-to-end with Semgrep + markdown report
