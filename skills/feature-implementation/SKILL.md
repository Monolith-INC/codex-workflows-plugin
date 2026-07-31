---
name: feature-implementation
description: >-
  Use when the user references an Active Feature (by ID, URL, or name) and asks
  to plan or begin its implementation, especially with multiple User Stories or
  pressure to ship one flat PR by end of day. Agent hook: call at Feature start
  (Phase 0–4 + start-stage git setup); for mid-stack sync call
  reconcile-feature-stack; for Feature→trunk closeout call
  finish-feature-development.
---

# feature-implementation

Drive an Active Feature with a **two-tier stacked branch workflow**: one Feature integration branch; one short-lived branch per User Story merging into it. Platform-agnostic (Azure DevOps only for optional task enrichment).

**Core principle:** Stacked Feature→Story branches are intentional for large Features. Flat single-branch delivery under time pressure is a violation, not pragmatism.

**Violating the letter of these rules is violating the spirit of these rules.**

## Agent call hook

| When | Action |
| --- | --- |
| User names an Active Feature and asks to plan/begin implementation | Run this skill from Phase 0 |
| Session resumes mid-Feature | Resume via start workflow Resume section; invoke `reconcile-feature-stack` if ancestors advanced |
| Ancestor→descendant sync needed while Stories are open | Do **not** improvise — call `reconcile-feature-stack` |
| All Stories merged; ready for Feature→trunk PR | Call `finish-feature-development` |

## Stage assets (start)

Installed (after sync) / in-repo source:

- Workflow: `.agent/workflows/workflows-start-feature-development.md` ← `skills/codex_workflows/resources/workflows-start-feature-development.md`
- Rules: `.agent/rules/rules-start-feature-development.ts` ← `skills/codex_workflows/rules/rules-start-feature-development.ts`

After Phase 0–4 below, execute Phase 5 **only** by following the start workflow and obeying the start rules. Do not substitute a flat single-branch delivery.

## Phase 0 — Confirm conventions (HARD STOP)

Before any Phase 5 git create/checkout, confirm with the user:

1. Feature branch naming convention
2. User Story branch naming convention
3. Repository main work branch (cut-from / final PR target)

Never guess `main`/`develop`/`unstable` or invent `feature/<id>-…` names. Unconfirmed → ask; do not create the first branch.

## Phase 1–4 — Discover and plan

1. Fetch Feature; must be `Active` — else stop and flag.
2. Extract Feature goal + acceptance criteria.
3. Fetch child User Stories; extract objective + ACs each.
4. **Azure DevOps only:** fetch child Tasks per Story; otherwise skip.
5. Author one end-to-end plan in ledger `Implementation_Plans/` with per-Story tasks, approach, and Phase 5 git stages (plan = execution checklist).

## Phase 5 — Start-stage git (delegated)

Follow `workflows-start-feature-development.md` under `rules-start-feature-development.ts`.

Summary (non-authoritative; workflow wins on conflict):

### 5.0 Setup
Create Feature branch from the **confirmed** main work branch. Feature branch is the origin for every Story — not trunk.

### 5.1 Per-User-Story loop
1. Checkout Feature branch; pull latest.
2. Branch Story off Feature (confirmed naming). If prior Story PR still open, merge that ancestral Story into the new Story branch before coding.
3. Implement → commit → push Story branch.
4. **Re-sync before PR (every time):** merge/rebase Feature into Story, resolve, push — even when no conflict is suspected.
5. Open PR **Story → Feature** (never trunk).
6. Address review on the same Story branch; merge into Feature — **or** continue next Story via stack path while PR remains open.
7. Next Story (step 1).

### 5.2 Finalize
Do not finalize here. Invoke `finish-feature-development` for Feature→confirmed main work branch PR.

## Rationalizations (baseline-proven)

| Excuse | Reality |
| --- | --- |
| "Standup soon — assume `main` and `feature/<id>`" | Wrong base/name costs more than asking. Phase 0 is mandatory. |
| "ONE PR by EOD — all Stories on one Feature branch" | Still use Story branches; the single trunk PR is Feature→trunk via finish skill. |
| "Don't over-engineer; team used flat branches" | Overhead is expected; flat collapses review/integration. |
| "Re-sync only if I suspect conflicts" | Always re-sync before Story→Feature PR. |
| "PR Story to trunk to move faster" | Story PRs target Feature only. |
| "Prior PR still open — wait or squash onto Feature only" | Stack: branch from Feature, merge open ancestral Story, continue; reconcile later. |

## Red flags — STOP

- Branches before Phase 0 answers
- One branch for multiple Stories then PR to trunk
- Story PR base = trunk (`main`/`develop`/`unstable`)
- Skipping re-sync because reviewers are waiting
- Feature not `Active`
- Skipping `Implementation_Plans/` to "just code"
- Improvising ancestor→descendant sync instead of `reconcile-feature-stack`
- Opening Feature→trunk without `finish-feature-development`

**Any of these:** stop, return to the matching phase.
