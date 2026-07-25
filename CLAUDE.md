# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python3 -m unittest -v

# Run a single test module
python3 -m unittest test.contract.test_policy_engine -v
python3 -m unittest test.installer.test_installer_smoke -v

# Run the legacy integration test suite
python3 -m unittest test_plugin.py -v

# Run the installer CLI (dry-run)
python3 -m scripts.installer.cli --target claude

# Install plugin assets into a destination project
python3 -m scripts.installer.cli --target all-agents --dest /path/to/project

# Purge legacy markdown-allowlist hooks/configs, then re-wire
python3 -m scripts.installer.bootstrap --purge-allowlist --target all-agents

# Build a release archive
python3 -m scripts.release_packager --output-dir dist

# Validate the plugin manifest
python3 /home/agentrick/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

Debug logs from the hook runtime are written to `/tmp/codex_hook_debug.log`.

## Architecture

This is a **Codex-style AI agent plugin** that enforces workflow policies across multiple AI agent hosts (Claude Code, Codex, Gemini CLI, Antigravity). It ships as a plugin with skills, a pre-tool hook, and an installer.

### Core request flow

Every agent tool call is intercepted by `skills/codex_workflows/scripts/codex_enforce_hook.py`, which calls into `scripts/hook_runtime.py::run()`. The runtime:

1. Detects the host client from stdin shape
2. Routes through the matching **adapter** (`scripts/adapters/`) to produce a `CanonicalToolEvent`
3. Passes the event to `scripts/policy/engine.py::evaluate()` for policy decisions
4. Formats the verdict back through the adapter and prints it as JSON to stdout

### Key layers

**Adapters** (`scripts/adapters/`) — one per host. Each exposes `parse_<host>_payload(payload, *, project_root, vault_dir) -> CanonicalToolEvent` and `format_<host>_decision(decision) -> dict`. Adapters normalize the different hook payload shapes into `CanonicalToolEvent` (defined in `scripts/policy/events.py`).

**Policy engine** (`scripts/policy/engine.py`) — pure function `evaluate(event) -> PolicyDecision`. Contains all enforcement rules:
- Destructive `rm` commands against the AI Codex vault are denied
- Code writes require a continuable open Agent Session (`next: null`) under `AI_Codex/Agent_Sessions/` or `AI_Codex/Projects/*/Agent_Sessions/` (same branch, max 8 hours); otherwise close and open a new session
- `/skip-ledger` sets `{vault}/.codex_ledger_skip` to bypass session/ticket/branch/YouTrack ledger guards until `/resume-ledger` (vault delete protection remains)
- Mutating git on `main`/`master`/`develop`/`unstable` is denied; create a `feature/`/`bugfix/`/`techdebt/` branch first
- Ticket moves follow strict lifecycle: `Ready → Active → Closed` (tasks) or `Ready → Active → Resolved` (bugfixes, detected by `bug` in filename)
- Starting a ticket enforces: no other ticket already active, branch is not the integration base, branch is synced with `origin/<base>`, no unmerged commits from another feature branch

**Session / ledger helpers** — `scripts/policy/session_gate.py`, `ledger_skip.py`, `git_branch_guard.py` support the hook runtime.

**Git utilities** (`scripts/policy/git_utils.py`) — called during ticket-start checks and branch guards; detects the integration branch, fetches origin, computes divergence.

**YouTrack integration** (`scripts/ticket_runtime.py`) — validates that the agent made the required YouTrack state transitions (`update_issue` MCP calls) before allowing ticket lifecycle moves. Reads the Codex transcript (`.jsonl`) to verify calls appeared in-session.

**Installer** (`scripts/installer/`) — project-only. Requires `--dest`; runtime under `<dest>/.codex-workflows`; wires project hook configs; syncs `.claude/skills|commands`, `.agents/skills`, and `.agent/workflows|rules`. Global/`$HOME` install was removed.

**Profiles** (`scripts/profiles/`) — `WorkspaceProfile` dataclasses capturing per-project conventions (vault name, branch, verify command). Currently scaffolded but not yet wired into the runtime (see TODO in `base.py`).

### Plugin manifest

`.codex-plugin/plugin.json` is the authoritative plugin manifest consumed by the Codex plugin runtime. `plugin.json` at repo root is a lightweight name alias. The release packager (`scripts/release_packager.py`) reads from `.codex-plugin/plugin.json` when building the archive.

### Test layout

- `test/contract/` — unit and integration tests per module (adapters, policy engine, hook runtime, installer, packager, ticket runtime)
- `test/installer/` — smoke and target-path tests for the installer
- `test_plugin.py` — legacy end-to-end suite that invokes the hook script via subprocess with mock payloads

### Markdown access

Markdown allowlisting was removed in 0.5.6. `.md` reads are unrestricted by this plugin; writes still require a continuable Agent Session when they go through write tools (unless `/skip-ledger` is active). Bootstrap `--purge-allowlist` strips leftover managed hooks and deletes legacy `codex-workflow.config.json` allowlist companions.
