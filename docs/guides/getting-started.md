# Getting started with securecoder

A 10-minute first-time walkthrough. You'll install securecoder, configure your project, run your first scan, and remediate the findings.

## What you need

- A coding agent installed locally (Claude Code, Cursor, Codex, Cline, Copilot, Windsurf, Gemini, etc.).
- Python 3.9+ on your machine. Verify with `python3 --version`.
- `git` on your PATH.
- A project to scan. Any language works — Python, JavaScript, TypeScript, Go, Java, Kotlin, Ruby, PHP, C#, Swift, C/C++, Rust, Bash, Terraform.
- Network access for the first run (subsequent runs are fully offline if the cache is populated).

## Step 1 — Install the skill

```bash
npx skills@latest add nerdy-krishna/securecoder
```

The skills.sh installer detects every coding agent on your machine and prompts you to pick which ones to install into. Pick the ones you actually use; you can re-run this command later to add more.

After installation, every selected agent now has 7 new slash commands available:

```
/securecoder-setup
/securecoder-scan
/securecoder-fix
/securecoder-secure
/securecoder-review
/securecoder-build
/securecoder-advise
```

## Step 2 — Configure your project (3 minutes)

Open your coding agent inside the project you want to audit. Run:

```
/securecoder-setup
```

The skill walks you through 10 questions one at a time, with sensible defaults pre-selected:

1. **Frameworks** — which compliance frameworks should the scan check against? Default: ASVS v5 (web app coverage). Add MASVS for mobile, Proactive Controls for defensive design.
2. **Severity floor** — findings below this level are informational, not blocking. Default: low (show everything).
3. **Default fix scope** — which severities should `/securecoder-secure` auto-fix? Default: critical + high.
4. **Git push strategy** — `push-each` / `commit-local-push-at-end` / `commit-local-never-push`. Default: commit local, push at end of run.
5. **Scan-output gitignore policy** — how the project-root `.gitignore` treats scan output. Default: `runs-and-reviews` (ignore `.securecoder/runs/` + `.securecoder/reviews/`, keep `config.json` shared).
6. **Languages** — auto-detected from your repo. Confirm or override.
7. **Rule pins** — advanced, accept defaults unless you have a reason.
8. **System-installed tools** — advanced, accept defaults (the skill uses its own cached tools).
9. **Custom rule sources** — advanced, leave as none unless you're adding your own Semgrep rules.
10. **Framework fit** — advanced; the poor-fit warning threshold (default 15%) and whether the `secure-coding-essentials` baseline runs (default on).

When you select a compliance framework for the first time, the skill shows a one-time privacy notice:

> When you enable a compliance framework, future `/securecoder-scan` and `/securecoder-secure` runs will send portions of your source code to whichever LLM provider your coding agent uses (Anthropic, OpenAI, Google, etc.). securecoder itself never sends source code anywhere; the framework markdown is fetched from public OWASP repos over HTTPS and contains no user code.

Acknowledge by saying "ok" or "continue."

When the wizard finishes, you'll have `.securecoder/config.json` checked into your repo (team-shared) plus `.securecoder/.gitignore` (auto-generated, ignores `runs/` and `reviews/`).

## Step 3 — Run your first scan

```
/securecoder-scan
```

The skill asks: **SAST only / LLM compliance only / Both**.

For your first scan, pick **SAST only** — it's free in LLM tokens (everything runs deterministically on your machine) and finishes in seconds-to-minutes depending on repo size.

On the first run only, the skill asks one-time permission to install ~200MB of tools (Semgrep, Bandit, Gitleaks, OSV-scanner) under `~/.cache/securecoder/tools/`. Accept.

The skill then:
- Walks your repo, detects languages
- Fetches Semgrep rule packs from the official repo (~100MB cached once)
- Runs the four SAST tools in sequence
- Normalizes findings into a unified schema
- Writes a `findings.jsonl`, a `manifest.json`, a `report.md`, and a `report.html`

When it finishes, you'll see something like:

```
securecoder-scan complete
  Run dir:     .securecoder/runs/20260514T140000Z/
  Mode:        SAST only
  Findings:    23 total (2 critical, 8 high, 9 medium, 4 low)
  ...
  Report:      .securecoder/runs/20260514T140000Z/report.md
```

Open `report.html` in a browser. You'll see:
- A severity breakdown
- Findings grouped by file, sorted critical-first
- Interactive filters by severity, source, framework
- Free-text search

For each finding, the report shows the rule, line range, CWE refs, framework refs (ASVS controls, OWASP Top 10 categories), evidence excerpt, and a remediation hint.

