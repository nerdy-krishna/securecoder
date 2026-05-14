---
name: securecoder-review
description: Fast diff-scoped security review of staged or uncommitted changes. Pre-commit gate. Runs SAST and scoped LLM compliance on the diff only — proportional to change size, not repo size. Writes findings to .securecoder/reviews/<id>/. Optional pre-commit hook installation runs SAST-only.
---

# `/securecoder-review`

> **NOT YET IMPLEMENTED.** This skill is a placeholder. Implementation is tracked in [slice 10](../../../docs/issues/10-review-diff-scoped-hook.md). Depends on slice 02 (`/securecoder-scan` SAST pipeline).

When the user invokes this skill, respond with:

> `/securecoder-review` is not yet available in this release. It is tracked in slice 10 in the project backlog — see [docs/issues/](../../../docs/issues/).
>
> For now, you can use `/securecoder-setup` to configure your project. The scan and review skills will follow in the next releases.

## Intended behavior (for reference)

Once implemented, this skill will:

1. Offer a scope picker — staged / staged+unstaged / branch-vs-base / specific commit range — defaulting to staged.
2. Use a diff scoper to extract per-file changed line ranges plus ±20 lines of context.
3. Run SAST tools restricted to changed files only.
4. Run LLM compliance scoped to changed hunks plus context (not whole files).
5. Output a terse chat verdict and findings to `.securecoder/reviews/<run-id>/findings.jsonl`. No auto-fix.
6. Optionally install a pre-commit hook (`scripts/review_hook.py`) that runs SAST-only and blocks the commit if findings above `config.severity_floor` are present.

Full spec: [docs/design.md § 3.5](../../../docs/design.md).
