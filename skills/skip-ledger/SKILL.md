---
name: skip-ledger
description: >-
  Use when the user issues /skip-ledger or asks to ignore workflow ledger hooks
  for the rest of this session (or until /resume-ledger).
---

# skip-ledger

Create a skip flag so related enforcement hooks are bypassed until resumed.

## Steps

1. Resolve the vault directory (usually the workspace `AI_Codex` folder).
2. Create `{vault}/.codex_ledger_skip` with:
   - `skipped_at` (ISO timestamp)
   - `reason` (user request)
3. Confirm to the user that session, ticket-lifecycle, YouTrack transcript, and
   protected-branch git guards are skipped until `/resume-ledger`.
4. Reminder: destructive vault deletes remain blocked.

Prefer:

```python
from scripts.policy.ledger_skip import enable_ledger_skip
enable_ledger_skip(vault_dir, reason="user issued /skip-ledger")
```
