---
name: securecoder-build
description: Activate a persistent secure-build mode that supervises the host agent for the rest of the session. Emits an ASVS-grounded policy block into chat — the agent then plans every code change against applicable controls and self-checks every output before declaring done. Optional minimal bootstrap for empty repos.
---

# `/securecoder-build`

You are running the `/securecoder-build` skill. Your job is to install a persistent security-policy layer into the host agent's chat context so that every subsequent code-producing task in this session is supervised against the configured compliance frameworks.

> **HITL — the policy block text below is the heart of this skill.** Word choice has outsized impact on how the host agent behaves for the rest of the session. Treat changes to this template as breaking changes requiring maintainer review.

This skill does NOT run a daemon. There's no background process. The mechanism is purely: emit a structured instruction block to chat → the host agent's normal context retention keeps it alive across turns → every subsequent task flows through it. When the user explicitly signals "end secure build mode" or the host agent's context drops the block, the mode is naturally over.

## Optional minimal bootstrap

### When to offer

If the project root is empty or near-empty (≤ 3 files, or no source code detected by the walker), ask:

> Starting fresh or supervising an existing project?
>   [fresh]     I'll generate a minimal secure runway so you can start coding.
>   [existing]  Skip the runway; just activate secure-build mode on what's here.

If the user picks `fresh`, run the bootstrap. Otherwise skip directly to mode activation.

### What the bootstrap generates

A short interview:

- **App type?** (web API / web app / CLI tool / library / mobile)
- **Primary stack?** (Python+FastAPI / Python+Django / Node+Express / Next.js / Go / Java+Spring / other — accept any token)

Generate:

1. `.securecoder/config.json` seeded with `frameworks: ["asvs-v5"]`, `severity_floor: "low"`, `default_fix_scope: ["critical", "high"]`, `git.push_strategy: "commit-local-push-at-end"`.
2. `.gitignore` with standard exclusions for the chosen stack.
3. `.env.example` listing the secrets the app will need (DB URL, JWT secret, etc.) as environment variables — never inline values.
4. A pre-commit hook installed via `/securecoder-review`'s install action (SAST-only blocking gate).
5. A `README.md` skeleton with a `Security` section noting the active framework and pointing at `.securecoder/config.json`.

The bootstrap is intentionally MINIMAL — just the runway to start coding securely. It does NOT generate framework-specific scaffolds (FastAPI app structure, Django settings, etc.) — `/securecoder-build` is not a scaffold generator. The agent in secure-build mode will scaffold those when the user asks ("build me an auth endpoint"), with the policy block ensuring it does so against ASVS controls.

## Mode activation

This is the heart of the skill. Emit the following block to chat verbatim, with `{{...}}` variables substituted from configuration. The block is sized to be informative without bloating every subsequent response (~600 words / ~3KB).

```
═══════════════════════════════════════════════════════════════════════════
SECURE BUILD MODE — ACTIVATED

For the remainder of this session, you (the host agent) will supervise every
code-producing task against the active compliance frameworks. The user
signals end-of-mode with "end secure build mode" or "/securecoder-build
--end". This block falling out of context also ends the mode.

ACTIVE FRAMEWORKS
  {{framework_list}}

FRAMEWORK MARKDOWN — read on demand when controls apply
  ASVS v5:  ~/.cache/securecoder/rules/frameworks/asvs/<sha>/5.0/en/
            (chapters 0x10-V1 through 0x26-V17)

PROTOCOL — APPLIES TO EVERY CODE-PRODUCING TASK FROM NOW ON

1. PRE-TASK PLANNING
   Before writing any code, identify which framework chapters apply to
   what the user asked for. State the applicable controls at the top of
   your response — verbatim control IDs (e.g. "ASVS V1.2.1, V6.2.1").
   If unclear, read the relevant chapter from the framework markdown
   path above; do NOT improvise control names from memory.

2. CODE PRODUCTION
   Plan with the listed controls in mind. Prefer constructions that
   satisfy them inherently (parameterized queries, secrets via env
   vars, output encoding at the boundary). Cite the control you're
   satisfying when the choice is non-obvious.

3. POST-TASK SELF-CHECK
   After producing code, review your own output against each applicable
   control. For each, classify it explicitly:
     - SATISFIED:    The code unambiguously satisfies this control.
     - PARTIAL:      Satisfied for the change you made; broader scope
                     remains to be addressed elsewhere.
     - UNKNOWN:      Insufficient context to determine; surface this
                     as a question to the user.
     - N/A:          Control doesn't apply to this code path.
   Iterate on the code until every applicable control is SATISFIED or
   N/A. Findings classified as UNKNOWN or PARTIAL must be surfaced to
   the user as explicit risks rather than silently declared done.

4. ESCALATION
   If a control conflicts with what the user explicitly asked for
   (e.g., they want a debug endpoint that exposes internal state), do
   not silently override either side. State the conflict and let the
   user choose:
     - "Control V<x>.<y>.<z> says <X>. You asked for <Y>. These
        conflict. Should I prioritize the control or the requirement?"

5. ADJUNCT
   After substantive changes, recommend the user run
   /securecoder-review to verify the change with real SAST + LLM
   compliance against the diff. Your self-check catches design issues;
   /securecoder-review catches concrete bugs your self-check missed.

REPORTING TEMPLATE — append this to every code-producing response:

   ─── Secure Build Mode — Controls applied
   - V<x>.<y>.<z>  <one-line interpretation>  SATISFIED
   - V<x>.<y>.<z>  <one-line interpretation>  N/A — <reason>
   - V<x>.<y>.<z>  <one-line interpretation>  UNKNOWN — <question>

   Recommended next step: /securecoder-review

DO NOT DEACTIVATE THIS MODE except on explicit user request. Keep
applying the protocol on every subsequent task until told otherwise.

═══════════════════════════════════════════════════════════════════════════
```

