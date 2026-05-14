---
name: securecoder-scan
description: Audit a codebase for vulnerabilities and OWASP compliance issues. Currently runs Semgrep SAST and emits findings in the unified securecoder schema, with markdown report and run-history under .securecoder/runs/<id>/. Other SAST tools (Bandit, Gitleaks, OSV-scanner) and the LLM-driven compliance pass land in subsequent releases.
---

# `/securecoder-scan`

You are running the `/securecoder-scan` skill. Your job is to audit the user's codebase for security findings and write the results to `.securecoder/runs/<run-id>/`.

> **Slice 02 scope (this release).** Only the SAST-Semgrep path is implemented. If the user asks for "LLM compliance only" or "Both," gracefully decline with the message in [§ Phase B](#phase-b--llm-compliance-pass-not-yet-implemented) below. Multi-tool SAST (Bandit, Gitleaks, OSV-scanner) ships in slice 03; compliance in slice 07.

## Pre-flight

### 1. Locate the project root

1. If a `.git/` directory exists in the current working directory or any ancestor, use the git toplevel (`git rev-parse --show-toplevel`).
2. Otherwise, use the current working directory.

Every relative path below is rooted at this project root. Capture it as `PROJECT_ROOT`.

### 2. Load configuration

Read `<PROJECT_ROOT>/.securecoder/config.json` if it exists and is parseable. Otherwise use these documented defaults:

```json
{
  "schema_version": "1.0",
  "frameworks": ["asvs-v5"],
  "severity_floor": "low",
  "default_fix_scope": ["critical", "high"],
  "git": { "push_strategy": "commit-local-push-at-end" },
  "languages": [],
  "rule_pins": {},
  "tools": {},
  "custom_sources": []
}
```

If the file is missing, mention to the user once: "Running with default configuration. Run `/securecoder-setup` to customize."

### 3. Ask the user which mode to run

Present three options with the explanations + token warnings below. Use whatever interactive prompt mechanism your host agent supports.

- **SAST only** *(implemented)* — Run Semgrep against the codebase. Detects code-level vulnerabilities (injection, weak crypto, SSRF, etc.). Free in LLM tokens. Typical wall time: 30 seconds for a small repo, a few minutes for a large one.
- **LLM compliance only** *(not yet implemented in this release)* — Will run an LLM-driven review against the configured frameworks. Slice 07 lands this; for now, falls through to a friendly "not yet" message.
- **Both** *(not yet implemented in this release)* — Combines the two. Same caveat as above.

If the user picks an unimplemented mode, jump to [§ Phase B](#phase-b--llm-compliance-pass-not-yet-implemented).

### 4. Generate the run ID and run directory

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$PROJECT_ROOT/.securecoder/runs/$RUN_ID"
mkdir -p "$RUN_DIR"
```

Initialize a run log inside the run dir; you'll append per-phase rows to it as the scan progresses.

```bash
cat > "$RUN_DIR/log.md" <<EOF
# securecoder-scan run — $RUN_ID

- Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)
- Mode: SAST only
- Project root: $PROJECT_ROOT

| Phase | Started | Finished | Status | Notes |
| --- | --- | --- | --- | --- |
EOF
```

### 5. Pre-flight cost estimate

For SAST-only mode the LLM cost is `$0` and wall time is bounded by tool execution. Still print the estimate and ask the user to confirm before doing any installation or fetching, so the gate flow is consistent with future modes.

Print:

```
Scan estimate for SAST-only mode:
  Files in scope:    (computed after repo walk)
  LLM cost:          $0
  Wall time:         ~30s for a small repo, a few minutes for larger
  Will install:      Semgrep into ~/.cache/securecoder/tools/semgrep/ (if not cached)
  Will fetch:        returntocorp/semgrep-rules at the pinned tag (if not cached)

Continue? [proceed / abort]
```

Wait for `proceed`. On `abort`, append a `cancelled-at-estimate` row to the log and exit cleanly.

## Phase A — Semgrep SAST

### A.1 Ensure Semgrep is installed

Pinned version for this release: **`semgrep==1.91.0`**.

```bash
SEMGREP_VERSION="1.91.0"
TOOLS_DIR="$HOME/.cache/securecoder/tools"
SEMGREP_DIR="$TOOLS_DIR/semgrep"
SEMGREP_INSTALLED_JSON="$SEMGREP_DIR/installed.json"
SEMGREP="$SEMGREP_DIR/venv/bin/semgrep"

# Cache hit?
if [ -f "$SEMGREP_INSTALLED_JSON" ] && [ -x "$SEMGREP" ]; then
  CACHED_VERSION="$(python3 -c "import json,sys; print(json.load(open('$SEMGREP_INSTALLED_JSON')).get('version',''))")"
  if [ "$CACHED_VERSION" = "$SEMGREP_VERSION" ]; then
    : # Cache is current; nothing to do.
  fi
fi
```

If the cache check above doesn't match the pinned version, install:

```bash
mkdir -p "$SEMGREP_DIR"

# Consent gate — first time only
SECURECODER_MANIFEST="$HOME/.cache/securecoder/manifest.json"
if [ ! -f "$SECURECODER_MANIFEST" ]; then
  # Ask the user once: "securecoder needs to install Semgrep (~50MB) into
  # ~/.cache/securecoder/tools/. It won't touch your system Python or PATH.
  # Proceed?"
  # On approval, record consent:
  mkdir -p "$HOME/.cache/securecoder"
  cat > "$SECURECODER_MANIFEST" <<EOF
{
  "consent": {
    "tools": true,
    "granted_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  }
}
EOF
fi

# Install Semgrep into a private venv (no pipx required)
python3 -m venv "$SEMGREP_DIR/venv"
"$SEMGREP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$SEMGREP_DIR/venv/bin/pip" install --quiet "semgrep==$SEMGREP_VERSION"

# Record installation
cat > "$SEMGREP_INSTALLED_JSON" <<EOF
{
  "version": "$SEMGREP_VERSION",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "binary": "$SEMGREP"
}
EOF
```

If `python3 -m venv` fails because the venv module isn't installed (some minimal Linux distros), fall back to advising the user: "Securecoder needs `python3 -m venv` to install Semgrep. On Debian/Ubuntu: `sudo apt install python3-venv`. On RHEL: `sudo dnf install python3-venv`. Then re-run `/securecoder-scan`."

If there is no network and the cache is empty, fail with:

> Source `semgrep==1.91.0` needs network access to install. Either connect to the internet and re-run, or pre-populate `~/.cache/securecoder/tools/semgrep/` from another machine.

### A.2 Fetch the Semgrep rule packs

Pinned upstream: **`returntocorp/semgrep-rules` at branch `main`**, content-addressed by the resulting commit SHA.

```bash
RULES_REPO="https://github.com/returntocorp/semgrep-rules.git"
RULES_BRANCH="main"
RULES_CACHE_ROOT="$HOME/.cache/securecoder/rules/semgrep"
TMP_CLONE="$RULES_CACHE_ROOT/_tmp_clone"

mkdir -p "$RULES_CACHE_ROOT"

# Probe upstream and decide if any cached version is reusable.
# Simplest correct policy: if any sub-dir is present under
# $RULES_CACHE_ROOT and contains a manifest.json with `branch == main`
# and `last_verified_at` within the last 7 days, reuse it. Otherwise
# clone fresh.
REUSE_DIR=""
for d in "$RULES_CACHE_ROOT"/*/; do
  [ -d "$d" ] || continue
  if [ -f "$d/manifest.json" ]; then
    META_BRANCH="$(python3 -c "import json; print(json.load(open('$d/manifest.json')).get('branch',''))" 2>/dev/null || true)"
    if [ "$META_BRANCH" = "$RULES_BRANCH" ]; then
      REUSE_DIR="$d"
      break
    fi
  fi
done

if [ -z "$REUSE_DIR" ]; then
  rm -rf "$TMP_CLONE"
  git clone --depth 1 --branch "$RULES_BRANCH" "$RULES_REPO" "$TMP_CLONE" 2>&1
  SHA="$(git -C "$TMP_CLONE" rev-parse HEAD)"
  FINAL_DIR="$RULES_CACHE_ROOT/$SHA"
  if [ -d "$FINAL_DIR" ]; then
    rm -rf "$TMP_CLONE"
  else
    mv "$TMP_CLONE" "$FINAL_DIR"
    cat > "$FINAL_DIR/manifest.json" <<EOF
{
  "source": "$RULES_REPO",
  "branch": "$RULES_BRANCH",
  "sha": "$SHA",
  "fetched_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
  fi
  RULES_DIR="$FINAL_DIR"
else
  RULES_DIR="$REUSE_DIR"
  SHA="$(python3 -c "import json; print(json.load(open('$RULES_DIR/manifest.json'))['sha'])")"
fi
```

**Integrity invariant.** Before invoking Semgrep, verify the cached dir's stored SHA still matches the directory name. If they disagree, refuse to run with the message: "Cached rule pack integrity check failed for `$SHA`. Refusing to use. Remove `$RULES_DIR` and re-run to fetch fresh."

**Offline behavior.** If `git clone` fails because of no network AND no usable cached dir exists, fail with:

> Source `returntocorp/semgrep-rules @ main` needs network access. Either connect and re-run, or pre-populate `~/.cache/securecoder/rules/semgrep/` from another machine.

### A.3 Walk the repo and pick rule subdirectories

Run the bundled walker:

```bash
python3 "<this-skill-dir>/scripts/repo_walker.py" "$PROJECT_ROOT" \
  --output "$RUN_DIR/repo_map.json"
```

Read the resulting `languages` map. For each language with at least one file, select the Semgrep rule subdir if it exists under `$RULES_DIR`. The mapping is:

| Detected language | Semgrep rules subdir (under `$RULES_DIR/`) |
| --- | --- |
| python | `python/` |
| javascript | `javascript/` |
| typescript | `typescript/` |
| go | `go/` |
| rust | `rust/` |
| java | `java/` |
| kotlin | `kotlin/` |
| ruby | `ruby/` |
| php | `php/` |
| csharp | `csharp/` |
| swift | `swift/` |
| c, cpp | `c/` |
| bash | `bash/` |
| terraform | `terraform/` |
| dockerfile | `dockerfile/` |
| html, yaml, json, sql, css, markdown, toml | (skip — no Semgrep subdir) |

Always also include `$RULES_DIR/generic/` (if present) and `$RULES_DIR/owasp/` (if present) as cross-language packs.

Build a Semgrep `--config` argument string by concatenating the absolute paths of every selected subdir with one `--config` flag each.

If no language matches any rule subdir, append a row to the log with status `no-rules-applicable` and skip to phase A.6 (the report renderer will still emit a clean summary).

### A.4 Run Semgrep

```bash
SEMGREP_JSON="$RUN_DIR/_semgrep_raw.json"
SEMGREP_LOG="$RUN_DIR/_semgrep_stderr.log"

cd "$PROJECT_ROOT"

"$SEMGREP" \
  --metrics=off \
  --quiet \
  --json \
  --output "$SEMGREP_JSON" \
  <... one --config <subdir> flag per selected subdir, computed in A.3 ...> \
  "$PROJECT_ROOT" \
  2> "$SEMGREP_LOG" || true
```

> **Note.** Do NOT pass `--error` to Semgrep. With `--error`, Semgrep exits non-zero on any finding, which we don't want — Semgrep finding something is a successful scan, not a failure. The `|| true` above keeps the shell happy on non-zero exit codes from rule-internal issues; we determine failure separately by checking whether `$SEMGREP_JSON` is parseable.

Capture Semgrep's exit code separately. Non-zero exit with a parseable `_semgrep_raw.json` is acceptable. Non-zero exit with no JSON is a hard failure; print the stderr log and abort.

Time the invocation; capture wall seconds for the manifest.

### A.5 Normalize, enrich, and write findings.jsonl

```bash
python3 "<this-skill-dir>/scripts/normalize_semgrep.py" \
  "$SEMGREP_JSON" \
  --cwe-table "<this-skill-dir>/references/cwe-to-framework.json" \
  --repo-root "$PROJECT_ROOT" \
  --output "$RUN_DIR/findings.jsonl"
```

The normalizer:
- Computes canonical IDs per the v1.0 schema (`sha256(file | line_start | rule_id)`)
- Maps Semgrep ERROR/WARNING/INFO to securecoder's 5-level severity (with rule-id heuristics that escalate injection/secret patterns to `critical` when severity is ERROR)
- Maps Semgrep `metadata.confidence` to securecoder's 3-level confidence
- Enriches findings with `framework_refs` via the shipped CWE-to-framework table
- Pulls any OWASP Top 10 category tokens from Semgrep metadata into the same `framework_refs` list

Apply `severity_floor` from config: any finding with severity below the floor stays in the file but is tagged for the report's "informational" group rather than the headline counts.

### A.6 Write the manifest

```bash
SEMGREP_FOUND="$(wc -l < "$RUN_DIR/findings.jsonl" | tr -d ' ')"
REPO_SHA="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo no-git)"

python3 - <<PY
import json, os, time
manifest = {
  "schema_version": "1.0",
  "run_id": os.environ["RUN_ID"],
  "started_at": os.environ.get("STARTED_AT", ""),
  "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "repo_root": os.environ["PROJECT_ROOT"],
  "repo_sha": os.environ.get("REPO_SHA", "no-git"),
  "mode": "sast-only",
  "tools": {
    "semgrep": os.environ["SEMGREP_VERSION"]
  },
  "rule_packs": {
    "returntocorp/semgrep-rules": os.environ["SHA"]
  },
  "frameworks": {},
  "phases": {
    "sast": {
      "duration_s": int(os.environ.get("SAST_SECONDS", "0")),
      "findings": int(os.environ.get("SEMGREP_FOUND", "0")),
      "input_tokens": 0,
      "output_tokens": 0
    }
  },
  "totals": {
    "findings": int(os.environ.get("SEMGREP_FOUND", "0")),
    "duration_s": int(os.environ.get("SAST_SECONDS", "0"))
  }
}
with open(os.path.join(os.environ["RUN_DIR"], "manifest.json"), "w") as fh:
  json.dump(manifest, fh, indent=2)
  fh.write("\n")
PY
```

(Export the variables before calling: `STARTED_AT`, `RUN_ID`, `PROJECT_ROOT`, `REPO_SHA`, `SEMGREP_VERSION`, `SHA`, `SAST_SECONDS`, `SEMGREP_FOUND`, `RUN_DIR`.)

### A.7 Render the markdown report

```bash
python3 "<this-skill-dir>/scripts/render_markdown.py" \
  "$RUN_DIR/findings.jsonl" \
  --manifest "$RUN_DIR/manifest.json" \
  --output "$RUN_DIR/report.md"
```

The HTML report and cross-run trend section are placeholders in v0.2.0 — they land in slice 04.

### A.8 Update the `latest` pointer

```bash
LATEST="$PROJECT_ROOT/.securecoder/runs/latest"
# Symlink on POSIX; small JSON file fallback on Windows.
if ln -sfn "$RUN_ID" "$LATEST" 2>/dev/null; then
  : # symlink succeeded
else
  echo "{\"latest_run_id\": \"$RUN_ID\"}" > "$LATEST.json"
fi
```

If the symlink approach fails on Windows or restricted filesystems, the `.json` fallback satisfies the same role — downstream skills read either form.

### A.9 Write the `.securecoder/.gitignore` if it doesn't exist

```bash
GITIGNORE="$PROJECT_ROOT/.securecoder/.gitignore"
if [ ! -f "$GITIGNORE" ]; then
  cat > "$GITIGNORE" <<EOF
# Securecoder runtime state — local and per-developer
runs/
reviews/
EOF
fi
```

(`/securecoder-setup` writes this too; this step is a safety net for users who skipped setup.)

### A.10 Print the summary and exit

Output to the user, with substitutions:

```
securecoder-scan complete
  Run dir:     .securecoder/runs/$RUN_ID/
  Mode:        SAST only
  Findings:    <N> total (<critical> critical, <high> high, <medium> medium, <low> low, <info> info)
  Wall time:   <T>s
  LLM cost:    $0

  Report:      .securecoder/runs/$RUN_ID/report.md
  Findings:    .securecoder/runs/$RUN_ID/findings.jsonl
  Manifest:    .securecoder/runs/$RUN_ID/manifest.json

  Next steps:
    - /securecoder-fix       remediate findings (lands in v0.3.0)
    - cat .securecoder/runs/$RUN_ID/report.md     review the report
```

Append a final `COMPLETED` row to `$RUN_DIR/log.md`.

## Phase B — LLM compliance pass (not yet implemented)

If the user selected "LLM compliance only" or "Both" at the mode picker, do NOT run a compliance pass — that ships in slice 07. Instead, respond:

> The LLM compliance pass is not yet available in this release. It is tracked in slice 07 of the project backlog ([`docs/issues/07-scan-asvs-compliance-pass.md`](../../../docs/issues/07-scan-asvs-compliance-pass.md)). For now, the SAST-only mode is fully functional.
>
> Re-run `/securecoder-scan` and pick "SAST only" to proceed.

Do not proceed with phase A in this case. Exit cleanly.

## Failure handling

**Soft failures — log and continue.**

- Some files unreadable (permissions) → repo walker skips them and records nothing; scan still proceeds with the rest.
- Semgrep emits warnings on stderr but returns valid JSON → recorded in `_semgrep_stderr.log` and ignored.
- An individual Semgrep rule errors out internally → recorded in Semgrep's own `errors` array within the JSON; surface a one-line note in the run log but don't fail.

**Hard failures — write a crash report and exit.**

Triggers:
- `python3` not on PATH (Semgrep install impossible)
- `git` not on PATH (rule fetch impossible)
- Disk full or permission denied writing to `$RUN_DIR` or `$HOME/.cache/securecoder/`
- Semgrep returns non-zero AND wrote no `_semgrep_raw.json` AND no findings were captured
- The cached rule-pack directory's SHA doesn't match its name (integrity tamper)
- The user picked an unimplemented mode (this is a clean exit, not a crash — see Phase B)

On hard failure (not user abort or unimplemented-mode):

```bash
cat > "$RUN_DIR/crash_report.md" <<EOF
# Crash report — $RUN_ID
- Failed phase: <name>
- Failure mode: <one-line>
- Failed at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
- Last good phase: <name>

## Runlog up to failure
$(cat "$RUN_DIR/log.md")

## Last error
<verbatim stderr or exception trace>

## Remediation suggestions
- <suggestion 1>
- <suggestion 2>
EOF
```

Print a one-paragraph summary pointing the user at the crash report. Do not modify the user's working tree.

## Invariants

These hold at every phase boundary; if you ever observe one violated, that's itself a hard failure:

1. Every dispatched tool (Semgrep) has at least a recorded version in `installed.json` under `$TOOLS_DIR`.
2. Every fetched rule pack has a SHA recorded in its `manifest.json` and that SHA equals its parent directory name.
3. After a successful run, `$RUN_DIR/findings.jsonl` exists and every line parses as JSON conforming to v1.0 schema fields.
4. After a successful run, `$RUN_DIR/manifest.json` exists and includes `schema_version: "1.0"`, `run_id`, `tools`, `rule_packs`, and `phases.sast` keys.
5. `latest` (or `latest.json`) points at the most recent run id that completed without a `crash_report.md`.

## Notes for future slices

This SKILL.md is structured to absorb additional SAST tools (slice 03) and the compliance pass (slice 07) without major restructuring:

- New SAST tools each add: an installer block in A.1, an invocation block in A.4, a normalizer call in A.5 with their own `normalize_<tool>.py` script, and a row in `manifest.json.tools`.
- The compliance pass adds: a framework fetcher analogous to A.2, a relevance-filter step before invoking the LLM, the per-file/per-chapter dispatch loop, and a coverage-matrix validator. The findings normalize into the same `findings.jsonl` with `category: "compliance"`.
- The HTML report (slice 04) shares the manifest + findings inputs; `render_markdown.py` becomes one of two siblings (`render_html.py` being the other).
