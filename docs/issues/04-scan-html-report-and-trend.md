# 04 — HTML report (self-contained) + cross-run trend

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

Extends the report renderer beyond markdown. After this slice, every `/securecoder-scan` run produces both `report.md` and `report.html` in the run dir, and reports include a Trend section comparing against prior runs in `.securecoder/runs/`.

The HTML report is fully self-contained: inlined CSS, no external scripts or `<link>` tags, no CDN dependencies. Opens in any modern browser, works offline, works when emailed. The structure matches the markdown report's sections (summary, severity breakdown, compliance posture *placeholder for slice 07 to fill*, findings grouped by file, trend, manifest footer) but adds HTML-only features: client-side filterable findings table (by severity, source, framework), collapsible per-file groups, severity badges with consistent color coding.

The trend computation reads sibling run dirs under `.securecoder/runs/`, matches findings across runs by canonical ID, and produces three buckets:
- **New** — finding ID present in this run, absent in previous run
- **Resolved** — finding ID present in previous run, absent in this run
- **Persistent** — finding ID present in both

The trend renders in both markdown and HTML. If only one run exists, the trend section says "First run — no trend data yet."

## Acceptance criteria

- [ ] Every `/securecoder-scan` run writes both `report.md` and `report.html` to the run dir
- [ ] `report.html` validates as self-contained: no `<link rel="stylesheet" href="http...">`, no `<script src="http...">`, no `<img src="http...">`; opens correctly with browser network disabled
- [ ] HTML filtering by severity / source / framework works client-side (no server, no JS framework dependency — plain JS only)
- [ ] After two runs against the same repo, the second run's report shows Trend with non-empty New / Resolved / Persistent buckets when expected
- [ ] First-run report shows "no trend data yet" rather than empty buckets
- [ ] Canonical IDs match across runs for unchanged findings (validates the ID stability test from slice 02)
- [ ] Tests cover: report renderer (markdown + HTML structural assertions), self-contained HTML validation (regex against external resource patterns), trend computation (new / resolved / persistent buckets, first-run case)

## Blocked by

- 02 — `/securecoder-scan` SAST end-to-end with Semgrep + markdown report
