---
name: resume-ledger
description: >-
  Use when the user issues /resume-ledger or asks to restore workflow ledger
  hook enforcement after a prior /skip-ledger.
---

# resume-ledger

Clear the skip flag so ledger hooks enforce again.

## Steps

1. Resolve the vault directory (usually the workspace `AI_Codex` folder).
2. Delete `{vault}/.codex_ledger_skip` if present (use Python `Path.unlink`).
3. Confirm whether enforcement was restored or the flag was already absent.

Prefer:

```python
from scripts.policy.ledger_skip import disable_ledger_skip
disable_ledger_skip(vault_dir)
```
