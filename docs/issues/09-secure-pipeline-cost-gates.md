# 09 — `/securecoder-secure` end-to-end pipeline + cost gates

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The easy-button skill. Wires `/securecoder-scan` and `/securecoder-fix` (already implemented) into a single straight-through pipeline with one up-front approval, per design.md §3.4 and prd.md per-skill specifics.

**Flow:**

1. Pre-flight (clean-tree + branch checks) — same as `/securecoder-fix`'s pre-flight.
2. **Whole-pipeline cost estimate.** Token-first reporting covering: SAST phase (always $0), compliance phase (estimated from relevance-filtered dispatch list × per-pair token math), fix phase (estimated from anticipated SAST findings count + anticipated compliance findings count, each × per-fix token average). Multi-model reference rate table shown. Three approval options: `proceed` / `scan-only` (exits after SAST + compliance, skipping fix) / `abort`.
3. **Run straight through, no further user prompts between phases:**
   - Phase 1: SAST scan (slice 02+03 path)
   - Phase 2: Fix pass over SAST findings using `config.default_fix_scope` (typically `critical + high`)
   - Phase 3: Compliance scan (slice 07 path)
   - Phase 4: Fix pass over compliance findings (slice 08 path; respects `fix_complexity` gating)
4. **50%-overrun mid-run gate.** After Phase 3 completes, compare actual compliance tokens to estimate. If actual ≥ 1.5× estimate, pause before Phase 4 and ask `continue` / `abort`. This is the single safety valve for blown estimates.
5. Post-flight: unified report + summary + `git diff --stat`.

The cost estimator (pure function) is the deep module to build here. Inputs: repo map + active frameworks + fix scope. Outputs: per-phase `(input_tokens, output_tokens, wall_seconds_estimate)`. The math is documented in design.md §9: `input_tokens ≈ chars / 4`, `output_tokens ≈ input × 0.30`. Calibration heuristics ship in the SKILL.md so they're tweakable without code change.

## Acceptance criteria

- [ ] `/securecoder-secure` runs the full pipeline against a sample repo and produces a final unified report covering SAST + compliance findings and applied fixes
- [ ] Pre-flight cost estimate is shown before any LLM call, token-first with multi-model reference rates
- [ ] Approval options work: `proceed` runs full pipeline; `scan-only` exits after Phase 3 with no fixes applied; `abort` exits without doing anything
- [ ] Pipeline runs phases 1–4 sequentially without prompting between them
- [ ] 50%-overrun mid-run gate triggers when actual compliance tokens ≥ 1.5× estimate; offers `continue` / `abort`
- [ ] When estimate is accurate (within ±50%), no mid-run gate fires
- [ ] Fix scope honors `config.default_fix_scope`; user can override via natural-language ask before the approval gate
- [ ] Post-flight summary distinguishes SAST findings vs compliance findings, applied vs editor_failed vs manual_review_required
- [ ] `/securecoder-secure` declares "requires `/securecoder-scan` and `/securecoder-fix` installed" in its description; install validation happens at invocation time
- [ ] Tests cover: cost estimator (input → expected token estimate within tolerance, scaling tests with repo size), pipeline orchestration (`scan-only` exit, 50% overrun trigger, normal full-pipeline path)

## Blocked by

- 05 — `/securecoder-fix` for SAST findings (safety loop + commit-per-fix)
- 07 — `/securecoder-scan` ASVS compliance pass
