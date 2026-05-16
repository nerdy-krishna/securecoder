---
name: securecoder-scan
description: Audit a codebase for vulnerabilities and OWASP compliance issues. Runs four SAST tools — Semgrep, Bandit, Gitleaks, OSV-scanner — and an LLM-driven compliance pass against OWASP ASVS v5 / MASVS / Proactive Controls. Emits findings in the unified securecoder schema, with markdown + HTML reports and run-history under .securecoder/runs/<id>/.
---

# `/securecoder-scan`

You are running the `/securecoder-scan` skill. Your job is to audit the user's codebase for security findings and write the results to `.securecoder/runs/<run-id>/`.

> **Scope.** All three scan modes are fully implemented and usable: SAST-only (Semgrep + Bandit + Gitleaks + OSV-scanner), LLM-compliance-only (ASVS v5 — and MASVS / Proactive Controls when configured), and Both. The mode picker in pre-flight step 3 routes between them; the SAST tools run in Phase A and the LLM compliance pass runs in Phase B.

## Pre-flight

### 1. Locate the project root

1. If a `.git/` directory exists in the current working directory or any ancestor, use the git toplevel (`git rev-parse --show-toplevel`).
2. Otherwise, use the current working directory.

Every relative path below is rooted here. Capture it as `PROJECT_ROOT`.

### 2. Load configuration

Read `<PROJECT_ROOT>/.securecoder/config.json` if it exists and is parseable. Otherwise use these defaults:

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

If the file is missing, mention once: "Running with default configuration. Run `/securecoder-setup` to customize."

### 3. Ask which mode to run

Show three options with token warnings. Use whatever interactive prompt mechanism the host agent supports.

- **SAST only** — Runs Semgrep, Bandit, Gitleaks, and OSV-scanner. Free in LLM tokens. Typical wall time: under a minute for a small repo, a few minutes for a large one.
- **LLM compliance only** — Runs the OWASP ASVS v5 compliance review (one LLM call per relevant file × chapter pair). Token-heavy: typical cost is dollars-to-tens-of-dollars depending on repo size and host model. See cost estimate below.
- **Both** *(Recommended for thorough audits)* — SAST first, then compliance. SAST findings often reveal issues the compliance pass would also flag, plus stuff compliance misses.

### 4. Generate the run ID and run directory

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_DIR="$PROJECT_ROOT/.securecoder/runs/$RUN_ID"
mkdir -p "$RUN_DIR"

cat > "$RUN_DIR/log.md" <<EOF
# securecoder-scan run — $RUN_ID

- Started: $STARTED_AT
- Mode: SAST only
- Project root: $PROJECT_ROOT

| Phase | Started | Finished | Status | Notes |
| --- | --- | --- | --- | --- |
EOF
```

### 5. Pre-flight cost estimate

For SAST-only mode the LLM cost is `$0` and wall time is bounded by tool execution. Print the estimate and get approval anyway so the gate flow is consistent with future modes.

```
Scan estimate for SAST-only mode:
  Files in scope:    (computed after repo walk)
  Tools to run:      Semgrep, Bandit, Gitleaks, OSV-scanner (per config.tools)
  LLM cost:          $0
  Will install:      Any of the four tools not already cached in ~/.cache/securecoder/tools/
  Will fetch:        returntocorp/semgrep-rules at the pinned tag (if not cached)

Continue? [proceed / abort]
```

Wait for `proceed`. On `abort`, append `cancelled-at-estimate` to the log and exit cleanly.

## Phase A — SAST (multi-tool)

### A.0 Determine which tools to run

Read `config.tools` from `.securecoder/config.json`. For each of the four tools (`semgrep`, `bandit`, `gitleaks`, `osv-scanner`), resolve:

- `enabled`: `config.tools.<tool>.enabled` if present, else `true`.
- `path`: optional `config.tools.<tool>.path` for using a system-installed binary instead of the cached one.

**Auto-skip OSV-scanner if no dependency manifest exists.** Before deciding to run OSV-scanner, check whether any of these manifests live in the project (search up to 3 levels deep):

```
package.json, package-lock.json, yarn.lock, pnpm-lock.yaml,
requirements.txt, pyproject.toml, poetry.lock, Pipfile.lock,
go.sum, go.mod,
Cargo.lock,
Gemfile.lock,
composer.lock,
pubspec.lock,
mix.lock
```

If none are present, set OSV-scanner's status to `skipped_no_lockfile` and don't attempt to install or run it. Note this in the run log.

### A.1 Detect OS + architecture

```bash
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"   # darwin | linux
ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
  x86_64|amd64) ARCH=amd64 ;;
  arm64|aarch64) ARCH=arm64 ;;
  *) ARCH="$ARCH_RAW" ;;
esac
```

Used by binary downloads in A.2.c and A.2.d. For Windows hosts, detect via `$env:OS == 'Windows_NT'` or equivalent and substitute `OS=windows`.

### A.2 Ensure each enabled tool is installed

The user gave a one-time consent the first time any tool was installed (recorded at `~/.cache/securecoder/manifest.json`). Per-version installs after that are silent. If the consent record doesn't exist yet, ask once:

> securecoder needs to install up to four tools (~200MB total): Semgrep, Bandit, Gitleaks, OSV-scanner. They'll be cached under `~/.cache/securecoder/tools/` and never touch your system Python or PATH. Proceed?

Record consent on approval:

```bash
mkdir -p "$HOME/.cache/securecoder"
cat > "$HOME/.cache/securecoder/manifest.json" <<EOF
{
  "consent": { "tools": true, "granted_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)" }
}
EOF
```

Per-tool installation follows. For each, check `~/.cache/securecoder/tools/<tool>/installed.json` against the pinned version below; install or upgrade only on mismatch.

#### A.2.a Semgrep — pinned `1.91.0`

```bash
SEMGREP_VERSION="1.91.0"
TOOL_DIR="$HOME/.cache/securecoder/tools/semgrep"
INSTALLED="$TOOL_DIR/installed.json"
SEMGREP_BIN="$TOOL_DIR/venv/bin/semgrep"

