# Codex Workflows Plugin

Provider-neutral workflow orchestration for agent hosts (v0.5.21). The plugin keeps the orchestrator focused on discovering skills, invoking them, validating contracts, retrying transient work, and reflecting on artifacts. It does not proxy provider calls.

## Architecture

- `scripts/orchestrator/` returns workflow instructions and artifact plans; it has no durable project state.
- `scripts/integrations/` is the provider gateway. It exposes generic tracker and SCM operations over MCP and delegates transport to configured adapters.
- `scripts/hook_runtime.py` enforces branch, work-item state, artifact, and completion preconditions. It fails closed when integration configuration or provider access is unavailable.
- Tracker systems are the durable work-state and artifact store. SCM systems own branches, pull requests, and review threads.

See [docs/provider-neutral-workflow.md](docs/provider-neutral-workflow.md) for bootstrap, work, feature/story, and recovery checkpoints. Roadmap status: [docs/roadmap.md](docs/roadmap.md).

## Bootstrap

Run the installer in the project root:

```sh
python3 -m scripts.installer.bootstrap --dest /path/to/project --target all-agents \
  --tracker linear --scm github --branch-template '{category}/{key}-{slug}'
```

The interactive wizard offers Linear or Azure DevOps Boards, GitHub or Azure Repos, provider scope, and branch presets plus an `other` option. A custom branch template must contain `{key}`. Bootstrap discovers provider tools (or verifies `gh` for GitHub), confirms logical kind/state mappings, and writes `.codex-workflows/integrations.json`; reinstallation preserves it. Use `--skip-discovery` only when applying presets without a live provider probe.

Linear and Azure DevOps are supported through tracker adapters. GitHub and Azure Repos are supported through separate SCM adapters. The core only depends on the generic contract: fetch/search/create work items, list children, transition state, publish/link artifacts, create pull requests, retrieve review threads, and reply to threads.

## Workflow lifecycle

1. Bootstrap selects and validates the tracker, SCM, mappings, provider connections, and branch convention.
2. `start-ticket` identifies the work item, requests the logical `in_progress` transition, and plans required specification artifacts.
3. `write-spec` creates provider-backed specification artifacts using Actor-Critic review.
4. Hooks require a branch mapped to one work item, an `in_progress` state, and accepted specification evidence before governed writes.
5. `resolve-ticket` produces a provider-backed resolution artifact and requires verification and pull-request evidence before a logical `done` transition.
6. Feature/story workflows (`feature-implementation`, `finish-feature-development`, `reconcile-feature-stack`) use the same generic work-item and SCM contracts; vendor-specific details stay inside adapters.

## Hooks

Hooks remain first-class enforcement points for protected-branch safety, configured branch naming, work-item mapping, state gating, artifact prerequisites, completion evidence, and fail-closed integration errors. Local filesystem workflow state is outside the plugin boundary.

## Tests

```sh
python3 -m unittest discover -s test -t . -p 'test_*.py'
```
