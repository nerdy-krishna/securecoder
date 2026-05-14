# `/securecoder-secure` — usage guide

## What this skill does

The easy-button skill. Runs the entire audit-and-remediate pipeline in 4 phases with one up-front cost approval and a 50%-overrun mid-run gate. Equivalent to running `/securecoder-scan` → `/securecoder-fix` → `/securecoder-scan` (compliance) → `/securecoder-fix` (compliance) in sequence, but with no per-phase prompts and a unified summary.

## When to invoke it

- **You don't want to choose between scan modes.** Let the pipeline do the right thing.
- **You want to audit + remediate a codebase you inherited.** This is the canonical one-command answer.
- **You want a quarterly security sweep.** Run `/securecoder-secure` once; the report tells you what changed since last quarter.

## When NOT to invoke it

- **You're tweaking one file.** Use `/securecoder-review` for diff-scoped feedback instead — cheaper and faster.
- **You want maximum control.** Use the individual skills (`/securecoder-scan` + `/securecoder-fix`) to handle each phase's decisions explicitly.
- **You're new to securecoder.** Read the report from a manual `/securecoder-scan` first to know what to expect.

## How to invoke

```
/securecoder-secure
```

No arguments. The skill walks the same flow regardless of where you call it from. Recovery from failures during the run is supported via the individual fix run's `--restore`.

## The 4 phases

```
Pre-flight  →  Approval gate  →  [1] SAST scan  →  [2] SAST fix
                                                          │
                                                          ▼
                                  [3] Compliance scan  →  50%-overrun gate (if triggered)
                                                          │
                                                          ▼
                                                    [4] Compliance fix  →  Post-flight
```

**Phase 1 — SAST scan** invokes the full `/securecoder-scan` SAST flow (Semgrep + Bandit + Gitleaks + OSV-scanner). Free in LLM tokens.

**Phase 2 — SAST fix** runs `/securecoder-fix` non-interactively against Phase 1's findings, using `config.default_fix_scope` (typically critical + high). Each successful fix is a git commit; same safety loop as standalone `/securecoder-fix`.

**Phase 3 — Compliance scan** invokes the LLM compliance pass against the now-patched code. Cost-heavy.

**50%-overrun mid-run gate** — after Phase 3 completes, the skill compares actual token usage to the pre-flight estimate. If actual ≥ 1.5× estimated, it pauses and asks:

> Phase 3 used `<actual>` tokens vs estimate of `<estimated>` — a `<ratio>x` overrun. Phase 4 may be similarly off.
>
> Continue to fix phase?
>   [continue]   Proceed with Phase 4 anyway.
>   [abort]      Stop here; Phase 3 findings are in the unified report; no compliance fixes applied.

This is your one safety bail. If your estimate was wildly wrong, you can cut your losses here.

**Phase 4 — Compliance fix** runs `/securecoder-fix` against Phase 3's findings.

## Approval gate (the one approval)

The pre-flight estimate shows token totals across all 4 phases plus reference dollar costs at common model rates:

```
/securecoder-secure pipeline estimate:

Repo:
  Files in scope:           142
  Lines of code:            38,910
  Compliance pairs:         487

Phases:
  [1] SAST scan:            ~30s, $0
  [2] SAST fix:             ~14 findings, ~70k tokens
  [3] Compliance scan:      ~487 LLM calls, ~9.7M in / ~2.4M out tokens
  [4] Compliance fix:       ~150 fix calls, ~600k tokens

Total LLM tokens (estimated):
  Input:   ~10.4M
  Output:  ~3.0M

Approximate cost at common rates:
  Claude Opus 4.7:    $381.20
  Claude Sonnet 4.6:  $ 76.30
  Claude Haiku 4.5:   $ 25.40

Estimated wall time (sequential): ~4.5 hours

Continue?
  [proceed]    Run the full pipeline.
  [scan-only]  Run Phases 1 and 3 only (no fixes applied).
  [abort]      Exit without doing anything.
```

Options:

- **`proceed`** — full pipeline. Pre-flight (clean tree / branch / approval) → straight through. The mid-run gate is your one bail point.
- **`scan-only`** — Phases 1 and 3 only. No code modifications. Useful for compliance audits where you want findings without auto-remediation.
- **`abort`** — exits cleanly.

## What it produces

```
.securecoder/runs/<pipeline-run-id>/
└── manifest.json        unified pipeline manifest referencing every sub-run

.securecoder/runs/<sast-scan-run-id>/        from Phase 1
.securecoder/runs/<sast-fix-run-id>/         from Phase 2 (skipped in scan-only)
.securecoder/runs/<compliance-scan-run-id>/  from Phase 3
.securecoder/runs/<compliance-fix-run-id>/   from Phase 4 (skipped in scan-only)
```

Each phase writes its own run dir. The pipeline manifest references every sub-run id, so each phase's full output is inspectable independently.

Plus git commits on your working branch — one per successful fix from Phases 2 and 4.

## Follow-up

- **Verify the diff:** `git diff --stat`. Look for unexpected changes.
- **Open the report:** `.securecoder/runs/<compliance-scan-run-id>/report.html` is usually the most informative (it has compliance posture + all findings).
- **Roll back if something broke:** restore each fix phase separately:
  - `/securecoder-fix --restore <compliance-fix-run-id>`
  - `/securecoder-fix --restore <sast-fix-run-id>`
  - Run them in reverse order.
- **Install the pre-commit hook for ongoing protection:** `/securecoder-review` → install hook.

## Common pitfalls

- **Cost estimate can be off.** The compliance phase heuristic assumes ~30% of file × chapter pairs produce a fail, which varies wildly by codebase. The 50%-overrun gate is the safety net; don't rely on the pre-flight number being exact.
- **Sequential phases means slow wall time.** A medium-large codebase can take 4+ hours of mostly LLM latency. Run it overnight, or pick scan-only and remediate manually.
- **Auto-fix scope can be aggressive.** `config.default_fix_scope` defaults to critical + high. If your team only wants critical-only fixes by default, change that in `/securecoder-setup`.
- **`scan-only` mode still does the clean-tree check.** Even though no fixes will be applied, the skill still verifies your tree is clean — it's a safety check, not a fix prerequisite.
- **You can't easily resume after the mid-run gate aborts.** The compliance findings from Phase 3 are still in `.securecoder/runs/<compliance-scan-run-id>/`. To apply them later, invoke `/securecoder-fix from run <compliance-scan-run-id>` explicitly.
- **Both fix phases are individually `--restore`-able.** You don't have to undo both at once.

## See also

- [`/securecoder-scan` guide](securecoder-scan.md) — what each scan phase does internally
- [`/securecoder-fix` guide](securecoder-fix.md) — what each fix phase does internally
- [Scenarios guide](../scenarios.md) — Scenario 1 uses /securecoder-secure as the inherited-codebase fast path
