---
description: Start feature development — Feature branch, first Story, resume cues
rules: rules-start-feature-development.ts
---

# workflows-start-feature-development

## Given
- Active Feature identified
- Phase 0 conventions confirmed with user

## Sequence
1. VERIFY Feature is Active (or OPEN Feature treated as Active when platform has no Active state)
2. LOAD Feature goal and acceptance criteria
3. LOAD child User Stories (ledger and/or platform); IF none THEN STOP and request decomposition
4. WRITE or UPDATE Implementation Plan under vault `Implementation_Plans/`
5. CHECKOUT confirmed main work branch
6. PULL latest from origin for main work branch
7. CREATE Feature branch from main work branch using confirmed Feature naming
8. PUSH Feature branch with upstream
9. FOR each User Story in dependency order:
   1. CHECKOUT Feature branch
   2. PULL Feature branch latest
   3. IF prior Story PR still open THEN CREATE Story branch from Feature AND MERGE open ancestral Story into new Story branch ELSE CREATE Story branch from Feature using confirmed Story naming
   4. STOP this workflow for implementation handoff on current Story branch
   5. AFTER Story implementation commits: PUSH Story branch
   6. MERGE or REBASE Feature into Story branch
   7. PUSH Story branch
   8. OPEN PR Story → Feature
   9. IF continuing while PR open THEN LOOP to step 9.1 for next Story using stack path in 9.3
   10. ELSE WAIT merge into Feature THEN LOOP to next Story
10. WHEN all Stories merged into Feature THEN INVOKE finish-feature-development skill

## Resume
1. READ Active ledger and Implementation Plan
2. DETECT open Story PRs targeting Feature branch
3. DETECT current branch role (Feature | Story | trunk)
4. IF ancestor Story changed after descendant branched THEN INVOKE reconcile-feature-stack skill BEFORE new commits
5. CONTINUE Sequence at the earliest incomplete step
