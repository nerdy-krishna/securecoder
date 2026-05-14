# `/securecoder-review` — usage guide

## What this skill does

Runs SAST and (optionally) LLM compliance review against only the changes you're about to commit — not the whole repo. Cost is proportional to change size. Designed as a pre-commit gate; also installable as a `.git/hooks/pre-commit` that runs SAST-only without LLM cost.

## When to invoke it

- **Right before you commit.** Catches issues in staged changes before they land.
- **Right before opening a PR.** Scope: "Branch vs base" — reviews everything new on your branch against `main`.
- **To install the pre-commit hook.** One-time setup; subsequent commits run SAST-only automatically.
- **NOT** as a substitute for `/securecoder-scan` — review only looks at the diff, so unchanged-but-broken code is invisible.

## How to invoke

```text
# Default — interactive scope picker
/securecoder-review

# (Future) Explicit scope
/securecoder-review --scope staged
/securecoder-review --scope unstaged-too
/securecoder-review --scope branch-vs-base --base main
/securecoder-review --scope range abc123..def456

# Install the pre-commit hook
/securecoder-review
# Then pick "Install pre-commit hook" at the scope prompt
```

## Scope options

| Scope | Diff command | Use case |
| --- | --- | --- |
| **Staged only** *(default)* | `git diff --cached` | Right before `git commit` |
| **Staged + unstaged** | `git diff HEAD` | Before staging — review everything local |
| **Branch vs base** | `git diff main...HEAD` (or whatever base) | Before opening a PR |
| **Specific commit range** | `git diff abc..def` | Reviewing a specific commit span |
| **Install pre-commit hook** | (n/a) | One-time installation |

## What happens (interactive mode)

1. **Diff scoper** parses the chosen diff into per-file added line ranges + ±20-line context windows.
2. **Scoped SAST** runs each tool restricted to the changed file list:
   - Semgrep with `--include=<file>` per changed file
   - Bandit on changed Python files only
   - Gitleaks `--staged` (when scope is staged-only) or on the file list
   - OSV-scanner only if a dependency manifest changed
3. **Scoped LLM compliance** (when `config.frameworks` is non-empty) — for each touched file, runs the relevance filter against active frameworks. For each (file, chapter) pair, the architect prompt sees only the changed hunks + ±20 lines context, not the whole file. Cost is proportional to diff size.
4. **Diff-scope filter** — only findings whose `file:lines` overlap a changed range are kept. Findings in unchanged regions of touched files are dropped from the review report (run `/securecoder-scan` to see those).
5. **Verdict in chat** + markdown report at `.securecoder/reviews/<id>/report.md`.

## Verdict outputs

If no findings:

```
[securecoder-review] OK to commit — 0 findings in diff scope.
  Files reviewed:   3
  Added lines:      47
  Scoped report:    .securecoder/reviews/20260514T145000Z/report.md
```

If findings:

```
[securecoder-review] 4 issues found — review before committing.
  Critical: 1  High: 2  Medium: 1  Low: 0  Info: 0

By source:
  Semgrep:    2
  Bandit:     1
  Gitleaks:   0
  Compliance: 1

Top 5 findings:
  1. [CRITICAL] Tainted SQL string  ·  src/api/users.py:142
  2. [HIGH]     Weak hash (MD5)     ·  src/auth/legacy.py:58
  3. ...

To fix the findings from this review:
  /securecoder-fix from review 20260514T145000Z

Full report:  .securecoder/reviews/20260514T145000Z/report.md
```

## What it produces

```
.securecoder/reviews/<review-id>/
├── findings.jsonl       diff-scoped findings (v1.0 schema)
├── manifest.json        review metadata + diff stats
├── report.md            markdown report (no HTML for reviews)
├── diff_scope.json      per-file changed line ranges + context windows
└── log.md
```

**Note the directory is `reviews/`, not `runs/`.** Review history is kept separate from scan history so the cross-run trend in `/securecoder-scan` reports isn't polluted by per-commit reviews.

## Pre-commit hook installation

```
/securecoder-review
# At the scope picker, choose "Install pre-commit hook"
```

The skill writes `.git/hooks/pre-commit` invoking `scripts/review_hook.py`. Any pre-existing hook gets backed up to `.git/hooks/pre-commit.before-securecoder-<timestamp>` rather than being overwritten.

**The hook is SAST-only.** It runs Semgrep / Bandit / Gitleaks against staged files using the cached tool binaries from `~/.cache/securecoder/tools/`. It does NOT call the LLM (since `git`'s shell context doesn't have agent access). Exit non-zero blocks the commit when any finding above `config.severity_floor` is present.

Bypass once: `git commit --no-verify`.

## Follow-up

- **If review found nothing:** commit normally.
- **If review found findings:**
  - Inspect via the markdown report.
  - To fix automatically: `/securecoder-fix from review <review-id>`.
  - To unstage and fix manually: `git restore --staged <file>` and edit by hand.
- **Install the hook** if you haven't already, so the next commit auto-checks.
- **Before pushing significant changes**: run `/securecoder-review` interactively (not just the hook) — the interactive mode runs LLM compliance review, which the hook skips.

## Example workflows

### Pre-commit gate every change

```bash
# Edit code, stage with git add
/securecoder-review
# Verdict: OK to commit
git commit -m "..."
# Hook re-runs SAST as a safety net; commit proceeds
git push
```

### Branch-vs-base check before opening a PR

```bash
git checkout my-feature-branch
/securecoder-review
# Scope: Branch vs base
# Findings: 3 in your new code
/securecoder-fix from review <review-id>
git push
gh pr create
```

### Pre-commit hook only (no interactive review)

```bash
# Install once
/securecoder-review
# Choose: Install pre-commit hook

# From then on, every git commit auto-runs SAST
git add .
git commit -m "..."   # hook blocks if SAST findings above floor
```

## Common pitfalls

- **The hook can't run LLM compliance.** It runs in `git`'s shell context with no agent. Compliance review needs `/securecoder-review` interactively. The hook reminds you each time: "SAST passed. Run `/securecoder-review` interactively for compliance review before pushing."
- **Diff scoper misses very large diffs.** It's tolerant of various diff shapes but for >10k line diffs, switch to `/securecoder-scan` (whole repo) instead.
- **`--no-verify` bypasses the hook silently.** Useful in genuine emergencies. Set a policy of "never bypass without a follow-up issue" if your team needs that discipline.
- **Existing pre-commit hooks get backed up, not merged.** If you had a custom hook before, the backup is at `.git/hooks/pre-commit.before-securecoder-<timestamp>`. Manually merge if you need both.
- **Renamed files can confuse the diff scoper.** A renamed file's added lines might be detected as "the whole new file is new." This is benign — SAST still runs on the new path.
- **Cached tools must exist for the hook to work.** Run `/securecoder-scan` once before installing the hook to populate `~/.cache/securecoder/tools/`. If the cache is empty, the hook prints a hint and exits 0 (doesn't block commits over a missing cache).

## See also

- [`/securecoder-fix` guide](securecoder-fix.md) — to remediate findings the review surfaced
- [`/securecoder-scan` guide](securecoder-scan.md) — for whole-repo audits (review is diff-only)
- [Scenarios guide](../scenarios.md) — Scenarios 3 and 6 use `/securecoder-review`
