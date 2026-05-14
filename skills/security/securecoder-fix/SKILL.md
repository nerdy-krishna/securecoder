---
name: securecoder-fix
description: Apply fixes to findings from a previous /securecoder-scan run. Severity multi-select, backup-before-edit, language-agnostic syntax check, re-scan to verify, automatic rollback on failure, one git commit per successful fix. Push strategy honored from config. Supports interactive one-by-one mode and explicit restore.
---

# `/securecoder-fix`

> **NOT YET IMPLEMENTED.** This skill is a placeholder. Implementation is tracked in [slice 05](../../../docs/issues/05-fix-sast-findings-safety-loop.md) (SAST fix loop + safety + commit-per-fix), [slice 06](../../../docs/issues/06-fix-rollback-restore.md) (restore command), and [slice 08](../../../docs/issues/08-fix-compliance-findings.md) (compliance-findings handling).

When the user invokes this skill, respond with:

> `/securecoder-fix` is not yet available in this release. It is tracked in slices 05, 06, and 08 in the project backlog — see [docs/issues/](../../../docs/issues/).
>
> For now, you can use `/securecoder-setup` to configure your project. Scan and fix skills will follow in the next releases.

## Intended behavior (for reference)

Once implemented, this skill will:

1. Read `.securecoder/runs/latest/findings.jsonl` (or an explicit run ID from natural-language ask).
2. Ask the user which severities to fix (any combination, By ID, or interactive one-by-one).
3. Pre-flight: refuse to start on a dirty git tree without explicit acceptance; offer to create a `securecoder-fix/<run-id>` branch when on a protected branch; back up every file slated for edit to `.securecoder/runs/<run-id>/backups/<path>`.
4. Per-fix loop: locate target → LLM emits SEARCH/REPLACE → validate single-match → apply → language-detected syntax check (installing the checker on demand) → re-scan with the originating SAST tool → on success, one git commit; on any failure, restore from backup and mark `editor_failed`. Up to 3 LLM tries per finding.
5. Honor `config.git.push_strategy` for push semantics.
6. Compliance findings with `fix_complexity: "high"` or `lines: null` are marked `manual_review_required` and not auto-fixed.
7. Post-flight summary + `git diff --stat` + restore instructions.

Full spec: [docs/design.md § 3.3](../../../docs/design.md) and [§ 8](../../../docs/design.md).
