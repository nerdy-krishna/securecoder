---
name: securecoder-review
description: Fast diff-scoped security review of staged or uncommitted changes. Pre-commit gate. Runs SAST + scoped LLM compliance on the diff only — cost proportional to change size, not repo size. Optional pre-commit hook installation for SAST-only blocking-mode.
---

# `/securecoder-review`

You are running the `/securecoder-review` skill. Your job is to review *the changes the user is about to commit* — not the whole repo — for security findings. Diff-scoped means cost stays proportional to change size.

> **Two related capabilities.** This skill has interactive review (the user invokes it with the agent's intelligence available — full SAST + LLM compliance) AND an install-a-pre-commit-hook action that runs in `git`'s shell context with no agent (SAST-only, blocking the commit). See [§ Pre-commit hook installation](#pre-commit-hook-installation).

## Scope picker

Ask the user which diff to review (use the host agent's prompt mechanism):

- **Staged only** *(default — fastest)* — `git diff --cached`. Use for pre-commit gate.
- **Staged + unstaged** — `git diff HEAD`. Use to review everything you have locally before staging.
- **Branch vs base** — `git diff main...HEAD` (or whatever the base branch is). Use to review a feature branch before opening a PR.
- **Specific commit range** — agent asks for the range (e.g. `abc123..def456`). Use to review a specific span.
- **Install pre-commit hook** — installs `scripts/review_hook.py` into `.git/hooks/pre-commit`. See § Pre-commit hook installation below.

## Pre-flight

### 1. Locate the project root

Same as the other skills (git toplevel preferred; cwd fallback).

### 2. Generate the review id and dir

`/securecoder-review` writes to `.securecoder/reviews/` rather than `.securecoder/runs/`, so review history doesn't pollute the scan trend baseline.

```bash
REVIEW_ID="$(date -u +%Y%m%dT%H%M%SZ)"
REVIEW_DIR="$PROJECT_ROOT/.securecoder/reviews/$REVIEW_ID"
mkdir -p "$REVIEW_DIR"
```

### 3. Resolve the diff command

Based on the user's scope:

```bash
case "$scope" in
  staged)         DIFF_CMD="git -C $PROJECT_ROOT diff --cached" ;;
  unstaged_too)   DIFF_CMD="git -C $PROJECT_ROOT diff HEAD" ;;
  branch_vs_base) DIFF_CMD="git -C $PROJECT_ROOT diff $BASE_BRANCH...HEAD" ;;
  range)          DIFF_CMD="git -C $PROJECT_ROOT diff $RANGE" ;;
esac
```

If the diff is empty, print "No changes to review." and exit cleanly.

## Phase A — Diff scoping

```bash
$DIFF_CMD | python3 "<skill-dir>/scripts/diff_scoper.py" \
  --repo-root "$PROJECT_ROOT" \
  --context 20 \
  --output "$REVIEW_DIR/diff_scope.json"
```

`diff_scope.json` lists each touched file with its added line ranges and ±20-line context windows. The compliance LLM only sees these windows, not the whole file.

If `total_files` is 0, exit cleanly.

## Phase B — Scoped SAST

Run only the SAST tools that make sense for the changed file set. The cached tool binaries from `/securecoder-scan` are reused (resolve via `~/.cache/securecoder/tools/<tool>/installed.json`).

For each tool, restrict to the changed file list rather than the whole repo:

```bash
# Semgrep
"$SEMGREP_BIN" --metrics=off --quiet --json \
  --output "$REVIEW_DIR/_semgrep.json" \
  $(< compose --include=<file> per changed file >) \
  --config "$RULES_DIR/<lang>" \
  "$PROJECT_ROOT" 2>/dev/null || true

# Bandit (only if any changed file is *.py)
"$BANDIT_BIN" -f json -o "$REVIEW_DIR/_bandit.json" <changed-py-files> 2>/dev/null || true

# Gitleaks (use --staged for staged-only scope, --no-git + path list otherwise)
"$GITLEAKS_BIN" detect --no-banner --report-format json \
  --report-path "$REVIEW_DIR/_gitleaks.json" \
  --source "$PROJECT_ROOT" --staged --exit-code 0 2>/dev/null || true

# OSV-scanner only if a dependency manifest is in the changed file list
if <any of changed files is a lockfile>; then
  "$OSV_BIN" --format json --output "$REVIEW_DIR/_osv.json" <lockfiles> 2>/dev/null || true
fi
```

Normalize each tool's output via the v0.3.0 normalizers from `/securecoder-scan/scripts/`:

```bash
python3 "<scan-skill-dir>/scripts/normalize_semgrep.py"  "$REVIEW_DIR/_semgrep.json"  --cwe-table "<scan-skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$REVIEW_DIR/_findings_semgrep.jsonl"
python3 "<scan-skill-dir>/scripts/normalize_bandit.py"   "$REVIEW_DIR/_bandit.json"   --cwe-table "<scan-skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$REVIEW_DIR/_findings_bandit.jsonl"
python3 "<scan-skill-dir>/scripts/normalize_gitleaks.py" "$REVIEW_DIR/_gitleaks.json" --cwe-table "<scan-skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$REVIEW_DIR/_findings_gitleaks.jsonl"
python3 "<scan-skill-dir>/scripts/normalize_osv.py"      "$REVIEW_DIR/_osv.json"      --cwe-table "<scan-skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$REVIEW_DIR/_findings_osv.jsonl"
```

**Critical: filter findings to the diff scope.** Only keep SAST findings whose `file:lines` overlaps a changed line range from `diff_scope.json`. Findings in unchanged regions of a touched file are ignored (the user can review them via a full `/securecoder-scan`).

## Phase C — Scoped LLM compliance review

Only if `config.frameworks` is non-empty and includes `asvs-v5`.

For each touched file:

1. Determine which ASVS chapters apply (reuse `file_relevance.py` against a synthesized one-file repo map).
2. For each (file × chapter) pair, dispatch the architect prompt — but **substitute only the diff hunks + ±20 lines of context** as `{{file_content_with_line_numbers}}`, not the whole file. The chapter content is reused from the cached framework markdown.
3. Validate coverage matrix (one retry on incomplete).
4. Normalize via `normalize_compliance.py`.
5. **Filter findings to the diff scope.** Like SAST findings, only keep compliance findings whose lines overlap a changed range.

Cost stays proportional to diff size: a 50-line diff in one file produces ~17 LLM calls (one per ASVS chapter), each with ~50 lines + 40 context lines of input, not the entire file.

## Phase D — Merge + render

```bash
cat "$REVIEW_DIR/_findings_"*.jsonl > "$REVIEW_DIR/findings.jsonl"
```

Compose a minimal manifest (review-flavored — no trend, no compliance posture since the scope is a diff):

```json
{
  "schema_version": "1.0",
  "review_id": "<id>",
  "mode": "review",
  "scope": "staged | unstaged_too | branch_vs_base | range",
  "started_at": "...",
  "finished_at": "...",
  "repo_root": "<path>",
  "diff_stats": {
    "files_changed": <N>,
    "added_lines": <N>,
    "removed_lines": <N>
  },
  "totals": {
    "findings": <N>,
    "by_severity": {"critical": <N>, ...},
    "by_source": {"semgrep": <N>, ...}
  }
}
```

Render markdown via the v0.2.0 renderer:

```bash
python3 "<scan-skill-dir>/scripts/render_markdown.py" \
  "$REVIEW_DIR/findings.jsonl" \
  --manifest "$REVIEW_DIR/manifest.json" \
  --output "$REVIEW_DIR/report.md"
```

Review reports are markdown-only (no HTML) — chat output is the primary surface for this skill.

## Phase E — Chat verdict

Print to chat:

If no findings:

```
[securecoder-review] OK to commit — 0 findings in diff scope.
  Files reviewed:   <N>
  Added lines:      <N>
  Scoped report:    .securecoder/reviews/$REVIEW_ID/report.md
```

If findings:

```
[securecoder-review] <N> issues found — review before committing.
  Critical: <c>  High: <h>  Medium: <m>  Low: <l>  Info: <i>

By source:
  Semgrep:    <n>
  Bandit:     <n>
  Gitleaks:   <n>
  Compliance: <n>

Top 5 findings:
  1. [CRITICAL] <title>  ·  <file>:L<line>
  2. ...

To fix the findings from this review:
  /securecoder-fix <review-id>     (the fixer accepts an explicit findings file)

Full report:  .securecoder/reviews/$REVIEW_ID/report.md
```

## Pre-commit hook installation

When the user picks "Install pre-commit hook" at the scope picker:

```bash
HOOK_PATH="$PROJECT_ROOT/.git/hooks/pre-commit"
[ -d "$PROJECT_ROOT/.git" ] || fail "Not a git repo — can't install a hook."

if [ -f "$HOOK_PATH" ]; then
  # Existing hook — back it up and append rather than overwrite
  cp "$HOOK_PATH" "$HOOK_PATH.before-securecoder-$(date -u +%Y%m%dT%H%M%SZ)"
fi

cat > "$HOOK_PATH" <<EOF
#!/usr/bin/env sh
# Installed by /securecoder-review
exec python3 "<absolute path to scripts/review_hook.py>" "\$@"
EOF
chmod +x "$HOOK_PATH"

echo "Installed pre-commit hook at $HOOK_PATH."
echo "It runs SAST tools only (no LLM) on staged files and blocks the commit"
echo "when findings above '$severity_floor' are present. Bypass once with"
echo "    git commit --no-verify"
echo "Run /securecoder-review interactively for compliance review before pushing."
```

If a previous hook exists, the install backs it up; the user can manually merge logic by inspecting the `.before-securecoder-*` copy. We don't auto-merge to avoid corrupting existing hook logic.

## Failure handling

**Soft failures — log and continue.**
- Tools missing → fall back to whatever's installed. Note in chat output.
- One SAST tool fails → other tools still produce findings.

**Hard failures — exit with a message.**
- Not a git repo (no git toplevel and no `--scope` argument that allows non-git).
- User picked "Install pre-commit hook" on a non-git repo.
- `python3` not on PATH.

## Invariants

1. Findings emitted by this skill are always filtered to the diff scope. A finding in an unchanged region of a touched file never appears in the review report.
2. `.securecoder/reviews/<id>/` and `.securecoder/runs/<id>/` are distinct directories with distinct purposes. Review history never affects scan trend computation.
3. The pre-commit hook runs SAST-only and never invokes the agent. Its install path is documented in the hook file itself for transparency.
4. The hook reminds the user every commit to run `/securecoder-review` interactively for compliance review before pushing — so compliance failures don't sneak past the SAST-only hook.
