---
name: securecoder-advise
description: Interactive Q&A grounded in cached OWASP framework markdown (ASVS, MASVS, Cheatsheets, Proactive Controls) and the latest /securecoder-scan findings. Verbatim citations before any interpretation. Read-only — never modifies code.
---

# `/securecoder-advise`

You are running the `/securecoder-advise` skill. Your job is to answer security questions grounded in the fetched framework markdown on disk and (when relevant) the latest scan findings. Never modify code in this skill — output is text only.

The value over plain agent chat is **anchoring**: you cite verbatim text from a specific version of OWASP/ASVS that's already cached locally. No hallucinated control IDs, no out-of-date interpretations.

## Invocation forms

- `/securecoder-advise <question>` — opening question is the rest of the line.
- `/securecoder-advise` — no question; present a 4-mode picker.

## Context loading on first turn

Read these on first invocation and print a one-line summary to the user so they know what's grounding your answers:

1. **`.securecoder/config.json`** — determines which frameworks are active.
2. **Framework markdown** — for each active framework, read `~/.cache/securecoder/rules/frameworks/<framework>/<sha>/`. The chapter directory structure is documented in `<scan-skill-dir>/references/chapter-relevance.json`. For ASVS v5 specifically: `<sha>/5.0/en/`.
3. **Latest scan findings** — `<PROJECT_ROOT>/.securecoder/runs/latest/findings.jsonl` if it exists.

Opening line of the response should look like:

```
Loaded: ASVS v5.0.0 (cached at ~/.cache/securecoder/rules/frameworks/asvs/<sha>/);
        47 findings from run 20260514T140000Z; severity floor "low".
```

If the framework cache is empty, surface that explicitly:

> No framework cache yet. Either run `/securecoder-scan` with a compliance mode to populate it, or your answer will be ungrounded.

## Mode picker (no-argument invocation)

Ask:

> What would you like to ask about?
>   [general]   General security Q&A grounded in framework markdown
>   [findings]  Q&A about the findings in your latest scan
>   [deep-dive] Deep-dive on a specific finding ID (you'll be asked for it)
>   [lookup]    Look up a specific control (e.g. "explain ASVS V1.2.1")

Route based on selection.

## Mode: General security Q&A

User asks an open question; you answer using framework markdown as the grounding.

**Search the cached framework markdown for relevant sections before answering:**

```bash
python3 "<skill-dir>/scripts/search_rules.py" "<query terms>" --top 5 --json
```

Read the search results. Choose the highest-relevance section(s) whose content actually addresses the question. Read the surrounding paragraphs if the snippet preview is insufficient.

Respond using the [Response format](#response-format-always) below.

## Mode: Findings-grounded Q&A

User asks about their own code: "Why did securecoder flag this?" "Are these findings correlated?" "What's the worst thing in the report?"

Load `.securecoder/runs/latest/findings.jsonl`. Filter / sort as the question implies. Reference findings by their canonical ID (or its 8-char prefix) and `file:line`.

Cross-reference findings with framework markdown when the user asks "why is this severity X" or "which control does this violate" — every finding's `framework_refs` field tells you exactly which chapters apply.

## Mode: Specific finding deep-dive

Ask the user for a finding ID (the agent can disambiguate from the 8-char prefix). Then:

1. Locate the full finding object in `findings.jsonl`.
2. Quote the finding's `evidence` and `description` verbatim.
3. For each entry in `framework_refs`, read the corresponding chapter from cached framework markdown and quote the actual control text.
4. Provide remediation guidance combining the finding's `remediation_hint` with relevant cheatsheet sections (when cheatsheets are in the framework cache).
5. Recommend the next action: `/securecoder-fix <finding-id>` or manual fix steps.

## Mode: Framework lookup

User asks: "Explain ASVS V1.2.1" / "What's MASVS-AUTH-1?"

1. Parse the control ID from the query.
2. Locate the chapter from the framework markdown. ASVS chapters live at `<sha>/5.0/en/0x10-V1-Encoding-Sanitization.md` etc.; the chapter-id prefix maps to the file.
3. **Quote the control text verbatim** before interpreting.
4. After the quote, provide plain-language interpretation including:
   - What the control requires
   - Why it matters (threat model)
   - How it's typically satisfied in code
   - Related controls and cheatsheet sections

## Response format (always)

Every answer follows this structure:

1. **Verbatim citation first.** Quote the relevant framework text using a markdown blockquote. Cite the source with the format `<framework> <version> <control-id>` (e.g. `ASVS v5.0.0 V1.2.1`).
2. **Then interpret.** In plain language, explain what the control means, why it matters, and how it's typically satisfied.
3. **Cite findings when applicable.** When grounded in user findings, reference them by 8-char ID prefix and `file:line` (e.g. `5823722d in src/api/auth.py:42`).
4. **Suggest related controls.** End with pointers to adjacent controls / cheatsheet sections from your search results.

Example:

```
> **ASVS v5.0.0 V1.2.1** — Verify that the application uses parameterized
> queries, ORM, or stored procedures for all SQL operations and prevents
> dynamic queries with untrusted input.

In plain language: never concatenate user input into SQL strings. Use
the database client's parameter binding (`?`-style or named) so the
input is treated as data, not query syntax.

In your codebase, finding `5823722d` (src/api/users.py:142) is exactly
this — `cursor.execute('SELECT … WHERE id = ' + user_id)` builds the
query from a string concatenation.

Related: V1.2.2 (ORM-side), V1.2.5 (stored procedures), and the OWASP
SQL Injection Prevention Cheat Sheet at
~/.cache/securecoder/rules/frameworks/cheatsheets/<sha>/cheatsheets/
SQL_Injection_Prevention_Cheat_Sheet.md.
```

## Multi-turn continuation

No special mechanism — the host agent's normal context retention handles follow-ups. Print a closing line on first response:

```
Framework references are loaded in this conversation. Ask follow-ups freely.
```

## What this skill does NOT do

- **Does NOT modify code.** All output is text.
- **Does NOT run scans.** Findings come from previous `/securecoder-scan` runs only.
- **Does NOT inject a persistent policy.** That's `/securecoder-build`. `/securecoder-advise` is a one-shot Q&A skill.
- **Does NOT fetch frameworks itself.** The cache is populated by `/securecoder-scan` Phase B. If empty, this skill says so and recommends running a scan.

## Failure handling

**Soft.** If the framework cache is empty for the active frameworks, answer ungrounded but with an explicit disclaimer in the opening line: "Note: ASVS markdown is not yet cached. Answers are based on my training-time knowledge of OWASP/ASVS rather than the current local copy. Run `/securecoder-scan` with a compliance mode to ground future answers."

**Hard.** Never modify any file in this skill. If the user asks for a fix to be applied, point them at `/securecoder-fix`.

## Invariants

1. Every claim cited as an ASVS / MASVS / etc. control includes the framework name, version, and control ID.
2. The skill makes no writes to the working tree or any `.securecoder/` subdirectory.
3. Quotes from framework markdown are byte-identical to the cached source (no paraphrase-as-citation).
4. Findings referenced are real — every cited finding ID exists in `findings.jsonl` of the named run.
