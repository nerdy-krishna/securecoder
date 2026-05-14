# Common scenarios

Recipes for common situations. Each scenario shows the recommended sequence of skill invocations + what to expect at each step.

## Scenario 1 — I just inherited a codebase

**Goal:** Understand the security state of code I didn't write, then start fixing the worst stuff.

**Sequence:**

```
1.  /securecoder-setup
2.  /securecoder-secure            (Recommended — pipeline runs scan + fix + compliance + fix automatically)
3.  Open .securecoder/runs/<latest>/report.html
4.  /securecoder-review            (Install pre-commit hook)
```

**What happens:**

- **Step 1:** Configure frameworks (default: ASVS v5), severity floor (default: low — show everything), default fix scope (critical + high). 3 minutes.

- **Step 2:** `/securecoder-secure` runs the full 4-phase pipeline with one approval. It walks the repo, computes a cost estimate, asks for approval, then runs straight through: SAST scan → fix critical+high SAST findings → ASVS compliance scan → fix critical+high compliance findings → unified report.

  Expect substantial wall time and LLM cost for a medium-large codebase. The pre-flight estimate is your gate; the 50%-overrun mid-run gate is the safety net.

  Alternative if you want more control: run `/securecoder-scan` (SAST only first), review, then `/securecoder-fix`, then a compliance scan separately.

- **Step 3:** Read the HTML report. Filter by severity (start with `critical`), then by source. Look at the trend section the second time you run (compares to the first run).

- **Step 4:** Install the pre-commit hook so future commits don't regress. SAST-only blocks anything above your severity floor.

**Time budget:**
- SAST-only path: 5–30 minutes wall time, $0
- Full pipeline including compliance + fixes: hours, dollars (varies with repo size + model)

---

## Scenario 2 — Starting a new project from scratch

**Goal:** Build a project that's secure by construction, with the agent supervising every change.

**Sequence:**

```
1.  /securecoder-setup
2.  /securecoder-build              (activates secure-build mode for this chat session)
3.  Work with the agent — build features as usual
4.  /securecoder-review             (each time before committing)
5.  /securecoder-fix                (if /securecoder-review surfaces findings)
```

**What happens:**

- **Step 1:** Configure your project's frameworks and preferences.

- **Step 2:** `/securecoder-build` emits a persistent policy block into your chat. From this point until the session ends, every code-producing task the agent does flows through ASVS controls. The agent identifies applicable controls before writing code, then self-checks its output and appends a "Controls applied" block.

- **Step 3:** Build features normally — "add a user signup endpoint", "wire up Stripe", etc. The agent now does so with security in mind. If you ask for something insecure (e.g., a debug endpoint exposing internal state), the agent surfaces the conflict ("V14.4.1 says don't expose internal state in responses; you asked for a debug endpoint — should I prioritize the control or your requirement?") and lets you decide.

- **Step 4:** Before each commit, run `/securecoder-review`. It's diff-scoped, so cost is proportional to change size — typically pennies for a small commit, sub-dollar for a large one.

- **Step 5:** If review flagged anything, `/securecoder-fix` handles it.

**Tip:** Install the pre-commit hook via `/securecoder-review`'s install action. It runs SAST-only without LLM cost on every commit, catching the obvious stuff. The LLM compliance review through `/securecoder-review` interactively catches the design-level issues.

---

## Scenario 3 — About to open a PR

**Goal:** Make sure my branch doesn't introduce security regressions before asking reviewers.

**Sequence:**

```
1.  /securecoder-review            (scope: Branch vs base)
2.  /securecoder-fix               (if findings)
3.  Push the cleaned-up branch
```

**What happens:**

- **Step 1:** Pick "Branch vs base" at the scope prompt. The skill diffs your branch against `main` (or whatever your base branch is), extracts the changed files + line ranges, and runs SAST + LLM compliance on only the changed hunks. Cost is proportional to your branch's diff size, not the whole repo.

  Output: a terse verdict in chat (`OK to commit` or `N issues found`) + a full markdown report at `.securecoder/reviews/<id>/report.md`.

- **Step 2:** If findings are present, `/securecoder-fix` against the review's findings file:

  ```
  /securecoder-fix from review <review-id>
  ```

  The fixer accepts a review's findings file the same way it accepts a scan's. Same safety loop applies.

- **Step 3:** Push. Your reviewers see a clean branch.

**Tip:** Add this to your PR template's checklist: `- [ ] /securecoder-review --scope branch-vs-base passed`.

---

## Scenario 4 — I want to understand a finding

**Goal:** "Why did securecoder flag line 42 as critical? Is this a real issue?"

**Sequence:**

```
1.  /securecoder-advise
2.  Pick "Specific finding deep-dive"
3.  Paste the 8-char finding ID prefix from your report
```

**What happens:**

`/securecoder-advise` loads your latest scan's findings, locates the specific one, quotes its `evidence` and `description` verbatim, looks up the relevant ASVS/MASVS control text from the cached framework markdown, and explains:

- What the control requires (verbatim quote)
- Why it matters (threat model)
- How it's typically satisfied
- The specific code in your file that violates it
- What `/securecoder-fix` would do for this finding
- Related controls and Cheatsheet sections

