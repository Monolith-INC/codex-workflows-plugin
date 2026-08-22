# Changelog

## 0.5.22

### Documentation and install
- README rewrite with curl install one-liner and Monolith-INC repo slug.
- Release workflow uploads zip and `install.sh` on `v*` tags.

### Quality and CI
- mypy fix in orchestrator handlers.
- Tracked workflow templates in `skills/codex_workflows/resources/templates` for CI.


## 0.5.21

### Provider-neutral workflow
- Replaced provider-specific workflow assumptions with tracker and SCM adapters (Linear, Azure DevOps Boards, GitHub, Azure Repos).
- Added the `workflow-integrations` MCP gateway; the orchestrator stays instruction-only.
- Durable work state and artifacts live on the configured tracker; SCM adapters own PRs and review threads.
- Hooks fail closed when integration configuration or provider access is unavailable.
- Removed local workflow persistence and bypass capabilities.

### Bootstrap and discovery
- Bootstrap wizard confirms logical kind/state mappings and writes `.codex-workflows/integrations.json`.
- Provider capability discovery resolves MCP tool bindings; GitHub uses `gh` instead of MCP discovery.
- Post-install verification checks bindings, mappings, and MCP server wiring.
- Azure org placeholders expand from env/remote at config write and again via `expandvars` at spawn.

### Integrations hardening
- Idempotent artifact publication with `created`/`reused` outcomes, bounded retry, and gateway stderr telemetry.
- Fixture-backed adapter contract tests for Linear, Azure DevOps, GitHub, and Azure Repos.
- MCP client sends required `initialize` params and enforces read deadlines with `select`.
- GitHub PRs map `headRefName`/`baseRefName`; `link_work_item` appends a durable PR-body marker.

### Feature orchestration
- Restored feature workflow markdown resources and finish/reconcile commands.
- Orchestrator handlers for feature-implementation, finish-feature-development, and reconcile-feature-stack emit structured story plans over the same contracts.

## 0.5.20

- `review-pr` dual SCM support: GitHub via `gh` / Azure DevOps via MCP
- First-run SETUP wrote project-local `.codex-workflows/scm-provider.json` (superseded by `integrations.json` in 0.5.21)
- GitHub path requires `-R` from settings; REST fallback is root-comment only
- Azure mechanics use settings `repo` (no origin re-parse during INGEST/ACT)
