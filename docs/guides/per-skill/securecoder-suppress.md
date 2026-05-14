# `/securecoder-suppress` — usage guide

## What this skill does

Marks findings as false positives. Writes structured entries to `.securecoder/suppressions.json` — the team-shared source of truth. Other skills read this file (directly or via the `status: "suppressed"` field that `/securecoder-scan` stamps on matching findings) and skip suppressed findings in their flows.

## When to invoke it

- You read a finding in a scan report and know it's not actually a problem
- You want to suppress a class of findings (e.g., all hardcoded-credential warnings in test fixtures)
- You want to remove a previous suppression after refactoring
- You want to see what's currently suppressed and why

## When NOT to invoke it

- **You want to suppress something for one commit only.** Suppressions are persistent. Use `git commit --no-verify` for one-off bypasses of the pre-commit hook.
- **You want to fix the finding.** Use `/securecoder-fix`. Suppressing is for false positives you've decided shouldn't be fixed; fixing addresses real ones.

## How to invoke

### Mark a single finding by ID

```text
/securecoder-suppress <finding-id> "<reason>"

# Example
/securecoder-suppress 5823722d "Validated upstream by auth middleware"
```

Reason is required, free text.

### Mark a pattern (rule + path)

```text
/securecoder-suppress add --match "<match-expr>" --reason "<reason>"

# Example — suppress hardcoded-password warnings in test fixtures
/securecoder-suppress add \
  --match "rule=B105 and file_glob=tests/**" \
  --reason "Test fixtures intentionally hardcode credentials"

# JSON form is also accepted
/securecoder-suppress add \
  --match '{"rule": "B105", "file_glob": "tests/**"}' \
  --reason "Test fixtures intentionally hardcode credentials"
```

Match keys: `id` (canonical finding ID), `rule` (source_rule_id), `file` (exact path), `file_glob` (gitignore-style glob), `framework_ref` (e.g., `asvs-v5/V1.2.1`).

### Import a batch (typically from the HTML report's "Export to agent" button)

```text
/securecoder-suppress import '[
  {"match": {"id": "5823722d"}, "reason": "..."},
  {"match": {"rule": "B608"}, "reason": "..."}
]'
```

This is the form the HTML report generates when you click "Export to agent" on staged suppressions.

### Show all current suppressions

```text
/securecoder-suppress show
```

Plain-text table: index, match, reason, created_at, created_by, expires_at.

### Show why a specific finding is suppressed

```text
/securecoder-suppress show --finding <id>
```

Looks up the finding in `.securecoder/runs/latest/findings.jsonl`, finds which suppression entry caused its status, and displays the entry verbatim.

### Show stale entries (didn't match anything in last scan)

```text
/securecoder-suppress show --stale
```

Likely candidates for removal — the code they referenced may have been refactored or removed. Cross-references the manifest's `suppressed_by_entry` field.

### Show expired entries

```text
/securecoder-suppress show --expired
```

Entries past their `expires_at` date. They stay in the file (audit trail) but are ignored at match time.

### Remove a specific entry

```text
/securecoder-suppress remove --index 3
```

Use `show` first to find the index.

### Purge expired entries

```text
# Dry-run first (the default)
/securecoder-suppress expire

# Apply after reviewing
/securecoder-suppress expire --yes
```

## Alternative input — source-code annotations (v1.2.0)

Beyond the eight CLI modes above, suppressions can also come from in-source comment annotations. These get picked up automatically by `/securecoder-scan` during Phase A.7.3:

```python
def get_user(user_id):
    # securecoder: ignore reason="validated upstream by middleware"
    return db.execute(f"SELECT * FROM users WHERE id = {user_id}")

PASSWORD = "dev-only"  # securecoder: ignore reason="dev env only" expires="2027-01-01"
```

Both `#` (Python, Ruby, Shell, YAML, TOML, etc.) and `//` (JavaScript, TypeScript, Go, Java, C/C++, etc.) line comments are recognized. Block comments (`/* ... */`) and JSX braces are not yet supported.

**Targeting:**
- **Inline annotation** (code + marker on the same line) → applies to that line.
- **Line-only annotation** (the whole line is just the comment) → applies to the next non-blank, non-comment line.

