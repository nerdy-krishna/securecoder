# 08 — `/securecoder-fix` compliance-findings handling

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

Extends `/securecoder-fix` to handle `category: "compliance"` findings produced by slice 07. The fix loop infrastructure from slice 05 stays the same; this slice adds compliance-specific decision logic.

**Behavior changes:**

1. When `/securecoder-fix` reads a `findings.jsonl` containing compliance findings, it processes them in the same severity-multi-select pass as SAST findings.
2. **`fix_complexity` gating:** Compliance findings with `fix_complexity: "high"` OR `lines: null` are NOT auto-fixed. They're marked `manual_review_required`, logged with their `remediation_hint`, and the user sees them in the post-flight summary as "N findings need manual review — see report."
3. Compliance findings with `fix_complexity: "low"` or `"medium"` AND a defined `lines` range go through the standard per-fix loop (slice 05's flow), with one specialization: the re-scan step after applying a fix re-runs the LLM compliance pass ONLY for that file × that control (not the full chapter), to verify the finding is resolved. Reusing the slice 07 prompt template with single-control scope.
4. Per-fix commit message specialization: `fix(securecoder): <severity>/<title> [compliance asvs-v5/<control> <finding-id-short>]` to make compliance commits visually distinct from SAST commits.

**What stays the same:** pre-flight checks, backup capture, syntax check, 3-tries retry, rollback, push strategy, post-flight summary.

**Edge cases:**
- A compliance finding whose location is ambiguous ("missing CSRF middleware" — file is `__init__.py`, line is null) → `manual_review_required`
- A compliance finding whose fix would touch a file not in the original scan scope → log warning, still apply (user can re-scan after)
- Re-scan LLM call after fix fails (3 tries) → mark `applied_unverified`, leave commit in place but flag in summary

## Acceptance criteria

- [ ] `/securecoder-fix` processes compliance findings in the same multi-select severity pass as SAST findings
- [ ] Compliance findings with `fix_complexity: "high"` or `lines: null` are skipped, marked `manual_review_required`, and surfaced in post-flight summary
- [ ] Auto-fixable compliance findings go through the full per-fix loop including post-fix re-scan
- [ ] Re-scan after a compliance fix calls the LLM with single-control scope (not the full chapter), verifying just that control's resolution
- [ ] Commit messages for compliance fixes follow the documented distinct format
- [ ] Re-scan LLM failure (3 tries) marks finding `applied_unverified` with explanatory log entry; the working-tree change is left in place
- [ ] Post-flight summary distinguishes applied / applied_unverified / editor_failed / manual_review_required counts
- [ ] Tests cover: `fix_complexity` gating logic, compliance-finding canonical-ID match across before/after re-scan, commit-message format distinction, `applied_unverified` status path

## Blocked by

- 05 — `/securecoder-fix` for SAST findings (safety loop + commit-per-fix)
- 07 — `/securecoder-scan` ASVS compliance pass
