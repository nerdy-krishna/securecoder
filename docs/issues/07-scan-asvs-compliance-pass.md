# 07 — `/securecoder-scan` ASVS compliance pass (HITL)

- **Type:** HITL — the LLM prompt template and relevance-filter rules are high-leverage and need human review before merge
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The LLM-driven compliance path. Extends `/securecoder-scan` so the "LLM compliance only" and "Both" modes light up. Single framework (ASVS v5); MASVS / Proactive Controls / Cheatsheets land in slice 13.

After this slice, the user invokes `/securecoder-scan`, picks "Both" at the mode prompt, sees the cost estimate (token-first reporting + multi-model reference table per design.md §9), approves, and gets a unified `findings.jsonl` containing both SAST and ASVS-compliance findings, plus a per-framework compliance posture score in the report.

**Components:**
1. **Framework fetcher.** `git clone --depth 1 --branch v5.0.0 OWASP/ASVS` into `~/.cache/securecoder/rules/frameworks/asvs/v5.0.0/` (content-addressed). Allowlist allows `OWASP/*` automatically. Integrity verify on reuse. Offline-with-cache works; cold-cache-no-network fails per design.md §6.
2. **Relevance filter.** Pure function: `(file metadata, chapter applicability rules) → bool + rationale`. Shipped per-chapter applicability hints in `references/chapter-relevance.json` for ASVS V1–V17. Cuts the file × chapter dispatch list dramatically; only relevant pairs reach the LLM.
3. **Architect-style prompt template.** Per design.md §3.2 Phase B and the asvs-shell precedent at `/Users/overlord/Projects/asvs-shell/templates/architect-prompt.md`. Inputs: chapter content + line-numbered file content + repo context excerpt + chapter ID. Output: coverage matrix (every control ID has exactly one row) + JSON findings array.
4. **Coverage matrix validator.** Parses the LLM response, extracts every control ID from the chapter source via the regex on `\*\*(\d+\.\d+\.\d+)\*\*`, asserts each appears exactly once in the matrix, emits retry context with the named-missing IDs if not. One retry max; second failure marks the file/chapter `architect_incomplete` and skips fix.
5. **Compliance findings normalization.** Parse the JSON findings array; assign `category: "compliance"`, `source: "asvs-v5"`, `source_rule_id: "<control id>"`, canonical ID via `sha256(file + "asvs-v5" + control_id)`, framework_refs always populated. Merge into the run's `findings.jsonl`.
6. **Compliance posture in report.** Per framework: `(controls_evaluated, controls_passing, controls_with_findings, posture_score)`. Render in both markdown and HTML; HTML compliance-posture section is the placeholder slice 04 left.
7. **Cost gating.** Pre-flight estimate covers both phases. The user's mode choice ("Both") shows the token warning per design.md §3.2. Approval gate at the top; mid-run 50%-overrun gate is deferred to slice 09 (`/securecoder-secure`) since this slice runs scan-only.

**HITL review focus areas before merging:**
- The architect prompt's exact phrasing (asvs-shell's is a starting point but should be reviewed for portability across LLM hosts)
- The chapter-relevance JSON entries (each chapter's keyword + role list)
- The coverage-matrix retry context wording
- The compliance posture computation (counting rules across `N/A` vs `Insufficient context` vs `Fail` vs `Pass`)

## Acceptance criteria

- [ ] `/securecoder-scan` in "Both" mode runs SAST then compliance against ASVS v5 and merges findings into one `findings.jsonl`
- [ ] Compliance findings carry `category: "compliance"`, `source: "asvs-v5"`, valid `source_rule_id`, populated `framework_refs`, and stable canonical IDs
- [ ] `~/.cache/securecoder/rules/frameworks/asvs/v5.0.0/` is populated on first run; allowlist enforcement rejects fetches from non-`OWASP/*` non-`returntocorp/*` orgs without explicit confirmation
- [ ] Relevance filter cuts file × chapter dispatch by at least 60% on a typical web-app repo (i.e., not every chapter runs against every file)
- [ ] Coverage matrix validator catches LLM responses missing control rows and produces a usable retry context naming the missing IDs
- [ ] Second failure marks the pair `architect_incomplete` and skips fix without crashing the run
- [ ] Report includes per-framework compliance posture section in both markdown and HTML
- [ ] Pre-flight cost estimate shows token totals and the multi-model reference rate table
- [ ] **HITL review:** prompt template, relevance JSON, retry context wording, and posture computation are reviewed by the maintainer before merge
- [ ] Tests cover: framework fetcher (allowlist gating, integrity verify, offline modes), coverage matrix validator (complete / missing-rows / malformed responses), file relevance filter (positive / negative / unknown-language), compliance findings normalizer

## Blocked by

- 02 — `/securecoder-scan` SAST end-to-end with Semgrep + markdown report
