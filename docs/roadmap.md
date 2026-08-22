# Roadmap

Completed in **v0.5.21** (provider-neutral workflows):

- [x] Complete provider capability discovery and mapping confirmation in bootstrap.
- [x] Add contract tests for Linear, Azure DevOps, GitHub, and Azure Repos adapters.
- [x] Add idempotency and retry telemetry for artifact publication.
- [x] Expand generic feature/story orchestration over the same contracts.

Completed in **v0.5.24** (quality gates and local tracking):

- [x] Add one canonical check/fix runner for plugin validation, Ruff, mypy, unit tests, and Markdown linting.
- [x] Enforce the quality runner in CI and tag-release packaging.
- [x] Add tracker pause/resume commands while preserving SCM safety gates.
- [x] Add local tracker bootstrap and storage for Epic -> Feature -> User Story -> Task work.

## Next

- Optional live provider smoke tests (outside CI fixtures).
- Resolve merged-PR review threads in GitHub UI when automation replies (cosmetic).
