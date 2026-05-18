---
name: securecoder-setup
description: One-time team configuration wizard for securecoder. Asks 10 questions and writes `.securecoder/config.json` to the project root — overlay frameworks, severity floor, default fix scope, git push strategy, scan-output gitignore policy, language overrides, advanced source/tool pins, and framework-fit settings. Run once when a team adopts securecoder; re-run any time to change preferences.
---

# `/securecoder-setup`

You are running the `/securecoder-setup` skill. Your job is to walk the user through a 10-question wizard and write `.securecoder/config.json` to their repo root.

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

### 3. Detect primary languages (for question 6's default)

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

### Q1 — Compliance overlay frameworks (multi-select)

> The **secure-coding-essentials** baseline (memory safety, integer handling, injection, concurrency, error handling, crypto, access control) runs on every compliance scan automatically — it's universal and needs no configuration.
>
> Which *domain-specific overlay* frameworks should also run, layered on top of the baseline?

Multi-select. Options:

- **ASVS v5** — OWASP Application Security Verification Standard. Web app coverage. *(Default ON.)*
- **MASVS** — OWASP Mobile Application Security Verification Standard. *(Default OFF; will auto-enable later if `/securecoder-scan` detects a mobile stack.)*
- **Proactive Controls** — OWASP's defensive design checklist. *(Default OFF.)*
- **Cheatsheets** — OWASP CheatSheetSeries, used as remediation reference only (not scanned against). *(Default OFF.)*
- **None** — run the baseline only; no overlay frameworks.

Default when no existing config: `["asvs-v5"]`. (The baseline always runs in addition — see the closing note below.)

Tell the user: when `/securecoder-scan` runs against code an overlay doesn't fit (e.g. ASVS over a C kernel routine), the fit-check in pre-flight will warn and offer to skip the poor-fit overlay for that run. The baseline still covers the universal concerns. So picking ASVS here is safe even for a mixed codebase.

