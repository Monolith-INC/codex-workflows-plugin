/**
 * Rules for workflows-start-feature-development.md only.
 * Binding: skills/codex_workflows/resources/workflows-start-feature-development.md
 * Installed as: .agent/workflows/workflows-start-feature-development.md
 */
export const workflow = "workflows-start-feature-development.md" as const;

export const rules = [
  "CONFIRM Feature branch naming, User Story branch naming, and main work branch with the user before any git create or checkout.",
  "DO NOT invent branch names or guess main/develop/unstable/trunk.",
  "DO NOT create the Feature branch until Phase 0 answers are confirmed.",
  "CREATE the Feature branch only from the confirmed main work branch.",
  "CREATE every User Story branch from the Feature branch, never from trunk.",
  "WHEN a prior Story PR is still open, CREATE the next Story branch from Feature and MERGE that open ancestral Story into it before new work.",
  "OPEN every Story pull request with base = Feature branch.",
  "DO NOT open a Story pull request with base = trunk.",
  "BEFORE every Story→Feature pull request, MERGE or REBASE the Feature branch into the Story branch and PUSH, even when conflicts are not suspected.",
  "DO NOT place multiple User Stories on one branch then PR that branch to trunk.",
  "DO NOT skip writing the Implementation Plan under Implementation_Plans/.",
  "ON resume, READ the Active ledger and open Story PRs before new commits.",
  "ON resume, IF an ancestor Story advanced after a descendant branched, INVOKE reconcile-feature-stack before continuing.",
  "WHEN all Stories are merged into Feature, INVOKE finish-feature-development; DO NOT open Feature→trunk from this workflow.",
] as const;
