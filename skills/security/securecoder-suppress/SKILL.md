---
name: securecoder-suppress
description: Mark findings as false positives. Writes structured entries to .securecoder/suppressions.json — the source of truth that /securecoder-scan honors when stamping status="suppressed" on matching findings. Eight modes for add / import / show / show <id> / show stale / show expired / remove / expire.
---

# `/securecoder-suppress`

You are running the `/securecoder-suppress` skill. Your job is to mutate `.securecoder/suppressions.json` (the team-shared false-positive ledger) based on the user's intent. The skill is the source of truth for suppressions — every other skill reads `.securecoder/suppressions.json` (directly or via the `status: "suppressed"` field that `/securecoder-scan` stamps).

> **What this skill does NOT do.** It does not re-run scans. It does not recompute suppression effects against existing findings. Effects materialize the next time `/securecoder-scan` runs (when `apply_suppressions.py` matches the updated suppressions file against fresh findings).

## Eight modes

All modes invoke the same helper at `<skill-dir>/scripts/suppress.py`. Interpret the user's natural-language ask and dispatch to the right subcommand.

### 1. `add` — add a new entry from a match expression + reason

```bash
python3 "<skill-dir>/scripts/suppress.py" add \
  --match "rule=B105 and file_glob=tests/**" \
  --reason "Test fixtures intentionally hardcode credentials" \
  [--expires 2027-01-01] \
  [--scope project]
```

The `--match` expression accepts either:

- Simple form: `key=value and key=value ...` — keys allowed are `id`, `rule`, `file`, `file_glob`, `framework_ref`
- JSON form: `{"rule": "B105", "file_glob": "tests/**"}`

`--reason` is required. `--expires` is optional ISO date (entry auto-disabled past that date). `--scope` defaults to `project` (only valid value for v1.1.0).

`created_at` and `created_by` are auto-populated. `created_by` uses `git config user.email`; falls back to `"unknown@local"`.

The helper dedupes by signature (`match + reason`) — re-adding an identical entry is a no-op.

**Natural-language → subcommand mapping:**
- "suppress B105 in tests/" → `add --match "rule=B105 and file_glob=tests/**" --reason "..."` (ask user for the reason if not supplied)
- "suppress this finding" — see the `<finding-id>` shortcut below

### 2. `add` shortcut — by finding ID

When the user says "suppress finding `5823722d`" or pastes a specific finding ID, dispatch to:

```bash
python3 "<skill-dir>/scripts/suppress.py" add \
  --match '{"id": "5823722d…"}' \
  --reason "..."
```

The reason is REQUIRED — ask the user if they haven't supplied one. Free text, no minimum length.

### 3. `import` — batch import from the HTML report's export button

The HTML report's "Export to agent" button generates a `/securecoder-suppress import [...]` invocation with a JSON array body. Dispatch to:

```bash
python3 "<skill-dir>/scripts/suppress.py" import --entries '<json-array>'
```

`--entries` accepts either an inline JSON string or a path to a file. The helper validates each entry, dedupes against existing, and reports added / skipped (dup) / skipped (bad) counts.

### 4. `show` — list all current entries

```bash
python3 "<skill-dir>/scripts/suppress.py" show
```

Plain-text table: index, match expression, reason, created_at, created_by, expires_at.

### 5. `show --finding <id>` — explain why a finding is suppressed

When the user says "why is finding `5823722d` suppressed?" or "who suppressed `5823722d`?":

```bash
python3 "<skill-dir>/scripts/suppress.py" show --finding 5823722d
```

The helper:
1. Looks up the finding in `.securecoder/runs/latest/findings.jsonl`
2. If `status != "suppressed"`: reports current status and exits.
3. Otherwise: reads the `suppression_match` field (`suppressions.json#<index>`) and displays the corresponding entry verbatim.

### 6. `show --stale` — entries that didn't match anything in the last scan

```bash
python3 "<skill-dir>/scripts/suppress.py" show --stale
```

Reads `manifest.suppressed_by_entry` from `.securecoder/runs/latest/manifest.json`. Entries with count 0 (and not expired) are likely stale — the code they referenced may have been removed or refactored.

### 7. `show --expired` — entries past their `expires_at`

```bash
python3 "<skill-dir>/scripts/suppress.py" show --expired
```

Lists entries past their `expires_at` date. These are still in the file (audit trail preserved) but ignored at match time.

### 8. `remove <index>` — delete one entry by index

```bash
python3 "<skill-dir>/scripts/suppress.py" remove --index 3
```

Deletes entry at the given index. Indexes are 0-based and refer to the entry's position in the `entries` array. Use `show` first to find the right index.

### 9. `expire` — purge expired entries

```bash
python3 "<skill-dir>/scripts/suppress.py" expire
```

By default, lists what would be removed and asks the user to re-invoke with `--yes` to apply. Once confirmed:

```bash
python3 "<skill-dir>/scripts/suppress.py" expire --yes
```

Removes all entries past their `expires_at`.

## What gets written

`.securecoder/suppressions.json` — team-shared file, checked in:

```json
{
  "schema_version": "1.0",
  "entries": [
    {
      "match": { "rule": "B105", "file_glob": "tests/**" },
      "scope": "project",
      "reason": "Test fixtures intentionally hardcode credentials",
      "created_at": "2026-05-14T15:30:00Z",
      "created_by": "krishna@example.com",
      "expires_at": null
    }
  ]
}
```

## Where the suppression actually takes effect

`/securecoder-suppress` does NOT re-run scans. Its only output is the mutated `suppressions.json` file. Effects materialize the NEXT time `/securecoder-scan` runs (or `/securecoder-secure`, since it invokes scan internally), when `apply_suppressions.py` stamps `status: "suppressed"` on matching findings.

If the user wants to see the suppression take effect immediately, they should run `/securecoder-scan` after invoking `/securecoder-suppress`.

For the pre-commit hook (`/securecoder-review`'s installed hook), the script reads `.securecoder/suppressions.json` directly — so suppression changes apply on the very next commit attempt without needing a fresh scan.

## Failure handling

- **Suppressions file missing on read** (show modes): treat as zero entries; the show modes still work, just return empty.
- **Suppressions file missing on write** (add/import/remove/expire): create the file + parent dirs as needed.
- **Suppressions file malformed JSON**: print a warning, treat as empty; user must manually fix before further edits stick.
- **Index out of range on remove**: error message with the valid range; exit non-zero.
- **Match expression unparseable**: error message; exit non-zero.

## Invariants

1. The file always validates against schema v1.0 after every mutation.
2. The `entries` array is always present (possibly empty).
3. `created_at` and `created_by` are always populated on new entries by the helper, never the user's job.
4. Dedupe by signature (`match + reason`) prevents accidental duplicate adds.
5. The file is the SOLE source of truth for suppressions; other skills read it but never mutate it.
