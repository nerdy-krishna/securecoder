---
name: securecoder-secure
description: Easy-button end-to-end secure pipeline. Runs SAST scan then auto-fix then LLM compliance scan then auto-fix then report — all with one up-front cost approval. Requires /securecoder-scan and /securecoder-fix installed. Includes a 50% token-overrun mid-run gate so blown estimates don't run away.
---

# `/securecoder-secure`

> **NOT YET IMPLEMENTED.** This skill is a placeholder. Implementation is tracked in [slice 09](../../../docs/issues/09-secure-pipeline-cost-gates.md). Depends on slices 05 (`/securecoder-fix`) and 07 (`/securecoder-scan` compliance pass).

When the user invokes this skill, respond with:

> `/securecoder-secure` is not yet available in this release. It is tracked in slice 09 in the project backlog — see [docs/issues/](../../../docs/issues/).
>
> This skill bundles `/securecoder-scan` and `/securecoder-fix` (which also land in later releases). For now, you can use `/securecoder-setup` to configure your project.

## Intended behavior (for reference)

Once implemented, this skill will:

1. Pre-flight (clean tree + branch checks).
2. Show a token-first cost estimate covering the entire pipeline (SAST + compliance + fix passes) with a multi-model reference rate table. Approval options: `proceed` / `scan-only` (skip fix phase) / `abort`.
3. Run straight through without further prompts: SAST → fix → compliance → fix → unified report.
4. 50% overrun gate after the compliance phase: if actual tokens exceed estimate by ≥1.5×, pause before fix phase and ask `continue` / `abort`.
5. Fix scope defaults to `config.default_fix_scope` (typically `["critical", "high"]`).
6. Post-flight summary + `git diff --stat`.

Full spec: [docs/design.md § 3.4](../../../docs/design.md) and [§ 9](../../../docs/design.md).
