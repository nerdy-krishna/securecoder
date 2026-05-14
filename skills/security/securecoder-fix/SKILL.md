---
name: securecoder-fix
description: Remediate findings from a previous /securecoder-scan run. Pre-flight (clean-tree, branch, backup) + per-fix loop (LLM SEARCH/REPLACE → syntax check → re-scan → commit) + automatic rollback on any verification failure. Supports severity multi-select, by-finding-ID targeting, interactive one-by-one mode, and a --restore action to roll back a previous fix run.
---

# `/securecoder-fix`

You are running the `/securecoder-fix` skill. Your job is to safely remediate findings from a previous `/securecoder-scan` run, with every fix verified and any failed fix automatically rolled back.

> **v0.7.0 scope.** Handles both SAST findings (Semgrep, Bandit, Gitleaks, OSV-scanner) and compliance findings (ASVS v5 — produced by `/securecoder-scan` Phase B). Compliance findings with `fix_complexity: "high"` or `lines: null` are flagged `manual_review_required` rather than auto-fixed.

## Two modes

- **Default — apply fixes.** The user invokes with no `--restore` flag. Skill reads the latest findings, asks which severities to fix, then runs the per-fix loop.
- **Restore — roll back.** The user invokes `--restore <run-id>` (or asks in natural language "undo the last sccap-fix" / "restore run X"). Skill copies the run's backup files over the working tree and writes a `restore_log.md`. See [§ Restore](#restore-mode) below.

## Pre-flight (apply-fix mode)

### 1. Locate the project root

1. If a `.git/` directory exists in the current working directory or any ancestor, use the git toplevel (`git rev-parse --show-toplevel`).
2. Otherwise, use the current working directory.

Capture it as `PROJECT_ROOT`.

### 2. Find the findings file to fix

By default, read `<PROJECT_ROOT>/.securecoder/runs/latest/findings.jsonl`. If the user asked for a specific run id ("fix run 20260514T140000Z"), use that run's `findings.jsonl`. If neither exists, fail with:

> No findings to fix. Run `/securecoder-scan` first.

Record the source run id as `SOURCE_RUN_ID`. Generate a new id for this fix run:

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$PROJECT_ROOT/.securecoder/runs/$RUN_ID"
mkdir -p "$RUN_DIR/backups"
echo "$SOURCE_RUN_ID" > "$RUN_DIR/source_run.txt"
```

### 3. Load configuration

Read `<PROJECT_ROOT>/.securecoder/config.json` (or use defaults if missing). Capture: `default_fix_scope`, `git.push_strategy`, `severity_floor`.

### 4. Ask the user which severities to fix

Present a single-select picker with these options (pre-select `config.default_fix_scope` when available):

- **All severities**
- **Critical only**
- **High only**
- **Medium only**
- **Low only**
- **Critical + High** (Recommended)
- **Critical + High + Medium**
- **Custom multi-select** — agent asks "which severities?" and accepts any subset of `critical / high / medium / low / info`
- **Interactive one-by-one** — review each fix before it's applied
- **By specific finding IDs** — agent asks for a comma-separated list of canonical IDs

Record the chosen scope. Filter the findings list:

- **Skip findings with `status: "suppressed"`** — they were marked as false positives via `/securecoder-suppress`, the HTML report's suppress UI, or `.securecoder/suppressions.json`. Record them in the fix log with status `editor_skipped_suppressed` so the user sees how many were skipped for this reason, distinct from `editor_skipped` (user manually skipped in interactive mode).
- Of the remainder, keep `category: "sast"` and `category: "compliance"` findings whose `severity` is in the scope.
- For findings with `fix_complexity: "high"` or `lines: null`, append to a separate `MANUAL_REVIEW` list (they're recorded in the fix log with status `manual_review_required` but never auto-fixed).
- Everything else lands in `TO_FIX`.

Capture all three lists (`TO_FIX`, `MANUAL_REVIEW`, `SUPPRESSED_SKIPPED`).

If `TO_FIX` is empty, print "No findings match the selected scope. Exiting." and exit cleanly.

### 5. Git clean-tree check

```bash
if [ -d "$PROJECT_ROOT/.git" ]; then
  if ! git -C "$PROJECT_ROOT" diff --quiet || ! git -C "$PROJECT_ROOT" diff --cached --quiet; then
    # Uncommitted changes exist
    # Ask user: stash and continue / abort / proceed anyway (risky)
    :
  fi
