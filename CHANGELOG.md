# Changelog

All notable changes to securecoder ship here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [Unreleased]

## [0.2.0] — 2026-05-14

`/securecoder-scan` becomes functional for the Semgrep SAST path. Establishes every cross-cutting mechanism the rest of the skill bundle relies on: tool installation with one-time consent, content-addressed rule cache, repo walker with language detection, SAST findings normalization, CWE-to-framework enrichment, run directory management, and markdown report rendering.

### Added
- `/securecoder-scan` SAST mode (Semgrep only). Mode picker prompts for SAST-only / LLM-compliance-only / Both; the last two are gracefully not-yet-implemented stubs.
- Helper scripts under `skills/security/securecoder-scan/scripts/`:
  - `repo_walker.py` — walks the project tree, prunes vendored / generated / hidden dirs, detects language per file by extension, emits a JSON inventory.
  - `normalize_semgrep.py` — parses Semgrep `--json` output into the v1.0 findings schema. Computes canonical IDs (`sha256(file|line_start|rule_id)`), maps severity with rule-id heuristics, enriches with framework refs.
  - `render_markdown.py` — renders `findings.jsonl` + `manifest.json` as a markdown report. Sections: summary, severity breakdown, phases, findings grouped by file, manifest footer. Compliance posture and trend sections are placeholders for slices 04 and 07.
- Curated `references/cwe-to-framework.json` covering 39 CWE → framework-ref mappings. Each entry links to relevant ASVS v5 controls and OWASP Top 10 2021 categories.
- Run directory layout under `.securecoder/runs/<run-id>/` containing `findings.jsonl`, `manifest.json`, `report.md`, `repo_map.json`, `log.md`, and raw Semgrep output for debugging.
- `latest` pointer (symlink on POSIX; `latest.json` fallback for Windows) so downstream skills like `/securecoder-fix` can find the most recent run without arg parsing.

### Pinned upstream versions
- Semgrep tool: `1.91.0`. Installed into `~/.cache/securecoder/tools/semgrep/venv/` via `python3 -m venv` + `pip install`; no pipx required.
- `returntocorp/semgrep-rules`: branch `main`, content-addressed by the resulting commit SHA recorded in `~/.cache/securecoder/rules/semgrep/<sha>/manifest.json`. Per-language rule subdirs are selected by the walker's detected languages.

### Compatibility
- Host agents: any reading SKILL.md markdown; instructions use plain English flow plus explicit bash commands, no host-specific primitives.
- OS: macOS, Linux. Windows path handling implemented but not yet validated end-to-end.
- Python: 3.9+. Helper scripts use `from __future__ import annotations` so PEP 604 syntax is parse-only.

### Tests
- Deferred to a separate slice. The acceptance criteria for unit tests in `docs/issues/02-scan-sast-semgrep-markdown-report.md` remain open and will be added in a follow-up commit. Manual smoke-testing of all three helper scripts validated the pipeline end-to-end with synthetic Semgrep output before this release.

## [0.1.0] — 2026-05-14

The foundation release. Establishes the repo as a skills.sh-installable agent skill collection.

### Added
- `.claude-plugin/plugin.json` listing all seven skills.
- `/securecoder-setup` — full 8-question configuration wizard. Writes `.securecoder/config.json` to the user's project root; surfaces a privacy notice when a compliance framework is selected; pre-selects existing values when re-run.
- Stub `SKILL.md` for the six skills landing in later slices: `/securecoder-scan`, `/securecoder-fix`, `/securecoder-secure`, `/securecoder-review`, `/securecoder-build`, `/securecoder-advise`. Each stub describes the intended behavior, links to its tracking issue, and tells the host agent the skill is not yet implemented.
- README with quickstart, privacy section, and pointers to the design document, PRD, and issue backlog.
- MIT license.

### Pinned upstream versions
- None — first release ships only the configuration surface. Tool and rule pack pins land in 0.2.0 alongside `/securecoder-scan`.

### Compatibility
- Host agents: any reading `SKILL.md` markdown. Validated against Claude Code in this release; broader host coverage tracked as a v0.x stability item.
- OS: macOS, Linux. Windows path handling implemented but not yet validated end-to-end.
- Python: 3.9+ for helper scripts (`/securecoder-setup` is pure SKILL.md and needs no Python).

[Unreleased]: https://github.com/nerdy-krishna/securecoder/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.2.0
[0.1.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.1.0
