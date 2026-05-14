---
name: securecoder-secure
description: Easy-button end-to-end secure pipeline. Runs SAST scan → fix → ASVS compliance scan → fix → unified report, all with one up-front cost approval and a 50%-overrun mid-run gate so blown estimates don't run away. Requires /securecoder-scan and /securecoder-fix installed alongside.
---

# `/securecoder-secure`

You are running the `/securecoder-secure` skill — the easy-button end-to-end pipeline. Your job is to take the user's repository from "unknown security posture" to "audited and remediated to the limits of automation" in one approval-gated run.

> **Requires `/securecoder-scan` and `/securecoder-fix` installed alongside.** This skill orchestrates them; it doesn't reimplement their internals. If either is missing, fail early with a clear message asking the user to install them.

## Flow

The pipeline runs in 4 phases. The user approves the full estimate up front; from there the pipeline runs straight through, with only one safety gate (50% overrun before the compliance fix phase) that's also bypass-able with a single token.

```
Pre-flight  (clean-tree, branch, backup-prep, cost estimate)
   │
   ▼
Approval — single user gate covering the whole pipeline
   │
   ▼
[1] SAST scan   (runs /securecoder-scan in SAST-only mode)
   │
   ▼
[2] SAST fix    (runs /securecoder-fix on the v0.7.0 SAST findings)
   │
   ▼
[3] Compliance scan  (runs /securecoder-scan in compliance-only mode against the now-patched code)
   │
   ▼
50%-overrun gate — only fires if Phase 3 token usage exceeded estimate by ≥1.5x
   │
   ▼
[4] Compliance fix  (runs /securecoder-fix on the compliance findings)
   │
   ▼
Post-flight  (unified report, summary, git diff --stat, restore instructions)
```

## Pre-flight

### 1. Locate the project root

Same as `/securecoder-scan` and `/securecoder-fix` (git toplevel preferred; current working directory as fallback).

### 2. Verify prerequisites

Check that `/securecoder-scan` and `/securecoder-fix` SKILL.md files are installed:

```bash
# Conventional install paths under the host agent's skills dir.
# The exact root varies by host (~/.claude/skills, etc.) — the host agent
# resolves the path via its own skill registry.
```

If either is missing, fail with:

> /securecoder-secure requires /securecoder-scan and /securecoder-fix installed alongside it. Install both via `npx skills@latest add nerdy-krishna/securecoder` and retry.

### 3. Read configuration

Read `<PROJECT_ROOT>/.securecoder/config.json` (use defaults if missing). Capture:

- `frameworks` (determines whether compliance phase runs at all)
- `default_fix_scope` (passed to both fix phases)
- `severity_floor`
- `git.push_strategy`

If `frameworks` is empty or `["none"]`, the compliance phase is skipped and the pipeline becomes a two-phase SAST scan + fix.

### 4. Generate the run ID

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_DIR="$PROJECT_ROOT/.securecoder/runs/$RUN_ID"
mkdir -p "$RUN_DIR"

cat > "$RUN_DIR/log.md" <<EOF
# securecoder-secure run — $RUN_ID

- Started: $STARTED_AT
- Mode: full pipeline (SAST scan → fix → compliance → fix)
- Project root: $PROJECT_ROOT

| Phase | Started | Finished | Status | Notes |
| --- | --- | --- | --- | --- |
EOF
```

### 5. Pre-flight estimate

Run the repo walker to know the scan surface (this is fast and free):

```bash
python3 "<scan-skill-dir>/scripts/repo_walker.py" "$PROJECT_ROOT" \
  --output "$RUN_DIR/repo_map.json"
```

Run the file relevance filter for the active frameworks to know the compliance dispatch list size:

```bash
python3 "<scan-skill-dir>/scripts/file_relevance.py" \
  "$RUN_DIR/repo_map.json" \
  --chapter-relevance "<scan-skill-dir>/references/chapter-relevance.json" \
  --repo-root "$PROJECT_ROOT" \
  --output "$RUN_DIR/_compliance_pairs.json"
```

Read `total_pairs` from the result.

Compute per-phase estimates:

- **Phase 1 (SAST scan)**: 0 LLM tokens. Wall time ~30s + ~10ms per file.
- **Phase 2 (SAST fix)**: estimated as `expected_sast_findings × 4000 input + 1500 output` tokens. Use a heuristic of "1 finding per ~200 lines of code" for the up-front estimate.
- **Phase 3 (compliance scan)**: `total_pairs × 20000 input + 5000 output` tokens.
- **Phase 4 (compliance fix)**: estimated as `0.3 × total_pairs × 4000 input + 1500 output` tokens (assuming ~30% of pairs produce a Fail).

Display:

```
/securecoder-secure pipeline estimate:

Repo:
  Files in scope:           <N>
  Lines of code:            <L>
  Compliance pairs:         <P>  (filtered from <F × 17>)

