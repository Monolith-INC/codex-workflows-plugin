# Host adapter architecture

Host adapters normalize hook payloads into a common event. The policy boundary validates protected branches, configured work-item mapping, provider state, artifact prerequisites, and completion evidence. Provider transport is isolated in the `workflow-integrations` gateway (`scripts/integrations/`); the orchestrator only executes skills and returns instructions.

Tracker and SCM adapters own vendor payloads, logical kind/state mappings, and connection details persisted in `.codex-workflows/integrations.json`. Bootstrap may discover MCP tool bindings and confirm mappings before writing that config.
