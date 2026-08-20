# Provider-Neutral Workflow Refactor

## Summary

Remove every local ledger/vault responsibility and reference, while retaining enforced workflow governance. The tracker becomes the sole durable source for work state and artifacts. A new integration gateway owns provider communication; the orchestrator remains limited to skill execution, contracts, retries, and reflection.

Existing workflow commands remain, except the ledger bypass commands, and are redefined over generic tracker and SCM contracts.

## Public Contracts

- Add a separate `workflow-integrations` MCP gateway exposing only generic operations:
  - Tracker: `get_work_item`, `search_work_items`, `create_work_item`, `list_children`, `transition_work_item`, `publish_artifact`, `list_artifacts`, `link_development_artifact`.
  - SCM: `get_pull_request`, `create_pull_request`, `list_review_threads`, `reply_to_thread`, `link_work_item`.
- Normalize provider data into:
  - `WorkItemKind`: `epic`, `feature`, `user_story`, `task`, `bug`.
  - `LogicalState`: `backlog`, `ready`, `in_progress`, `done`, `canceled`.
  - `WorkItem`, `ArtifactRef`, `PullRequest`, `ReviewThread`, and provider-neutral paginated results/errors.
- Define stable error codes including `not_configured`, `unauthorized`, `not_found`, `invalid_mapping`, `unsupported_capability`, `rate_limited`, `provider_unavailable`, `conflict`, and `validation_failed`.
- Store only non-secret integration configuration in `.codex-workflows/integrations.json`; provider credentials remain in the provider tool’s credential store.
- Support Linear and Azure DevOps tracker adapters, plus GitHub and Azure Repos SCM adapters.
- Keep provider names, tool names, field mappings, pagination, authentication, and transport entirely inside adapters. Core skills and the orchestrator see only normalized contracts.

## Implementation Phases

1. **Create the resumable implementation record**
   - Add a neutral tracked migration plan and adapter-boundary ADR under `docs/`.
   - Record decisions, ordered milestones, current status, verification evidence, and the exact next step after every completed milestone.
   - Use neutral terminology so the completed repository contains no references to the removed branded ledger system.

