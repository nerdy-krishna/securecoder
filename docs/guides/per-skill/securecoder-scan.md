# `/securecoder-scan` — usage guide

## What this skill does

Audits your codebase for security findings. Runs deterministic SAST tools (Semgrep, Bandit, Gitleaks, OSV-scanner) and/or LLM-driven compliance review against OWASP frameworks (ASVS v5, MASVS, Proactive Controls). Produces a unified `findings.jsonl`, a `manifest.json`, a markdown report, and a self-contained HTML report under `.securecoder/runs/<run-id>/`.

## When to invoke it

- **First-time audit** of a codebase you're new to
- **Periodic re-audits** to track security drift over time (the trend section in the report shows new / resolved / persistent since the last run)
- **Before remediating** — every `/securecoder-fix` run reads a previous `/securecoder-scan`'s findings
- **For compliance deliverables** — the HTML report includes a per-framework posture score

## How to invoke

```
/securecoder-scan
```

The skill asks one question — the **mode picker**:

| Mode | What it runs | Cost | Wall time |
| --- | --- | --- | --- |
| **SAST only** | Semgrep + Bandit + Gitleaks + OSV-scanner | $0 LLM | Seconds to minutes |
| **LLM compliance only** | Architect-style prompt per file × ASVS chapter pair | Dollars to tens-of-dollars | Hours for large repos |
| **Both** (Recommended for thorough audits) | SAST first, then compliance against the same code | Same as LLM compliance only | Same |

Pick the right mode for your situation:

- **First scan, no idea what's in the repo:** SAST only. Free and fast. Read the report. Then decide if compliance review is worth the cost.
- **Deep audit ahead of a release:** Both.
- **Compliance posture report for a stakeholder:** LLM compliance only (skips SAST since it's irrelevant to the deliverable).

## Pre-flight cost estimate

For LLM modes, the skill shows a token-first estimate before any expensive call:

```
Compliance pass estimate (ASVS v5):
  Files in scope:           142
  File × chapter pairs:     487  (filtered from 142 × 17 via relevance filter)
  LLM calls expected:       487
  Estimated input tokens:   ~9.7M
  Estimated output tokens:  ~2.4M

Approximate cost at common rates:
  Claude Opus 4.7:    $329.50
  Claude Sonnet 4.6:  $ 65.20
  Claude Haiku 4.5:   $ 21.70

Continue? [proceed / abort]
```

Read this carefully. The cost can be substantial for medium-large repos on a quality model.

## What it produces

```
.securecoder/runs/<run-id>/
├── findings.jsonl          unified findings (v1.0 schema)
├── manifest.json           run metadata + per-tool stats + trend data
├── report.md               human-readable markdown report
├── report.html             self-contained HTML report (filterable)
├── repo_map.json           file inventory the walker produced
├── log.md                  per-phase progress log
├── _trend.json             trend computation vs prior run
└── _<tool>_raw.json        per-tool raw output (debugging)

.securecoder/runs/latest    symlink to the most recent run
```

The `findings.jsonl` is the single source of truth. The reports are derivatives.

## Example invocations

```text
# Default — interactive mode picker
/securecoder-scan

# (Future) Force SAST only without the mode picker
/securecoder-scan sast

# (Future) Force compliance only
/securecoder-scan compliance

# (Future) Restrict to specific ASVS chapters
/securecoder-scan compliance --chapters V1,V11
```

Argument-form invocations are aspirational — current implementation always prompts via the mode picker. The agent can interpret natural-language form ("run securecoder-scan in SAST-only mode") and skip the prompt.

## Reading the report

Open `.securecoder/runs/<run-id>/report.html` in a browser.

Sections:
- **Summary** — total findings + severity breakdown + by-source breakdown
- **Trend** — vs prior run (new / resolved / persistent counts); says "First run" on first invocation
- **Phases & tools** — per-tool stats (duration, findings, status)
- **Compliance posture** — per-framework controls-evaluated / passing / with-findings / posture score (only when compliance phase ran)
- **Findings** — grouped by file, sorted critical-first; each entry shows rule, lines, CWE, framework refs, evidence excerpt, remediation hint
- **Manifest footer** — exact tool versions and rule pack SHAs used

The HTML report has interactive filters for severity / source / framework + a free-text search across file paths / titles / evidence. Use these to triage hundreds of findings quickly.

## Follow-up

After scanning:

- **To remediate findings:** `/securecoder-fix`
- **To understand a specific finding:** `/securecoder-advise` (mode: specific finding deep-dive)
- **To run the whole audit-and-fix pipeline in one go:** `/securecoder-secure`

## Common pitfalls

- **First compliance run takes ~30 seconds longer** because the OWASP/ASVS markdown needs to be cloned (~10MB).
- **Semgrep rule pack is ~100MB cached.** Don't be alarmed by the disk usage at `~/.cache/securecoder/rules/semgrep/<sha>/`. Same cache is reused across all your projects.
- **Compliance scans are expensive at default scope.** The relevance filter cuts most file × chapter pairs (typical ~30% pass the filter), but the absolute number scales with repo size. For a 1000-file repo, expect ~5000 LLM calls.
- **Re-running rewrites `latest`.** If you ran a scan you wanted to keep as a snapshot, copy the run dir somewhere safe before re-running.
- **The pre-flight estimate is a heuristic.** Actual token usage can exceed by 10–30% in practice. `/securecoder-secure` has a 50%-overrun mid-run gate; `/securecoder-scan` doesn't (it just reports actuals in the summary).

## Inspecting findings programmatically

```bash
# Count findings by severity
jq -r '.severity' .securecoder/runs/latest/findings.jsonl | sort | uniq -c

# Find all critical findings touching auth code
jq -c 'select(.severity == "critical" and (.file | contains("auth")))' \
  .securecoder/runs/latest/findings.jsonl

# Extract all framework_refs for trend analysis
jq -r '.framework_refs[] | .framework + " " + (.control // .category)' \
  .securecoder/runs/latest/findings.jsonl | sort | uniq -c
```

## See also

- [`/securecoder-fix` guide](securecoder-fix.md) — next step after scan
- [`/securecoder-secure` guide](securecoder-secure.md) — easy-button pipeline that wraps scan + fix
- [Scenarios guide](../scenarios.md) — multiple scenarios use scan as the entry point
