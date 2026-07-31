---
description: Finish feature development — Feature→trunk PR after Stories merge
rules: rules-finish-feature-development.ts
---

# workflows-finish-feature-development

## Given
- Active Feature branch exists
- All User Story work for the Feature is merged into the Feature branch
- No required open Story PRs remain (or user explicitly waives remaining Stories)

## Sequence
1. VERIFY every required Story PR is merged into Feature
2. IF any required Story PR still open THEN STOP and INVOKE reconcile-feature-stack only if sync is needed; DO NOT open Feature→trunk
3. CHECKOUT Feature branch
4. PULL Feature branch latest
5. RUN project verification commanded by the repo (tests / lint as applicable)
6. PUSH Feature branch
7. OPEN pull request Feature → confirmed main work branch
8. ADDRESS review on Feature branch
9. MERGE Feature PR into main work branch when approved
10. UPDATE Active ledger with Feature PR URL and merge outcome
11. STOP

## Forbidden in this stage
- Creating new User Story branches
- Opening Story→Feature PRs
- Merging Stories that are not ready
