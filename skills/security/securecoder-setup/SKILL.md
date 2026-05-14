---
name: securecoder-setup
description: One-time team configuration wizard for securecoder. Asks 8 questions and writes `.securecoder/config.json` to the project root — frameworks to scan against, severity floor, default fix scope, git push strategy, language overrides, and advanced source/tool pins. Run once when a team adopts securecoder; re-run any time to change preferences.
---

# `/securecoder-setup`

You are running the `/securecoder-setup` skill. Your job is to walk the user through an 8-question wizard and write `.securecoder/config.json` to their repo root.

`/securecoder-setup` is **convenient but not required.** Other securecoder skills (`/securecoder-scan`, `/securecoder-fix`, etc.) read this file when present and fall back to documented defaults when it's missing.

## Pre-flight

### 1. Locate the project root

1. If a `.git/` directory exists in the current working directory or any ancestor, use the git toplevel (`git rev-parse --show-toplevel`).
2. Otherwise, use the current working directory.

All paths in this skill are relative to this project root.

### 2. Detect existing config

Read `<project-root>/.securecoder/config.json` if it exists.

- If present and JSON-parseable, use its field values as the **pre-selected defaults** for the questions below. In your prompts, say "current: X" or pre-select the relevant option so the user can re-run setup quickly without re-answering everything.
- If present but unparseable, copy it to `.securecoder/config.json.bak.<UTC-timestamp>`, note this in the closing summary, and use documented defaults instead.
- If absent, use the inline documented defaults.

### 3. Detect primary languages (for question 5's default)

Walk the project root to a depth of 3 directories. Skip these directories: `.git`, `node_modules`, `dist`, `build`, `__pycache__`, `.venv`, `venv`, `.tox`, `target`, `out`, `vendor`.

Count source files by extension using this map:

| Extensions | Language |
| --- | --- |
| `.py` | python |
| `.js`, `.mjs`, `.cjs` | javascript |
| `.ts`, `.tsx`, `.jsx` | typescript |
| `.go` | go |
| `.rs` | rust |
| `.java` | java |
| `.kt`, `.kts` | kotlin |
| `.rb` | ruby |
| `.php` | php |
| `.cs` | csharp |
| `.swift` | swift |
| `.c`, `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp` | cpp |

Detected primary languages = any language with **>= 5 files** AND **>= 10% of total source files**, OR whichever count first hits 10 files. Cap at the top 3 by file count.

If you find no source files (empty or non-code repo), suggest `["other"]` as the detected list and let the user override.

## The wizard

Ask one question at a time. Wait for the user's answer before moving on. Use whatever interactive prompt mechanism the host agent supports — Claude Code's `AskUserQuestion`, Cursor's inline picker, plain markdown question in chat, etc.

After each question, briefly confirm the captured answer back to the user before proceeding ("Got it — frameworks: ASVS v5.").

### Q1 — Compliance frameworks (multi-select)

> Which compliance frameworks should `/securecoder-scan` and `/securecoder-secure` check your code against?

Multi-select. Options:

- **ASVS v5** — OWASP Application Security Verification Standard. Web app coverage. *(Default ON.)*
- **MASVS** — OWASP Mobile Application Security Verification Standard. *(Default OFF; will auto-enable later if `/securecoder-scan` detects a mobile stack.)*
- **Proactive Controls** — OWASP's defensive design checklist. *(Default OFF.)*
- **Cheatsheets** — OWASP CheatSheetSeries, used as remediation reference only (not scanned against). *(Default OFF.)*
- **None** — skip compliance review entirely; SAST tools still run.

Default when no existing config: `["asvs-v5"]`.

**If the user selects at least one framework, display this privacy notice once before recording the answer.** Ask for explicit acknowledgment.

> **SECURECODER PRIVACY NOTE**
>
> Enabling a compliance framework means future `/securecoder-scan` and `/securecoder-secure` runs will send portions of your source code to whichever LLM provider your coding agent uses (Anthropic, OpenAI, Google, etc.). securecoder itself never sends source code anywhere; the framework markdown is fetched from public OWASP repos over HTTPS and contains no user code.
>
> Confirm you understand by replying "ok" or "continue".

If the user picks **None**, skip the notice.

### Q2 — Severity floor

> Findings below this severity will be recorded as informational only and won't block CI or trigger auto-fix. What's your floor?

Single-select: `critical` / `high` / `medium` / `low` / `info`.

Default: `low`.

### Q3 — Default fix scope for `/securecoder-secure`

> When you invoke `/securecoder-secure`, which severities should it auto-fix by default?

Single-select:

- `["critical"]` — most conservative
- `["critical", "high"]` — Recommended; default
- `["critical", "high", "medium"]` — broader
- `["critical", "high", "medium", "low", "info"]` — fix everything

Default: `["critical", "high"]`.

### Q4 — Git push strategy after each fix

> When `/securecoder-fix` lands a successful fix as a commit, what should happen next?

Single-select:

- `push-each` — push to your remote after every fix commit (CI workflows that gate per-commit benefit from this)
- `commit-local-push-at-end` — Recommended; accumulate commits locally, push once at end of run
- `commit-local-never-push` — commit locally only; you push manually when ready

Default: `commit-local-push-at-end`.

### Q5 — Primary languages

> Auto-detected primary languages for this project: `<comma-separated list from pre-flight>`. Accept or override?

Options:

- **Accept** the detected list (Recommended)
- **Override** — user provides a comma-separated list. Accept any of the language tokens from the language map in the pre-flight section, plus `other`.

Default: accept detected.

### Q6 — Customize rule source pins (advanced)

