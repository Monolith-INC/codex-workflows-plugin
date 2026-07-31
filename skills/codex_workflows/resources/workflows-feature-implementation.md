---
description: End-to-end flow for implementing features using the Codex Ledger
---

# Feature Implementation Workflow

> Prefer stage workflow: [workflows-start-feature-development.md](./workflows-start-feature-development.md) with rules `rules-start-feature-development.ts`. Mid-stack: `reconcile-feature-stack`. Closeout: `finish-feature-development`.

This workflow provides a rigorous, documentation-first protocol for feature development, ensuring all architectural decisions are anchored in the **AI_Codex**.

## 1. Context & Research (The Mandate)

1.  **Read Codex Index**: Start by reading `AI_Codex/README.md` to identify relevant architectural anchors.
2.  **Semantic Search**: Search `AI_Codex/Knowledge/` for patterns related to the task.
3.  **Identify Active Ledger**: Locate the ticket file in `AI_Codex/Tickets/Active/` (created via `/start-ticket`). If it doesn't exist, **ABORT** and run `/start-ticket` first.

## 2. Strategy & Implementation Lock

1.  **Draft Implementation Plan**: Write the plan directly into the **Codex Ledger**.
    - **Mandatory Content**: `### Codex Context`, `### Scope Boundary`, `### Dependency Tree`.
2.  **Architect Review**: Present the plan to the user. Do NOT proceed until you receive: **"IMPLEMENTATION APPROVED"**.

## 3. Execution Loop (Stage IV)

1.  **Sequential Execution**: Apply changes file-by-file. Adhere to **Rule 14 (Mandatory Checkpoints)**.
2.  **Sync**: After each atomic task (e.g., "Add Repository", "Update UI"), update the Codex Ledger with:
    - **Outcome**: Technical result.
    - **Deviations**: Any diverge from the original plan.
3.  **Static Analysis**: After each significant write, run `fvm flutter analyze` to ensure no regressions.

## 4. Quality Assurance

1.  **Run Tests**: Execute `fvm flutter test` for the affected modules.
2.  **Verify UI**: If applicable, run `/run-web-verification`.

## 5. Handoff

1.  **Finalize Ledger**: Append final considerations and technical debt to the Codex Ledger.
2.  **Commit**: Run `/commit` to finalize changes.
3.  **Resolve**: Once the PR is ready, run `/resolve-ticket`.

## Usage & Invocation Examples

- `/implement-feature` (Assumes a ticket is already active)
- `/feature-implementation` → start stage assets above

**Architect Tip**: The Codex Ledger is your source of truth. If the model restarts, reading the active ticket file will restore your entire implementation state.