**Attributes (optional):**
- `reason="..."` — free-text; appears in the suppression's audit trail. Falls back to `"(in-source annotation)"` if omitted.
- `expires="YYYY-MM-DD"` — entry is auto-disabled past this date (preserved in audit but ignored at match time).

**When annotations vs config-file suppressions?**

| Use annotations when... | Use config (`/securecoder-suppress`) when... |
| --- | --- |
| The suppression is anchored to a specific line of code | The suppression covers a pattern (rule + path glob) |
| The reasoning is most natural to read next to the code itself | The reasoning is administrative ("we use SQLAlchemy throughout, this rule fires across the codebase") |
| You want git blame to attribute who added it | You want explicit `created_by` from `git config user.email` |
| The code is short-lived and the suppression doesn't need cross-team coordination | The suppression should be team-reviewed via PR on the config file |

Annotations live in the source code, so they move with refactoring, survive branch merges naturally, and are version-controlled alongside the code they protect. Config-file entries are easier to audit in bulk and easier to bulk-remove.

## What it writes

`.securecoder/suppressions.json` — team-shared, checked in:

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

`created_at` and `created_by` (via `git config user.email`) are auto-populated. Schema is documented in `docs/design.md` §3.9.

## When suppressions take effect

**Effects materialize on the NEXT `/securecoder-scan` run.** The skill itself doesn't re-scan or recompute anything; it just edits the suppressions file. After invoking `/securecoder-suppress`, run `/securecoder-scan` to see findings transition to `status: "suppressed"`.

For the **pre-commit hook** installed by `/securecoder-review`, the hook reads `suppressions.json` directly on every commit attempt — so changes apply immediately, no need to re-scan first.

## Most-specific-wins resolution

When multiple suppression entries could match a single finding, the most-specific one wins. Specificity ranking:

| Score | Match shape |
|---|---|
| 0 (most specific) | `id` present |
| 1 | `rule` + `file` |
| 2 | `rule` + `file_glob` |
| 3 | `rule` alone, or `framework_ref` alone |
| 4 (least specific) | `file_glob` alone |

The finding's `suppression_reason` is set from the winning entry. The `suppression_match` field carries a `suppressions.json#<index>` pointer for audit.

## Follow-up skills

| After suppressing | Run |
|---|---|
| To see the suppression take effect | `/securecoder-scan` |
| To verify the report no longer flags this | `/securecoder-scan` then read the report |
| To audit current suppressions | `/securecoder-suppress show` or `/securecoder-advise "show all suppressions"` |
| To roll back a suppression | `/securecoder-suppress remove --index <N>` |

## Common pitfalls

- **Finding still appears after `/securecoder-suppress`?** Effects materialize on the next scan. Re-run `/securecoder-scan` (or for diff-scoped reviews, the next `/securecoder-review` reads suppressions.json directly).
- **`id`-matched suppressions are fragile.** The canonical ID is `sha256(file + line + rule_id)`. If anyone shifts the code's line numbers (e.g., adds 10 lines above the finding), the ID changes and the suppression no longer matches. The cluster view's pattern-based matches (`rule + file_glob`) are stable across reorganization and recommended for most cases.
- **Duplicate adds are silently skipped.** The helper dedupes by `(match, reason)` signature. To add another entry with the same match but a different reason, just provide the different reason — that's a new signature.
- **`framework_ref` matches against the finding's `framework_refs` list.** Format must be `"<framework>/<control>"`, e.g., `"asvs-v5/V1.2.1"`. The framework portion is required; the control portion can be omitted to match any control in that framework.
- **The `entries` array is intentionally team-shared.** Suppressions aren't a personal hide-from-my-view feature — they're a team decision recorded for the codebase. If you want to silence findings locally without committing, raise `severity_floor` in `.securecoder/config.json` for that level.

## See also

- [`/securecoder-scan` guide](securecoder-scan.md) — produces findings + applies suppressions in Phase A.7.5
- [`/securecoder-fix` guide](securecoder-fix.md) — skips status=suppressed findings; offers "suppress" action in interactive mode
- [`/securecoder-review` guide](securecoder-review.md) — pre-commit hook reads suppressions.json directly
- [Scenarios guide](../scenarios.md) — "Triaging a 2,000-finding scan" uses suppress + cluster view together
- [`docs/design.md` §3.9](../../design.md) — full schema + cross-skill integration details
