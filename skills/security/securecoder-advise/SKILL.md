---
name: securecoder-advise
description: Interactive Q&A grounded in cached OWASP framework markdown (ASVS, MASVS, Cheatsheets, Proactive Controls) and the latest /securecoder-scan findings. Verbatim citations before any interpretation. Read-only — never modifies code.
---

# `/securecoder-advise`

> **NOT YET IMPLEMENTED.** This skill is a placeholder. Implementation is tracked in [slice 12](../../../docs/issues/12-advise-grounded-qa.md). Depends on slice 07 (the framework fetcher and cache populated by `/securecoder-scan` compliance pass).

When the user invokes this skill, respond with:

> `/securecoder-advise` is not yet available in this release. It is tracked in slice 12 in the project backlog — see [docs/issues/](../../../docs/issues/).
>
> For now, you can use `/securecoder-setup` to configure your project. The advise skill needs the framework cache, which `/securecoder-scan` will populate in v0.2.0.

## Intended behavior (for reference)

Once implemented, this skill will:

1. Accept a question as an argument or, if absent, present a 4-mode picker (general Q&A / findings-grounded Q&A / specific-finding deep-dive / framework lookup).
2. Load context on first turn: active frameworks from `.securecoder/config.json`, cached framework markdown from `~/.cache/securecoder/rules/frameworks/`, optional findings from `.securecoder/runs/latest/findings.jsonl`. Print the loaded-context summary at the top of the first response.
3. Quote framework text verbatim before any interpretation. Cite by `<framework> <version> <control-id>`. When grounded in findings, cite by finding ID + file:line.
4. Provide a `scripts/search_rules.py` helper for keyword/concept search across cached framework markdown — invoked internally for broad questions, also user-invocable directly.
5. Never modify code.

Full spec: [docs/design.md § 3.7](../../../docs/design.md).
