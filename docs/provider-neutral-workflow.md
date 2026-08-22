# Provider-neutral workflow implementation

The workflow is intentionally modeled around logical roles rather than vendor
objects. Skills talk about Epics, Features, User Stories, Tasks, Bugs, states,
artifacts, and development links. Adapters translate that contract into Linear,
Azure DevOps Boards, or local tracker storage.

The key design promise is that a team can change tracker provider without
rewriting the workflow skills. The provider boundary sits behind the
`workflow-integrations` gateway; the orchestrator remains instruction-only.
Agent-host details are a different boundary: host hook payload parsing and
decision formatting live under `scripts/host_adapters/`, while tracker and SCM
provider behavior lives under `scripts/integrations/`.

## Bootstrap checkpoint

1. Select tracker: Linear, Azure DevOps Boards, or local tracker.
2. Select SCM: GitHub or Azure Repos.
3. Discover provider tools and confirm logical kind/state mappings.
4. Choose a branch template preset or `other`; custom templates must include `{key}`.
5. Persist `.codex-workflows/integrations.json` and verify both MCP servers.

When local tracker is selected, bootstrap creates `.local-tracker/` with state
folders for `backlog`, `ready`, `in_progress`, `done`, and `canceled`; records
are committed by default and the user may instead select the managed ignore
policy.

Example non-interactive local bootstrap:

```bash
python3 -m scripts.installer.bootstrap \
  /path/to/codex-workflows-plugin-0.5.24.zip \
  --dest /path/to/app \
  --target all-agents \
  --tracker local_tracker \
  --local-tracker-storage committed \
  --scm github \
  --branch-template 'story/{key}-{slug}'
```

The generated tracker root is deliberately small and inspectable:

```text
.local-tracker/
  backlog/
    STORY-0001.json
  ready/
  in_progress/
  done/
  canceled/
  artifacts/
    STORY-0001/
      implementation-plan-001.md
      resolution-report-001.md
```

External providers use their own storage, but expose the same logical contract:
work-item lookup, state transition, children, artifact publication, and
development links.

The bootstrap result must answer these questions for later hooks and skills:

- Which tracker adapter owns work-item state?
- Which SCM adapter owns pull requests and review threads?
- Which provider states map to `backlog`, `ready`, `in_progress`, `done`, and
  `canceled`?
- Which provider kinds map to Epic, Feature, User Story, Task, and Bug?
- Which branch template contains the single required `{key}` placeholder?
- Is tracker enforcement currently `enforced` or `skipped`?

## Tracking pause

`/skip-tracker` records `tracking.mode: skipped` without removing the configured
provider. While skipped, tracker gateway operations and tracker-dependent
workflows are unavailable, and tracker-only hook checks are bypassed. SCM
workflows and protected-branch Git safety remain active. `/resume-tracker`
returns the mode to `enforced`; `/tracking-status` shows the current mode and
provider.

Use pause mode for work that should not claim, transition, or publish to a
tracker item:

```text
/skip-tracker
# edit non-ticket release documentation or investigate locally
/tracking-status
/resume-tracker
```

The mode is a pause, not a removal. Bootstrap-discovered provider bindings,
state mappings, and branch templates remain in `.codex-workflows/integrations.json`.

While paused, tracker calls are rejected through the gateway so workflows do
not accidentally write partial artifacts to a stale provider. The pause is
visible through `/tracking-status`, making it explicit when a repository is
running in untracked mode.

## Work checkpoint

1. Resolve the current branch to exactly one tracker work-item key.
2. Fetch the work item and transition it to logical `in_progress`.
3. Publish specification artifacts through the tracker adapter.
4. Implement and verify on the configured branch.
5. Create/link a pull request through the SCM adapter.
6. Publish resolution and verification artifacts, then request logical `done`.

Example branch and item flow:

```text
Branch template: story/{key}-{slug}
Branch:          story/ENG-42-add-login
Tracker item:    ENG-42
State path:      backlog -> in_progress -> done
Artifacts:       implementation-plan.md, verification.md, resolution-report.md
SCM link:        pull request URL stored as a development link
```

Expected durable evidence for a finished tracked item:

| Artifact | Produced by | Purpose |
| --- | --- | --- |
| Implementation/spec artifact | `/write-spec` | Defines accepted scope, approach, and verification before implementation. |
| Pull request link | SCM adapter | Connects tracker state to reviewable code. |
| Review report | `/review-pr` | Captures reviewer decisions and follow-up handling. |
| Resolution report | `/resolve-ticket` | Records what changed, how it was verified, and any residual risk. |

## Feature/story checkpoint

1. Resolve the feature work item and list child stories through the tracker adapter.
2. Publish the feature implementation plan; create the feature branch from the bootstrap template.
3. Implement stories on stacked branches with pull requests targeting the feature branch.
4. Reconcile ancestor updates into descendants before further descendant commits.
5. After stories complete, open the feature→trunk pull request, publish closeout artifacts, and request logical `done`.

The generic hierarchy is:

```text
Epic -> Feature -> User Story -> Task
                  -> Bug        -> Task
```

An Epic records the product or organizational outcome. A Feature groups a
deliverable slice. A User Story captures user-facing behavior. A Task captures
implementation work. Bug keeps compatibility with existing defect workflows
and can own Tasks when the work is corrective rather than planned feature work.

Example local hierarchy:

```text
EPIC-0001 Verified delivery
  FEATURE-0001 Quality gates
    STORY-0001 Add canonical quality runner
      TASK-0001 Configure Ruff and mypy
      TASK-0002 Configure Markdown lint
    STORY-0002 Block releases without quality checks
  FEATURE-0002 Tracker flexibility
    STORY-0003 Add skip/resume tracking mode
    STORY-0004 Add local tracker adapter
```

## Interruption recovery

On restart, rerun bootstrap verification, read the configured work item and its artifacts, inspect the linked pull request, and continue from the first incomplete checkpoint. The orchestrator does not reconstruct local session files. If the gateway, credentials, or mappings are unavailable, hooks fail closed; repair the integration configuration and rerun verification before writing.

## Responsibility boundaries

The orchestrator discovers skills, invokes them, validates contracts, retries transient failures, and reflects on drafts. The `workflow-integrations` gateway performs provider calls. Tracker adapters own tracker payloads and mappings; SCM adapters own repository and pull-request payloads. Core skills only use the abstract contract.
