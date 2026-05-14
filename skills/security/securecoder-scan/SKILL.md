---
name: securecoder-scan
description: Audit a codebase for vulnerabilities and OWASP compliance issues. Runs SAST tools (Semgrep, Bandit, Gitleaks, OSV-scanner) and/or LLM-driven framework review (ASVS, MASVS, Proactive Controls). Produces a unified findings.jsonl plus markdown and HTML reports under .securecoder/runs/<id>/.
---

# `/securecoder-scan`

> **NOT YET IMPLEMENTED.** This skill is a placeholder. Implementation is tracked in [slice 02](../../../docs/issues/02-scan-sast-semgrep-markdown-report.md) (SAST with Semgrep), [slice 03](../../../docs/issues/03-scan-sast-add-bandit-gitleaks-osv.md) (multi-tool SAST), [slice 04](../../../docs/issues/04-scan-html-report-and-trend.md) (HTML report + trend), and [slice 07](../../../docs/issues/07-scan-asvs-compliance-pass.md) (ASVS compliance pass).

When the user invokes this skill, respond with:

> `/securecoder-scan` is not yet available in this release. It is tracked across slices 02, 03, 04, and 07 in the project backlog — see [docs/issues/](../../../docs/issues/).
>
> For now, you can use `/securecoder-setup` to configure your project. The scan and fix skills will follow in the next releases.

## Intended behavior (for reference)

Once implemented, this skill will:

1. Read `.securecoder/config.json` to know which frameworks are active and which tools are enabled.
2. Offer a mode picker — SAST only / LLM compliance only / Both — with token-cost warnings per option.
3. Show a deterministic pre-flight cost estimate before any LLM call; ask for approval.
4. Install missing tools into `~/.cache/securecoder/tools/` and fetch rule packs into `~/.cache/securecoder/rules/`.
5. Run the SAST tools, normalize their output into the v1.0 findings schema, enrich SAST findings with framework refs via the shipped CWE-to-framework table.
6. Optionally run the LLM compliance pass: for each (file, applicable chapter) pair, dispatch an architect-style prompt; validate the coverage matrix; emit compliance findings into the same `findings.jsonl`.
7. Write `.securecoder/runs/<run-id>/` with `findings.jsonl`, `manifest.json`, `report.md`, `report.html`, `log.md`. Maintain a `latest` symlink (or `latest.json` on Windows).

Full spec: [docs/design.md § 3.2](../../../docs/design.md).
