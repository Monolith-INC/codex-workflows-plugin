# Provider-neutral workflow implementation

## Bootstrap checkpoint

1. Select tracker: Linear or Azure DevOps Boards.
2. Select SCM: GitHub or Azure Repos.
3. Discover provider tools and confirm logical kind/state mappings.
4. Choose a branch template preset or `other`; custom templates must include `{key}`.
5. Persist `.codex-workflows/integrations.json` and verify both MCP servers.

## Work checkpoint

1. Resolve the current branch to exactly one tracker work-item key.
2. Fetch the work item and transition it to logical `in_progress`.
3. Publish specification artifacts through the tracker adapter.
4. Implement and verify on the configured branch.
5. Create/link a pull request through the SCM adapter.
6. Publish resolution and verification artifacts, then request logical `done`.

## Interruption recovery

On restart, rerun bootstrap verification, read the configured work item and its artifacts, inspect the linked pull request, and continue from the first incomplete checkpoint. The orchestrator does not reconstruct local session files. If the gateway, credentials, or mappings are unavailable, hooks fail closed; repair the integration configuration and rerun verification before writing.

## Responsibility boundaries

The orchestrator discovers skills, invokes them, validates contracts, retries transient failures, and reflects on drafts. The `workflow-integrations` gateway performs provider calls. Tracker adapters own tracker payloads and mappings; SCM adapters own repository and pull-request payloads. Core skills only use the abstract contract.