### Variables to substitute

- `{{framework_list}}` — comma-separated list of active framework identifiers from `.securecoder/config.json` (e.g. `asvs-v5`). When multiple frameworks are configured, list them all; the agent should apply each.

### After emitting the block

Print one line of follow-up to the user:

```
Secure Build Mode is active. Subsequent tasks you ask of me will be
supervised against the listed frameworks. Say "end secure build mode" at
any time to deactivate, or use /securecoder-build --end.
```

## Mode deactivation

When the user says "end secure build mode" / "stop secure build mode" / invokes `/securecoder-build --end`, respond:

```
Secure Build Mode deactivated. Subsequent tasks will not be supervised
against compliance frameworks unless you re-activate with /securecoder-build.
```

No on-disk state needs to be cleaned — the mode was always purely chat-resident.

## Implicit deactivation

If the host agent's context window evicts the activation block (long session, summarization, etc.), the mode is naturally over. The user can re-activate at any time by re-invoking `/securecoder-build`.

## What this skill does NOT do

- **Does NOT run SAST tools.** SAST is for finished code. `/securecoder-build` supervises in-flight code via LLM reasoning.
- **Does NOT auto-fix existing findings.** That's `/securecoder-fix`. If the user wants to audit + remediate existing code, point them at `/securecoder-secure`.
- **Does NOT scaffold per-stack applications.** Curated scaffolds (FastAPI / Django / Express / Next / Go) were deliberately dropped from v1 scope — the agent's own knowledge plus the ASVS reference is sufficient. If you want curated scaffolds, that's a future enhancement.
- **Does NOT generate detailed coverage matrices** like `/securecoder-scan` Phase B. The self-check is per-task and concise (the "controls applied" appendix), not a full chapter sweep.

## Failure handling

**Soft.** If the framework markdown isn't yet cached at `~/.cache/securecoder/rules/frameworks/asvs/<sha>/`, run a fetch (same procedure as `/securecoder-scan` Phase B.1) before activating the mode. If the fetch fails offline, activate with reduced grounding — the agent can still apply protocol but won't be able to read chapter source verbatim.

**Hard.** If `.securecoder/config.json` has no enabled frameworks AND the user hasn't supplied any via natural-language ask ("activate with ASVS"), fail with:

> No frameworks configured. Either run `/securecoder-setup` to enable ASVS, or say "/securecoder-build activate with asvs" to use a one-shot framework override.

## Invariants

1. The skill emits exactly one activation block per invocation (no duplicates).
2. The activation block contains every section above; missing sections mean a future Edit to this SKILL.md should be reverted.
3. Mode activation does not modify any file on disk except `.securecoder/config.json` (and only during bootstrap).
4. Mode deactivation modifies nothing — the chat block aging out is enough.
5. The agent in this mode never declares a task done while an applicable control is in `UNKNOWN` or `PARTIAL` state without surfacing it explicitly to the user.
