---
name: securecoder-build
description: Activate a persistent secure-build mode that supervises the host agent for the rest of the session. Emits an ASVS-grounded policy block into chat — the agent then plans every code change against applicable controls and self-checks every output before declaring done. Optional minimal bootstrap for empty repos.
---

# `/securecoder-build`

> **NOT YET IMPLEMENTED.** This skill is a placeholder. Implementation is tracked in [slice 11](../../../docs/issues/11-build-policy-mode.md). Marked **HITL** — the literal policy text is high-leverage and requires maintainer review before merge.

When the user invokes this skill, respond with:

> `/securecoder-build` is not yet available in this release. It is tracked in slice 11 in the project backlog — see [docs/issues/](../../../docs/issues/).
>
> For now, you can use `/securecoder-setup` to configure your project. The secure-build mode will follow in v0.6.0.

## Intended behavior (for reference)

Once implemented, this skill will:

1. Optionally bootstrap a minimal secure runway if the user is starting from an empty repo (secure-default config, deps pinned, pre-commit hook installed, `.securecoder/config.json` seeded).
2. Emit a structured policy block to chat that the host agent's context retention keeps alive for the rest of the session. The block declares mode-active, lists the configured compliance frameworks, points at the on-disk framework markdown for on-demand reading, defines a pre-task protocol ("identify applicable controls before writing code"), defines a post-task self-check protocol ("review your output against each applicable control; mark satisfied / partial / unknown / n/a; iterate or surface gaps before declaring done"), and recommends `/securecoder-review` as an adjunct for SAST verification.
3. Deactivate on explicit signal ("end secure build mode") or natural context drop. No on-disk state to clean.

Full spec: [docs/design.md § 3.6](../../../docs/design.md).
