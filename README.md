# securecoder

An installable collection of AI-agent skills that audits, fixes, and supervises code against OWASP security frameworks. Works inside Claude Code, Cursor, Codex, Cline, Copilot, Windsurf, Gemini, and other agent hosts.

securecoder is **fully agent-driven**. No server, no daemon, no API keys. It fetches SAST tools (Semgrep, Bandit, Gitleaks, OSV-scanner) and OWASP framework markdown (ASVS, MASVS, Cheatsheets, Proactive Controls) at runtime on your machine — nothing is sent to a third party by the skill itself.

> **Status:** v1.1.0 — eight skills functional. v1.1.0 adds `/securecoder-suppress` for marking false positives, plus cluster-based bulk suppression in the HTML report and tighter `/securecoder-fix` + `/securecoder-review` integration.

## Quickstart

Install once:

```bash
npx skills@latest add nerdy-krishna/securecoder
```

The skills.sh installer detects every coding agent on your machine and offers to install securecoder into each one. Pick the ones you use.

Then from any project:

```text
/securecoder-setup       # one-time team config (3 minutes)
/securecoder-scan        # audit your code
/securecoder-fix         # remediate findings
```

That's the minimum path. The other four skills add specific value — see [§ The seven skills](#the-seven-skills) below.

## How the skills chain together

```
                       ┌─────────────────────┐
                       │  /securecoder-setup │   one-time config
                       └──────────┬──────────┘
                                  │ writes .securecoder/config.json
                                  ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                                                                 │
   │  Auditing existing code                                         │
   │  ─────────────────────                                          │
   │   /securecoder-scan  →  /securecoder-fix  →  /securecoder-scan  │
   │      (audit)              (remediate)         (verify)          │
   │                                                                 │
   │      OR the easy-button equivalent:                             │
   │   /securecoder-secure   (does all the above in one approval)    │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────────────────────────┐
   │                                                                 │
   │  In-flight work / new projects                                  │
   │  ─────────────────────────────                                  │
   │   /securecoder-build  ─→ (you work with the agent, supervised)  │
   │   /securecoder-review ←─    pre-commit gate on each change set  │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────────────────────────┐
   │                                                                 │
   │  Q&A and learning                                               │
   │  ───────────────                                                │
   │   /securecoder-advise   any time, grounded in framework docs    │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘
```

## The eight skills

| Skill | One-line purpose | When to invoke it | Follow up with |
| --- | --- | --- | --- |
| `/securecoder-setup` | Configure frameworks, severity floor, fix scope, push strategy. | Once when adopting securecoder, or when team preferences change. | `/securecoder-scan` |
| `/securecoder-scan` | Audit your code — SAST (Semgrep, Bandit, Gitleaks, OSV) and/or ASVS/MASVS LLM compliance. | When you want to know what's wrong before changing anything. | `/securecoder-fix` |
| `/securecoder-fix` | Apply fixes to a previous scan's findings, with full safety loop. | After `/securecoder-scan`, to remediate. | `/securecoder-scan` (verify) |
| `/securecoder-secure` | Easy-button pipeline: scan → fix → compliance scan → fix → report, one approval. | When you don't want to choose between scan modes — let the pipeline do the right thing. | `/securecoder-review` (next commit) |
| `/securecoder-review` | Diff-scoped review of staged or branch changes. Pre-commit gate. | Right before you commit / push. | `/securecoder-fix` (if findings) |
| `/securecoder-build` | Activate persistent ASVS supervision for the rest of the chat session. | When starting new feature work or a fresh project. | `/securecoder-review` (each substantive change) |
| `/securecoder-advise` | Q&A grounded in cached framework markdown. Verbatim citations. | When you don't understand a finding, want to look up a control, or are weighing a design choice. | (no specific follow-up — read and learn) |
| `/securecoder-suppress` | Mark findings as false positives. Team-shared via `.securecoder/suppressions.json`. | When a finding is wrong or expected. Also via the HTML report's per-finding/cluster Suppress UI. | `/securecoder-scan` (re-run for effect) |

### Example invocations

```text
# First-time setup
/securecoder-setup

# Audit a Python repo for SAST + ASVS compliance
/securecoder-scan
# At the mode prompt: "Both"

# Apply fixes to the latest scan, critical and high severity only
/securecoder-fix
# At the scope prompt: "Critical + High"

# Specific run by id (e.g., to redo a previous fix)
/securecoder-fix run 20260514T140000Z

# Roll back the last fix run
/securecoder-fix --restore 20260514T143000Z
# or natural language:  "undo my last sccap-fix"

# Easy button — entire pipeline, one approval
/securecoder-secure

# Pre-commit review of staged changes only
/securecoder-review

# Pre-PR review of your feature branch vs main
/securecoder-review
# At the scope prompt: "Branch vs base"

# Install the SAST-only pre-commit hook
/securecoder-review
# At the scope prompt: "Install pre-commit hook"

# Activate secure-build mode for the rest of this session
/securecoder-build

# Ask a security question
/securecoder-advise "How do I prevent SSRF in this codebase?"

# Look up a specific ASVS control
/securecoder-advise "Explain ASVS V1.2.1"

# Deep-dive on a specific finding from your last scan
/securecoder-advise
# At the mode prompt: "Specific finding deep-dive"
# Then provide the finding ID prefix
```

