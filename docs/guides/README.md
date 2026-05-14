# securecoder guides

User-facing walkthroughs and per-skill deep dives.

## Where to start

| If you... | Read |
| --- | --- |
| Just installed securecoder and want to try it | [`getting-started.md`](getting-started.md) — 10-minute first run |
| Have a specific situation in mind | [`scenarios.md`](scenarios.md) — recipes for inherited code, new projects, pre-PR checks, etc. |
| Want to know exactly what a skill does + how to invoke it | The per-skill guides under [`per-skill/`](per-skill/) |
| Want the architectural details | [`../design.md`](../design.md) — every design decision |
| Want the product-side framing | [`../prd.md`](../prd.md) — user stories + modules |

## Per-skill guides

| Skill | Guide |
| --- | --- |
| `/securecoder-setup` | [`per-skill/securecoder-setup.md`](per-skill/securecoder-setup.md) |
| `/securecoder-scan` | [`per-skill/securecoder-scan.md`](per-skill/securecoder-scan.md) |
| `/securecoder-fix` | [`per-skill/securecoder-fix.md`](per-skill/securecoder-fix.md) |
| `/securecoder-secure` | [`per-skill/securecoder-secure.md`](per-skill/securecoder-secure.md) |
| `/securecoder-review` | [`per-skill/securecoder-review.md`](per-skill/securecoder-review.md) |
| `/securecoder-build` | [`per-skill/securecoder-build.md`](per-skill/securecoder-build.md) |
| `/securecoder-advise` | [`per-skill/securecoder-advise.md`](per-skill/securecoder-advise.md) |

Each per-skill guide covers:

- **What this skill does** — one paragraph
- **When to invoke it** (and **When NOT to**)
- **How to invoke** — example syntax + variants
- **What it produces** / what it writes
- **Follow-up skill recommendations**
- **Common pitfalls**

## Skill chains at a glance

```
Auditing existing code:
   setup  →  scan  →  fix  →  scan (verify)
   or:    setup  →  secure   (does the above in one approval)

New project / in-flight work:
   setup  →  build  →  (your coding session)  →  review (each commit)

Pre-PR / pre-push:
   review  →  fix (if findings)  →  push

Q&A / learning:
   advise (any time, grounded in cached frameworks + latest scan)
```

## Related

- [Top-level README](../../README.md) for install + quickstart
- [CHANGELOG](../../CHANGELOG.md) for release-by-release history
- [docs/issues/](../issues/) for the 14 implementation slices (PRD-derived)
