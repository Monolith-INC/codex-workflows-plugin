# Host adapter architecture

Host adapters normalize hook payloads into a common event. The policy boundary validates protected branches, configured work-item mapping, provider state, artifact prerequisites, and completion evidence. Provider transport is isolated in the workflow-integrations gateway; the orchestrator only executes skills and returns instructions.