if [ ! -x "$SEMGREP_BIN" ] || ! grep -q "\"version\": \"$SEMGREP_VERSION\"" "$INSTALLED" 2>/dev/null; then
  mkdir -p "$TOOL_DIR"
  python3 -m venv "$TOOL_DIR/venv"
  "$TOOL_DIR/venv/bin/pip" install --quiet --upgrade pip
  "$TOOL_DIR/venv/bin/pip" install --quiet "semgrep==$SEMGREP_VERSION"
  cat > "$INSTALLED" <<EOF
{"version": "$SEMGREP_VERSION", "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "binary": "$SEMGREP_BIN"}
EOF
fi
```

#### A.2.b Bandit — pinned `1.7.10`

```bash
BANDIT_VERSION="1.7.10"
TOOL_DIR="$HOME/.cache/securecoder/tools/bandit"
INSTALLED="$TOOL_DIR/installed.json"
BANDIT_BIN="$TOOL_DIR/venv/bin/bandit"

if [ ! -x "$BANDIT_BIN" ] || ! grep -q "\"version\": \"$BANDIT_VERSION\"" "$INSTALLED" 2>/dev/null; then
  mkdir -p "$TOOL_DIR"
  python3 -m venv "$TOOL_DIR/venv"
  "$TOOL_DIR/venv/bin/pip" install --quiet --upgrade pip
  "$TOOL_DIR/venv/bin/pip" install --quiet "bandit==$BANDIT_VERSION"
  cat > "$INSTALLED" <<EOF
{"version": "$BANDIT_VERSION", "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "binary": "$BANDIT_BIN"}
EOF
fi
```

#### A.2.c Gitleaks — pinned `8.18.4`

Asset naming for the 8.x line:

| OS | ARCH | Asset name |
| --- | --- | --- |
| darwin | arm64 | `gitleaks_8.18.4_darwin_arm64.tar.gz` |
| darwin | amd64 | `gitleaks_8.18.4_darwin_x64.tar.gz` |
| linux | amd64 | `gitleaks_8.18.4_linux_x64.tar.gz` |
| linux | arm64 | `gitleaks_8.18.4_linux_arm64.tar.gz` |
| windows | amd64 | `gitleaks_8.18.4_windows_x64.zip` |

Note Gitleaks uses `x64` (not `amd64`) for x86_64 in its asset names. Map accordingly.

```bash
GITLEAKS_VERSION="8.18.4"
TOOL_DIR="$HOME/.cache/securecoder/tools/gitleaks"
INSTALLED="$TOOL_DIR/installed.json"
GITLEAKS_BIN="$TOOL_DIR/gitleaks"

if [ ! -x "$GITLEAKS_BIN" ] || ! grep -q "\"version\": \"$GITLEAKS_VERSION\"" "$INSTALLED" 2>/dev/null; then
  mkdir -p "$TOOL_DIR"
  case "$ARCH" in
    amd64) GLA="x64" ;;
    *) GLA="$ARCH" ;;
  esac
  case "$OS" in
    darwin|linux) EXT="tar.gz" ;;
    windows) EXT="zip" ;;
  esac
  ASSET="gitleaks_${GITLEAKS_VERSION}_${OS}_${GLA}.${EXT}"
  URL="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${ASSET}"
  curl -fsSL "$URL" -o "$TOOL_DIR/_pkg.${EXT}"
  case "$EXT" in
    tar.gz) tar -xzf "$TOOL_DIR/_pkg.tar.gz" -C "$TOOL_DIR" gitleaks ;;
    zip) (cd "$TOOL_DIR" && unzip -o _pkg.zip gitleaks.exe && mv gitleaks.exe gitleaks) ;;
  esac
  rm -f "$TOOL_DIR/_pkg.${EXT}"
  chmod +x "$GITLEAKS_BIN" 2>/dev/null || true
  cat > "$INSTALLED" <<EOF
{"version": "$GITLEAKS_VERSION", "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "binary": "$GITLEAKS_BIN"}
EOF
fi
```

#### A.2.d OSV-scanner — pinned `1.9.2`

Asset naming for the 1.9.x line (direct binary, no archive):

| OS | ARCH | Asset name |
| --- | --- | --- |
| darwin | arm64 | `osv-scanner_1.9.2_darwin_arm64` |
| darwin | amd64 | `osv-scanner_1.9.2_darwin_amd64` |
| linux | amd64 | `osv-scanner_1.9.2_linux_amd64` |
| linux | arm64 | `osv-scanner_1.9.2_linux_arm64` |
| windows | amd64 | `osv-scanner_1.9.2_windows_amd64.exe` |

```bash
OSV_VERSION="1.9.2"
TOOL_DIR="$HOME/.cache/securecoder/tools/osv-scanner"
INSTALLED="$TOOL_DIR/installed.json"
OSV_BIN="$TOOL_DIR/osv-scanner"

if [ ! -x "$OSV_BIN" ] || ! grep -q "\"version\": \"$OSV_VERSION\"" "$INSTALLED" 2>/dev/null; then
  mkdir -p "$TOOL_DIR"
  EXT=""
  [ "$OS" = "windows" ] && EXT=".exe"
  ASSET="osv-scanner_${OSV_VERSION}_${OS}_${ARCH}${EXT}"
  URL="https://github.com/google/osv-scanner/releases/download/v${OSV_VERSION}/${ASSET}"
  curl -fsSL "$URL" -o "$OSV_BIN"
  chmod +x "$OSV_BIN" 2>/dev/null || true
  cat > "$INSTALLED" <<EOF
{"version": "$OSV_VERSION", "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "binary": "$OSV_BIN"}
EOF
fi
```

#### Offline mode

If `python3 -m venv` fails because the venv module isn't installed (some minimal Linux distros), or any of the binary downloads fail because there's no network AND the cache is empty for that tool, fail with:

> Source `<tool>@<version>` needs network access to install. Either connect to the internet and re-run, or pre-populate `~/.cache/securecoder/tools/<tool>/` from another machine. To skip this tool, set `config.tools.<tool>.enabled = false` in `.securecoder/config.json`.

### A.3 Fetch Semgrep rule packs (Semgrep only)

Same as v0.2.0. Pinned upstream: **`returntocorp/semgrep-rules` at branch `main`**, content-addressed by the resulting commit SHA. The other three tools ship rules bundled and need no rule fetch.

```bash
RULES_REPO="https://github.com/returntocorp/semgrep-rules.git"
RULES_BRANCH="main"
RULES_CACHE_ROOT="$HOME/.cache/securecoder/rules/semgrep"
TMP_CLONE="$RULES_CACHE_ROOT/_tmp_clone"

mkdir -p "$RULES_CACHE_ROOT"
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

Integrity: verify the cached dir name matches its `sha`. Mismatch refuses to run.

### A.4 Walk the repo

Run the bundled walker:

```bash
python3 "<this-skill-dir>/scripts/repo_walker.py" "$PROJECT_ROOT" \
  --output "$RUN_DIR/repo_map.json"
```

Read the resulting `languages` map. Use it to:

- **Pick Semgrep rule subdirs** per the table below. Always also include `$RULES_DIR/generic/` and `$RULES_DIR/owasp/` (when present).
- **Decide whether Bandit runs** — only if `python` ≥ 1 file.
- **Decide whether Gitleaks runs** — always (file-type agnostic).

| Detected language | Semgrep rules subdir |
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
| html, yaml, json, sql, css, markdown, toml | (skip) |

### A.5 Run each enabled tool

Run sequentially. For each tool, time it, capture stderr to a per-tool log, write raw JSON to `_<tool>_raw.json` in the run dir.

**Per-tool soft failure policy.** If a tool fails to run (crashes, exits with no parseable JSON, times out), log it to `log.md` with status `failed`, set `phases.sast.per_tool.<tool>.status = "failed"` in the manifest, and continue with the other tools. The overall scan still succeeds — just with fewer findings.

#### A.5.a Semgrep

```bash
SEMGREP_RAW="$RUN_DIR/_semgrep_raw.json"
"$SEMGREP_BIN" --metrics=off --quiet --json --output "$SEMGREP_RAW" \
  <one --config <subdir> flag per selected subdir from A.4> \
  "$PROJECT_ROOT" 2> "$RUN_DIR/_semgrep_stderr.log" || true
```

Do NOT pass `--error` — Semgrep finding something is a successful scan, not a failure. The `|| true` lets us check JSON existence rather than exit code.

#### A.5.b Bandit (skip if no Python files in repo)

```bash
BANDIT_RAW="$RUN_DIR/_bandit_raw.json"
"$BANDIT_BIN" -r "$PROJECT_ROOT" -f json -o "$BANDIT_RAW" \
  --exit-zero -x "**/.securecoder/**,**/node_modules/**,**/.venv/**,**/venv/**" \
  2> "$RUN_DIR/_bandit_stderr.log" || true
```

`--exit-zero` makes Bandit always exit 0; we determine success by whether `$BANDIT_RAW` is valid JSON.

#### A.5.c Gitleaks

```bash
GITLEAKS_RAW="$RUN_DIR/_gitleaks_raw.json"
"$GITLEAKS_BIN" detect --no-banner --report-format json \
  --report-path "$GITLEAKS_RAW" --source "$PROJECT_ROOT" \
  --exit-code 0 2> "$RUN_DIR/_gitleaks_stderr.log" || true
```

`--exit-code 0` makes Gitleaks exit 0 even when secrets are found (success = scan ran; secrets = findings, not error).

When the repo has no `.git/` directory, Gitleaks falls back to filesystem mode, which is what we want for repos outside version control.

#### A.5.d OSV-scanner (skip if `phases.sast.per_tool.osv-scanner.status` was set to `skipped_no_lockfile` in A.0)

```bash
OSV_RAW="$RUN_DIR/_osv_raw.json"
"$OSV_BIN" --format json --output "$OSV_RAW" "$PROJECT_ROOT" \
  2> "$RUN_DIR/_osv_stderr.log" || true
```

**OSV network handling.** OSV-scanner needs `api.osv.dev` reachable. If the network call fails, OSV exits non-zero and `$OSV_RAW` may be empty or malformed. Record `phases.sast.per_tool.osv-scanner.status = "failed_no_network"` and continue. Don't abort the whole scan.

### A.6 Normalize each tool's output

For each tool that produced parseable JSON, run its normalizer. The normalizers all accept the same arguments and emit JSONL to the per-tool intermediate file.

```bash
python3 "<skill-dir>/scripts/normalize_semgrep.py"  "$SEMGREP_RAW"  --cwe-table "<skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$RUN_DIR/_findings_semgrep.jsonl"
python3 "<skill-dir>/scripts/normalize_bandit.py"   "$BANDIT_RAW"   --cwe-table "<skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$RUN_DIR/_findings_bandit.jsonl"
python3 "<skill-dir>/scripts/normalize_gitleaks.py" "$GITLEAKS_RAW" --cwe-table "<skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$RUN_DIR/_findings_gitleaks.jsonl"
python3 "<skill-dir>/scripts/normalize_osv.py"      "$OSV_RAW"      --cwe-table "<skill-dir>/references/cwe-to-framework.json" --repo-root "$PROJECT_ROOT" --output "$RUN_DIR/_findings_osv.jsonl"
```

(Only run a normalizer when its raw input exists and the corresponding tool's status is `"ok"`.)

### A.7 Merge per-tool JSONL into one `findings.jsonl`

```bash
: > "$RUN_DIR/findings.jsonl"   # truncate
for tool in semgrep bandit gitleaks osv; do
  intermediate="$RUN_DIR/_findings_${tool}.jsonl"
  [ -s "$intermediate" ] && cat "$intermediate" >> "$RUN_DIR/findings.jsonl"
done
```

Canonical IDs are deterministic and per-tool prefixes in `source` keep cross-tool collisions impossible.

### A.7.3 Scan for in-source suppression annotations (v1.2.0)

Before applying suppressions, walk the project for `# securecoder: ignore` (and `// securecoder: ignore`) annotations. The scanner emits ephemeral suppression entries the next step merges with the persistent `suppressions.json`:

```bash
python3 "<skill-dir>/scripts/scan_annotations.py" "$PROJECT_ROOT" \
  --output "$RUN_DIR/_annotations.json"
```

Annotation syntax:
- `# securecoder: ignore` — applies to the next non-blank code line
- `# securecoder: ignore reason="..."` — same, with explicit reason
- `# securecoder: ignore reason="..." expires="2027-01-01"` — same, with expiry
- Inline form (end of code line) — applies to that line

The scanner outputs a JSON array of ephemeral entries with `source: "annotation"` and `created_by: "<annotation>"`. Block comments (`/* ... */`) are not yet recognized — v1.2.0 line comments only.

### A.7.5 Apply suppressions

Mark matching findings as suppressed in-place. Merges persistent entries from `.securecoder/suppressions.json` (if present) with ephemeral annotation entries from A.7.3 above. See [`docs/design.md` § 3.9](../../../docs/design.md) for the matching semantics and most-specific-wins resolution.

```bash
SUPPRESSIONS_PATH="$PROJECT_ROOT/.securecoder/suppressions.json"
ANN_ARG=""
if [ -s "$RUN_DIR/_annotations.json" ]; then
  ANN_ARG="--annotations $RUN_DIR/_annotations.json"
fi

if [ -f "$SUPPRESSIONS_PATH" ] || [ -n "$ANN_ARG" ]; then
  python3 "<skill-dir>/scripts/apply_suppressions.py" \
    "$RUN_DIR/findings.jsonl" \
    --suppressions "${SUPPRESSIONS_PATH:-/dev/null}" \
    $ANN_ARG \
    --output "$RUN_DIR/findings.jsonl" \
    --stats "$RUN_DIR/_suppression_stats.json"
else
  # No suppressions file AND no annotations = no-op; create an empty
  # stats record so the manifest writer below has a consistent input.
  echo '{"totals":{"findings":0,"findings_active":0,"findings_suppressed":0},"suppressed_by_entry":{}}' \
    > "$RUN_DIR/_suppression_stats.json"
fi
```

Findings matching a suppression get `status: "suppressed"`, plus two new fields: `suppression_reason` (the winning entry's reason) and `suppression_match` (e.g., `suppressions.json#3`, where `3` is the entry index). Expired entries (past their `expires_at`) are ignored at match time but remain in `suppressions.json` for audit. `_suppression_stats.json` feeds the manifest builder in A.9.

### A.8 Compute the trend vs prior runs

Before writing the manifest, compare this run's findings to the most recent prior run in `.securecoder/runs/`:

```bash
python3 "<skill-dir>/scripts/compute_trend.py" \
  "$RUN_DIR/findings.jsonl" \
  --runs-dir "$PROJECT_ROOT/.securecoder/runs" \
  --current-run-id "$RUN_ID" \
  --output "$RUN_DIR/_trend.json"
```

`_trend.json` is an intermediate file; its contents get embedded into `manifest.json` under the `trend` key in A.9.

If no prior run exists, `compute_trend.py` still emits a valid file with `previous_run_id: null` and empty buckets. The renderers interpret that as "first run for this project."

### A.9 Write the manifest

```bash
REPO_SHA="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo no-git)"

python3 - <<PY
import json, os, time
def count(p):
  try:
    with open(p) as fh: return sum(1 for line in fh if line.strip())
  except OSError: return 0
def get_tool_version(name):
  try:
    with open(os.path.expanduser(f"~/.cache/securecoder/tools/{name}/installed.json")) as fh:
      return json.load(fh).get("version", "")
  except OSError: return "skipped"
def load_json(p, default=None):
  try:
    with open(p) as fh: return json.load(fh)
  except OSError: return default

run_dir = os.environ["RUN_DIR"]
per_tool = {}
for tool, friendly in [("semgrep","semgrep"),("bandit","bandit"),
                        ("gitleaks","gitleaks"),("osv","osv-scanner")]:
  intermediate = f"{run_dir}/_findings_{tool}.jsonl"
  per_tool[friendly] = {
    "duration_s": int(os.environ.get(f"{tool.upper()}_SECONDS", "0")),
    "findings": count(intermediate),
    "status": os.environ.get(f"{tool.upper()}_STATUS", "ok"),
  }

trend = load_json(f"{run_dir}/_trend.json")
sup_stats = load_json(f"{run_dir}/_suppression_stats.json", default={}) or {}
sup_totals = sup_stats.get("totals", {})
suppressed_by_entry = sup_stats.get("suppressed_by_entry", {})

total_findings = count(f"{run_dir}/findings.jsonl")

manifest = {
  "schema_version": "1.0",
  "run_id": os.environ["RUN_ID"],
  "started_at": os.environ["STARTED_AT"],
  "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "repo_root": os.environ["PROJECT_ROOT"],
  "repo_sha": os.environ.get("REPO_SHA", "no-git"),
  "mode": "sast-only",
  "tools": {
    "semgrep": get_tool_version("semgrep"),
    "bandit": get_tool_version("bandit"),
    "gitleaks": get_tool_version("gitleaks"),
    "osv-scanner": get_tool_version("osv-scanner"),
  },
  "rule_packs": {
    "returntocorp/semgrep-rules": os.environ.get("SHA", "")
  },
  "frameworks": {},
  "phases": {
    "sast": {
      "duration_s": sum(t["duration_s"] for t in per_tool.values()),
      "findings": total_findings,
      "input_tokens": 0,
      "output_tokens": 0,
      "per_tool": per_tool,
    }
  },
  "trend": trend,
  "suppressed_by_entry": suppressed_by_entry,
  "totals": {
    "findings": total_findings,
    "findings_active": sup_totals.get("findings_active", total_findings),
    "findings_suppressed": sup_totals.get("findings_suppressed", 0),
    "duration_s": sum(t["duration_s"] for t in per_tool.values())
  }
}
with open(f"{run_dir}/manifest.json", "w") as fh:
  json.dump(manifest, fh, indent=2)
  fh.write("\n")
PY
```

Export the variables before calling: `RUN_ID`, `STARTED_AT`, `PROJECT_ROOT`, `REPO_SHA`, `SHA` (Semgrep rules), `RUN_DIR`, plus `<TOOL>_SECONDS` and `<TOOL>_STATUS` for each tool (`SEMGREP_SECONDS`, `SEMGREP_STATUS`, `BANDIT_SECONDS`, etc.).

### A.10 Render the markdown and HTML reports

```bash
SUPPRESSIONS_ARG=""
if [ -f "$PROJECT_ROOT/.securecoder/suppressions.json" ]; then
  SUPPRESSIONS_ARG="--suppressions $PROJECT_ROOT/.securecoder/suppressions.json"
fi

python3 "<skill-dir>/scripts/render_markdown.py" "$RUN_DIR/findings.jsonl" \
  --manifest "$RUN_DIR/manifest.json" --output "$RUN_DIR/report.md"

python3 "<skill-dir>/scripts/render_html.py" "$RUN_DIR/findings.jsonl" \
  --manifest "$RUN_DIR/manifest.json" $SUPPRESSIONS_ARG \
  --output "$RUN_DIR/report.html"
```

The HTML report is self-contained: inlined CSS in a `<style>` block, inlined filtering JS in a `<script>` block, no external resources. It includes client-side filtering by severity / source / framework and a free-text search across file path / title / description / evidence. Opens in any modern browser with networking disabled.

The trend section (in both formats) compares this run's findings to the most recent prior run by canonical ID, showing new / resolved / persistent counts. On the first run, it shows "First run — no trend data yet."

### A.11 Update the `latest` pointer

```bash
LATEST="$PROJECT_ROOT/.securecoder/runs/latest"
if ln -sfn "$RUN_ID" "$LATEST" 2>/dev/null; then
  :
else
  echo "{\"latest_run_id\": \"$RUN_ID\"}" > "$LATEST.json"
fi
```

### A.12 Ensure `.securecoder/.gitignore`

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

### A.13 Print the summary

```
securecoder-scan complete
  Run dir:     .securecoder/runs/$RUN_ID/
  Mode:        SAST only
  Findings:    <total> total (<crit> critical, <high> high, <med> medium, <low> low, <info> info)
  Per tool:
    semgrep:     <N> findings (<status>, <T>s)
    bandit:      <N> findings (<status>, <T>s)
    gitleaks:    <N> findings (<status>, <T>s)
    osv-scanner: <N> findings (<status>, <T>s)
  Wall time:   <total>s
  LLM cost:    $0

  Report:      .securecoder/runs/$RUN_ID/report.md
  Findings:    .securecoder/runs/$RUN_ID/findings.jsonl
  Manifest:    .securecoder/runs/$RUN_ID/manifest.json

  Next steps:
    - /securecoder-fix       remediate findings (lands in v0.5.0)
    - cat .securecoder/runs/$RUN_ID/report.md     review the report
```

Append `COMPLETED` to the run log.

## Phase B — LLM compliance pass

Only runs when the user picked "LLM compliance only" or "Both" at the mode picker. Iterates over file × chapter pairs from the relevance filter, dispatches one LLM call per pair, validates the coverage matrix is complete (one retry if incomplete), and merges compliance findings into the same `findings.jsonl` as Phase A.

> **HITL — prompt template under maintainer review.** The architect prompt at `<skill-dir>/references/asvs-architect-prompt.md` is high-leverage. Changes to it should go through a manual review before merge.

### B.0 Determine which frameworks are active

Read `config.frameworks` from `.securecoder/config.json` (default: `["asvs-v5"]`).

The framework registry at `<skill-dir>/references/frameworks.json` declares supported frameworks:

- **`secure-coding-essentials`** — `layer: "baseline"`, bundled in this skill. The universal baseline; runs on every compliance scan unless `config.baseline_enabled` is `false`. Not subject to fit-detection.
- **`asvs-v5`** — `layer: "overlay"`, fully scannable, default-enabled
- **`masvs`** — `layer: "overlay"`, fully scannable, auto-enabled when `_mobile_stack_signals` patterns match files in the repo (iOS / Android / Kotlin / Swift / React Native / Flutter)
- **`proactive-controls`** — `layer: "overlay"`, fully scannable, opt-in via `/securecoder-setup`
- **`cheatsheets`** — NOT scanned against; fetched for `/securecoder-fix` remediation context and `/securecoder-advise` grounding

**Construct the active set:** start with `secure-coding-essentials` (unless `config.baseline_enabled` is `false`), then add every overlay framework listed in `config.frameworks`. That combined set is what B.0.5's fit-check and B.1–B.6 operate on.

**Mobile-stack auto-detection** — before deciding the active framework list, check whether any file in the repo matches the `_mobile_stack_signals` globs from `frameworks.json`. If yes AND `masvs` isn't already enabled, add it to the active list and log a note: "Detected mobile stack; auto-enabled MASVS. Disable in /securecoder-setup if unwanted."

**The baseline framework always runs.** `secure-coding-essentials` (`layer: "baseline"`) is included in the active set on every compliance scan regardless of `config.frameworks`, unless `config.baseline_enabled` is explicitly `false`. The `config.frameworks` list governs *overlay*-layer frameworks only. See [`docs/design.md` §3.10](../../../docs/design.md).

For each active framework that's `scannable: true`, run Phases B.1–B.6 below in turn. Each framework writes its findings into the same merged `findings.jsonl`. Cheatsheets (when enabled) are fetched but not scanned.

### B.0.5 Framework fit check

Before fetching any chapter content or estimating cost, check whether the active *overlay* frameworks actually fit the repo. `baseline`-layer frameworks skip this check — they always run.

First ensure a repo map exists (the walker is cheap and idempotent; B.2 reuses this file):

```bash
[ -f "$RUN_DIR/repo_map.json" ] || python3 "<skill-dir>/scripts/repo_walker.py" \
  "$PROJECT_ROOT" --output "$RUN_DIR/repo_map.json"
```

Then run the fit checker. The threshold comes from `config.framework_fit.poor_fit_threshold_pct` (default 15):

```bash
python3 "<skill-dir>/scripts/fit_check.py" \
  "$RUN_DIR/repo_map.json" \
  --frameworks-json "<skill-dir>/references/frameworks.json" \
  --active "<comma-separated active framework ids>" \
  --repo-root "$PROJECT_ROOT" \
  --threshold "<config.framework_fit.poor_fit_threshold_pct, default 15>" \
  --json > "$RUN_DIR/_fit_check.json"
```

Read `_fit_check.json`. Two outcomes:

- **`poor_fit` is empty** — every active overlay fits (or is rescued by a signal file). Proceed to B.1 with the full active set.
- **`poor_fit` is non-empty** — one or more active overlays are a poor fit. Warn the user before doing any expensive work:

  ```
  Framework fit check:
    secure-coding-essentials  — baseline, always runs       ✓
    asvs-v5                   — poor fit (<fit_pct>% of files are
                                target languages; repo is <top languages>)  ⚠

    <poor-fit framework> targets <its domain>. On this repo it will
    produce mostly "N/A" coverage rows and burn tokens for little
    signal. The secure-coding-essentials baseline already covers the
    universal concerns (memory safety, integer handling, concurrency,
    injection, error handling, ...) that matter for this code.

  Continue?
    [recommended]   Run secure-coding-essentials + any good-fit overlays
                    only (skip the poor-fit overlays this run)
    [as-configured] Run every active framework anyway
    [abort]         Exit
  ```

  - `recommended` — drop the `poor_fit` framework ids from the active set *for this run only*. Does NOT rewrite `.securecoder/config.json`. Append a note: "To make this permanent, run `/securecoder-setup` and disable `<framework>`."
  - `as-configured` — keep the full active set.
  - `abort` — clean exit, no scan performed.

If `_fit_check.json`'s `suggested_enable` is non-empty, also surface it: "This repo's language profile matches `<framework>`, which isn't enabled — consider enabling it in `/securecoder-setup`."

The active set after this step (post-`recommended`-pruning, if chosen) is what B.1–B.6 iterate over, and what the B.3 cost estimate is computed from.

### B.1 Resolve the framework's chapter content

A framework's `frameworks.json` entry has a `source` field. Two cases:

**`source: "bundled"`** (e.g., `secure-coding-essentials`) — the chapters ship inside this skill. No fetch. Point `CHAPTERS_DIR` straight at the bundled path:

```bash
# For a bundled framework, e.g. secure-coding-essentials:
CHAPTERS_DIR="<skill-dir>/$(framework's bundled_path from frameworks.json)"
# e.g. <skill-dir>/references/frameworks/secure-coding-essentials
```

There is no SHA, no cache dir, no network — skip directly to B.2 with `CHAPTERS_DIR` set. Bundled frameworks are always available offline.

**`source: <git URL>`** (e.g., `asvs-v5`) — fetch + cache as below.

Pinned upstream for ASVS: **`OWASP/ASVS` at branch `master`** (the OWASP repo doesn't tag every release; we content-address by the resulting SHA, same model as the Semgrep rule pack).

```bash
ASVS_REPO="https://github.com/OWASP/ASVS.git"
ASVS_BRANCH="master"
ASVS_CACHE_ROOT="$HOME/.cache/securecoder/rules/frameworks/asvs"
TMP_CLONE="$ASVS_CACHE_ROOT/_tmp_clone"

mkdir -p "$ASVS_CACHE_ROOT"
REUSE_DIR=""
for d in "$ASVS_CACHE_ROOT"/*/; do
  [ -d "$d/5.0/en" ] || continue
  if [ -f "$d/manifest.json" ]; then
    REUSE_DIR="$d"
    break
  fi
done

if [ -z "$REUSE_DIR" ]; then
  rm -rf "$TMP_CLONE"
  git clone --depth 1 --branch "$ASVS_BRANCH" "$ASVS_REPO" "$TMP_CLONE" 2>&1
  ASVS_SHA="$(git -C "$TMP_CLONE" rev-parse HEAD)"
  FINAL_DIR="$ASVS_CACHE_ROOT/$ASVS_SHA"
  if [ -d "$FINAL_DIR" ]; then
    rm -rf "$TMP_CLONE"
  else
    mv "$TMP_CLONE" "$FINAL_DIR"
    cat > "$FINAL_DIR/manifest.json" <<EOF
{"source": "$ASVS_REPO", "branch": "$ASVS_BRANCH", "sha": "$ASVS_SHA", "fetched_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
  fi
  ASVS_DIR="$FINAL_DIR"
else
  ASVS_DIR="$REUSE_DIR"
  ASVS_SHA="$(python3 -c "import json; print(json.load(open('$ASVS_DIR/manifest.json'))['sha'])")"
fi

CHAPTERS_DIR="$ASVS_DIR/5.0/en"
```

Allowlist: `OWASP/*` is auto-allowed (covered by the v0.2.0 trust model). Integrity check: cache dir name must match its `manifest.json.sha`.

Offline-fail message follows the same pattern as A.2.

### B.2 Build the file × chapter dispatch list

```bash
python3 "<skill-dir>/scripts/file_relevance.py" \
  "$RUN_DIR/repo_map.json" \
  --chapter-relevance "<skill-dir>/references/relevance-<framework>.json" \
  --repo-root "$PROJECT_ROOT" \
  --output "$RUN_DIR/_compliance_pairs.json"
```

The filter cuts the dispatch list to relevant pairs only — files whose language matches the chapter, with optional keyword-trigger gating. Read the output's `total_pairs` count for the cost estimate.

If `total_pairs` is 0, skip the compliance pass entirely and proceed to A.6 (normalize) with only SAST findings. Set `manifest.phases.compliance.status = "skipped_no_pairs"`.

### B.3 Show the user the compliance cost estimate

```
Compliance pass estimate (ASVS v5):
  Files in scope:           <N>
  File × chapter pairs:     <P>  (filtered down from <N × 17>)
  LLM calls expected:       <P>  (one per pair)
  Estimated input tokens:   ~<P × 20000> = <T_in>
  Estimated output tokens:  ~<P × 5000> = <T_out>

Approximate cost at common rates:
  Claude Opus 4.7:    $<X.XX>      (input $15/M, output $75/M)
  Claude Sonnet 4.6:  $<Y.YY>      (input $3/M,  output $15/M)
  Claude Haiku 4.5:   $<Z.ZZ>      (input $1/M,  output $5/M)

Wall time estimate (sequential dispatch): ~<P × 30s> = <hours/minutes>

Continue? [proceed / abort]
```

Wait for `proceed`. On `abort`, append `cancelled-at-compliance-estimate` to the run log and skip Phase B (Phase A's results still produce a valid report).

### B.4 Dispatch each pair (sequential)

For each pair in `_compliance_pairs.json`:

1. **Compose the prompt.** Read the architect prompt template at `<skill-dir>/references/asvs-architect-prompt.md`. Read the chapter content from `$CHAPTERS_DIR/<filename>`. Read the target file (relative to PROJECT_ROOT) with line numbers prefixed for citation. Substitute the `{{...}}` variables:
   - `{{chapter_id}}` → e.g. `V1`
   - `{{chapter_title}}` → e.g. `Encoding and Sanitization`
   - `{{chapter_content}}` → full chapter markdown
   - `{{file_path}}` → relative path
   - `{{language}}` → detected language
   - `{{line_count}}` → file line count
   - `{{file_content_with_line_numbers}}` → file content with each line prefixed by `NNN: `

2. **Dispatch the LLM call.** This is a single host-LLM turn. The host agent reads the composed prompt and produces the response. Save the response to `$RUN_DIR/_compliance/<NNNN>_<chapter_id>_<file-slug>.md`. (Pad the index to 4 digits.)

3. **Validate the coverage matrix.** Pass the framework's control-ID regexes from its `frameworks.json` entry (`control_id_regex` and `control_id_response_regex`) so validation works for ASVS's three-number IDs, MASVS's `MASVS-STORAGE-1` form, `secure-coding-essentials`'s `SCE-MEM-1` form, etc. When the regexes are omitted, validate_coverage defaults to the ASVS form.

   ```bash
   python3 "<skill-dir>/scripts/validate_coverage.py" \
     "$CHAPTERS_DIR/<chapter_filename>" \
     "$RUN_DIR/_compliance/<NNNN>_<chapter_id>_<file-slug>.md" \
     --chapter-regex "<framework.control_id_regex>" \
     --response-regex "<framework.control_id_response_regex>" \
     --json > "$RUN_DIR/_compliance/<NNNN>_validation.json"
   ```

   If `status: "incomplete"` → retry once. The retry prompt appends:

   > **Retry context (try 2 of 2)**
   >
   > Your previous response was missing coverage matrix rows for: `<missing-control-ids>`. Re-emit the complete two-section response. Every control ID listed in the chapter must have exactly one row in the coverage matrix.

   On second failure (still incomplete) → mark this pair `architect_incomplete` in the run log and skip it (no findings emitted for this pair, but the scan as a whole continues).

4. **Normalize compliance findings.**

   ```bash
   python3 "<skill-dir>/scripts/normalize_compliance.py" \
     "$RUN_DIR/_compliance/<NNNN>_<chapter_id>_<file-slug>.md" \
     --framework asvs-v5 \
     --chapter-id "<chapter_id>" \
     --cwe-table "<skill-dir>/references/cwe-to-framework.json" \
     --repo-root "$PROJECT_ROOT" \
     --output "$RUN_DIR/_compliance/<NNNN>_findings.jsonl"
   ```

5. **Append to the merged findings file.** After all pairs are processed, concatenate `_compliance/*_findings.jsonl` into `findings.jsonl` alongside the SAST findings.

### B.5 Update the manifest

Add a `compliance` phase entry to `phases`:

```json
"phases": {
  "sast": { ... },
  "compliance": {
    "duration_s": <total seconds>,
    "findings": <count>,
    "input_tokens": <est sum>,
    "output_tokens": <est sum>,
    "frameworks_run": ["asvs-v5"],
    "pairs_total": <P>,
    "pairs_successful": <P-skipped>,
    "pairs_architect_incomplete": <N>,
    "status": "ok" | "partial" | "failed"
  }
}
```

Also populate `manifest.frameworks`:

```json
"frameworks": { "asvs-v5": "<ASVS_SHA shortened to 12>" }
```

### B.6 Compute the per-framework compliance posture

For each framework that ran, compute posture:

```python
controls_evaluated = (count of unique control IDs across all coverage matrices)
controls_with_findings = (count of unique control IDs where any pair returned Fail)
controls_passing = controls_evaluated - controls_with_findings
posture_score = controls_passing / controls_evaluated  # 0.0 to 1.0
```

Insert into manifest:

```json
"compliance_posture": {
  "asvs-v5": {
    "controls_evaluated": 142,
    "controls_passing": 119,
    "controls_with_findings": 23,
    "posture_score": 0.84
  }
}
```

The HTML and markdown renderers display this in their compliance-posture section (previously a placeholder).

## Failure handling

**Soft failures — log and continue.**

- One tool fails (crash, no JSON, network error for OSV) → log it, mark `per_tool.<tool>.status` accordingly, continue with the others.
- A normalizer chokes on unexpected tool output → log the exception, mark that tool's status `normalize_failed`, continue.
- Some files unreadable → walker skips them silently; scan still proceeds.
- Semgrep emits warnings on stderr but returns valid JSON → recorded in `_semgrep_stderr.log` and ignored.

**Hard failures — write a crash report and exit.**

Triggers:
- `python3` not on PATH (most tools impossible).
- `git` not on PATH (rule fetch impossible).
- Disk full or permission denied writing to `$RUN_DIR` or `~/.cache/securecoder/`.
- ALL FOUR tools failed (no findings produceable; the scan has no value).
- The cached rule-pack directory's SHA doesn't match its name (integrity tamper).

On hard failure:

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

Print a one-paragraph summary pointing at the crash report. Do not modify the user's working tree.

## Invariants

These hold at every phase boundary:

1. Every dispatched tool has a recorded version in `installed.json` under its tool cache dir.
2. Every fetched rule pack has a SHA in its `manifest.json` and that SHA equals its parent directory name.
3. After a successful run, `$RUN_DIR/findings.jsonl` exists. Every non-empty line parses as JSON and conforms to v1.0 schema fields.
4. After a successful run, `$RUN_DIR/manifest.json` exists with `schema_version: "1.0"`, `run_id`, `tools` (with one entry per attempted tool), `rule_packs`, and `phases.sast.per_tool` (one entry per attempted tool with `status` and `findings` keys).
5. `latest` (or `latest.json`) points at the most recent run id that completed without a `crash_report.md`.

If any invariant is violated, that's itself a hard failure.

## Extending this skill

- **Adding a SAST tool** — new tools plug in by adding: an installer block under A.2, an invocation block under A.5, a normalizer under `scripts/normalize_<tool>.py`, a row in the per-tool merge in A.7, and a friendly name in the manifest builder.
- **Adding a compliance framework** — register it in `references/frameworks.json` with its source repo, chapter directory, and control-ID regex; add a `references/relevance-<framework>.json`; Phase B's per-framework loop picks it up automatically.
