---
date: 2026-06-07
type: workspace-index
tags: [ai-codex, workspace, lean-vault]
---

# AI_Codex

This vault tracks repository-local agent sessions and active work ledgers.

## Projects

- `codex-workflows-plugin`
- `airlock` — moved out; keeps its own ledger at `../airlock/AI_Codex/`

## Current Operating Rule

- Keep the vault lean unless a task requires more structure.
- Track active work in `AI_Codex/Projects/<project>/Tickets/Active/`.
- Track work sessions in `AI_Codex/Projects/<project>/Agent_Sessions/` (also discoverable at `AI_Codex/Agent_Sessions/`).
- Open sessions (`next: null`) may continue when the branch matches and the session is under 8 hours old; otherwise close and open a new session.
- `/skip-ledger` creates `AI_Codex/.codex_ledger_skip` to bypass ledger hooks until `/resume-ledger` (vault destructive deletes remain blocked).
