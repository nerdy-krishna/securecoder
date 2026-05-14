# 12 — `/securecoder-advise` grounded Q&A + search helper

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The Q&A skill. Read-only — never modifies code. Grounded in the cached framework markdown (fetched in slice 07) and optionally in the latest scan's findings (produced by slices 02, 03, 07).

Spec is in design.md §3.7 and prd.md per-skill specifics.

**Invocation:** `/securecoder-advise <question>` (with arg) or `/securecoder-advise` (skill asks for a question).

**Context loading on first turn:**

1. Read `.securecoder/config.json` to know active frameworks
2. Read framework markdown from `~/.cache/securecoder/rules/frameworks/<framework>/<version>/`
3. If `.securecoder/runs/latest/findings.jsonl` exists, read it
4. Print the list of loaded context surfaces once at the top of the response (e.g., "Loaded: ASVS v5.0.0 from `~/.cache/securecoder/rules/frameworks/asvs/v5.0.0/`; 47 findings from run 20260513T140000Z")

**Mode picker (only when invoked without a question):**

- General security Q&A (frameworks only, no repo context)
- Findings-grounded Q&A (uses last scan)
- Specific finding deep-dive (user picks an ID; skill returns framework refs + remediation + cheatsheet pointers)
- Framework lookup (e.g., "explain ASVS V1.2.1" → verbatim quote + plain-language interpretation)

**Response format (always):**

- Quote framework text verbatim before interpreting (no paraphrase-as-citation)
- Cite by control ID + version: `ASVS v5.0.0 V1.2.1`
- When grounding in user findings, cite by finding ID + file:line
- Suggest related controls / cheatsheets at the end of each answer

**Search helper** — `scripts/search_rules.py` ships with the skill. Keyword/concept search across cached framework markdown. Returns top-N matching sections with control IDs. Agent invokes internally when answering broad questions; user can invoke directly ("search the ASVS for SSRF" / "find cheatsheet sections about XSS").

Multi-turn continuation uses the host agent's normal context retention — no special mechanism. Skill prints a closing line: "Framework references are loaded into context. Ask follow-ups freely."

## Acceptance criteria

- [ ] `/securecoder-advise "how do I prevent SSRF?"` returns an answer with verbatim ASVS quote(s), control IDs, and remediation guidance
- [ ] `/securecoder-advise` (no arg) presents the 4-mode picker and routes correctly
- [ ] Specific finding deep-dive mode accepts a finding ID and returns framework refs + remediation hint + related cheatsheet pointers
- [ ] Framework lookup mode produces verbatim control text followed by plain-language interpretation
- [ ] Loaded-context summary appears at the top of the first response
- [ ] Every answer quotes framework text verbatim before interpreting
- [ ] Citations include control ID + framework version
- [ ] Findings-grounded answers reference finding ID + file:line
- [ ] Search helper (`scripts/search_rules.py`) runs against cached framework markdown and returns ranked top-N matches with control IDs
- [ ] User-invoked search ("search the ASVS for SSRF") works via natural-language ask
- [ ] Skill never modifies code — verified by the post-invocation working-tree comparison
- [ ] Tests cover: search helper (keyword match, ranking, top-N cutoff), context-loader (graceful handling of missing config, missing latest run, missing framework cache), citation-format assertions

## Blocked by

- 07 — `/securecoder-scan` ASVS compliance pass (provides the cached framework markdown the skill grounds on)