**If the user selects at least one overlay framework, display this privacy notice once before recording the answer.** Ask for explicit acknowledgment. (The baseline framework also sends code to the LLM — the notice covers it too; the baseline is bundled so there's no fetch, but the per-file LLM evaluation still applies.)

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

### Q5 — Scan-output gitignore policy

> `/securecoder-scan` writes the full list of discovered vulnerabilities to `.securecoder/runs/` (and `/securecoder-review` to `.securecoder/reviews/`). That's sensitive data — usually you don't want it pushed to a shared remote. How should the project-root `.gitignore` treat securecoder's output?

Single-select:

- `runs-and-reviews` — Recommended; default. Root `.gitignore` ignores `.securecoder/runs/` and `.securecoder/reviews/`. `config.json` and `suppressions.json` stay tracked and team-shared.
- `whole-folder` — root `.gitignore` ignores the entire `.securecoder/` directory. This *also* stops `config.json` and `suppressions.json` being shared. Files already committed under `.securecoder/` keep being tracked until you `git rm --cached` them — `/securecoder-scan` warns when it detects this.
- `none` — securecoder never touches the root `.gitignore`.

> securecoder always writes a nested `.securecoder/.gitignore` (ignoring `runs/` and `reviews/`) as a backstop regardless of this choice. This setting controls the *root* `.gitignore` — visible where developers actually look. `/securecoder-setup` only records the preference; `/securecoder-scan` applies it to the root `.gitignore` on its next run.

Default: `runs-and-reviews`.

### Q6 — Primary languages

> Auto-detected primary languages for this project: `<comma-separated list from pre-flight>`. Accept or override?

Options:

- **Accept** the detected list (Recommended)
- **Override** — user provides a comma-separated list. Accept any of the language tokens from the language map in the pre-flight section, plus `other`.

Default: accept detected.

### Q7 — Customize rule source pins (advanced)

> securecoder pins specific tags of upstream rule repositories so scans are reproducible. Override any pins for this project?

Single-select:

- **Use defaults** (Recommended)
- **Override per source** — for each source the user wants to pin differently, capture: source name (one of `semgrep-rules`, `asvs`, `masvs`, `proactive-controls`, `cheatsheets`) and the git tag or commit to pin to.

Default: use defaults. The resulting `rule_pins` field is an empty object when defaults are used.

### Q8 — Use system-installed tools instead of cached?

> By default securecoder installs Semgrep, Bandit, Gitleaks, and OSV-scanner into `~/.cache/securecoder/tools/` for reproducibility. Override any with system-installed versions?

Single-select:

- **Use cached** (Recommended)
- **Override per tool** — for each, capture: tool name (`semgrep`, `bandit`, `gitleaks`, `osv-scanner`) and absolute path to its executable.

Default: use cached. The resulting `tools` field is an empty object when cached versions are used.

### Q9 — Custom rule sources beyond the OWASP / returntocorp allowlist

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

### Q10 — Framework fit (advanced)

> When `/securecoder-scan` runs an overlay framework against code it doesn't fit (ASVS over C kernel code, etc.), a pre-flight fit-check warns you. An overlay is flagged poor-fit when fewer than this percentage of the repo's files are in the framework's target languages.

Single-select:

- **Default threshold (15%)** (Recommended)
- **Custom threshold** — capture an integer 1–100. Lower = more permissive (only warn on near-zero overlap); higher = more aggressive (warn whenever a framework isn't the dominant fit).

> The **secure-coding-essentials baseline runs on every compliance scan** and is never subject to fit-checking. Disable it only if you specifically want overlay-only coverage.

Single-select:

- **Keep the baseline on** (Recommended)
- **Disable the baseline** — `/securecoder-scan` compliance runs overlay frameworks only

Defaults: threshold 15, baseline enabled.

## Write the config

After all 10 questions are answered, write `<project-root>/.securecoder/config.json` with this exact schema. Use 2-space indentation. End with a trailing newline.

```json
{
  "schema_version": "1.1",
  "frameworks": [<overlay list from Q1>],
  "severity_floor": "<from Q2>",
  "default_fix_scope": [<list from Q3>],
  "git": {
    "push_strategy": "<from Q4>",
    "gitignore_strategy": "<from Q5>"
  },
  "languages": [<list from Q6>],
  "rule_pins": <object from Q7, {} if defaults>,
  "tools": <object from Q8, {} if cached>,
  "custom_sources": [<list from Q9, [] if none>],
  "framework_fit": {
    "poor_fit_threshold_pct": <int from Q10, default 15>
  },
  "baseline_enabled": <bool from Q10, default true>
}
```

### Schema notes

- `frameworks` lists *overlay* frameworks only. Valid tokens: `asvs-v5`, `masvs`, `proactive-controls`, `cheatsheets`. Empty list if user picked "None" — the baseline still runs.
- `baseline_enabled` — when `true` (default), `secure-coding-essentials` runs on every compliance scan regardless of `frameworks`. Set `false` only for overlay-only coverage.
- `framework_fit.poor_fit_threshold_pct` — integer 1–100; the fit-check's poor-fit cutoff.
- A `config.json` written by an older securecoder (no `framework_fit` / `baseline_enabled` keys, `schema_version: "1.0"`) is read as `baseline_enabled: true`, `poor_fit_threshold_pct: 15` — upgrading installs get the baseline automatically.
- `severity_floor` valid values: `critical`, `high`, `medium`, `low`, `info`.
- `default_fix_scope` is a subset of the severity tokens.
- `git.push_strategy` is one of `push-each`, `commit-local-push-at-end`, `commit-local-never-push`.
- `git.gitignore_strategy` is one of `runs-and-reviews`, `whole-folder`, `none`. It controls how `/securecoder-scan` reconciles the project-root `.gitignore` with its scan output. A `config.json` written before v1.3.1 has no such key — `/securecoder-scan` reads that as unset, prompts once on its next run, and persists the answer back here. `/securecoder-setup` itself only records the value; it never edits the root `.gitignore`.
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

This nested `.securecoder/.gitignore` is the always-on backstop. The **project-root `.gitignore`** is a separate, visible layer governed by `git.gitignore_strategy` (Q5) — `/securecoder-setup` does **not** edit it; `/securecoder-scan` reconciles it on its next run.

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
  Scan-output ignore: <value>   (applied to the root .gitignore on next scan)
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
