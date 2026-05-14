# securecoder

An installable collection of AI-agent skills that audits, fixes, and supervises code against OWASP security frameworks. Works inside Claude Code, Cursor, Codex, Cline, Copilot, Windsurf, Gemini, and other agent hosts.

securecoder is **fully agent-driven**. No server, no daemon, no API keys. It fetches SAST tools (Semgrep, Bandit, Gitleaks, OSV-scanner) and OWASP framework markdown (ASVS, MASVS, Cheatsheets, Proactive Controls) at runtime on your machine — nothing is sent to a third party by the skill itself.

> **Status:** v0.1.0 — `/securecoder-setup` is functional today. The other six skills ship slice-by-slice. See [docs/issues/](docs/issues/) for the implementation backlog.

## Quickstart

```bash
npx skills@latest add nerdy-krishna/securecoder
```

The skills.sh installer will detect every coding agent on your machine and offer to install securecoder into each one. Pick the ones you use.

Then, from any project you want to secure:

```
/securecoder-setup
```

Walk through the 8-question wizard. You're done — securecoder's other skills now have a configuration to read.

A "first scan in 5 minutes" walkthrough lands once `/securecoder-scan` ships in v0.2.0.

## The seven skills

| Slash command | Purpose | Status |
| --- | --- | --- |
| `/securecoder-setup` | One-time team configuration. Writes `.securecoder/config.json`. | **Shipping in v0.1.0.** |
| `/securecoder-scan` | Audit existing code with SAST tools and/or LLM-driven compliance review. | v0.2.0 (slice 02–03) |
| `/securecoder-fix` | Remediate findings safely — backup, syntax check, commit-per-fix. | v0.3.0 (slice 05) |
| `/securecoder-secure` | Easy-button end-to-end pipeline. One approval, runs scan→fix→compliance→fix straight through. | v0.4.0 (slice 09) |
| `/securecoder-review` | Diff-scoped pre-commit gate. Fast SAST + scoped LLM compliance on staged changes. | v0.5.0 (slice 10) |
| `/securecoder-build` | Activate persistent ASVS-supervised build mode. The host agent self-checks every output against ASVS controls. | v0.6.0 (slice 11) |
| `/securecoder-advise` | Q&A grounded in cached OWASP framework markdown. Verbatim citations, no hallucinations. | v0.7.0 (slice 12) |

## Privacy

securecoder itself **never sends your source code anywhere**. The skill performs these network operations:

- `git clone` from public OWASP and Semgrep rule repos at pinned tags (no user code)
- HTTPS download of Gitleaks and OSV-scanner release binaries from GitHub
- HTTPS POST to `api.osv.dev` with dependency package names and versions (no source code)
- `git push` only if you explicitly configure that strategy, to your own remote

**LLM calls flow source code to whichever model provider your coding agent uses** — Anthropic, OpenAI, Google, etc. This is your existing relationship with that provider; securecoder doesn't introduce a new vendor. The compliance-scan, fix, build, and review skills inherently include source in prompts.

You can run securecoder offline once tools and rule packs are cached at `~/.cache/securecoder/`.

## How it relates to SCCAP

This project distills the OWASP-driven scan/fix workflow from the [SCCAP platform](https://github.com/nerdy-krishna/ai-secure-coding-compliance-platform) into a portable, server-less skill bundle. SCCAP remains the heavyweight server-side answer (FastAPI, multi-agent LangGraph, Postgres, RabbitMQ, dashboards, multi-user). securecoder is the lightweight agent-resident answer for individual developers and small teams who want the same audit-first discipline without standing up infrastructure.

The two projects share design intent but have **no runtime dependency on each other**.

## Design

- **Design doc:** [docs/design.md](docs/design.md) — every architectural decision, schema, and protocol.
- **Product requirements:** [docs/prd.md](docs/prd.md) — user stories, modules, testing scope.
- **Implementation issues:** [docs/issues/](docs/issues/) — 14 vertical slices, dependency-ordered.

The seventeen-decision grilling session that produced these is summarized in `docs/design.md` § Appendix.

## Contributing

The project is in active early-stage development. The simplest contribution path:

1. Pick a slice from `docs/issues/` that isn't yet implemented.
2. Open a PR implementing it against the acceptance criteria listed inline.
3. The two HITL-tagged slices (07 and 11) need maintainer review before merging.

## License

[MIT](LICENSE).
