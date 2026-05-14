# 11 — `/securecoder-build` persistent ASVS policy block + optional bootstrap (HITL)

- **Type:** HITL — the literal policy text injected into users' chat sessions is high-leverage; word choice has outsized impact on how the host agent behaves for the rest of the session
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The session-scoped secure-build skill. Not a scaffold generator — a policy layer that gets injected into the host agent's chat context and stays alive for the remainder of the session, supervising every build task the user gives the agent.

Spec is in design.md §3.6 and prd.md per-skill specifics.

**On invocation:**

1. **Optional minimal bootstrap (if repo is empty or near-empty).** Skill asks "existing project or starting fresh?" If fresh: short interview (app type + stack), then generates just enough to start coding — secure-default config, deps pinned, pre-commit hook installed (via slice 10's hook shim), `.securecoder/config.json` seeded. NOT a full app scaffold — only the runway. If the user's stack isn't one the skill knows specifically, the bootstrap falls back to a generic minimal scaffold (env-var-driven secrets, structured logging stub, deps file, pre-commit hook).
2. **Always: emit the persistent policy block to chat.** This is the heart of the skill. Block contains:
   - Mode declaration ("Secure Build Mode is active until you say `end secure build mode` or context drops it.")
   - Active frameworks (read from `.securecoder/config.json`, defaults to ASVS v5)
   - Absolute paths to fetched framework markdown in `~/.cache/securecoder/rules/frameworks/` for on-demand reading
   - **Pre-task protocol:** before writing code, identify applicable framework chapters; state which controls apply at the top of the response; plan with those controls in mind
   - **Post-task self-check:** review output against applicable controls; for each, mark `satisfied` / `partial` / `unknown` / `n/a`; iterate until all relevant are `satisfied` or `n/a`, or explicitly surface unresolved items as risks
   - **Escalation rule:** if a control conflicts with what the user asked for, surface the conflict rather than silently overriding either side
   - **Adjunct hint:** "Run `/securecoder-review` after substantive changes for real SAST + LLM verification on the diff"
3. **Mode deactivation.** Explicit user signal ("end secure build mode", `/securecoder-build --end`) OR natural context drop. No on-disk state to clean.

The policy block uses ONLY the configured compliance frameworks (typically ASVS). SAST tools do not enter `/securecoder-build` mode — they're for finished code.

**HITL review focus areas before merging:**

- The exact text of the policy block — small wording changes have large effects on agent behavior across the session
- The pre-task and post-task protocols — these are the operative parts; they should be specific enough that the agent acts on them but compact enough not to bloat every response
- The "self-check satisfied/partial/unknown/n/a" rubric — needs to be clear without being verbose
- The bootstrap scaffold contents — what counts as "just enough to start coding securely" varies by stack

## Acceptance criteria

- [ ] `/securecoder-build` invoked on an empty repo offers the minimal bootstrap interview and generates a runway (secure-default config, deps pinned, pre-commit hook installed, `.securecoder/config.json` seeded)
- [ ] `/securecoder-build` invoked on an existing repo skips the bootstrap and goes straight to mode activation
- [ ] The emitted policy block is a single well-structured response containing all six elements (mode declaration, active frameworks, framework paths, pre-task protocol, post-task self-check, escalation rule, adjunct hint)
- [ ] After mode activation, subsequent user requests to the agent visibly invoke the protocol: agent states applicable controls before writing code, and self-checks after producing code
- [ ] "End secure build mode" command (or natural-language equivalent) is acknowledged; subsequent agent responses no longer apply the protocol
- [ ] Mode deactivation also happens implicitly when the policy block falls out of context (no explicit cleanup required)
- [ ] For unknown stacks, bootstrap falls back to the generic minimal scaffold
- [ ] `/securecoder-build` references only the configured compliance frameworks; SAST tools are not invoked
- [ ] **HITL review:** the policy block text, the pre-task and post-task protocols, the self-check rubric, and the bootstrap stacks list are reviewed by the maintainer before merge
- [ ] Tests cover: bootstrap interview flow (empty repo vs populated repo), config seeding by stack, hook install integration with slice 10's shim. The persistent-policy-block emit is a fixture-snapshot test (the block content is asserted against a known-good template).

## Blocked by

- 01 — Repo skeleton + plugin.json + `/securecoder-setup` minimal wizard