> securecoder pins specific tags of upstream rule repositories so scans are reproducible. Override any pins for this project?

Single-select:

- **Use defaults** (Recommended)
- **Override per source** — for each source the user wants to pin differently, capture: source name (one of `semgrep-rules`, `asvs`, `masvs`, `proactive-controls`, `cheatsheets`) and the git tag or commit to pin to.

Default: use defaults. The resulting `rule_pins` field is an empty object when defaults are used.

### Q7 — Use system-installed tools instead of cached?

> By default securecoder installs Semgrep, Bandit, Gitleaks, and OSV-scanner into `~/.cache/securecoder/tools/` for reproducibility. Override any with system-installed versions?

Single-select:

- **Use cached** (Recommended)
- **Override per tool** — for each, capture: tool name (`semgrep`, `bandit`, `gitleaks`, `osv-scanner`) and absolute path to its executable.

Default: use cached. The resulting `tools` field is an empty object when cached versions are used.

### Q8 — Custom rule sources beyond the OWASP / returntocorp allowlist

> By default securecoder only fetches rules from official OWASP repos and Semgrep's official rules repo. Want to add custom sources?

Single-select:

- **None** (Recommended)
- **Add sources** — for each, capture: a short identifier, the git repo URL, and the pinned tag or commit.

Default: none.

**If the user adds any custom source, show this warning before recording the answer.** Ask for explicit acknowledgment.

> **WARNING — Custom rule sources execute on every scan.**
>
> Rules from a malicious or compromised source can:
>
> - Send your source code to attacker-controlled endpoints (Semgrep custom Python rules execute inside Semgrep's sandbox)
> - Inject misleading findings designed to provoke bad fixes
> - Add noise that buries real findings
>
> Only add sources you trust. securecoder will additionally ask for explicit confirmation the first time it uses each custom source.
>
> Confirm by replying "ok" or "continue".

## Write the config

After all 8 questions are answered, write `<project-root>/.securecoder/config.json` with this exact schema. Use 2-space indentation. End with a trailing newline.

```json
{
  "schema_version": "1.0",
  "frameworks": [<list from Q1>],
  "severity_floor": "<from Q2>",
  "default_fix_scope": [<list from Q3>],
  "git": {
    "push_strategy": "<from Q4>"
  },
  "languages": [<list from Q5>],
  "rule_pins": <object from Q6, {} if defaults>,
  "tools": <object from Q7, {} if cached>,
  "custom_sources": [<list from Q8, [] if none>]
}
```

### Schema notes

- `frameworks` valid tokens: `asvs-v5`, `masvs`, `proactive-controls`, `cheatsheets`. Empty list if user picked "None."
- `severity_floor` valid values: `critical`, `high`, `medium`, `low`, `info`.
- `default_fix_scope` is a subset of the severity tokens.
- `git.push_strategy` is one of `push-each`, `commit-local-push-at-end`, `commit-local-never-push`.
- `languages` is a list of language tokens from the pre-flight language map, or `["other"]`.
- `rule_pins` shape: `{"<source>": "<tag-or-sha>"}`. Empty `{}` when defaults are used.
- `tools` shape: `{"<tool>": {"path": "<abs-path>"}}`. Empty `{}` when cached versions are used.
- `custom_sources` shape: `[{"id": "...", "url": "...", "pin": "..."}]`. Empty `[]` when none.

### Write `.securecoder/.gitignore` if it doesn't exist

```gitignore
# Securecoder runtime state — local and per-developer
runs/
reviews/
```

`config.json` itself is NOT gitignored — it is intentionally team-shared.

### Re-runs

If `.securecoder/config.json` already exists and the user changed any values, overwrite it. Do not preserve old fields that are no longer relevant.

If the user opens setup and accepts every default without changes, still overwrite (idempotent write); record nothing about the run in any history file.

## Closing summary

After the file is written, print this summary to chat. Substitute the actual captured values.

```
Securecoder configured.

  Project root:       <path>
  Config file:        <path>/.securecoder/config.json
  Frameworks:         <comma-separated list>
  Severity floor:     <value>
  Default fix scope:  <comma-separated list>
  Push strategy:      <value>
  Languages:          <comma-separated list>

Next steps:
  - /securecoder-scan      audit existing code
  - /securecoder-secure    full scan + fix pipeline (one approval)
  - /securecoder-build     persistent secure-build mode for active development
  - /securecoder-advise    ask grounded questions about the active frameworks
```

If the user re-ran setup and changed values, also list the diffs, only for fields that changed:

```
Changes from previous config:
  - frameworks:      ["asvs-v5"] -> ["asvs-v5", "masvs"]
  - severity_floor:  "low" -> "medium"
```

If the existing config was corrupted and you backed it up, also print:

```
Previous config was unparseable and backed up to:
  <path>/.securecoder/config.json.bak.<timestamp>
```

## Failure modes

- **Cannot write to project root** — print a clear permission error pointing at the path. Do not partially write. Exit without changing any state.
- **Existing config is unparseable** — back up to `.securecoder/config.json.bak.<UTC-timestamp>`, proceed with documented defaults, mention the backup in the closing summary.
- **User cancels mid-wizard** — preserve existing config unchanged. Do not write the new file. Print: "Setup cancelled. Existing config (if any) was not modified."

## Invariants

1. Exactly zero or one `.securecoder/config.json` exists in the project root after this skill completes.
2. After a successful run, `config.json` validates against the v1.0 schema documented in `docs/design.md` § 3.1.
3. `.securecoder/.gitignore` excludes `runs/` and `reviews/` but not `config.json`.
4. The skill makes no network calls and installs no tools — it is pure configuration writing.
