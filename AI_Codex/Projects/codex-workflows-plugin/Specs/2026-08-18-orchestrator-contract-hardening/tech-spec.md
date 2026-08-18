---
type: spec
kind: tech-spec
ticket: 2026-08-18-orchestrator-contract-hardening
status: accepted
---

# Tech Spec: Orchestrator Contract Hardening

## Overview

The version 0.5.20 orchestrator has a working end-to-end path from filesystem
capability discovery through tool projection, supervised execution, critique
reflection, and MCP emission. Its defensive contracts are weaker than their
documentation: schemas are not validated, unknown inputs are implicitly
permitted, frozen dataclasses retain mutable nested values, semantic acceptance
is inferred from producer-controlled fields, and reducer history depends on the
selected branch.

This change strengthens those boundaries without deleting the source behavior
that Airlock failed to preserve. Compatibility is explicit: existing manifests
remain permissive unless they opt into strict inputs, and current `mode` plus
`critiques` semantics remain available through the default legacy evaluator.

## Data Model

### Manifest diagnostics

`ManifestDiagnostic` is a frozen value containing the manifest path, an error
code, and a human-readable message. `ManifestDiscovery` contains an ordered
tuple of valid manifest dictionaries and an ordered tuple of diagnostics.
Discovery order MUST remain stable by capability-directory name.

The validator checks:

- the manifest root is an object;
- `name` is a non-empty string;
- `description`, when present, is a string;
- `input_schema` and `output_signature`, when present, are objects;
- schema `type`, `required`, `properties`, and `additionalProperties` have the
  supported shapes;
- each property schema is an object with a supported scalar/container type;
- capability names are unique within one discovery root.

An invalid capability produces diagnostics and is excluded. It MUST NOT prevent
other capabilities from being listed or invoked.

### Immutable orchestration state

`Event`, `Task`, and `QueueState` remain frozen dataclasses. Their construction
normalizes nested mappings and sequences into recursively immutable values.
The representation MUST remain readable through the existing mapping and
sequence interfaces and MUST remain serializable by the prompt and MCP paths.

Every dispatched event appears exactly once in `events_history`, including
unknown events, missing task identifiers, and invalid transitions. A known event
with an invalid transition is a recorded no-op.

### Semantic evaluator

A semantic evaluator is a callable with this logical contract:

```python
SemanticEvaluator = Callable[[Mapping[str, Any], Mapping[str, Any]], list[str]]
```

The first argument is structurally valid output and the second is its manifest.
The engine receives an evaluator through construction. Structural output
validation always runs first and MUST short-circuit semantic evaluation.

`legacy_semantic_evaluator` preserves current behavior: completed mode suppresses
stale critiques; other modes split string/list critiques; blocked-without-detail
produces a fallback critique. The legacy behavior is named as compatibility,
not presented as independent verification.

## API

### Discovery

```python
discover_manifests(skills_dir: str | Path) -> ManifestDiscovery
read_manifests(skills_dir: str | Path) -> list[dict[str, Any]]
manifest_by_name(skills_dir: str | Path) -> dict[str, dict[str, Any]]
```

`discover_manifests` is the diagnostic API. The two existing functions remain
compatibility wrappers over its valid set. They SHOULD log or otherwise expose
diagnostics without changing their return shape.

### Input validation

`validate_inputs(arguments, manifest)` retains its list-of-critiques response.
Unknown keys are allowed when `additionalProperties` is absent or true. When it
is false, each unknown key yields a deterministic critique. This preserves all
current manifests while permitting a capability to declare the stronger
boundary explicitly.

### Engine construction

```python
OrchestratorEngine(
    skills_dir,
    *,
    max_retries=3,
    interactive=False,
    quiet=False,
    semantic_evaluator=legacy_semantic_evaluator,
)
```

No global semantic registry is introduced. Existing callers require no change.
Evaluator exceptions MUST become ordinary execution critiques or a documented
failed result; they MUST NOT terminate the MCP server process.

### Reducer transitions

The valid transition set is:

- `TaskSpawnedEvent`: `READY → IN_PROGRESS`;
- `TaskCompletedEvent`: `IN_PROGRESS → COMPLETED`;
- `TaskFailedEvent`: `IN_PROGRESS → READY` or
  `BLOCKED_REQUIRES_REVIEW`, according to retry budget;
- `AuthorizationReceivedEvent`: `BLOCKED_REQUIRES_REVIEW → READY` when
  authorization is valid.

Dependency promotion after completion remains unchanged. Unknown events and
invalid known transitions change no task but are recorded once.

## Implementation Plan

1. Add characterization tests for source behavior that must survive.
2. Implement manifest diagnostics and compatibility wrappers.
3. Add opt-in strict unknown-property validation.
4. Add recursive immutable normalization and central history recording.
5. Enforce the transition table without changing valid-loop behavior.
6. Introduce the semantic evaluator type, legacy adapter, and engine injection.
7. Run focused tests, the complete suite, plugin validation, and regression
   checks for prompts, MCP, host fixtures, and installer behavior.

Ownership remains within `scripts/orchestrator/` and `test/`. Tenant handlers
continue to own domain semantics and configuration.

## Testing Strategy

Unit tests cover every validator error code, mixed valid/invalid discovery,
duplicate names, permissive and strict unknown inputs, recursive mutation
attempts, invalid reducer transitions, exactly-once history, legacy semantic
compatibility, custom evaluators, and evaluator exceptions.

Integration tests exercise a retry whose second prompt contains the first
critique, an instruction-only MCP call retaining current output fields, and a
capability set containing both broken and valid manifests. Existing host payload
fixtures and installer tests remain unchanged to detect unrelated drift.

Acceptance requires `python3 -m unittest` to pass with at least 233 tests and
`python3 scripts/validate_plugin.py` to exit zero.

## Rollback

The work is split into characterization, manifest/input, state/reducer,
semantic-evaluator, and integration commits. Each implementation commit can be
reverted independently. Compatibility wrappers, permissive-by-default input
handling, and the default legacy semantic evaluator prevent mandatory consumer
migration. If immutable normalization causes serialization incompatibility, the
state commit is reverted while its failing test remains as the next design
constraint.

## Requirements (RFC 2119)

- Discovery MUST isolate an invalid capability and MUST preserve valid siblings.
- Duplicate names MUST produce deterministic diagnostics and MUST NOT be
  resolved by silent overwrite.
- Unknown inputs MUST remain allowed by default and MUST be rejected when the
  manifest declares `additionalProperties: false`.
- Events and state MUST resist mutation through nested references after
  construction.
- Every dispatched event MUST appear exactly once in history.
- Invalid transitions MUST be recorded no-ops.
- Structural validation MUST precede semantic evaluation.
- Existing consumers MUST use the legacy evaluator unless they explicitly
  inject another evaluator.
- Critiques MUST remain present in retry prompts.
- Instruction-only MCP results MUST retain inputs, prompt, attempt, and
  reflection behavior.
- The implementation MUST remain standard-library-only.
- The full 233-test baseline and plugin validator MUST remain green.
