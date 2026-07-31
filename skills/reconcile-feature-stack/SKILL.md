---
name: reconcile-feature-stack
description: >-
  Use when an Active Feature has stacked User Story branches and an ancestor
  (Feature or older Story) advanced after a descendant branched — including
  review fixes on an open Story PR that later Stories stacked on. Agent hook:
  call before new commits on a descendant after any ancestor push/merge;
  do not improvise merge order.
---

# reconcile-feature-stack

Propagate ancestor commits through descendant User Story branches for an Active Feature stack.

## Agent call hook

| When | Action |
| --- | --- |
| Ancestor Story or Feature gained commits while descendant Stories exist | Run this skill before further descendant work |
| `feature-implementation` resume detects ancestor advanced after descendant branched | Run this skill, then resume Story work |
| User asks to sync / reconcile the feature stack | Run this skill |

Do **not** call this skill to start a Feature or to open Feature→trunk (use `feature-implementation` / `finish-feature-development`).

## Stage assets

- Workflow: `.agent/workflows/workflows-reconcile-feature-stack.md` ← `skills/codex_workflows/resources/workflows-reconcile-feature-stack.md`
- Rules: `.agent/rules/rules-reconcile-feature-stack.ts` ← `skills/codex_workflows/rules/rules-reconcile-feature-stack.ts`

## Steps

1. Confirm Active Feature and Feature branch name.
2. Follow `workflows-reconcile-feature-stack.md`.
3. Obey every command in `rules-reconcile-feature-stack.ts`.
4. Report which Story branches were updated and any conflict resolutions.