## Step 4 — Try the LLM compliance scan (optional, costs LLM tokens)

If you want compliance posture data (which OWASP ASVS controls your code violates), run:

```
/securecoder-scan
```

Pick **Both** at the mode prompt. The skill shows you a deterministic cost estimate before any LLM call:

```
Compliance pass estimate (ASVS v5):
  Files in scope:           142
  File × chapter pairs:     487 (filtered from 142 × 17)
  LLM calls expected:       487
  Estimated input tokens:   ~9.7M
  Estimated output tokens:  ~2.4M

Approximate cost at common rates:
  Claude Opus 4.7:    $329.50
  Claude Sonnet 4.6:  $ 65.20
  Claude Haiku 4.5:   $ 21.70

Wall time estimate (sequential dispatch): ~4 hours

Continue? [proceed / abort]
```

Read carefully. On Opus, a full compliance scan of a medium-large codebase can cost real money. Options:

- **`proceed`** — full scan. If this is more than you want to spend, abort and re-run with **SAST only** instead.
- **`abort`** — exits cleanly with SAST findings still produced (if you picked Both).
- Adjust the active frameworks via `/securecoder-setup` to scan against fewer chapters.

## Step 5 — Remediate findings

```
/securecoder-fix
```

The skill asks which severities to fix. For your first fix run, pick the conservative **Critical + High** (or the **Interactive one-by-one** mode if you want to review every change).

Pre-flight checks:
- If your git tree has uncommitted changes, the skill asks: stash / abort / proceed-anyway.
- If you're on `main` / `master` / `release/*`, the skill offers to create a `securecoder-fix/<run-id>` branch.
- Every file slated for edit gets copied to `.securecoder/runs/<run-id>/backups/<path>` before any modification.

The skill then applies fixes one at a time:
- LLM emits a SEARCH/REPLACE block
- Script validates exactly one match in the file
- Apply, then run a syntax check appropriate to the file's language (Python `py_compile`, Node `--check`, etc.)
- Re-scan the file with the originating SAST tool to verify the finding is actually gone
- On success: one git commit per fix, with a structured message
- On failure: restore from backup, log the reason, move on (up to 3 retries per finding)

When done, you'll see a summary plus instructions for rolling back:

```
securecoder-fix complete
  Run dir:    .securecoder/runs/20260514T143000Z/
  Applied:    18
  Editor failed:           2  (see fix_log.jsonl for reasons)
  Manual review required:  3  (compliance findings or fix_complexity=high)

  To roll back this fix run:
    /securecoder-fix --restore 20260514T143000Z
```

## Step 6 — Verify and commit

```
git diff --stat
```

Review the changes. If everything looks good, commit (the fixes are already each individual commits; you don't need to add more):

```bash
git log --oneline -5    # see the fix commits
git push                # if your push strategy was "commit local, push at end"
```

If something looks wrong:

```
/securecoder-fix --restore 20260514T143000Z
```

This rolls back every file from the backups and (optionally) runs `git revert` on each fix commit.

## Step 7 — Install the pre-commit hook (optional)

To catch SAST issues before they sneak into your next commit:

```
/securecoder-review
```

At the scope prompt, pick **Install pre-commit hook**. The skill writes `.git/hooks/pre-commit` that runs SAST-only on staged files and blocks the commit if any finding above your severity floor is present. Bypass with `git commit --no-verify` when needed.

## Step 8 — Use `/securecoder-build` for new features

When you ask your agent to build something new ("add an auth endpoint"), run:

```
/securecoder-build
```

This emits a persistent ASVS-supervision policy into the chat session. From then on, the agent identifies which ASVS controls apply to whatever it's building, plans with them in mind, and self-checks every output before declaring done. You'll see the agent append a "Controls applied" block to each code-producing response:

```
─── Secure Build Mode — Controls applied
- V6.2.1   bcrypt for password hashing   SATISFIED
- V7.2.1   Set-Cookie Secure flag        SATISFIED
- V1.2.1   Parameterized SQL queries     SATISFIED
- V4.2.1   CSRF protection on POST       UNKNOWN — Express defaults?

Recommended next step: /securecoder-review
```

To deactivate: say "end secure build mode" or wait for the chat context to roll over.

## Next steps

- Read the per-skill guides at [`docs/guides/per-skill/`](per-skill/) for deep dives.
- Read the [scenarios guide](scenarios.md) for common usage patterns.
- Read the [full design](../design.md) for every architectural decision and schema.
