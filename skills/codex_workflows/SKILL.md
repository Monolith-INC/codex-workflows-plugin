---
name: codex_workflows
description: "Manage, enforce, and execute AI Codex workflows (Start Ticket, Resolve Ticket, etc.) and git/session hooks for standard development compliance."
---

# Codex Workflows Skill

This skill provides a standardized way to define, install, and execute development workflows based on the AI Codex architecture. It packages git/session hooks, local session bootstrap enforcement, standardized workflow checklists, and the migration path toward a real Codex plugin with client-adaptive adapters.

## Purpose

To ensure that autonomous agents consistently follow strict repository governance protocols:
1. **Mandatory Session Bootstrap**: Initializing today's session record before editing files.
2. **Commit Pipeline Verification**: Running pre-merge checks (`ensure-can-merge`) before commits/PRs.
3. **Structured Ticket Progression**: Gating ticket status moves, YouTrack transitions, and code verification.

## Workflows Included

The following workflows are bundled in the skill's `resources/` folder:
- **`workflows-start-ticket.md`**: Initializing a ticket, setting up a branch, and creating the Codex Ledger.
- **`workflows-ai-codex-finish-ticket.md`**: Resolving a ticket (verifying code quality, push, PR review, YouTrack updating, merging, and syncing unstable).
- **`workflows-resolve-ticket.md`**: Standard reference for ticket completion and archival.
- **`workflows-atomic-commits.md`**: Guidelines for clean Conventional Commits.
- **`workflows-tdd-bug-fix.md`**: Red-Green bug fixing steps.
- **`workflows-git-origin-sync.md`**: Keeping branches in sync with upstream.

## Focused Migration Skills

The migration is splitting the omnibus workflow into smaller skills:
- `bootstrap`
- `start-ticket`
- `resolve-ticket`
- `repository-sync`
- `commit-prep`
- `automated-tests`

## Hooks Installed

The skill contains pre-tool git/session execution hooks:
- **`codex_enforce_hook.py`**: Intercepts tool calls to prevent destructive deletions in the vault and enforce session bootstrapping prior to code modification.
- **`gemini_enforce_hook.py`**: Gemini CLI host wrapper that reuses the shared policy core with Gemini hook I/O.
- **`antigravity_enforce_hook.py`**: Antigravity host wrapper that reuses the shared policy core with Antigravity hook I/O.
- **`claude_enforce_hook.py`**: Claude Code host wrapper that reuses the shared policy core with Claude hook I/O.

## Plugin Packaging

- The Codex plugin manifest lives at `.codex-plugin/plugin.json`.
- `hooks/hooks.json` is the Claude Code marketplace plugin manifest (consumed via `${CLAUDE_PLUGIN_ROOT}` when this repo is loaded directly as a plugin) and routes to `claude_enforce_hook.py`, not Codex. Codex's own hook config is written by the installer to `~/.gemini/config/hooks.json`.
- The shared policy/adaptor split is part of the migration work, not this skill's current runtime behavior.

## Sync Command / Usage

To install or sync these workflows into a project's `.agent/workflows/` directory:
1. Copy the markdown templates from this skill's `resources/` directory to the target project's `.agent/workflows/` directory.
2. Run the `scripts/install_codex_hooks.sh` script to set up the host-specific hook configuration for the chosen target.
