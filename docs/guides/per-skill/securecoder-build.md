# `/securecoder-build` — usage guide

## What this skill does

Emits a persistent ASVS-grounded policy block into your chat session. From the moment you invoke it until the chat context drops the block, every code-producing task you give your coding agent flows through the protocol:

1. **Pre-task** — identify which ASVS controls apply to what you asked for, state them at the top of the response.
2. **Code production** — plan with those controls in mind; cite the control when a design choice is driven by it.
3. **Post-task self-check** — classify each applicable control as SATISFIED / PARTIAL / UNKNOWN / N/A; iterate until everything is SATISFIED or N/A, OR surface unresolved items to you as explicit risks.
4. **Escalation** — when a control conflicts with what you asked for, the agent surfaces the conflict instead of silently overriding either side.

It's not a daemon. There's no background process. The mechanism is purely chat-resident — the host agent's context retention keeps the protocol alive across turns.

## When to invoke it

- **Starting a new project** that you want secure from day one.
- **Starting a new feature** in an existing project — particularly auth, API endpoints, anything user-input-driven.
- **Pair-programming with the agent** when you want it to think defensively without you having to remember to remind it.
- **Onboarding a junior developer** — they can ask the agent to build features, and the policy block enforces secure patterns even when they wouldn't have known to ask.

## When NOT to invoke it

- **Quick one-shot tasks** ("fix this typo") — the policy overhead adds noise without value.
- **Code review tasks** — `/securecoder-build` is for producing code, not reviewing it. Use `/securecoder-review` for review.
- **Already in the middle of a refactor** — activating mid-task may confuse the agent. Activate before starting.

## How to invoke

```text
# Basic activation
/securecoder-build

# (Future) Activate with explicit framework override
/securecoder-build activate with asvs
/securecoder-build activate with masvs

# Deactivate explicitly
/securecoder-build --end
# Or natural language:  "end secure build mode"
```

## What happens on activation

If your repo is empty or near-empty, the skill offers an **optional minimal bootstrap**:

> Starting fresh or supervising an existing project?
>   [fresh]     I'll generate a minimal secure runway so you can start coding.
>   [existing]  Skip the runway; just activate secure-build mode on what's here.

If you pick **fresh**, a short interview captures:
- App type (web API / web app / CLI / library / mobile)
- Primary stack (Python+FastAPI / Node+Express / Go / Java+Spring / etc.)

The skill then generates a minimal runway:
- `.securecoder/config.json` seeded for the chosen frameworks
- `.gitignore` with standard exclusions
- `.env.example` listing the secrets your app will need (as env var references, never inline values)
- A pre-commit hook installed via `/securecoder-review`'s install action
- A `README.md` skeleton with a `Security` section

**Important:** the bootstrap is deliberately minimal. It does NOT generate per-stack scaffolds (FastAPI app structure, Django settings, Express routes, etc.). Those come from the agent during regular work, with the policy block ensuring it does so securely.

Then the skill emits the **persistent policy block** to chat (≈600 words / 3KB). It contains:
- Mode declaration with explicit deactivation phrases
- Active frameworks
- Absolute paths to fetched framework markdown for on-demand reading
- Pre-task / post-task / escalation / adjunct protocols
- A "Controls applied" reporting template

You'll see one follow-up line:

> Secure Build Mode is active. Subsequent tasks you ask of me will be supervised against the listed frameworks. Say "end secure build mode" at any time to deactivate, or use /securecoder-build --end.

## What the supervised agent does after activation

Every subsequent code-producing task gets a "Controls applied" appendix. Example:

```
User: Add a signup endpoint that takes email + password.

Agent: I'll add the signup endpoint. Applicable ASVS controls for this work:
- V1.2.1 (Parameterized SQL)
- V6.2.1 (Password hashing — bcrypt/argon2/scrypt)
- V6.2.3 (Password complexity not enforced via composition rules)
- V13.1.1 (Secrets via env vars, not hardcoded)

[... code ...]

─── Secure Build Mode — Controls applied
- V1.2.1   Parameterized SQL via SQLAlchemy session   SATISFIED
- V6.2.1   bcrypt with cost factor 12                  SATISFIED
- V6.2.3   Min 12 chars enforced; no composition rules SATISFIED
- V13.1.1  JWT_SECRET via os.getenv                    SATISFIED
- V4.2.1   CSRF — no protection wired (POST endpoint)  UNKNOWN — should I add CSRF middleware? Recommend Yes for browser-facing apps.

Recommended next step: /securecoder-review
```

The `UNKNOWN` entry is the protocol working. The agent flagged a control it couldn't determine without your input rather than silently shipping code that might violate it.

## Mode deactivation

Three ways for the mode to end:

1. **Explicit user signal** — say "end secure build mode" or invoke `/securecoder-build --end`.
2. **Context drop** — long session, the agent's context window evicts the policy block, mode naturally ends.
3. **Conflict the agent surfaces** — strictly speaking the mode is still active, but you decide to override a specific control for a specific task.

There's no on-disk state to clean up. Reactivate any time with `/securecoder-build`.

## Follow-up

- **After substantive changes:** `/securecoder-review` — verifies the diff with real SAST + LLM compliance, catching anything the self-check missed.
- **Before pushing:** `/securecoder-review` with scope "branch vs base" — comprehensive check against your base branch.
- **For deeper questions about a control the agent applied:** `/securecoder-advise "Explain ASVS V6.2.1"`.

## Common pitfalls

- **Policy block consumes context space.** ~3KB. On agents with small context windows (Haiku, Gemini Flash), this can squeeze out other useful context. Worth it for security-critical work; consider a more capable model for long sessions.
- **The agent's self-check is heuristic, not deterministic.** It's LLM reasoning, so it can miss things or be over-confident. `/securecoder-review` is the safety net — run it after every substantive change.
- **Re-activating mid-session re-emits the block** but doesn't deduplicate. Two policy blocks in the same context is wasteful but not broken.
- **Some agents prune older messages aggressively.** The policy block may fall out of context mid-task. If you see the agent stop appending the "Controls applied" appendix, re-invoke `/securecoder-build`.
- **No SAST tools are invoked in this mode.** That's by design — SAST is for finished code; `/securecoder-build` supervises in-flight. To run SAST on what the agent produced, invoke `/securecoder-review` or `/securecoder-scan` separately.
- **The bootstrap is minimal on purpose.** If you want a fully-scaffolded FastAPI app, ask the agent: "build me a FastAPI scaffold for X." With `/securecoder-build` active, you get a secure scaffold.

## See also

- [`/securecoder-review` guide](securecoder-review.md) — verify what the supervised agent produced
- [`/securecoder-advise` guide](securecoder-advise.md) — look up controls the agent cited
- [Scenarios guide](../scenarios.md) — Scenario 2 (new project) uses `/securecoder-build` as the centerpiece
