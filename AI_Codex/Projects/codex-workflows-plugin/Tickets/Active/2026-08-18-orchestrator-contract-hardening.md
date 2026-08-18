---
timestamp: 2026-08-18T07:29:56-03:00
project: codex-workflows-plugin
branch: techdebt/orchestrator-contract-hardening
status: active
type: task
ticket: 2026-08-18-orchestrator-contract-hardening
tags: [orchestrator, contracts, hardening, technical-debt]
---

# Orchestrator Contract Hardening

## Goal

Harden the existing orchestrator contracts using the adversarial findings from
the Airlock extraction review while preserving the working feedback, dialect,
MCP transport, and host-enforcement behavior already present in version 0.5.20.

## Description

The live source comparison separated inherited defects from Airlock-only
regressions. This ticket addresses only defects present in
`codex-workflows-plugin`: malformed manifest isolation, permissive or
misrepresented input contracts, shallow state immutability, producer-controlled
semantic acceptance, and incomplete reducer transition/history guarantees.

## Requirements

- Preserve the critique-to-prompt feedback path, instruction-only prompt
  projection, tool-schema projections, MCP round trip, five inbound host
  adapters, hook runtime, installer, and deployment behavior.
- Validate manifest structure before a capability enters the discovered set.
- Isolate one invalid manifest without preventing valid capabilities from being
  discovered or invoked, and expose a diagnosable failure.
- Define and test the treatment of unknown input arguments without silently
  changing existing capability behavior.
- Make the state immutability guarantee accurate for nested event payloads,
  inputs, critiques, dependencies, outputs, and history.
- Replace implicit producer-controlled semantic acceptance with an explicit,
  testable evaluation contract while retaining compatibility for current
  handlers during migration.
- Validate reducer transitions and ensure every dispatched event has a
  deterministic history outcome.
- Keep the full existing suite green; 233 tests is the pre-change floor.

## Scope

In scope: `scripts/orchestrator/`, its manifests and handler boundary, focused
orchestrator tests, and compatibility fixtures needed to characterize behavior.

Out of scope: the Airlock repository, extraction/repackaging, tenant-policy
carve-outs in `hook_runtime.py`, installer redesign, new host dialects, and
changes to ticket or YouTrack workflow policy.

## Acceptance Criteria

- Invalid manifests are rejected per capability with deterministic diagnostics.
- Input validation behavior for unknown keys is explicit and covered by
  compatibility tests.
- Previously created state and event objects cannot be changed through nested
  mutable references.
- Semantic evaluation is supplied through a named contract rather than inferred
  only from magic output fields; legacy handler results remain supported through
  a deliberate compatibility adapter.
- Invalid state transitions are deterministic and event-history behavior is
  directly tested.
- Critiques still appear in retry prompts and MCP instruction-only calls retain
  inputs, prompt, attempt, and reflection content.
- `python3 -m unittest` passes with at least the existing 233 tests.

## Specs

- `AI_Codex/Projects/codex-workflows-plugin/Specs/2026-08-18-orchestrator-contract-hardening/implementation-plan.md`
- `AI_Codex/Projects/codex-workflows-plugin/Specs/2026-08-18-orchestrator-contract-hardening/tech-spec.md`

## Implementation Summary

Implemented in five atomic commits after the accepted specification gate:

- `e3f80d0` validates and isolates manifests, diagnoses duplicate capability
  names, and makes strict unknown-input rejection opt-in.
- `13a858f` recursively freezes queue state, enforces reducer transitions,
  records every event once, and makes deterministic retry stalls halt early.
- `ce381b9` introduces injectable semantic evaluation while retaining the named
  version 0.5.20 legacy adapter as the default.
- `648d810` closes the preconstructed-`FrozenDict` nesting loophole and adds
  explicit retry/MCP compatibility assertions and public contract notes.
- `8727d76` proves malformed-JSON sibling isolation and retry-prompt input
  preservation directly.

The deliberate compatibility choices are permissive-by-default input schemas,
the legacy semantic evaluator as the constructor default, unchanged MCP result
shapes, and compatibility wrappers for manifest lookup. No dependency, host
adapter, installer, tenant-policy, or ticket-workflow behavior was changed.

Rollback remains milestone-local: revert the manifest, state/reducer, semantic,
or final immutability commit independently. The characterization tests should
remain whenever they document the version 0.5.20 compatibility boundary.

## Verification

Baseline: `python3 -m unittest` passed 233 tests in 9.2 seconds on source version
0.5.20 before this ticket was activated.

Final verification on `8727d76`:

- `python3 -m unittest` — 249 tests passed in 8.650 seconds.
- Focused orchestrator tests — 36 tests passed.
- `python3 -m compileall -q scripts/orchestrator` — passed with bytecode directed
  to a temporary cache.
- `python3 scripts/validate_plugin.py` — passed.
- `git diff --check` — passed.
- Live `skills/` discovery — 13 manifests, 0 diagnostics.
