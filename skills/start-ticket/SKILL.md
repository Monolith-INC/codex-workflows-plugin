---
name: start-ticket
description: Start a configured tracker work item and plan its specification artifacts.
---

# Start ticket

Fetch the work item through the configured tracker adapter, confirm the current branch matches the bootstrap-selected {key} convention, and request the logical in_progress transition. Return generic work-item identity, provider state, child items, and the specification artifact plan. Durable state belongs in the tracker; do not create local workflow records.

If required specifications are missing, invoke write-spec and publish resulting artifacts through the integration gateway before implementation writes.
