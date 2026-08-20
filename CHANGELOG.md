# Changelog

## Unreleased

- Replaced provider-specific workflow assumptions with tracker and SCM adapters.
- Added the `workflow-integrations` MCP gateway for Linear, Azure DevOps Boards, GitHub, and Azure Repos.
- Kept the orchestrator instruction-only and made remaining branch/work-item/completion hooks fail closed.
- Removed local workflow persistence and bypass capabilities.
