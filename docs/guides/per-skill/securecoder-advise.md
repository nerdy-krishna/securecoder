# `/securecoder-advise` — usage guide

## What this skill does

Answers security questions grounded in cached OWASP framework markdown (ASVS, MASVS, Cheatsheets, Proactive Controls) and the latest `/securecoder-scan` findings. Verbatim citations — quotes the actual control text from the local cache rather than the agent's training-time recollection. Read-only; never modifies code.

The value over plain agent chat: anchoring. ASVS V1.2.1 will never be misquoted, and a finding's framework references trace back to specific control text you can verify.

## When to invoke it

- **You don't understand a finding.** "Why did securecoder flag line 42 as critical?"
- **You're weighing a design choice.** "Is OAuth or JWT-with-rotation better here?"
- **You're learning OWASP.** "Explain ASVS V1.2.1." "What does Proactive Control C3 say?"
- **You're writing security documentation.** Need verbatim control text to quote in your own docs.
- **You want a Cheatsheet recommendation.** "What does OWASP recommend for SQL injection prevention?"

## When NOT to invoke it

- **You want to fix a finding.** Use `/securecoder-fix`. `/securecoder-advise` is text-only.
- **You want to run a scan.** Use `/securecoder-scan`. `/securecoder-advise` doesn't scan — it reads from previous scan results.
- **The framework cache is empty.** The skill still works but with an explicit "ungrounded answer" disclaimer. Run `/securecoder-scan` with a compliance mode once to populate the cache.

## How to invoke

```text
# Question as argument
/securecoder-advise "How do I prevent SSRF in this codebase?"
/securecoder-advise "Explain ASVS V1.2.1"
/securecoder-advise "What's the difference between A03 Injection and A07 Auth?"
/securecoder-advise "Search the ASVS for SSRF"

# No argument — interactive mode picker
/securecoder-advise
```

## Mode picker (no-argument invocation)

| Mode | What you do | What the skill returns |
| --- | --- | --- |
| **General Q&A** | Ask any security question | Answer grounded in framework markdown search results |
| **Findings-grounded Q&A** | Ask about your latest scan ("which findings are correlated?") | Answer that references specific finding IDs + file:line |
| **Specific finding deep-dive** | Provide an 8-char finding ID | Verbatim evidence + framework control text + remediation + related controls |
| **Framework lookup** | Provide a control ID ("V1.2.1", "SCE-MEM-1") | Verbatim control text + plain-language interpretation + related controls |

## Response format (always)

Every answer follows this structure:

1. **Loaded context line** (first turn only): "Loaded: ASVS v5.0.0 (cached at ...); 47 findings from run 20260514T140000Z; severity floor 'low'."
2. **Verbatim quote** from the framework, in a markdown blockquote, with citation: `<framework> <version> <control-id>`.
3. **Plain-language interpretation** — what the control means, why it matters, how it's typically satisfied.
4. **Finding references** (when grounded in user findings) — by 8-char ID prefix + file:line.
5. **Related controls / Cheatsheet sections** at the end.

Example response to `/securecoder-advise "Explain ASVS V1.2.1"`:

```
Loaded: ASVS v5.0.0 (cached at ~/.cache/securecoder/rules/frameworks/asvs/abc123/);
        47 findings from run 20260514T140000Z; severity floor "low".

> **ASVS v5.0.0 V1.2.1** — Verify that the application uses parameterized queries,
> ORM, or stored procedures for all SQL operations and prevents dynamic queries
> with untrusted input.

In plain language: never concatenate user input into SQL strings. Use the database
client's parameter binding (`?`-style or named) so the input is treated as data,
not query syntax.

In your codebase, finding `5823722d` (src/api/users.py:142) is exactly this —
`cursor.execute('SELECT … WHERE id = ' + user_id)` builds the query from a
string concatenation.

Related: V1.2.2 (ORM-side), V1.2.5 (LDAP / XPath / NoSQL injections), and the
OWASP SQL Injection Prevention Cheat Sheet at
~/.cache/securecoder/rules/frameworks/cheatsheets/<sha>/cheatsheets/
SQL_Injection_Prevention_Cheat_Sheet.md.

Framework references are loaded in this conversation. Ask follow-ups freely.
```

## Example sessions

### Looking up a control

```
/securecoder-advise "Explain ASVS V6.2.1"
```

Returns the verbatim password-hashing requirement, plus interpretation, plus related controls (V6.2.2, V6.2.3), plus a pointer to the OWASP Password Storage Cheat Sheet.

### Deep-diving on a finding

```
/securecoder-advise
> Mode: Specific finding deep-dive
> Finding ID: 5823722d

Returns evidence excerpt + V1.2.1 quote + remediation + recommended next action.
```

### Cross-referencing OWASP categories

```
/securecoder-advise "Show me all findings tagged with OWASP A03 in the latest scan"
```

Returns a list of finding IDs + file:line grouped by severity, all tagged with `owasp-top-10-2021 A03`.

### Comparing frameworks

```
/securecoder-advise "What does Proactive Control C3 say about secure database access, compared to ASVS V1.2.1?"
```

Returns both verbatim quotes, then a comparison.

### Searching by keyword

```
/securecoder-advise "Search the ASVS for SSRF"
```

The skill invokes `scripts/search_rules.py` and returns top-N matching sections.

## What it does NOT modify

- Source code — never.
- `.securecoder/config.json` — never (use `/securecoder-setup`).
- `.securecoder/runs/<id>/findings.jsonl` — never (read-only).
- Git state — never.

Safe to invoke at any time without worrying about side effects.

## Follow-up

- **To fix something the advise surfaced:** `/securecoder-fix` (against the relevant findings file).
- **To re-scan after manual fixes:** `/securecoder-scan`.
- **To activate ASVS supervision for future work:** `/securecoder-build`.

## Common pitfalls

- **The cache must be populated for overlay frameworks.** Run `/securecoder-scan` with a compliance mode at least once to clone the OWASP framework repos (ASVS, MASVS, Cheatsheets, Proactive Controls). Otherwise the skill answers ungrounded with an explicit disclaimer.
- **`secure-coding-essentials` (`SCE-*`) needs no cache.** The baseline framework is bundled inside the skill, so `/securecoder-advise "Explain SCE-MEM-1"` works offline and on a fresh install — no scan required to populate it.
- **Verbatim quotes are exact.** If a control's text has typos in OWASP's source, the skill quotes the typos. They're upstream.
- **Cheatsheets are not scanned against** but they ARE in the cache for /securecoder-advise to read. Enable them in `/securecoder-setup` to populate.
- **Skill is host-LLM dependent for interpretation.** The verbatim quotes are deterministic; the plain-language interpretation comes from the host LLM. Quality varies by model.
- **Long Q&A sessions consume context.** The first turn loads all the framework markdown into context (~50–500KB depending on enabled frameworks). On agents with small windows, ask focused questions to stay efficient.
- **`/securecoder-advise` doesn't track conversation history on disk.** Each invocation is fresh — the host agent's context retention handles multi-turn.

## See also

- [`/securecoder-scan` guide](securecoder-scan.md) — populates the cache and findings the skill reads
- [`/securecoder-fix` guide](securecoder-fix.md) — to act on findings the advise surfaced
- [Scenarios guide](../scenarios.md) — Scenario 4 ("understand a finding") is the canonical use case
