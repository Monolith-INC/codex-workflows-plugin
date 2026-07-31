---
description: Reconcile ancestor Feature/Story commits into descendant Story branches
rules: rules-reconcile-feature-stack.ts
---

# workflows-reconcile-feature-stack

## Given
- Active Feature branch exists
- One or more descendant Story branches exist
- An ancestor (Feature or older Story) advanced after a descendant branched

## Sequence
1. IDENTIFY Feature branch name from ledger or remote
2. LIST open Story PRs with base = Feature ordered oldest→newest
3. CHECKOUT Feature branch
4. PULL Feature branch latest
5. FOR each Story branch in stack order (oldest open Story → newest):
   1. CHECKOUT Story branch
   2. PULL Story branch latest
   3. MERGE immediate ancestor into Story branch
      - First Story: ancestor = Feature
      - Later Story: ancestor = previous Story in stack (or Feature if prior Story already merged)
   4. IF conflicts THEN RESOLVE on Story branch THEN CONTINUE
   5. PUSH Story branch
   6. IF Story PR exists THEN UPDATE PR with pushed commits
6. VERIFY each open Story PR still targets Feature
7. STOP

## Loop invariant
After each Story iteration, that Story contains all commits from its ancestor at reconcile time.
