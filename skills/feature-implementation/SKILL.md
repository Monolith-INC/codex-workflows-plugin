---
name: feature-implementation
description: >-
  Use when the user references an Active Feature (by ID, URL, or name) and asks
  to plan or begin its implementation, especially with multiple User Stories or
  pressure to ship one flat PR by end of day.
---

# feature-implementation

Drive an Active Feature with a **two-tier stacked branch workflow**: one Feature integration branch; one short-lived branch per User Story merging into it. Platform-agnostic (Azure DevOps only for optional task enrichment).

**Core principle:** Stacked Feature→Story branches are intentional for large Features. Flat single-branch delivery under time pressure is a violation, not pragmatism.

**Violating the letter of these rules is violating the spirit of these rules.**

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

## Phase 5 — Two-tier git workflow

### 5.0 Setup
Create Feature branch from the **confirmed** main work branch. Feature branch is the origin for every Story — not trunk.

### 5.1 Per-User-Story loop
1. Checkout Feature branch; pull latest.
2. Branch Story off Feature (confirmed naming).
3. Implement → commit → push Story branch.
4. **Re-sync before PR (every time):** if Feature advanced since branch creation, merge/rebase Feature into Story, resolve, push — even when no conflict is suspected.
5. Open PR **Story → Feature** (never trunk).
6. Address review on the same Story branch; merge into Feature.
7. Next Story (step 1).

### 5.2 Finalize
Push Feature; open PR **Feature → confirmed main work branch**; review; merge.

## Rationalizations (baseline-proven)

| Excuse | Reality |
| --- | --- |
| "Standup soon — assume `main` and `feature/<id>`" | Wrong base/name costs more than asking. Phase 0 is mandatory. |
| "ONE PR by EOD — all Stories on one Feature branch" | Still use Story branches; the single trunk PR is Feature→trunk. |
| "Don't over-engineer; team used flat branches" | Overhead is expected; flat collapses review/integration. |
| "Re-sync only if I suspect conflicts" | Always re-sync before Story→Feature PR. |
| "PR Story to trunk to move faster" | Story PRs target Feature only. |

## Red flags — STOP

- Branches before Phase 0 answers
- One branch for multiple Stories then PR to trunk
- Story PR base = trunk (`main`/`develop`/`unstable`)
- Skipping re-sync because reviewers are waiting
- Feature not `Active`
- Skipping `Implementation_Plans/` to "just code"

**Any of these:** stop, return to the matching phase.
