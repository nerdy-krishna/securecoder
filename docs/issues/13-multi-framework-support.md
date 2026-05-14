# 13 — Multi-framework support (MASVS, Proactive Controls, Cheatsheets)

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

Generalizes the slice 07 compliance path beyond ASVS-only to the full v1 framework set: MASVS (mobile-app compliance), Proactive Controls (defensive design checklist), Cheatsheets (remediation reference material).

**What's needed:**

1. **Framework registry.** A shipped reference (e.g., `references/frameworks.json`) listing each supported framework: source repo URL, pinned tag, fetch method, primary-purpose tag (web / mobile / cross / remediation-reference), control-ID extraction regex, applicability hint structure.
2. **Per-framework relevance filters.** Each framework's chapter applicability rules ship as `references/relevance-<framework>.json`. MASVS rules trigger on mobile-stack signals (iOS / Android / Kotlin / Swift / React Native); Proactive Controls have broad applicability; Cheatsheets are primarily pulled as remediation reference, not a "scan against" target.
3. **Compliance pass generalization.** The slice 07 architect-prompt template parameterizes on framework — the same flow runs for any framework whose markdown structure matches the expected chapter/control-table pattern. MASVS and ASVS have similar table-based structures; Proactive Controls has a flatter checklist; Cheatsheets is unstructured prose and is NOT used for compliance scanning (only for `/securecoder-advise` and `/securecoder-fix` remediation lookups).
4. **Posture aggregation.** Per-framework posture scores in the report (slice 04's compliance-posture section already supports multiple frameworks; this slice populates them).
5. **Auto-detection of mobile stack.** If the repo walker (slice 02) finds iOS / Android / Kotlin / Swift / RN project signals, MASVS is enabled by default in `/securecoder-setup` even if the user didn't pick it. User can still disable explicitly.
6. **Cheatsheet integration into `/securecoder-fix`.** When applying a fix, the LLM is given the relevant Cheatsheet section as additional remediation context (e.g., fixing a SQL injection pulls in `Cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.md`). This raises fix quality but doesn't change the fix flow.

## Acceptance criteria

- [ ] `references/frameworks.json` registry lists ASVS, MASVS, Proactive Controls, Cheatsheets with all required metadata
- [ ] `/securecoder-scan` compliance pass works against MASVS the same way it works against ASVS (fetcher, relevance filter, coverage matrix validator, normalizer all parameterized)
- [ ] Proactive Controls scan produces findings with `source: "proactive-controls"` and correct control IDs
- [ ] Cheatsheets do NOT appear as a scannable target in `/securecoder-scan`'s framework picker — they're only referenced from `/securecoder-fix` and `/securecoder-advise`
- [ ] Mobile-stack auto-detection adds MASVS to the active set in `/securecoder-setup` when applicable
- [ ] Report renders per-framework compliance posture for each active framework
- [ ] `/securecoder-fix` pulls relevant Cheatsheet sections into the fix-LLM prompt when available
- [ ] All four frameworks fetch from allowlisted `OWASP/*` sources; pinned tags recorded in manifest
- [ ] Tests cover: framework registry parsing, per-framework relevance filters (positive / negative cases), mobile auto-detection logic, cheatsheet lookup-by-CWE for fix context

## Blocked by

- 07 — `/securecoder-scan` ASVS compliance pass
