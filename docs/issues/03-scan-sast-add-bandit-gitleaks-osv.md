# 03 — Add Bandit + Gitleaks + OSV-scanner to `/securecoder-scan`

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

Extends slice 02's SAST path to the full four-tool set. After this slice, "SAST only" mode covers code-pattern detection (Semgrep), Python-specific patterns (Bandit), secret detection (Gitleaks), and dependency CVEs (OSV-scanner).

Add three normalizers (Bandit JSON → findings, Gitleaks JSON → findings, OSV-scanner JSON → findings), each producing v1.0 schema findings with correct severity mapping (Bandit's H/M/L confidence + severity per the per-tool mapping table in the scan SKILL.md), correct canonical-ID derivation, and CWE enrichment where the tool emits CWE (Bandit yes; Gitleaks rarely; OSV maps via CVE→CWE).

Add the tool installers for Bandit (pipx, like Semgrep) and for Gitleaks + OSV-scanner (GitHub release-binary download matching the user's OS + arch, extracted into `~/.cache/securecoder/tools/<tool>/`, chmod +x). One-time consent already taken in slice 02; new tool installs during this slice are silent unless a version mismatch triggers reinstall.

Add tool-disable support: `config.tools.osv-scanner.enabled = false` skips the tool. Useful when the user's repo has no dep manifest.

OSV-scanner is online-API-queried (no rule fetch). It needs network access for the lookup itself — if `osv.dev` is unreachable, the scan logs the failure and continues without dep findings rather than aborting.

## Acceptance criteria

- [ ] `/securecoder-scan` SAST mode runs all four tools end-to-end on a multi-language sample repo (Python + JS + a lockfile) and produces findings from each
- [ ] Each tool's findings conform to the v1.0 schema with correct severity / confidence mapping
- [ ] Bandit findings carry CWE refs where available; OSV findings link CVE → CWE via the shipped enrichment table
- [ ] Gitleaks-detected secrets are flagged `critical` and included in the report's summary even if `severity_floor` is set to high
- [ ] Gitleaks + OSV-scanner native binaries install correctly on macOS (arm64 + x86_64) and Linux (x86_64); Windows install path is implemented (no need to verify on Windows in this slice)
- [ ] `config.tools.<tool>.enabled = false` skips the tool entirely
- [ ] OSV-scanner failure to reach `osv.dev` logs cleanly without aborting the scan; other tools still produce findings
- [ ] Tests cover: Bandit normalizer, Gitleaks normalizer, OSV-scanner normalizer (each with happy path + edge cases — empty output, malformed output, partial output)

## Blocked by

- 02 — `/securecoder-scan` SAST end-to-end with Semgrep + markdown report