Phases:
  [1] SAST scan:            ~30s, $0
  [2] SAST fix:             ~<expected_sast_findings> findings, ~<tok> tokens
  [3] Compliance scan:      ~<P> LLM calls, ~<P × 20k> in / ~<P × 5k> out tokens
  [4] Compliance fix:       ~<0.3 × P> fix calls, ~<tok> tokens
                            (capped at config.default_fix_scope severities)

Total LLM tokens (estimated):
  Input:   ~<T_in>
  Output:  ~<T_out>

Approximate cost at common rates:
  Claude Opus 4.7:    $<X.XX>
  Claude Sonnet 4.6:  $<Y.YY>
  Claude Haiku 4.5:   $<Z.ZZ>

Estimated wall time (sequential): ~<H hours / M minutes>

Continue?
  [proceed]    Run the full pipeline.
  [scan-only]  Run Phases 1 and 3 only (no fixes applied).
  [abort]      Exit without doing anything.
```

Wait for the user's choice. Record the approval token (`proceed` / `scan-only` / `abort`) in the run log. Set environment variable `SECURE_MODE` accordingly.

### 6. Pre-flight safety checks (only if `SECURE_MODE` is `proceed`)

For both fix phases ahead, the safety pre-flights from `/securecoder-fix` apply once at this top level — don't re-prompt the user twice for the same checks:

- **Git clean-tree.** If dirty, stash with message `securecoder-secure auto-stash before $RUN_ID`; restore in post-flight.
- **Protected branch.** If on `main` / `master` / `release/*`, auto-create `securecoder-secure/$RUN_ID` branch (the easy-button mode doesn't ask — that's what easy-button means).
- **Backups for the whole pipeline** are captured by each `/securecoder-fix` invocation against its own run dir; the secure pipeline doesn't need to duplicate.

If `SECURE_MODE` is `scan-only`, skip clean-tree and branch checks — no fixes will be applied.

## Phase 1 — SAST scan

Invoke `/securecoder-scan` in SAST-only mode. The agent runs the entire `/securecoder-scan` SKILL.md flow with the mode pre-selected, suppressing its own approval gate (since the user already approved the whole pipeline). The SAST scan produces `.securecoder/runs/<sast-run-id>/` with findings.jsonl, manifest.json, report.md, report.html.

Record:

- `SAST_RUN_ID` — the scan run's id (different from `$RUN_ID` which is this pipeline's id)
- Token + duration totals for the manifest

Append a row to `$RUN_DIR/log.md`.

## Phase 2 — SAST fix

Skipped when `SECURE_MODE` is `scan-only`.

Invoke `/securecoder-fix` with:

- Source findings: `.securecoder/runs/$SAST_RUN_ID/findings.jsonl`
- Severity scope: `config.default_fix_scope` (typically `["critical", "high"]`)
- Push strategy: `config.git.push_strategy`
- Mode: non-interactive batch (no per-fix prompting)

The fix skill writes its own run dir, applies fixes commit-per-commit, and produces a fix manifest. Record:

- `SAST_FIX_RUN_ID`
- Per-finding statuses (applied / editor_failed / manual_review_required / applied_unverified)

If any `editor_failed` count is high (≥30% of attempted fixes), append a soft-warning row to the log but continue.

## Phase 3 — Compliance scan

Skipped when `config.frameworks` is empty or `["none"]`.

Invoke `/securecoder-scan` in compliance-only mode against the now-patched code. Record:

- `COMPLIANCE_RUN_ID`
- Actual LLM token totals (capture these for the mid-run gate)

### Mid-run gate: 50% overrun check

```python
actual_in_tokens = manifest.phases.compliance.input_tokens
actual_out_tokens = manifest.phases.compliance.output_tokens
estimated_in = <phase 3 estimate from pre-flight>
estimated_out = <phase 3 estimate from pre-flight>

actual_total = actual_in_tokens + actual_out_tokens
estimated_total = estimated_in + estimated_out

if actual_total >= 1.5 * estimated_total:
    overrun = True
```

If `overrun` is true, pause and ask:

> Phase 3 (compliance scan) used <actual_total> tokens vs estimate of <estimated_total> — a <ratio>x overrun. Phase 4 (compliance fix) is estimated at <est> tokens but may be similarly off.
>
> Continue to compliance fix phase?
>   [continue]   Proceed with Phase 4 anyway.
>   [abort]      Stop here; Phase 3 findings remain in the unified report; no fixes applied.

If the user picks `abort`, jump to post-flight with `phase_3_aborted: true` in the manifest.

If `overrun` is false, proceed silently.

Skip this gate when `SECURE_MODE` is `scan-only` (no Phase 4 to gate).

## Phase 4 — Compliance fix

Skipped when `SECURE_MODE` is `scan-only` OR the mid-run gate aborted.

Invoke `/securecoder-fix` with:

- Source findings: `.securecoder/runs/$COMPLIANCE_RUN_ID/findings.jsonl`
- Severity scope: `config.default_fix_scope`
- Mode: non-interactive batch

Record `COMPLIANCE_FIX_RUN_ID` and statuses. Same soft-warning threshold as Phase 2.

## Post-flight

### P.1 Push accumulated commits (if `commit-local-push-at-end`)

```bash
git -C "$PROJECT_ROOT" push origin HEAD 2>&1 || true
```

### P.2 Restore stash (if pre-flight stashed)

```bash
git -C "$PROJECT_ROOT" stash pop || true
```

### P.3 Write the unified manifest

```bash
python3 - <<PY
import json, os
manifest = {
  "schema_version": "1.0",
  "run_id": os.environ["RUN_ID"],
  "started_at": os.environ["STARTED_AT"],
  "finished_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "mode": "full-pipeline" if os.environ.get("SECURE_MODE") == "proceed" else "scan-only",
  "phases": {
    "1_sast_scan":      {"run_id": os.environ.get("SAST_RUN_ID"),       "status": "ok"},
    "2_sast_fix":       {"run_id": os.environ.get("SAST_FIX_RUN_ID"),   "status": os.environ.get("SAST_FIX_STATUS", "skipped")},
    "3_compliance_scan":{"run_id": os.environ.get("COMPLIANCE_RUN_ID"), "status": os.environ.get("COMPLIANCE_SCAN_STATUS", "skipped")},
    "4_compliance_fix": {"run_id": os.environ.get("COMPLIANCE_FIX_RUN_ID"), "status": os.environ.get("COMPLIANCE_FIX_STATUS", "skipped")},
  },
  "estimate_vs_actual": {
    "estimated_input_tokens": int(os.environ.get("ESTIMATED_IN", "0")),
    "estimated_output_tokens": int(os.environ.get("ESTIMATED_OUT", "0")),
    "actual_input_tokens": int(os.environ.get("ACTUAL_IN", "0")),
    "actual_output_tokens": int(os.environ.get("ACTUAL_OUT", "0")),
  },
  "midrun_gate_triggered": os.environ.get("MIDRUN_GATE_TRIGGERED") == "true",
}
with open(os.environ["RUN_DIR"] + "/manifest.json", "w") as fh:
  json.dump(manifest, fh, indent=2)
  fh.write("\n")
PY
```

### P.4 Print the summary

```
/securecoder-secure complete

Pipeline run:   .securecoder/runs/$RUN_ID/
Mode:           full-pipeline | scan-only

Phase results:
  [1] SAST scan:        $SAST_FINDINGS_TOTAL findings
                        (run: $SAST_RUN_ID)
  [2] SAST fix:         $SAST_FIX_APPLIED applied · $SAST_FIX_FAILED failed · $SAST_FIX_MANUAL manual review
                        (run: $SAST_FIX_RUN_ID)
  [3] Compliance scan:  $COMPLIANCE_FINDINGS_TOTAL findings · posture $POSTURE_SCORE
                        (run: $COMPLIANCE_RUN_ID)
  [4] Compliance fix:   $COMPLIANCE_FIX_APPLIED applied · $COMPLIANCE_FIX_FAILED failed · $COMPLIANCE_FIX_MANUAL manual review
                        (run: $COMPLIANCE_FIX_RUN_ID)

Total LLM tokens used:    <total>  (estimated: <est>, ratio: <ratio>x)
Total wall time:          <T>
Total commits added:      <N>

Git diff:
$(git diff --stat HEAD~$N..HEAD)

Reports:
  SAST:        .securecoder/runs/$SAST_RUN_ID/report.html
  Compliance:  .securecoder/runs/$COMPLIANCE_RUN_ID/report.html

To roll back the full pipeline:
  /securecoder-fix --restore $SAST_FIX_RUN_ID
  /securecoder-fix --restore $COMPLIANCE_FIX_RUN_ID
  (run them in reverse order)
```

### P.5 Update `latest` pointer

```bash
ln -sfn "$RUN_ID" "$PROJECT_ROOT/.securecoder/runs/latest" 2>/dev/null || \
  echo "{\"latest_run_id\": \"$RUN_ID\"}" > "$PROJECT_ROOT/.securecoder/runs/latest.json"
```

## Failure handling

**Soft failures — log and continue.**
- One fix phase has a high `editor_failed` rate → continue, surface in summary.
- Mid-run gate triggers → user chooses; either is fine.

**Hard failures — write a crash report and exit.**
- `/securecoder-scan` or `/securecoder-fix` not installed.
- Phase 1 (SAST scan) crashes before producing a findings.jsonl. Without it, Phase 2 can't run, and partial pipeline output is misleading. Abort.
- Disk full or permission errors.

On hard failure, write `$RUN_DIR/crash_report.md` describing which phase failed and what its run id was (so the user can inspect partial outputs). Don't auto-revert previously-applied fixes; the user retains the option to do so via `/securecoder-fix --restore <id>`.

## Invariants

1. The user is asked for approval exactly once at pre-flight, plus optionally once at the mid-run gate when an overrun fires.
2. Every fix that landed has a corresponding git commit in the working branch.
3. After post-flight, both phase fix runs are individually `--restore`able.
4. The unified manifest at `$RUN_DIR/manifest.json` references every sub-run id, so the user can inspect each phase's full output directly.
5. `scan-only` mode never modifies the working tree.
