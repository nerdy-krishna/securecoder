# Roadmap

Forward-looking work. The CHANGELOG is the history of what shipped; this file is the queue of what's planned. Items here are deliberate deferrals — features and improvements considered but intentionally not in the current release.

## v1.2.0 — next minor release

### Planned features

1. **`/securecoder-update` — version check + upgrade helper**

   Tell the user what version of securecoder is installed and whether a newer release exists. Reasons it's not in v1.1.0: the eight-slice suppression sprint already filled v1.1.0, and a clean update story benefits from infrastructure that's worth a dedicated cut.

   Proposed shape:

   - Ship a `VERSION` file at the repo root containing the current tag (e.g., `v1.1.0`). The skills.sh installer copies it alongside `SKILL.md` files into the host agent's skill directory.
   - New `/securecoder-update` skill (or `/securecoder-setup --check-updates` mode):
     - Reads installed `VERSION`
     - Queries `https://api.github.com/repos/nerdy-krishna/securecoder/releases/latest`
     - Compares
     - Reports: current vs latest, days since release, link to release notes, the exact install command to upgrade
   - No automatic upgrade (security: the user always explicitly invokes the installer). The skill only surfaces info.

   Smallest viable slice — ~50 LOC + a SKILL.md.

2. **DOM-level virtualized rendering for the flat findings list**

   Deferred from slice 11.F (v1.1.0). Plain-JS virtual scroll (~100 LOC) so 2000+ finding cards don't all live in the DOM at once. The cluster view is the current workaround for very large repos, but the flat view would be noticeably more responsive on big scans with this in.

3. **Source-code comment annotations (`# securecoder: ignore`)**

   Deferred from v1.1.0's suppression design. An alternative input layer alongside the config-file source of truth — for cases where developers want suppressions visible inline in the code. Implementation: walk the repo during scan, parse annotations into `apply_suppressions.py`'s effective entry list. Trust model: annotations are author-attributed via `git blame` rather than user-supplied `created_by`.

4. **Sampling-assisted review for large clusters**

   Deferred from v1.1.0. When a cluster has > 50 findings, offer "review N random samples, then decide on the whole cluster" as an alternative to expanding 3 samples. Adds an interactive mode to the cluster suppress button: opens a modal with 5–10 random findings, lets the user vote keep/suppress per sample, and only enables the cluster suppress if ≥ 80% voted suppress.

### Planned maintenance

1. **Backfill unit tests for v0.x helper scripts**

   v1.1.0's slice 11.H shipped the project's first pytest suites — 22 tests covering `apply_suppressions.py` and `compute_clusters()`. The v0.x helpers (`normalize_<tool>.py` for all four SAST tools, `repo_walker.py`, `diff_scoper.py`, `render_markdown.py`, `render_html.py`, `validate_coverage.py`, `compute_trend.py`, `apply_patch.py`, `syntax_check.py`) still lack pytest coverage. Each is a pure-transform module — testable in isolation with synthetic input fixtures.

2. **Windows end-to-end validation**

   v1.0 path handling is implemented but only macOS + Linux were validated during development. Issues to watch: pipx behavior, GitHub binary download for Windows release assets, `git config user.email` on git-for-windows, fnmatch slash handling.

3. **Promote `scripts/ci/pinned-tag-bumps.yml.template` to a live workflow**

   v1.0.0 shipped the auto-PR bumper as a template (file at `scripts/ci/pinned-tag-bumps.yml.template`) because the skills.sh installer token lacks `workflow` scope. Manually moving it to `.github/workflows/` requires a workflow-scoped GitHub token. For v1.2.0 we wire a separate one-shot bootstrap step in the maintainer's repo setup that installs the workflow correctly, plus document the manual path for forks.

## Later / unscheduled

These are good ideas without a target release. Open for community PRs or future bandwidth.

- **SARIF / JUnit / SPDX export from `findings.jsonl`.** Mechanical transforms. Useful for CI integrations that consume security-tool output via standard formats.
- **Per-stack curated secure-scaffold guides for `/securecoder-build`.** Dropped from v1 scope per the Q14 design grilling. Would add `references/secure-scaffolds/python-fastapi.md`, etc., describing what "secure X" looks like per stack. Re-evaluate if v1 secure-build adoption shows users want this.
- **Real-time live cost ticker.** asvs-shell-style per-LLM-call cost surface during compliance scans. Currently shown only at run end via manifest. Useful for long-running scans where users want a live spend indicator.
- **Diff against previous run as a first-class feature.** Partially shipped in v0.4.0 (trend section in reports) but limited to canonical-ID matching. A richer diff view would show severity changes, evidence drift, and rule-pack version effects.
- **`scope: "review-only"` suppression scope.** Suppress in `/securecoder-review` but still surface in full scans. Considered and explicitly rejected for v1.1.0 to keep the model simple; revisit if users ask for it.
- **MCP integration for hosts that prefer MCP over slash commands.** Wrap the core commands as MCP tools. Most modern coding agents support both; the slash-command path is the primary one for now.
- **`/securecoder-build` mid-session intervention.** Currently the policy block is emitted once at activation; the agent's context retention keeps it alive. For very long sessions where context drops, an agent-side hook could re-emit periodically. Requires host-specific hook APIs.

## How items move between sections

- **v1.2.0 items are committed.** They have a target release and are the next sprint.
- **Later / unscheduled items are ideas.** They may move to a numbered release when a maintainer commits to them, or stay here indefinitely.
- **Deletion happens** when an idea becomes obsolete (e.g., upstream solves the problem) or actively rejected.

A roadmap update PR can move items between sections, add new ones, or remove ideas that no longer make sense. Treat this file like the rest of the design docs — durable and reviewable.
