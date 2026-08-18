---
type: spec
kind: implementation-plan
ticket: 2026-08-18-orchestrator-contract-hardening
status: accepted
---

# Implementation Plan: Orchestrator Contract Hardening

## Scope

This ticket hardens contracts already present in `scripts/orchestrator/` without
removing working version 0.5.20 behavior. It covers manifest discovery and
diagnostics, explicit unknown-input semantics, deeply immutable orchestration
state, an injectable semantic evaluator with a legacy compatibility adapter,
and deterministic reducer transition/history behavior.

The work MUST preserve critique projection into retry prompts, both outbound
prompt dialects and tool schemas, the instruction-only handler result, MCP
list/call behavior, the five inbound host adapters, hook enforcement, and the
installer. It does not extract code into Airlock, restructure tenant policy,
add dialects, or change ticket and YouTrack workflow rules.

## Milestones

1. Characterize compatibility-sensitive behavior that the current suite does
   not state explicitly.
2. Add manifest validation, isolated diagnostics, and opt-in strict input
   schemas while retaining permissive defaults.
3. Make state, events, and history recursively immutable and make reducer
   transitions deterministic.
4. Introduce an explicit semantic-evaluator contract behind a legacy adapter.
5. Run integration, packaging, and regression gates and record the outcome in
   the active ledger.

## Tasks

- [ ] M0 — Characterization (1–2 hours)
  - [ ] Assert unknown input keys remain accepted unless a manifest explicitly
    declares `additionalProperties: false`.
  - [ ] Assert retry prompts include prior critiques, task inputs, and an
    incremented attempt.
  - [ ] Assert instruction-only MCP results retain `mode`, `inputs`, `prompt`,
    `attempt`, and reflection content.
  - [ ] Assert current completed-mode semantic compatibility.
- [ ] M1 — Manifest and input contracts (2–4 hours)
  - [ ] Add a pure manifest validator for identity, description, input schema,
    and output signature shapes.
  - [ ] Add a discovery result containing valid manifests and per-path
    diagnostics; keep `read_manifests()` and `manifest_by_name()` compatibility
    wrappers.
  - [ ] Detect duplicate names deterministically instead of silently replacing
    one capability with another.
  - [ ] Enforce unknown-key rejection only for schemas that explicitly declare
    `additionalProperties: false`.
  - [ ] Test malformed JSON, non-object roots, malformed nested schemas,
    duplicate names, mixed valid/invalid sets, and strict/permissive inputs.
- [ ] M2 — State and reducer contracts (3–5 hours)
  - [ ] Add recursive freezing for mappings and sequences used by event payloads,
    task inputs, dependencies, critiques, outputs, task maps, and history.
  - [ ] Preserve JSON prompt projection and value equality for supported data.
  - [ ] Centralize history append so every dispatched event is recorded once.
  - [ ] Define valid state/event transitions; invalid transitions become
    deterministic recorded no-ops rather than implicit state changes.
  - [ ] Preserve dependency promotion and queued nested dispatch.
- [ ] M3 — Semantic evaluation contract (2–4 hours)
  - [ ] Define a callable semantic-evaluator protocol receiving the result and
    manifest and returning critiques.
  - [ ] Rename the current `mode`/`critiques` behavior as a legacy compatibility
    evaluator and retain it as the default for version 0.5.20 consumers.
  - [ ] Allow `OrchestratorEngine` to receive an evaluator explicitly without a
    module-level registry.
  - [ ] Test custom evaluation, legacy completed-mode behavior, structural
    short-circuiting, and evaluator exceptions.
- [ ] M4 — Integration and documentation (1–2 hours)
  - [ ] Run focused orchestrator tests after every milestone.
  - [ ] Run `python3 -m unittest` and require at least the 233-test baseline.
  - [ ] Run `python3 scripts/validate_plugin.py`.
  - [ ] Update public documentation only where contract behavior changed.
  - [ ] Record deliberate deltas, verification, and rollback points in the
    active ticket ledger.

## Dependencies

- Python 3 standard library only; no new runtime dependency is required.
- Existing capability manifests remain the compatibility corpus.
- The active ticket and technical specification are authoritative for scope.
- Work is stacked on ledger housekeeping commit `7113e20`; that commit must
  remain reachable until its branch is merged or the stack is rebased.

## Validation

- Focused unit tests MUST cover every new failure and compatibility path.
- The five captured inbound host payload suites MUST remain unchanged and green.
- Outbound adapter tests MUST still prove critique content appears in both prompt
  dialects.
- MCP tests MUST cover list and instruction-only call round trips.
- The complete test suite MUST pass with no reduction below 233 existing tests.
- Plugin validation MUST exit zero.
- `git diff --check` MUST report no whitespace errors.

## Rollback

Each milestone will be committed separately. If a milestone breaks a consumer,
revert only that milestone while retaining its characterization tests where
they describe pre-existing behavior. The semantic evaluator keeps the legacy
adapter as the default, and strict unknown-key rejection is opt-in, so neither
requires a flag-day manifest migration. If recursive freezing breaks prompt or
MCP serialization, revert the state milestone and retain the failing regression
test before selecting a different immutable representation.