Detailed per-skill guides live at [`docs/guides/per-skill/`](docs/guides/per-skill/).

## Common scenarios

| Scenario | Recommended sequence |
| --- | --- |
| **I just inherited a codebase** | `/securecoder-setup` → `/securecoder-secure` → review the `report.html` |
| **Starting a new project** | `/securecoder-setup` → `/securecoder-build` (then code with the agent) → `/securecoder-review` before each commit |
| **About to open a PR** | `/securecoder-review` (scope: branch vs base) → `/securecoder-fix` if findings |
| **Casual learning** | `/securecoder-advise "<question>"` — no setup required if you've run a scan once to populate the framework cache |
| **Compliance audit deliverable** | `/securecoder-scan` (mode: LLM compliance only) → share the `report.html` and the compliance-posture section |
| **A finding looks wrong** | `/securecoder-advise` (mode: specific finding deep-dive) — see the verbatim ASVS text + why securecoder flagged it |
| **Rolling back a bad fix** | `/securecoder-fix --restore <run-id>` |

Full scenario walkthroughs: [`docs/guides/scenarios.md`](docs/guides/scenarios.md).

## What gets installed where

```
<your project>/
└── .securecoder/
    ├── config.json        team-shared (checked in)
    ├── .gitignore         (auto-generated)
    ├── runs/<id>/         scan / fix runs (gitignored)
    └── reviews/<id>/      diff-scoped reviews (gitignored)

<your home cache>/         (~/.cache/securecoder/ on Linux, ~/Library/Caches/securecoder/ on macOS, %LOCALAPPDATA%\securecoder\ on Windows)
├── tools/
│   ├── semgrep/           pipped into a private venv
│   ├── bandit/            ditto
│   ├── gitleaks/          GitHub release binary
│   └── osv-scanner/       GitHub release binary
└── rules/
    ├── semgrep/<sha>/     returntocorp/semgrep-rules cloned, content-addressed
    └── frameworks/
        ├── asvs/<sha>/    OWASP/ASVS cloned, content-addressed
        ├── masvs/<sha>/
        └── proactive-controls/<sha>/
```

The skill **never modifies anything outside `<your project>/.securecoder/` and `<your home cache>/securecoder/`** unless you explicitly run `/securecoder-fix` (or `/securecoder-secure`) which writes to your source files. Even then, every modified file is backed up first.

## Privacy

securecoder itself **never sends source code anywhere**. It performs these network operations:

- `git clone` over HTTPS against the official OWASP and Semgrep rule repos (and any explicit custom sources)
- HTTPS POST to `api.osv.dev` with dependency package names + versions (no source code)
- HTTPS download of Gitleaks and OSV-scanner release binaries from GitHub
- `git push` only if your configured push strategy says to, and only to your own remote

**LLM calls send source code to whichever model provider your coding agent uses** — Anthropic, OpenAI, Google, etc. This is your existing relationship with that provider; securecoder doesn't introduce a new vendor. The compliance-scan, fix, build, and review skills inherently include source in prompts.

You can run securecoder fully offline once tools and rule packs are cached.

## How it relates to SCCAP

This project distills the OWASP-driven scan/fix workflow from the [SCCAP platform](https://github.com/nerdy-krishna/ai-secure-coding-compliance-platform) into a portable, server-less skill bundle. SCCAP remains the heavyweight server-side answer (FastAPI, multi-agent LangGraph, Postgres, RabbitMQ, dashboards, multi-user). securecoder is the lightweight agent-resident answer for individual developers and small teams who want the same audit-first discipline without standing up infrastructure.

The two projects share design intent but have **no runtime dependency on each other**.

## Design and contributing

- [`docs/design.md`](docs/design.md) — every architectural decision, schema, and protocol
- [`docs/prd.md`](docs/prd.md) — user-story-driven requirements
- [`docs/issues/`](docs/issues/) — 14 implementation slices, dependency-ordered
- [`docs/guides/`](docs/guides/) — usage walkthroughs and per-skill deep dives
- [`docs/roadmap.md`](docs/roadmap.md) — what's planned for v1.2.0 and beyond
- [`CHANGELOG.md`](CHANGELOG.md) — full release history from v0.1.0 onwards

Contributions welcome. The simplest path:

1. Pick a slice from `docs/issues/` that lists outstanding test work, or open a discussion for a new feature.
2. Open a PR with the implementation + tests if applicable.
3. The two HITL-tagged slices (07 ASVS prompt, 11 build-mode policy) need maintainer review of their literal text since it directly shapes agent behavior.

## License

[MIT](LICENSE).
