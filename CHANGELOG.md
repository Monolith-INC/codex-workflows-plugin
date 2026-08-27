# Changelog

## 0.5.26

### Stacked feature landing

- Added `/merge-story-stack-into-feature` skill, command, workflow, and binding rules to merge stacked Story branches into the Feature branch oldest→newest with merge commits only (never squash/rebase).
- Hooks deny `git rebase` and force-push while `.codex-workflows/active-stage` (or `CODEX_WORKFLOW_STAGE`) is set to `merge-story-stack-into-feature`.
- Documented the lifecycle gap fill between `reconcile-feature-stack` and `finish-feature-development`.

## 0.5.25

### Local tracker MCP

- Added a repository-local tracker MCP provider so local tracker installs use the same bound provider contract as remote tracker integrations.

## 0.5.24

### Quality gates

- Added `scripts/quality.py` as the canonical check/fix runner for plugin validation, Ruff linting and formatting, mypy, unit tests, and Markdown linting.
- Bootstrapped pinned Python and Node developer toolchains with Ruff, mypy, and `markdownlint-cli2`; CI and tag release now run the canonical quality gate before packaging.
- Added Markdown lint configuration for tracked docs and templates, including MD032 blank-line enforcement, and normalized the documentation baseline.
- Enabled Ruff timezone checks and replaced naive timestamp creation with UTC-aware timestamps in hook payload capture and release packaging.

### Tracking flexibility

- Added `/skip-tracker`, `/resume-tracker`, and `/tracking-status` commands plus `tracking.mode` persistence so teams can pause tracker enforcement without losing provider configuration.
- Bypassed tracker-only hooks and tracker gateway operations while tracking is skipped, while keeping SCM workflows and protected-branch Git safety active.
- Added the repository-local tracker integration with Epic -> Feature -> User Story -> Task roles, state-folder storage under `.local-tracker/`, versioned artifacts, and development links.
- Added bootstrap support for local tracker storage policy (`committed` by default, or managed ignore entry) and released `epic-template.md`.

### Package architecture

- Added neutral `codex-workflows-plugin.json` as the package manifest for release name/version validation.
- Made bootstrap the owner of project-local `.cursor/`, `.claude/`, `.agents/`, `.codex/`, hook, and MCP configuration generation.
- Moved agent-host hook payload adapters into `scripts/host_adapters/`, keeping tracker/SCM provider adapters centralized under `scripts/integrations/`.

## 0.5.23

### Linear MCP compatibility

- Updated Linear tracker discovery to prefer the current `save_issue` and `save_comment` MCP tools for write operations.
- Updated bootstrap defaults so rewiring Linear integrations preserves create, transition, publish, and development-artifact link bindings.
- Added regression coverage for renamed Linear write bindings in discovery and installer defaults.

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
