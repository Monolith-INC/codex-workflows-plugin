# Host Adapter Architecture

Date: 2026-06-07

## Context

The repository started as a Gemini/Antigravity-flavored hook bundle. The migration goal is to support multiple agent hosts without duplicating policy logic or hard-coding one host's file layout into another host's integration.

## Decision

Use a shared policy runtime plus thin host adapters.

The shared runtime owns:

- canonical event evaluation
- destructive command gating
- markdown allowlist checks (removed in 0.5.6; historical)
- session bootstrap checks
- ticket lifecycle and YouTrack gating

Each host adapter owns:

- payload normalization for that host
- response formatting for that host
- host-specific wrapper entrypoint

The installer owns:

- host-target selection
- target config path selection
- hook config merging
- shared asset installation

## Supported Targets

- `codex` writes `hooks/hooks.json`
- `gemini` writes `.gemini/settings.json`
- `antigravity` writes `.agents/hooks.json`
- `claude` writes `.claude/settings.json`
- `universal` installs shared assets only
- `all-agents` installs the shared assets without forcing a host config

## Consequences

Positive:

- policy logic stays testable and host-neutral
- host-specific drift is isolated to adapters
- installer behavior is explicit and auditable

Tradeoffs:

- the hook runtime now contains more explicit dispatch logic
- each new host requires a dedicated adapter and installer target