**Alternative invocations:**

```
/securecoder-advise "How do I prevent SSRF in this codebase?"
/securecoder-advise "Explain ASVS V1.2.1"
/securecoder-advise "What's the difference between A03 Injection and A07 Auth?"
```

The skill is read-only — it never modifies code. Use it freely without worrying about side effects.

---

## Scenario 5 — Compliance audit deliverable

**Goal:** Produce an ASVS compliance posture score for a security review.

**Sequence:**

```
1.  /securecoder-setup            (enable the frameworks you want)
2.  /securecoder-scan             (mode: LLM compliance only)
3.  Share .securecoder/runs/<id>/report.html with stakeholders
```

**What happens:**

- **Step 2:** "LLM compliance only" runs Phase B without SAST. The report includes a per-framework compliance posture section:

  ```
  ASVS v5.0.0:
    Controls evaluated:        142
    Controls passing:          119
    Controls with findings:     23
    Posture score:           0.838
  ```

  Plus per-finding rationale tied to specific ASVS controls.

- **Step 3:** The HTML report is fully self-contained — no external resources, opens offline. Safe to email or share via file system.

**Time + cost:** Same as Scenario 1's compliance phase. Plan a few hours and tens of dollars for medium-large codebases on a quality model.

**For periodic compliance reporting:** Re-run quarterly. The trend section in the report shows new / resolved / persistent findings since the previous run.

---

## Scenario 6 — Pre-commit gate in CI

**Goal:** Every developer's commits get the same baseline check before pushing.

**Sequence:**

```
1.  Each developer runs: /securecoder-review → install pre-commit hook (once per clone)
2.  Optionally wire scripts/ci/pinned-tag-bumps.yml.template into CI
```

**What happens:**

- The pre-commit hook (`.git/hooks/pre-commit`) runs SAST tools on staged files, blocks the commit if any finding above `severity_floor` is present. No LLM cost (no compliance review).

- For full compliance review on the diff, the developer invokes `/securecoder-review` interactively after staging and before pushing.

- For CI gating (e.g., "PRs must pass a SAST scan"), wire the relevant tools into your existing CI. securecoder's CHANGELOG documents the pinned tool versions; install them with the same pins in CI to match what runs locally.

---

## Scenario 7 — Rolling back a bad fix

**Goal:** "I ran /securecoder-fix, but one of the fixes broke something. Get my code back."

**Sequence:**

```
1.  /securecoder-fix --restore <run-id>
```

**What happens:**

- The skill locates the run directory at `.securecoder/runs/<run-id>/backups/`.
- Shows you a diff between each current file and its backup.
- Asks for confirmation: yes / abort / per-file (review each one).
- Restores files from backups.
- Optionally also runs `git revert` on the fix commits if they're still on the branch.
- Writes `restore_log.md` to the run directory.

**Variants:**

- `/securecoder-fix --restore latest` — restore the most recent fix run.
- "undo my last sccap-fix" — natural-language equivalent the skill interprets.

If you need partial rollback (some fixes good, one bad), use the per-file mode at the confirmation prompt.

**Tip:** Backups persist across reboots and even across `rm -rf node_modules` etc., because they live at `.securecoder/runs/<run-id>/backups/` separate from the working tree. They survive a fresh clone if you've committed `.securecoder/runs/` (you usually shouldn't — that dir is gitignored by default).

---

## Scenario 8 — Custom rule sources (advanced)

**Goal:** Add your own Semgrep rules from a private repo to the scan.

**Sequence:**

```
1.  /securecoder-setup            (Q8: add custom rule sources)
2.  Provide source name + git URL + pinned tag
3.  /securecoder-scan             (uses the custom source on next scan)
```

**What happens:**

- During setup, the skill warns about supply-chain risk on custom sources:

  > Custom rule sources execute on every scan. Rules from a malicious or compromised source can send your source code to attacker-controlled endpoints (Semgrep custom Python rules execute), inject misleading findings, or add noise that buries real findings. Only add sources you trust.

- The custom source goes into `config.custom_sources`. The first time `/securecoder-scan` uses it, the skill asks for explicit confirmation.

- The source is cloned to `~/.cache/securecoder/rules/semgrep-custom/<sha>/` content-addressed by SHA.

---

## Scenario 9 — Offline scanning (plane / train / air-gapped)

**Goal:** Run scans without network access.

