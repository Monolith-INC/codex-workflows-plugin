# Feature Implementation Skill

## Purpose

Given a **Feature** work item with status `Active`, produce an end-to-end implementation plan that decomposes the feature into its child User Stories, and drive the implementation of that plan using a **two-tier feature-branch (stacked) git workflow** — one integration branch for the feature, with a short-lived branch per User Story merging back into it.

This skill is **platform-agnostic**: Azure DevOps is only relevant to Phase 3 (task-level enrichment), not to the workflow itself. The two-tier branch structure is a deliberate design choice — it exists to automate implementation of large chunks of work (whole Features at once), and the added coordination overhead versus a flat single-tier branch strategy is intentional and expected, not a flaw to design around.

## Trigger

Invoke this skill when the user references an active Feature (by ID, URL, or name) and asks to plan or begin its implementation.

## Inputs

- The Feature identifier (Azure DevOps work item ID, vault ticket path, or equivalent).
- Repository access (git) and, if applicable, Azure DevOps access.

## Phase 0 — Confirm Project Conventions

Branch naming is project-specific and cannot be inferred. Before any git action in Phase 5, ask the user to confirm:

1. **Feature branch naming convention** (e.g. `feature/<id>-<slug>`, `epic/<id>`, or whatever this project uses).
2. **User Story branch naming convention** (e.g. `feature/<id>/<story-id>-<slug>`, `<story-id>-<slug>`, etc.).
3. **The repository's main work branch name** — the branch the Feature branch is cut from and the branch the finished Feature branch will PR into (e.g. `main`, `develop`, `unstable`).

Do not proceed to Phase 5 with an assumed convention. If any of the three is unconfirmed, ask before creating the first branch.

## Phase 1 — Feature Discovery

1. Fetch the Feature work item. Confirm its status is `Active` — if not, stop and flag this to the user before proceeding.
2. Extract:
   - The Feature's **goal** (the outcome it exists to deliver).
   - Its **acceptance criteria** item list.

## Phase 2 — User Story Discovery

1. Fetch all child **User Stories** linked to the Feature.
2. For each User Story, extract:
   - Its **objective**.
   - Its **acceptance criteria**.

## Phase 3 — Task Discovery (Azure DevOps only)

- **If** the work item source is Azure DevOps: for each User Story, additionally fetch its child **Tasks**.
- **Otherwise**: skip this phase and proceed directly to plan authoring using the Feature + User Story data gathered above.

## Phase 4 — Implementation Plan Authoring

1. Author a single implementation plan that covers the Feature **end to end**, containing, for every User Story:
   - A **task list** (from Azure DevOps tasks if available, otherwise derived from the acceptance criteria).
   - A **description** of the implementation approach.
2. Store the plan under the ledger, in the `Implementation_Plans/` folder.
3. The plan must also lay out the **git workflow stage** that sits between each User Story (see Phase 5) so the plan doubles as an execution checklist, not just a design document.

## Phase 5 — Git Workflow: Two-Tier Feature Branch Pattern

This is a **stacked branch workflow**: the Feature branch is the integration point ("origin") for the duration of the feature; every User Story branch is a short-lived child of it.

### 5.0 — One-time setup

- Create the **Feature branch** from the repository's main work branch (as confirmed in Phase 0), named per the **Feature branch naming convention confirmed in Phase 0** — never a guessed or assumed pattern.
- This Feature branch is the **origin** for every subsequent step in this phase — not the repo's main branch.

### 5.1 — Per-User-Story loop (repeat for every User Story in the plan)

1. **Sync**: `checkout` the Feature branch, `pull` to update it with the latest merged work.
2. **Branch**: create a new branch for the User Story off the Feature branch, named per the **User Story branch naming convention confirmed in Phase 0**.
3. **Implement**: do the work described in that User Story's task list.
4. **Commit**: commit the work on the User Story branch.
5. **Push**: push the User Story branch to the remote.
6. **Rule — re-sync before PR**: check whether the Feature branch has advanced (received other merges) since this branch was created in step 2. If it has, merge/rebase the Feature branch's latest state into the User Story branch, resolve any conflicts, and push again before opening the PR. This applies every time, not only when a conflict is suspected.
7. **Open PR**: open a pull request from the User Story branch **targeting the Feature branch** (not the repo's main branch).
8. **Code review**: the PR is reviewed; address feedback with additional commits/pushes to the same branch as needed.
9. **Merge**: once approved, merge the PR into the Feature branch.
10. Return to step 1 for the next User Story, until all User Stories are implemented.

### 5.2 — Feature branch finalization

1. Once every User Story is merged into the Feature branch, push the Feature branch one final time.
2. Open a pull request from the Feature branch **targeting the repository's main work branch**.
3. Review the PR.
4. Merge it into the repository's main work branch.

