---
name: finish-feature-development
description: >-
  Use when an Active Feature's User Stories are merged into the Feature branch
  and it is time to open Feature→trunk for closeout. Agent hook: call after
  Story→Feature merges complete; do not use for mid-stack sync (use
  reconcile-feature-stack) or Feature start (use feature-implementation).
---

# finish-feature-development

Close an Active Feature stack by opening and merging Feature → confirmed main work branch.

## Agent call hook

| When | Action |
| --- | --- |
| All required Stories merged into Feature | Run this skill |
| User asks to finish / close the Feature issue | Run this skill after verifying Story merges |
| `feature-implementation` reaches finalize | Hand off to this skill |

Do **not** call this skill to start a Feature or to reconcile open Story stacks.

## Stage assets

- Workflow: `.agent/workflows/workflows-finish-feature-development.md` ← `skills/codex_workflows/resources/workflows-finish-feature-development.md`
- Rules: `.agent/rules/rules-finish-feature-development.ts` ← `skills/codex_workflows/rules/rules-finish-feature-development.ts`

## Steps

1. Confirm Feature branch and main work branch from Phase 0 / ledger.
2. Follow `workflows-finish-feature-development.md`.
3. Obey every command in `rules-finish-feature-development.ts`.
4. Report Feature PR URL.
