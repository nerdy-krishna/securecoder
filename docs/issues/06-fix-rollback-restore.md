# 06 — `/securecoder-fix --restore <run-id>` rollback path

- **Type:** AFK
- **Triage label:** ready-for-agent

## Parent

[PRD — securecoder v1](../prd.md)

## What to build

Adds the formal restore command that consumes the backups slice 05 captured. Until this slice, restore was implicit (the user could `git revert` commits, but had no way to recover non-git changes or to undo a whole batch atomically).

The user invokes either:
- `/securecoder-fix --restore <run-id>` (explicit run ID)
- Or asks the host agent in natural language ("restore the fix run from earlier today" / "undo my last securecoder-fix")

The skill:
1. Lists candidate runs from `.securecoder/runs/` (or scopes to the named one) and shows what would be restored — per-file diff between current state and backup state
2. Asks for confirmation
3. Restores every backed-up file from `.securecoder/runs/<run-id>/backups/<path>` over the current working tree
4. For git repos: if the fix commits are still on the branch, optionally also `git revert` them (asked) so the history reflects the rollback
5. Writes a `restore_log.md` to the run dir recording what was restored and when

Edge cases to handle:
- A file in the backup no longer exists in the working tree (user deleted) → restore creates it, asks if intended
- A file in the working tree has been modified since the fix landed → diff is shown; user confirms overwrite
- Multiple overlapping runs (user did two `/securecoder-fix` passes without restoring between) → restore is per-run, not cumulative; later run's backups are the older state for files it touched

## Acceptance criteria

- [ ] `/securecoder-fix --restore <run-id>` restores all backed-up files from the named run
- [ ] Natural-language ask ("undo last securecoder-fix", "restore run X") works
- [ ] Before applying, the skill shows a per-file diff between current state and backup state and asks for confirmation
- [ ] For git repos, the user is offered the option to also `git revert` the corresponding fix commits
- [ ] `restore_log.md` is written to the run dir
- [ ] Files in the backup that no longer exist in the working tree are flagged and the user confirms restoration
- [ ] Files modified since the fix landed show a diff; user confirms overwrite per-file or for the whole batch
- [ ] Non-git repos restore correctly using backups only
- [ ] Tests cover: backup-restore round-trip across multiple runs, restore with modified-since-fix file, restore in non-git repo, restore with deleted-since-fix file

## Blocked by

- 05 — `/securecoder-fix` for SAST findings (safety loop + commit-per-fix)
