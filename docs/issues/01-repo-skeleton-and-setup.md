# 01 — Repo skeleton + plugin.json + `/securecoder-setup` minimal wizard

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

The foundation slice. Establishes the repo as a mattpocock-style skills bundle and ships the first working skill (`/securecoder-setup`) end-to-end.

Create the repo skeleton: `README.md`, `CHANGELOG.md`, `LICENSE`, `.claude-plugin/plugin.json` listing all seven skill paths (even though most are stubs at this point), and `skills/security/<skill-name>/SKILL.md` for each of the seven skills as a stub with valid frontmatter (name, description) so skills.sh recognizes them after install.

Implement `/securecoder-setup` fully against the spec in design.md §3.1 and prd.md "Per-skill specifics":

- 8-question wizard, asked one at a time, defaults pre-selected
- Validates and writes `.securecoder/config.json` against the v1.0 schema
- Re-running loads existing values as defaults instead of starting from scratch
- `.securecoder/.gitignore` written so `runs/` and `reviews/` are ignored but `config.json` is tracked
- Surfaces the privacy note explicitly when the user enables a compliance framework (data egress: LLM calls send code to the host model provider)

A README with quickstart, supported hosts, and a Privacy section.

## Acceptance criteria

- [ ] Running `npx skills@latest add nerdy-krishna/securecoder` (against a local checkout) installs all seven skill stubs into the host agent's skill dir
- [ ] All seven skills appear in the host agent's slash-command menu after install
- [ ] Invoking `/securecoder-setup` walks the user through the 8 questions in order and writes `.securecoder/config.json` matching the schema in design.md §3.1
- [ ] `.securecoder/config.json` is checked in by default; `.securecoder/.gitignore` ignores `runs/` and `reviews/`
- [ ] Re-invoking `/securecoder-setup` on an existing config pre-selects current values rather than asking from scratch
- [ ] The privacy note about LLM data egress is shown when the user selects any compliance framework
- [ ] `CHANGELOG.md` records this as the v0.1.0 entry
- [ ] README documents install command, the seven skills' purposes, the privacy section, and a "first scan in 5 minutes" walkthrough placeholder (real walkthrough lands once `/securecoder-scan` exists in slice 02)

## Blocked by

None — can start immediately.
