# Roadmap

Forward-looking work. The CHANGELOG is the history of what shipped; this file is the queue of what's planned. Items here are deliberate deferrals — features considered but intentionally not in the current release.

Shipped releases (v0.1.0 → v1.3.1) are recorded in the [CHANGELOG](../CHANGELOG.md), not here. Latest shipped: **v1.3.1** — project-root `.gitignore` integration for scan output.

## v1.4.0 — committed

1. **CERT C / C++ and domain-specific overlay frameworks.**
   Deferred from the v1.3.0 grilling (option B). Systems code deserves a real, citable standard rather than only the universal baseline. The blocker is ingestion: CERT C lives on an SEI wiki, not as clean `git clone` markdown at a stable tag. v1.4.0 builds a wiki-scraping ingestion path that converts the CERT C / C++ rule pages into the chapter-markdown shape `frameworks.json` expects, cached content-addressed like the OWASP clones. Once that path exists, other domain standards (where licensing permits) can follow. MISRA stays out — paywalled.

## Planned maintenance

1. **Windows end-to-end validation.**
   Path handling is implemented but only macOS + Linux were validated during development. Watch: pipx behavior, GitHub binary download for Windows release assets, `git config user.email` on git-for-windows, fnmatch slash handling.

2. **Promote `scripts/ci/pinned-tag-bumps.yml.template` to a live workflow.**
   Shipped as a template because the skills.sh installer token lacks `workflow` scope. Moving it to `.github/workflows/` needs a workflow-scoped GitHub token — a one-shot maintainer bootstrap step, plus documented manual path for forks.

## Later / unscheduled

Good ideas without a target release. Open for community PRs or future bandwidth.

- **DOM-level virtualized rendering for the flat findings list.** v1.2.0 shipped smart-collapse (file groups collapsed by default above 500 findings) as the stand-in. True virtual scroll (~100 LOC plain JS) would make the flat view responsive on any repo size; smart-collapse covers the common case well enough that this isn't urgent.
- **Block-comment annotation syntax** (`/* securecoder: ignore */`). v1.2.0's annotations recognize `#` and `//` line comments only.
- **SARIF / JUnit / SPDX export from `findings.jsonl`.** Mechanical transforms. Useful for CI integrations consuming security-tool output via standard formats.
- **Per-stack curated secure-scaffold guides for `/securecoder-build`.** Dropped from v1 scope per the Q14 design grilling. Re-evaluate if secure-build adoption shows users want this.
- **Real-time live cost ticker.** Per-LLM-call cost surface during compliance scans. Currently shown only at run end via manifest.
- **Richer diff against previous run.** v0.4.0's trend section is canonical-ID matching only. A richer view would show severity changes, evidence drift, rule-pack version effects.
- **`scope: "review-only"` suppression scope.** Suppress in `/securecoder-review` but still surface in full scans. Considered and rejected for v1.1.0 to keep the model simple; revisit if users ask.
- **MCP integration** for hosts that prefer MCP tools over slash commands.
- **`/securecoder-build` mid-session re-emit** for very long sessions where the policy block falls out of context. Requires host-specific hook APIs.
- **Higher-coverage pytest** for the render functions and search helpers (currently smoke-tested via integration only).

## How items move between sections

- **An `in progress` section** is added for the release currently being built — the current sprint. Once it ships, the section is removed and the release is recorded in the CHANGELOG.
- **v1.4.0 items are committed** — a maintainer has agreed to build them; they have a target release.
- **Later / unscheduled items are ideas** — they may move to a numbered release when a maintainer commits, or stay here indefinitely.
- **Deletion happens** when an idea becomes obsolete or is actively rejected.

A roadmap update PR can move items between sections, add new ones, or remove ideas that no longer make sense. Treat this file like the rest of the design docs — durable and reviewable.