**Prerequisite:** A previous online run that populated the cache:
- `~/.cache/securecoder/tools/` (Semgrep, Bandit, Gitleaks, OSV-scanner)
- `~/.cache/securecoder/rules/semgrep/<sha>/`
- `~/.cache/securecoder/rules/frameworks/asvs/<sha>/` (if you've done a compliance scan)

**Limitations offline:**
- OSV-scanner queries `api.osv.dev` for vulnerability data — if no network, the skill logs the failure and continues with the other tools.
- LLM calls still happen via your coding agent's normal flow — if your agent is offline (using a local model), compliance scans go through the local model.

The skill detects offline cleanly: if the rule pack or framework cache is empty AND no network is available, it fails with a clear message: "Source X needs network access. Either connect or remove X from your `.securecoder/config.json` to skip it."

---

## Scenario 12 — Marking a specific line as a known false positive (v1.2.0)

**Goal:** A specific line in production code is flagged by SAST, but the team has validated that path is safe upstream. Suppress it directly in the source so the suppression travels with the code.

**Sequence:** Edit the file, add the annotation, re-scan.

```python
def fetch_remote(url):
    # securecoder: ignore reason="URL is validated by middleware before reaching this fn"
    return requests.get(url, timeout=5)
```

For inline (end-of-line) form on short lines:

```python
PASSWORD = "dev-only"  # securecoder: ignore reason="dev env only" expires="2027-01-01"
```

**What happens:**

- On the next `/securecoder-scan`, the new Phase A.7.3 step walks source files for these markers.
- Each annotation becomes an ephemeral suppression entry with `match: {file: ..., lines: {...}}`, `source: "annotation"`, `created_by: "<annotation>"`.
- The ephemeral entries merge with `.securecoder/suppressions.json` at match time. Most-specific-wins still applies — line-anchored annotations beat rule-only config entries.
- Findings whose `lines.start` falls in the annotation's range get `status: "suppressed"` with the annotation's reason.

**When annotations vs `/securecoder-suppress`?**

Use annotations when:
- The suppression is anchored to specific code
- The reasoning is most natural to read next to the code
- You want git blame to attribute who added the suppression
- The code is short-lived and doesn't need separate team review

Use `/securecoder-suppress` when:
- The suppression covers a pattern (rule + path glob) across many findings
- The decision should be team-reviewed via PR on the config file
- You want explicit `created_by` from git config

---

## Scenario 11 — Triaging a 2,000-finding scan (false positives)

**Goal:** A SAST scan returned 2,000 medium findings. Most are false positives. Triage efficiently rather than fixing them one-by-one.

**Sequence:**

```
1.  Open .securecoder/runs/latest/report.html
2.  Click the [Clusters] tab — the 2,000 findings collapse to ~30–50 clusters
3.  Per cluster: [Suppress entire cluster] → reason → staged
4.  When done, click [Export to agent] in the sticky banner
5.  /securecoder-suppress import [paste]   (agent receives the batch)
6.  /securecoder-scan                       (re-scan to see suppressions take effect)
```

**What happens:**

- **Step 2:** The cluster view groups by `(rule_id, path_prefix)`. A rule that fires 1,247 times in `tests/fixtures/` becomes one row with a "Suppress entire cluster" button.
- **Step 3:** Each cluster suppress emits a pattern-based entry (`{match: {rule: ..., file_glob: ...}, reason: ...}`). The cluster row stays interactive — you can also expand to see 3 sample findings before deciding.
- **Step 4:** "Export to agent" generates `/securecoder-suppress import [{...}, {...}, ...]`. It copies the command to your clipboard with a confirmation toast.
- **Step 5:** Paste into your agent. The skill validates each entry, dedupes against existing, and writes them to `.securecoder/suppressions.json`. Reports added / skipped / invalid counts.
- **Step 6:** Re-running the scan applies the new suppressions during Phase A.7.5. Findings transition from `status: "open"` → `status: "suppressed"`. The report now shows "47 active (1,953 suppressed)" instead of 2,000 all-active.

**Multi-select alternative for individual findings:**

When findings don't cluster cleanly:

1. In the flat findings view, click checkboxes on findings you want to suppress.
2. The sticky bar shows "N selected" with `[Suppress N selected]` button.
3. Click it; provide one reason; entries are staged.
4. Same export flow as above.

**Time budget:** 30 minutes of triage replaces 2,000 individual fix decisions.

**Notes:**
- The HTML report's staging tray is `localStorage`-persisted by run id, so you can triage over multiple sittings — return to the page, see the staged entries still there.
- For very large reports (>1000 findings of one severity), the report shows an advisory banner suggesting alternatives (raise severity_floor, switch to clusters view).
- Suppressions are team-shared via `.securecoder/suppressions.json` — commit the file so your teammates' scans see the same triage decisions.

---

## Scenario 10 — Running multiple skills in one session

**Goal:** Mix and match — scan one part, advise on a finding, review the diff, fix, re-scan.

securecoder skills compose freely. They communicate via the filesystem (`.securecoder/runs/<id>/`, `.securecoder/reviews/<id>/`), so:

- The output of `/securecoder-scan` is automatically the input of `/securecoder-fix`.
- `/securecoder-advise` reads `.securecoder/runs/latest/findings.jsonl` for grounded answers.
- `/securecoder-review` writes its own findings file that `/securecoder-fix from review <id>` can target.
- `/securecoder-build` mode is purely chat-resident — it doesn't conflict with any other skill.

Example mixed session:

```
/securecoder-scan                                # full scan
/securecoder-advise                              # mode: deep-dive on a specific finding
/securecoder-fix                                 # apply fixes for critical+high
/securecoder-review                              # check what changed before committing
/securecoder-build                               # activate supervision for the next feature
```

The `latest` symlink under `.securecoder/runs/` always points at the most recent scan run, so downstream skills find findings without needing args.
