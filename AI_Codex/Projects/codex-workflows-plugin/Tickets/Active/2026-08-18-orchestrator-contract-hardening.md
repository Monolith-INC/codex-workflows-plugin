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

## Review Follow-Up (2026-08-19)

A code review of the branch diff found six defects in the delivered milestones.
Two are addressed here; four remain open.

### Delivered

- **Reducer unblock guard.** `handle_task_completed` dropped the
  `task_id in dependencies` check, so `all()` over an empty `dependencies`
  tuple promoted any dependency-free BLOCKED task to READY on an unrelated
  completion. The guard is restored and covered by two regression tests that
  fail without it.
- **Single parsed payload contract.** The manifest JSON Schema subset was read
  by four independent hand-written interpreters that disagreed with each other
  (`manifests._validate_schema`, `schema.validate_inputs`,
  `evaluator.evaluate_output`, and the engine's `attempt` injection). They are
  replaced by `scripts/orchestrator/contracts.py`: raw schema JSON is parsed
  exactly once into frozen algebraic types (`TypeContract`, `ExtraProperties`,
  `ValueContract`) and every consumer reads the parsed contract.

Two review findings are closed as a consequence:

- JSON Schema's `type` array form (`["string","null"]`) raised
  `TypeError: unhashable type: 'list'`, aborting discovery and the whole MCP
  server rather than isolating one manifest. Verified against the pre-change
  module; now parsed as a `OneOfTypes` union.
- The subschema form of `additionalProperties` was rejected, silently dropping
  the capability from `list_tools()` and surfacing only as
  `Unknown skill '<name>'`. Verified against the pre-change module; now parsed
  as `ConstrainExtras`.

`additionalProperties` is deliberately modelled as one contract with three
constructors. In JSON Schema a boolean *is* a schema (`true` accepts every
extra key, `false` accepts none), so the boolean spelling is sugar and is
normalized away at the parse boundary; no consumer sees it.

`discover_manifests` also contains parser defects now: an unexpected exception
from `parse_manifest` becomes a `parser_error` diagnostic for that manifest
instead of propagating.

`CapabilityManifest.wire` retains the frozen, JSON-identical image of
`manifest.json` purely for host dialect projection (MCP `inputSchema`,
Anthropic and OpenAI tool schemas), and is asserted to serialize identically to
the file on disk.

### Retry Path

The remaining three findings shared one cause: the retry path carried
orchestration metadata in channels belonging to something else.

- **Stall detection restored.** `_stall_signature` stripped volatile fields at
  the top level only, while handlers nest their counter in `reflection`, so the
  signature differed on every pass and the fast-fail was dead code. The
  projection now recurses. Measured on the repo's own skills: `write-spec` with
  a placeholder draft and `max_retries=50` invoked the handler 50 times before,
  and 2 times now.
- **Interactive approval honored.** The `halt` branch returned unconditionally
  even though `authorization_hook` had already reset the task to READY inside
  `dispatch`, discarding the approval and reporting
  `ok=False, state="Ready"`. The three copies of the post-failure branch are
  replaced by one `_next_step` returning `Retry | Stop`, decided from task state
  after every hook has seen the event. The stall memory is cleared on that path,
  or the approved attempt would re-detect the same stall.
- **Argument channel separated.** Handlers now receive a frozen `Invocation`
  carrying `arguments`, `manifest`, `instructions` and `attempt` as distinct
  fields; the engine no longer rewrites the caller's payload. A caller resuming
  a stateless MCP round trip still declares its own starting attempt and
  in-process retries advance from there, reproducing the previous numbering.

`last_output`/`last_critiques` became a frozen `RetryContext`, so clearing the
stall memory is one value rather than two rebinds that can drift apart.

Each new test was checked against a temporary revert of its own fix and fails
without it.

### Still Open

None from the review. Follow-ups worth considering, not defects:

- `_VOLATILE_OUTPUT_FIELDS` is a denylist that grows whenever a handler adds an
  orchestration field. Splitting handler output into a work product and an
  envelope would make the stall signature a projection instead of a
  subtraction, but it would change the MCP result shape this ticket preserves.
- `evaluate_output` now honors `additionalProperties` on `output_signature`,
  which no shipped manifest sets. A manifest that opted in would reject the
  `prompt`/`attempt` fields the worker appends.

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