fi
```

If the user picks **abort**, exit cleanly. If **stash**, run `git -C "$PROJECT_ROOT" stash push -u -m "securecoder-fix auto-stash before $RUN_ID"` and remember to restore it post-flight. If **proceed anyway**, log a warning to `$RUN_DIR/log.md`.

For non-git repos, skip this check but mention: "No git repo detected — backups will be used for rollback if needed."

### 6. Protected branch check

```bash
BRANCH="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo no-git)"
case "$BRANCH" in
  main|master|release/*|prod|production)
    PROTECTED=1 ;;
  *)
    PROTECTED=0 ;;
esac
```

If `PROTECTED=1`, ask:

> You're on a protected branch (`<branch>`). Create `securecoder-fix/<run-id>` branch before applying fixes?

Default yes. On approval: `git -C "$PROJECT_ROOT" checkout -b "securecoder-fix/$RUN_ID"`.

### 7. Backup capture

For every distinct file path in `TO_FIX`, copy it to `$RUN_DIR/backups/<path>` before any edit happens:

```bash
for file in <unique file paths in TO_FIX>; do
  src="$PROJECT_ROOT/$file"
  dst="$RUN_DIR/backups/$file"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
done
```

Backups exist independently of git history. If git rollback fails or the repo isn't git, backups are the ground truth.

### 8. Cost estimate

```
Fix run estimate:
  Findings to fix:   <count>
  Backed up files:   <count>
  Est. token cost:   ~<count × 4000> input + ~<count × 1500> output tokens

Approximate cost at common rates:
  Claude Opus 4.7:    $<X.XX>
  Claude Sonnet 4.6:  $<Y.YY>
  Claude Haiku 4.5:   $<Z.ZZ>

Continue? [proceed / abort]
```

(Use $15/$75 per M tokens for Opus, $3/$15 for Sonnet, $1/$5 for Haiku, in/out respectively.)

Wait for `proceed`. On `abort`, append `cancelled-at-estimate` to `$RUN_DIR/log.md` and exit cleanly.

## Per-fix loop

For each finding in `TO_FIX`:

### F.1 Show the user what's being fixed (interactive mode only)

If the user selected interactive one-by-one, display the finding summary before doing any LLM work:

```
[<n>/<total>] <severity> · <title> · <file>:L<start>-<end>
  Rule: <source_rule_id>
  CWE: <cwe>
  Remediation hint: <remediation_hint>

Action? [apply / skip / suppress / quit]
```

- `apply` → proceed with F.2.
- `skip` → mark finding `editor_skipped` and continue to the next finding.
- `suppress` → mark this finding as a false positive. Ask the user for a one-line reason, then invoke `/securecoder-suppress add --match '{"id": "<finding-id>"}' --reason "<reason>"` (the agent runs `suppress.py` directly). Mark the finding `editor_skipped_suppressed` in the fix log. Continue to the next finding. The suppression is now recorded in `.securecoder/suppressions.json` and will apply to future scans automatically.
- `quit` → exit the loop and proceed to post-flight.

### F.2 Compose the LLM prompt

Prompt template:

> You are fixing a security finding in a codebase. Produce a minimal patch that resolves the vulnerability while preserving behavior.
>
> **Finding:**
> - File: `<file>`
> - Lines: <start>-<end>
> - Severity: <severity>
> - Rule: <source_rule_id>
> - CWE: <cwe>
> - Title: <title>
> - Description: <description>
> - Evidence: ```<evidence>```
> - Remediation hint: <remediation_hint>
>
> **Current file content** (with line numbers, ±10 lines of context around the finding):
> ```<file-content-excerpt>```
>
> Produce one or more SEARCH/REPLACE blocks in EXACTLY this format. The SEARCH section must match the existing file content byte-for-byte (whitespace included). The REPLACE section is the corrected version. Do not include any other text between blocks.
>
> ```
> <<<<<<< SEARCH
> <exact existing code>
> =======
> <fixed code>
> >>>>>>> REPLACE
> ```
>
> Rules:
> 1. Make the SMALLEST change that resolves the vulnerability.
> 2. Preserve indentation, blank lines, and comments unless they are part of the vulnerability.
> 3. If you cannot fix this without architectural changes, say so explicitly in plain text and produce no SEARCH/REPLACE blocks. The skill will mark the finding `editor_failed` with your reason.

### F.3 Save the LLM response and run the patch applier

Write the LLM response to a temp file:

```bash
PATCH_FILE="$RUN_DIR/_patches/$(printf '%04d' $finding_index)_$finding_id_short.patch"
mkdir -p "$RUN_DIR/_patches"
echo "$llm_response" > "$PATCH_FILE"
```

Run the applier:

```bash
python3 "<skill-dir>/scripts/apply_patch.py" "$PROJECT_ROOT/$file" --patch "$PATCH_FILE" --json
```

Capture the JSON status. Interpret:
- `status: "ok"` → patch applied; proceed to F.4.
- `status: "no_match"`, `"multiple_match"`, `"no_blocks"` → patch failed to apply. Restore from backup if file changed, increment retry count, and either retry F.2 with retry context (up to 3 total tries) or mark `editor_failed`.

### F.4 Syntax check the patched file

```bash
python3 "<skill-dir>/scripts/syntax_check.py" "$PROJECT_ROOT/$file" --json
```

Exit 0 = clean; non-zero = syntax error introduced. On error, restore from backup and trigger a retry with the syntax-error message in the retry context.

### F.5 Re-scan to verify the fix

Best-effort verification that the finding is gone and no NEW finding of equal-or-higher severity was introduced. The mechanism depends on `category`:

#### F.5.sast — for SAST findings

Re-run the originating tool on just the fixed file:

```bash
case "$source" in
  semgrep)
    "$SEMGREP_BIN" --metrics=off --quiet --json --output "$RUN_DIR/_recheck.json" \
      --config "$RULES_DIR/<lang>" "$PROJECT_ROOT/$file" 2>/dev/null || true
    ;;
  bandit)
    "$BANDIT_BIN" -f json -o "$RUN_DIR/_recheck.json" "$PROJECT_ROOT/$file" 2>/dev/null || true
    ;;
  gitleaks)
    "$GITLEAKS_BIN" detect --no-banner --report-format json \
      --report-path "$RUN_DIR/_recheck.json" --source "$PROJECT_ROOT/$file" \
      --no-git --exit-code 0 2>/dev/null || true
    ;;
  osv-scanner)
    "$OSV_BIN" --format json --output "$RUN_DIR/_recheck.json" "$PROJECT_ROOT/$file" \
      2>/dev/null || true
    ;;
esac
```

Normalize via the same `normalize_<tool>.py` from `/securecoder-scan/scripts/`. Compare to the original finding:

- **The finding's canonical ID should NOT be in the re-scan results.** If it is, the fix didn't actually resolve the issue. Restore from backup and retry.
- **No NEW findings of equal-or-higher severity at the same file should appear.** If one does, the fix introduced a different vulnerability. Restore from backup and retry.

#### F.5.compliance — for compliance findings

Re-run the architect prompt for the originating chapter on the fixed file. The chapter ID is in the finding's `tags` (e.g., `"V1"`). The framework markdown is already cached at `~/.cache/securecoder/rules/frameworks/asvs/<sha>/5.0/en/<chapter_filename>` from the original scan.

Compose the same architect prompt the scan used, but on the now-patched file. Save the response to `$RUN_DIR/_recheck_compliance/<NNNN>_<chapter_id>_<file-slug>.md`. Validate coverage matrix (one retry on incomplete). Normalize via `normalize_compliance.py`.

Compare to the original finding:

- **The original finding's `source_rule_id` (control ID) should NOT be present in the re-scan's findings.** If it is, the fix didn't resolve the failing control. Restore from backup and retry.
- **No NEW compliance findings of equal-or-higher severity at the same file × chapter should appear.** If one does, the fix introduced a different compliance failure. Restore from backup and retry.

If the re-scan LLM call itself fails (3 tries), mark the finding `applied_unverified` — the patch is applied, the file is left in its post-fix state, but verification couldn't complete. The post-flight summary will flag these separately so the user can spot-check.

If verification passes, proceed to F.6.

### F.6 Commit the fix

Skip this step for non-git repos.

Commit message format differs by category:

- **SAST**: `fix(securecoder): <severity>/<title> [<id-short>]`
- **Compliance**: `fix(securecoder): <severity>/<title> [compliance <framework>/<control> <id-short>]`

```bash
SHORT_ID="${finding_id:0:8}"
if [ "$category" = "compliance" ]; then
  SUBJECT="fix(securecoder): $severity/$title [compliance $source/$source_rule_id $SHORT_ID]"
else
  SUBJECT="fix(securecoder): $severity/$title [$SHORT_ID]"
fi

COMMIT_MSG="$SUBJECT

Source: $source
Category: $category
Rule: $source_rule_id
CWE: $cwe_csv
Original lines: $file:L$start-L$end
Remediation: $remediation_hint

Applied by /securecoder-fix in run $RUN_ID."

git -C "$PROJECT_ROOT" add "$file"
git -C "$PROJECT_ROOT" commit -m "$COMMIT_MSG" >/dev/null
```

### F.7 Push (per `config.git.push_strategy`)

- `push-each`: `git -C "$PROJECT_ROOT" push` immediately.
- `commit-local-push-at-end`: accumulate; push once in post-flight.
- `commit-local-never-push`: skip.

### F.8 Update the finding status

Append to `$RUN_DIR/fix_log.jsonl`:

```json
{"id": "<finding-id>", "status": "applied", "commit_sha": "<sha>", "tries": <n>}
```

### F.9 Retry semantics

On any failure (parse, syntax, re-scan), restore from backup and retry the per-fix loop from F.2 with retry context appended to the LLM prompt:

> ## Retry context (try <N+1> of 3)
> Your previous attempt failed: <reason>.
> <if SEARCH did not match: include lines ±5 of the original finding location>
> <if syntax failed: include the syntax error message>
> <if re-scan failed: include the finding that's still present (or the new one)>
> Produce a corrected SEARCH/REPLACE block. Follow all the original rules.

Maximum 3 tries per finding. After 3 failures, mark `editor_failed` with the failure reason, leave the file in its restored (pre-attempt) state, and move on.

## Post-flight

### P.1 Push accumulated commits (if `commit-local-push-at-end`)

```bash
git -C "$PROJECT_ROOT" push origin HEAD 2>&1 || true
```

### P.2 Restore stash (if pre-flight stashed)

```bash
git -C "$PROJECT_ROOT" stash pop || true
```

### P.3 Write a manifest

```bash
python3 - <<PY
import json, os
def count_status(jsonl_path, status):
  try:
    return sum(1 for l in open(jsonl_path) if l.strip() and json.loads(l).get("status") == status)
  except FileNotFoundError:
    return 0

run_dir = os.environ["RUN_DIR"]
log = f"{run_dir}/fix_log.jsonl"
manifest = {
  "schema_version": "1.0",
  "run_id": os.environ["RUN_ID"],
  "started_at": os.environ["STARTED_AT"],
  "finished_at": os.environ.get("FINISHED_AT", ""),
  "mode": "fix",
  "source_run_id": os.environ["SOURCE_RUN_ID"],
  "repo_root": os.environ["PROJECT_ROOT"],
  "branch": os.environ.get("BRANCH", ""),
  "summary": {
    "applied": count_status(log, "applied"),
    "editor_failed": count_status(log, "editor_failed"),
    "editor_skipped": count_status(log, "editor_skipped"),
    "manual_review_required": count_status(log, "manual_review_required"),
  },
}
with open(f"{run_dir}/manifest.json", "w") as fh:
  json.dump(manifest, fh, indent=2)
  fh.write("\n")
PY
```

### P.4 Print the summary

```
securecoder-fix complete
  Run dir:     .securecoder/runs/$RUN_ID/
  Source run:  .securecoder/runs/$SOURCE_RUN_ID/
  Applied:     <N>
  Editor failed:           <N>  (see $RUN_DIR/fix_log.jsonl for reasons)
  Manual review required:  <N>  (compliance findings or fix_complexity=high)
  Skipped:     <N>          (interactive mode only)

  Git diff:    git diff $SOURCE_RUN_ID..HEAD  (or just `git diff --stat`)

  To roll back this fix run:
    /securecoder-fix --restore $RUN_ID

  Backups for this run: .securecoder/runs/$RUN_ID/backups/
```

### P.5 Update `latest` pointer

The fix run dir doesn't replace the scan run dir's `latest`. `latest` continues to point at the most recent scan run; the fix run's existence is referenced via the commit history and the `source_run.txt` file.

## Restore mode

When invoked with `--restore <run-id>` or via natural-language ("undo run X" / "restore the fix from earlier"):

### R.1 Locate the run

```bash
RESTORE_RUN_DIR="$PROJECT_ROOT/.securecoder/runs/$RUN_ID"
[ -d "$RESTORE_RUN_DIR/backups" ] || fail "No backups found for run $RUN_ID."
```

### R.2 Show what would be restored

For each file in `$RESTORE_RUN_DIR/backups/<path>`:

```bash
diff -u "$PROJECT_ROOT/<path>" "$RESTORE_RUN_DIR/backups/<path>" || true
```

Group the diffs and present them to the user. Highlight:
- Files in backup that no longer exist in working tree (deleted since fix) → ask if user wants to recreate.
- Files in backup whose current content has been modified since the fix landed → diff shown; user confirms per-file or for the whole batch.

### R.3 Confirm restoration

> Restoring will overwrite <N> files in the working tree with their pre-fix backups. <N> of these have been modified since the fix.
>
> Proceed with restore? [yes / abort / per-file]

### R.4 Apply the restore

```bash
while IFS= read -r path; do
  rel="${path#$RESTORE_RUN_DIR/backups/}"
  cp "$RESTORE_RUN_DIR/backups/$rel" "$PROJECT_ROOT/$rel"
done < <(find "$RESTORE_RUN_DIR/backups" -type f)
```

### R.5 Optionally git revert the fix commits

If git is available and the user wants:

> Revert the corresponding git commits too? [yes / no]

On yes, find commits referencing this run ID and revert them:

```bash
git -C "$PROJECT_ROOT" log --grep "$RUN_ID" --format="%H" | while read sha; do
  git -C "$PROJECT_ROOT" revert --no-commit "$sha"
done
git -C "$PROJECT_ROOT" commit -m "Revert securecoder-fix run $RUN_ID"
```

### R.6 Write the restore log

```bash
cat > "$RESTORE_RUN_DIR/restore_log.md" <<EOF
# Restore log — $RUN_ID

- Restored at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
- Files restored: <N>
- Modified-since-fix files restored: <N>
- Git revert performed: <yes|no>

## Restored files
$(find "$RESTORE_RUN_DIR/backups" -type f -exec echo "  - {}" \;)
EOF
```

## Failure handling

**Soft failures — log and continue.**
- One finding fails after 3 retries → mark `editor_failed`, restore from backup, move on.
- LLM emits no SEARCH/REPLACE blocks → mark `editor_failed` with reason "model declined or produced no patch".
- Re-scan tool crashes → log the crash, accept the apply (best effort), mark status `applied_unverified`.

**Hard failures — write a crash report and exit.**
- Cannot write to `$RUN_DIR` (disk full, permissions).
- Cached SAST tool binary is missing AND a new install fails.
- User attempts `--restore` on a run id with no `backups/` dir.

On hard failure, write `$RUN_DIR/crash_report.md` and exit. Do not partially write or partially commit.

## Invariants

1. Every file slated for modification has a backup at `$RUN_DIR/backups/<path>` before any patch is applied.
2. After the loop, every finding in `TO_FIX` has a corresponding entry in `$RUN_DIR/fix_log.jsonl` with one of: `applied`, `editor_failed`, `editor_skipped`, `editor_skipped_suppressed`, `manual_review_required`, `applied_unverified`.
3. Files that failed all 3 retries are byte-identical to their backup version.
4. No commit references a finding's `editor_failed` status. Only `applied` and `applied_unverified` produce commits.
5. After `--restore`, every file with a backup is either byte-identical to its backup OR the user explicitly skipped it via the per-file confirmation flow.
