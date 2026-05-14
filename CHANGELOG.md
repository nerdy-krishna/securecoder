# Changelog

All notable changes to securecoder ship here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/nerdy-krishna/securecoder/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nerdy-krishna/securecoder/releases/tag/v0.1.0
