# `/securecoder-fix` — usage guide

## What this skill does

Reads a previous `/securecoder-scan` (or `/securecoder-review`) findings file and applies fixes — one finding at a time, with the full safety loop: backup capture before any edit, LLM-driven SEARCH/REPLACE patch, atomic apply, language-agnostic syntax check, re-scan with the originating tool to verify the finding is actually gone, automatic rollback on any verification failure, and one git commit per successful fix.

Handles both SAST findings (Semgrep, Bandit, Gitleaks, OSV) and compliance findings (ASVS / MASVS / Proactive Controls).

## When to invoke it

- **Right after `/securecoder-scan`** to remediate what was found
- **Right after `/securecoder-review`** to fix issues in your branch before committing
- **To roll back a previous fix run** that introduced problems (use `--restore`)
- **NOT** as the first thing you ever run — fix needs findings to operate on

## How to invoke

```text
# Fix findings from the latest scan
/securecoder-fix

# Fix findings from a specific scan run
/securecoder-fix run 20260514T140000Z
# Or:  "fix findings from run 20260514T140000Z"

# Fix findings from a review (diff-scoped)
/securecoder-fix from review 20260514T145000Z
# Or:  "fix what /securecoder-review just found"

# Roll back a fix run
/securecoder-fix --restore 20260514T143000Z
# Or:  "undo my last sccap-fix"
```

The skill always asks **which severities to fix** at the start. Picker options:

- All severities
- Critical only / High only / Medium only / Low only
- Critical + High (Recommended)
- Critical + High + Medium
- Custom multi-select (any subset)
- **Interactive one-by-one** — pause before each fix, review the proposed SEARCH/REPLACE, apply / skip / quit
- By specific finding IDs (provide a list of canonical IDs)

For your first fix run on a real codebase, use **Interactive one-by-one** — it lets you see exactly what every change will be before it lands.

## Pre-flight checks

Before any fix, the skill:

1. **Git clean-tree check.** If your tree has uncommitted changes, asks: stash and continue / abort / proceed anyway (risky).
2. **Protected branch check.** On `main` / `master` / `release/*`, offers to create `securecoder-fix/<run-id>` branch.
3. **Backup capture.** Every file slated for edit gets copied to `.securecoder/runs/<run-id>/backups/<path>` before any modification. Backups are independent of git history.
4. **Cost estimate.** Token estimate + multi-model dollar reference; one approval before proceeding.

## Per-fix loop

For each finding in scope:

1. Locate target lines.
2. LLM produces a SEARCH/REPLACE block.
3. **`apply_patch.py`** validates exactly-one-match for each block, then applies atomically (all blocks land or none).
4. **`syntax_check.py`** runs the language-appropriate parse check (`python3 -m py_compile`, `node --check`, `gofmt -e`, `ruby -c`, `php -l`, `bash -n`, JSON via stdlib). UTF-8 fallback for unsupported languages.
5. **Re-scan** the file with the originating tool. For SAST findings: run Semgrep / Bandit / Gitleaks / OSV on just that file and confirm the original finding's canonical ID is no longer present + no new same-or-higher finding was introduced. For compliance findings: re-run the architect prompt for the originating ASVS chapter on the patched file.
6. **On success:** one git commit with structured message:

   - SAST: `fix(securecoder): <severity>/<title> [<id-short>]`
   - Compliance: `fix(securecoder): <severity>/<title> [compliance <framework>/<control> <id-short>]`
7. **Push** per `config.git.push_strategy` (`push-each` / `commit-local-push-at-end` / `commit-local-never-push`).
8. **On any failure** (parse, syntax, re-scan): restore from backup, mark `editor_failed` with reason, move on. Up to 3 LLM retries per finding with named-failure retry context.

## Finding statuses after the loop

| Status | Meaning |
| --- | --- |
| `applied` | Fix landed, re-scan confirmed the finding is gone, git commit created. |
| `applied_unverified` | Compliance fix landed but the LLM re-scan call failed 3 times. Patch is in place; you should spot-check. |
| `editor_failed` | LLM couldn't produce a valid fix in 3 tries. File reverted to backup. Reason logged in `fix_log.jsonl`. |
| `editor_skipped` | You picked "skip" in interactive one-by-one mode. |
| `manual_review_required` | Finding has `fix_complexity: "high"` or `lines: null` — too architectural / location-ambiguous for auto-fix. Read the remediation hint and apply manually. |

## What it produces

```
.securecoder/runs/<fix-run-id>/
├── manifest.json           run metadata, per-status counts
├── fix_log.jsonl           one entry per finding processed
├── backups/<path>          pre-fix file contents (every file slated for edit)
├── _patches/<NNNN>_*.patch verbatim LLM SEARCH/REPLACE patches
└── log.md                  per-phase progress
```

Plus git commits on your working branch — one per successful fix.

## Follow-up

- **Verify nothing else broke:** run `git diff --stat` and review the changes.
- **Re-run a scan to confirm the findings are gone:** `/securecoder-scan` (this also updates the trend section in the next report).
- **If you don't like a fix:** `/securecoder-fix --restore <run-id>`. Backups + git revert combine for complete rollback.
- **Pre-commit gate for future commits:** `/securecoder-review` → install hook.

## Restore mode

```text
/securecoder-fix --restore 20260514T143000Z
```

The skill:

1. Locates `.securecoder/runs/20260514T143000Z/backups/`.
2. Shows you a per-file diff between current state and backup state.
3. Flags files modified-since-the-fix (so you don't lose intervening work).
4. Asks confirmation: yes / abort / per-file review.
5. Copies backups over the working tree.
6. Optionally also runs `git revert` on each fix commit (asks).
7. Writes `restore_log.md` to the run directory.

Works on non-git repos too — backups alone are sufficient.

## Common pitfalls

- **`editor_failed` on stylistic findings.** Some lint-style findings (Bandit B603 "subprocess call with shell=True", etc.) require structural code change beyond a simple SEARCH/REPLACE. The LLM tries hard for 3 tries but sometimes hits a wall. The fix logs the failure reason; you can apply manually.
- **High `editor_failed` count on first run.** If you're seeing >30% failures, the LLM might be too small for your codebase complexity. Try a more capable model.
- **Compliance fixes are slow.** Each compliance fix involves a re-scan LLM call that's another full architect-prompt for the chapter. Expect ~30–60 seconds per compliance fix.
- **Re-scan considers ONLY equal-or-higher severity for new findings.** A high-severity fix that introduces a low-severity issue won't trigger a retry. Run a full `/securecoder-scan` to surface those.
- **Backups are NOT git-tracked by default.** If you `rm -rf .securecoder/runs/`, you lose backups. The auto-generated `.securecoder/.gitignore` excludes `runs/`. If you want persistent backups, override that.
- **Push strategy matters in CI.** `push-each` causes per-fix push events that may trigger many CI runs. `commit-local-push-at-end` is friendlier to CI; `commit-local-never-push` is friendliest.

## See also

- [`/securecoder-scan` guide](securecoder-scan.md) — produces findings for fix
- [`/securecoder-secure` guide](securecoder-secure.md) — pipeline that includes fix
- [Scenarios guide](../scenarios.md) — Scenario 7 covers rollback in detail
