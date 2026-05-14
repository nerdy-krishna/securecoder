# `/securecoder-setup` — usage guide

## What this skill does

Walks you through an 8-question wizard and writes `.securecoder/config.json` to your project root. Every other securecoder skill reads this file at runtime. If the file doesn't exist, those skills run with sensible defaults and remind you to invoke `/securecoder-setup`.

## When to invoke it

- **Once** when adopting securecoder on a new project
- **Re-run** any time your team's preferences change (frameworks, severity floor, fix scope, push strategy)
- **Re-run** when onboarding a new language to the codebase (so the language detection updates)

## How to invoke

```
/securecoder-setup
```

That's it — no arguments. The wizard runs unconditionally.

Re-running on an existing config pre-selects your current values as defaults, so you can fast-skip through unchanged questions and only adjust what you came to change.

## The 8 questions

| # | Question | Default | Notes |
| - | --- | --- | --- |
| 1 | Compliance frameworks (multi-select) | `["asvs-v5"]` | When you enable any framework, the skill displays a one-time privacy notice about LLM data egress. Acknowledge once. |
| 2 | Severity floor | `low` | Findings below this level are recorded as `info` and never block. Useful for very noisy repos. |
| 3 | Default fix scope for `/securecoder-secure` | `["critical", "high"]` | The easy-button pipeline uses this. `/securecoder-fix` asks each invocation regardless. |
| 4 | Git push strategy | `commit-local-push-at-end` | Other options: `push-each` (push after every fix commit), `commit-local-never-push` (manual push). |
| 5 | Primary languages | auto-detected | Accept or override. Used for SAST rule pack selection. |
| 6 | Customize rule source pins | use defaults | Advanced. Lets you pin specific tags for any rule source. |
| 7 | Use system-installed tools | use cached | Advanced. Lets you point at a system `semgrep` instead of the cached one. |
| 8 | Custom rule sources | none | Advanced. Adds Semgrep/etc. sources beyond the OWASP / returntocorp allowlist; one-time confirmation gate per source. |

## What it produces

```
<project-root>/.securecoder/
├── config.json     team-shared; CHECKED IN
└── .gitignore      auto-generated; ignores runs/ and reviews/
```

`config.json` schema is documented in [`docs/design.md` § 3.1](../../design.md).

## Follow-up

Now that the project is configured, run:

```
/securecoder-scan        # to audit existing code
```

or

```
/securecoder-build       # if starting fresh — activates supervision mode
```

## Common pitfalls

- **Re-running drops un-recognized fields.** If a future schema version adds fields and you re-run an older skill, those new fields get dropped. Always re-run setup with the latest skill version.
- **`config.json` is intentionally checked in.** Your `.gitignore` shouldn't ignore it. The auto-generated `.securecoder/.gitignore` correctly excludes only the per-developer state (`runs/`, `reviews/`).
- **The privacy notice only fires when you ENABLE a framework.** If you re-run setup and leave frameworks unchanged, you won't see it again.
- **The wizard does not install tools.** Tools install on the first `/securecoder-scan` invocation (with a one-time consent gate of their own).

## Inspecting output

```bash
cat .securecoder/config.json
```

Output looks like:

```json
{
  "schema_version": "1.0",
  "frameworks": ["asvs-v5"],
  "severity_floor": "low",
  "default_fix_scope": ["critical", "high"],
  "git": { "push_strategy": "commit-local-push-at-end" },
  "languages": ["python", "typescript"],
  "rule_pins": {},
  "tools": {},
  "custom_sources": []
}
```

## See also

- [`/securecoder-scan` guide](securecoder-scan.md) — first thing to run after setup
- [Scenarios guide](../scenarios.md) — Scenario 1 ("inherited codebase") starts here