2. **Build the integration gateway and contracts**
   - Add the gateway as an independent MCP server; do not add transport or proxy responsibilities to the orchestrator.
   - Implement a reusable downstream MCP/tool client and adapter registry.
   - Implement tracker artifact persistence through `publish_artifact`/`list_artifacts`; adapters may use comments, documents, or attachments but must provide idempotent revision keys and normalized references.
   - Implement Linear through its official remote MCP and Azure DevOps through the official MCP work-item domains. Linear supports issue/project/comment operations, while Azure’s MCP exposes work-item, hierarchy, comment, artifact-link, and PR operations. [Linear MCP](https://linear.app/docs/mcp), [Azure DevOps MCP toolset](https://github.com/microsoft/azure-devops-mcp/blob/main/docs/TOOLSET.md).

3. **Implement bootstrap and configuration**
   - Move managed runtime files beneath `.codex-workflows/runtime/` so `integrations.json` survives upgrades.
   - Interactive bootstrap selects and authenticates a tracker, discovers projects/teams/types/states, proposes logical mappings, and asks the user to confirm them.
   - Linear defaults: Epic → Project; Feature/Story/Task/Bug → issues using confirmed labels, project membership, and parent relationships.
   - Azure defaults: map logical kinds to process-discovered work-item types and logical states to discovered workflow states.
   - Detect SCM from `origin`, then require confirmation of GitHub or Azure Repos.
   - Present provider-aware branch presets plus an explicit custom option. Every template must contain `{key}`; supported placeholders are `{category}`, `{key}`, `{slug}`, and `{user}`. Validate the selected template against sample branches before saving it.
   - Require re-bootstrap for existing installations. Remove old hook entries generically by managed runtime path/provenance; retain no legacy filenames or cleanup signatures.
   - Provide non-interactive setup through a validated configuration file.
   - Fail installation if required provider capabilities cannot be discovered; never persist tokens.

4. **Redefine workflows without changing the orchestrator’s role**
   - Retain `start-ticket`, `write-spec`, `resolve-ticket`, feature-stack workflows, and `review-pr`.
   - Skills fetch work items/artifacts through the gateway, pass normalized ground truth into the orchestrator, and publish accepted results back through the gateway.
   - Make orchestrator handlers pure with respect to integrations and persistence: no tracker calls, provider dispatch, local ticket files, session files, or artifact writes.
   - Publish specifications, implementation plans, critic history, resolution reports, verification evidence, PR-review reports, and interruption checkpoints as tracker artifacts.
   - On resume, retrieve the work item and its latest artifacts/checkpoint from the tracker.
   - Remove vendor names and provider mechanics from core skills; move those details into adapter documentation and tests.

5. **Replace ledger-era policies with provider-neutral enforced policies**
   - Remove vault deletion blocking, Markdown allowlisting/purge behavior, session bootstrapping, transcript-based tracker verification, skip/resume commands, flags, and bypasses.
   - Retain host pre-tool hooks and payload adapters, but rewrite the shared policy engine around generic work context.
   - Enforce, fail closed:
     - protected branches cannot receive governed writes or mutating Git operations;
     - the current branch must match the configured convention and resolve to exactly one tracker item;
     - the item must be in logical `in_progress` before code-changing tools run;
     - required accepted spec artifacts must exist before implementation writes;
     - each worktree/branch may map to only one active item;
     - ticket start requires a valid ticket branch and existing sync/unmerged-commit checks;
     - transition to `done` requires accepted specs, resolution report, verification evidence, and a linked PR.
   - Missing configuration, authentication, gateway availability, or ambiguous mappings block governed actions with repair guidance. Bootstrap, authentication, uninstall, and repair operations receive narrowly defined exemptions.
   - Enforce the same transition rules inside the gateway as defense in depth; hooks remain the required host-facing policy mechanism.

6. **Remove obsolete content and update packaging**
   - Delete the complete tracked legacy vault tree rather than migrating or archiving it.
   - Delete local ticket/session runtimes, branded ticket creation helpers, skip/resume skills and commands, obsolete tests/fixtures, and historical documentation containing removed references.
   - Remove provider-specific mechanics from review and feature skills.
   - Update manifests, plugin descriptions, release packaging, installer/uninstaller behavior, README, changelog, and integration documentation.
   - Add a repository-wide validation gate proving no shipped file contains the removed vault name, branded ledger phrase, bypass command names, session paths, or YouTrack-specific behavior.

## Test Plan

- Standardize the baseline command as `python3 -m unittest discover -s test -t . -p "test_*.py"`; the current suite passes 271 tests with this discovery root.
- Add a shared adapter contract suite, executed against fake Linear and Azure DevOps tools, covering creation of every logical kind, hierarchy, discovery/mapping, state transitions, pagination, artifacts, idempotency, and normalized failures.
- Add SCM contract tests for GitHub and Azure Repos PR creation, retrieval, review threads, replies, and tracker linking.
- Test the gateway independently from the orchestrator and prove provider tool names never appear in orchestrator inputs/outputs or core skills.
- Test bootstrap interactively and non-interactively, including preset/custom branch formats, invalid placeholders, capability discovery, authentication failure, upgrades, uninstall, and secret leakage.
- Test every supported host hook for protected branches, malformed branches, missing/ambiguous items, wrong state, missing specs, completion prerequisites, gateway outages, and repair exemptions.
- Add end-to-end matrices for Linear+GitHub, Linear+Azure Repos, Azure Boards+GitHub, and Azure Boards+Azure Repos.
- Verify release archives contain both MCP servers, all four adapters, rewritten hooks, and no obsolete files or references.

## Assumptions

- Trackers are the only durable runtime store for work state and generated workflow artifacts; repository configuration and architecture documentation are not ticket ledgers.
- No historical local content is migrated.
- There is no policy bypass equivalent.
- The orchestrator’s role and responsibility remain unchanged.
- Linear branch presets retain its issue identifier because Linear’s integrations use that identifier to associate code activity; Azure branches use the configured work-item key and are explicitly linked by the adapter. [Linear code integration](https://linear.app/integrations/github), [Azure Boards linking](https://learn.microsoft.com/en-us/azure/devops/boards/github/link-to-from-github?view=azure-devops).

Next action: implement the resumable migration document and generic integration contracts before touching installer, workflow, or policy behavior.
