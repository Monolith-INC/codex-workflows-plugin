# AI Codex Workflows Plugin

A portable, multi-host workspace automation plugin that enforces session bootstrapping, ticket lifecycle governance, YouTrack state gating, and git safety checks across agent-driven development workflows.

> **v0.5.9** — Codex-compatible `PreToolUse` decisions, session continuity, protected-branch git guard, and **project-only install** (`--dest` required; no global/`$HOME` install).

## Purpose

To ensure that autonomous agents consistently follow strict repository governance protocols:
1. **Mandatory Session Bootstrap**: Blocks codebase writes until a continuable open Agent Session exists (`next: null` under vault or `Projects/*/Agent_Sessions/`, matching branch, ≤8 hours old).
2. **Structured Ticket Progression**: Validates and gates ticket folder transitions (`Ready -> Active -> Closed/Resolved`), enforcing YouTrack state synchronization at each step.
3. **Git Safety on Ticket Start**: Before activating a ticket, enforces that no other ticket is already active, the branch is not the base integration branch, the branch is synced with `origin/<base>`, and no unmerged commits from other feature branches are present.
4. **Protected-Branch Guard**: Blocks mutating git while checked out on `main`/`master`/`develop`/`unstable`; require a `feature/`/`bugfix/`/`techdebt/` ticket branch.
5. **Skip Ledger**: `/skip-ledger` bypasses session/ticket/branch ledger hooks until `/resume-ledger` (vault destructive deletes stay blocked).
6. **Destructive-Op Guard**: Prevents `rm`/`rmdir` against the Codex vault — status transitions must always be expressed as file moves.

## Architecture

```
scripts/
├── hook_runtime.py       # Entry point — orchestrates all policy checks
├── ticket_runtime.py     # Path extraction, YouTrack transcript scanner, bugfix inference
├── policy/               # Policy engine + session_gate, ledger_skip, git_branch_guard, git_utils
├── adapters/             # 5 host adapters: codex, gemini, claude, antigravity, cursor
├── installer/            # Multi-target hook wiring (cli.py, targets.py, merge.py, bootstrap.py)
├── artifact_reflection.py # Shared Actor-Critic reflection engine for skill artifacts
├── orchestrator/         # Event-sourced skill runner + MCP stdio server
├── validate_plugin.py    # Portable manifest validator (used by CI)
└── profiles/             # Workspace profiles (scaffolding — not yet wired into runtime)
commands/                 # Slash commands synced to Claude plugin cache on bootstrap
skills/                   # Skill folders + manifest.json for orchestrator MCP discovery
.agent/workflows/         # Workflow guides synced to target projects on install
.agent/rules/             # Coding & governance rule files synced to target projects
```

## Skills & Slash Commands

| Skill / Command | Description |
|---|---|
| `feature-implementation` | Plan and implement an Active Feature with stacked Feature + User Story branches (Story→Feature→trunk). |
| `start-ticket` | Validates and activates a ticket from `Ready/` to `Active/`, enforcing git safety and YouTrack state. |
| `resolve-ticket` | Actor-Critic resolution report grounded on specs, then archive; enforces YouTrack timer stop and spent time. |
| `commit-prep` | Guides atomic commits following conventional-commit conventions. |
| `automated-tests` | Runs the test suite and reports results in a structured format. |
| `repository-sync` | Rebases the current branch onto the latest `origin/<base>`. |
| `bootstrap` | One-time plugin install and host wiring. |
| `write-spec` | Actor-Critic spec generation (RFC, ADR, design doc, tech spec, SRS, etc.) under `<vault>/Specs/`. Triggered by `/start-ticket` when specs are missing. |
| `review-pr` | Retrieves Azure DevOps PR review threads, classifies each as comply or reject, presents a report for user confirmation, applies code edits for comply items, and posts rejection replies to threads (status never mutated). |
| `codex_workflows` | Core hook enforcement script — not invoked directly. |

Slash commands live in `commands/` and are registered into the Claude plugin cache alongside skills. Invoke in Claude Code as `/start-ticket`, `/review-pr <n>`, etc.

### Agentic Orchestrator (MCP)

The orchestrator exposes workflow skills as MCP tools over stdio:

```bash
python3 -m scripts.orchestrator.mcp_server
```

Bootstrap writes the MCP server to Claude-compatible `.mcp.json` and Codex-readable `.codex/config.toml` when `--dest` is provided:

```json
{
  "mcpServers": {
    "agentic-orchestrator": {
      "command": "python3",
      "args": ["-m", "scripts.orchestrator.mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/plugin",
        "ORCHESTRATOR_SKILLS_DIR": "/path/to/plugin/skills"
      }
    }
  }
}
```

Each skill under `skills/<name>/` carries a `manifest.json` with `input_schema` and `output_signature` consumed by the orchestrator.

---

## Packaging Boundary

- Plugin metadata: `.codex-plugin/plugin.json`
- Claude marketplace metadata: `.claude-plugin/`
- Claude Code marketplace hook wiring (consumed via `${CLAUDE_PLUGIN_ROOT}` when this repo is loaded directly as a plugin, routes to `claude_enforce_hook.py`): `hooks/hooks.json`
- Shared skill bundles: `skills/`
- Slash commands: `commands/`
- Release packager: `scripts/release_packager.py` emits `dist/codex-workflows-plugin-<version>.zip`

---

## Ticket Lifecycle & Status Folders

Tickets live in `<vault>/Tickets/` and progress through four states:

| Folder | Status | Transition |
|---|---|---|
| `Ready/` | Groomed, pickable | — |
| `Active/` | In progress | `/start-ticket` moves from `Ready/` |
| `Closed/` | Feature/task complete | Moved from `Active/` on completion |
| `Resolved/` | Bugfix complete | Moved from `Active/` on resolution |

**Bugfix detection** reads `type: bug` or `type: bugfix` from YAML frontmatter exclusively. Filename heuristics are intentionally excluded to avoid false positives (e.g. `debug-something.md`).

---

## Enforced Rules & Hooks

The plugin installs a `PreToolUse` / `BeforeTool` hook that intercepts every agent tool call:

* **No Destructive Deletions**: `rm`/`rmdir` against vault paths are denied.
* **Markdown Allowlist**: Only `CLAUDE.md`, `GEMINI.md`, `.agent/`, and the vault may be written.
* **Mandatory Session Bootstrapping**: Write tools require an open Agent Session (`next: null`) under `<vault>/Agent_Sessions/` or `<vault>/Projects/<project>/Agent_Sessions/`. An open session may continue when it matches the current branch and is under 8 hours old; otherwise close it and open a new one.
* **Skip Ledger**: `/skip-ledger` writes `<vault>/.codex_ledger_skip` to bypass session/ticket/branch ledger hooks until `/resume-ledger` (vault destructive deletes stay blocked).
* **Protected Branch Guard**: Mutating git on `main`/`master`/`develop`/`unstable` is denied; create and check out a `feature/`/`bugfix/`/`techdebt/` branch first.
* **Ticket Destination Validation**: Wrong folder for the ticket type is denied with a specific reason message.
* **Git Safety on Ticket Start**: When moving a ticket from `Ready/` to `Active/` (or writing a new file into `Active/`), the hook enforces:
  - No other ticket is already active in `Tickets/Active/`
  - Current branch is not the base integration branch (dynamically resolved — checks `origin/HEAD`, `remote show origin`, and known branch names in order)
  - Branch is not behind `origin/<base>` (fetches with a 2 s timeout before checking)
  - Branch contains no unmerged commits from another local feature/bugfix/techdebt branch
* **YouTrack State Verification**: Scans the JSONL conversation transcript for a completed `call_mcp_tool(youtrack/update_issue)` call. Enforces that: (a) starting tickets requires `State: In Progress` and `Timer: Start`, (b) resolving/closing tickets requires `State: Done/Fixed` (bypassing the testing lane), `Timer: Stop`, and a recorded `Spent time` value. Denial messages distinguish between:
  - `transcript_missing` — transcript path was absent from the hook payload
  - `state_not_found` — transcript present but the required state/fields were not recorded correctly

---

## Installation

### Prerequisites

- Python 3.11+
- Git (required for git safety checks at ticket-start time)
- The **target project** must be a git repository

### One-step local install

Install is **project-only**. `--dest` is required. There is no global/`$HOME` install.

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /path/to/your/project
```

For private repository access, download the installer with authenticated `gh` first:

```bash
tmp=$(mktemp -d)
gh release download v0.5.7 -R theocarranza/codex-workflows-plugin -p install.sh -D "$tmp"
bash "$tmp/install.sh" --dest /path/to/your/project
```

No additional Python dependencies are needed — the plugin uses only the standard library.

Bootstrap does the following under `--dest`:

1. **Installs the runtime** to `<dest>/.codex-workflows/` (hook commands reference this path).
2. **Wires project hook configs** (for example `.claude/settings.json`, `.cursor/hooks.json`, `.agents/hooks.json`).
3. **Syncs discovery trees**: Claude skills/commands under `.claude/skills/` and `.claude/commands/`; Antigravity skills under `.agents/skills/`; workflows/rules under `.agent/`.
4. **Merges** an `agentic-orchestrator` MCP entry into the project's `.mcp.json` and mirrors project MCP servers into `.codex/config.toml` for Codex.

> **After bootstrapping, restart your agent session in that project** so hooks and skills reload.

### Advanced install options

Pin a specific release:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh \
  | CODEX_WORKFLOWS_VERSION=v0.5.7 bash -s -- --dest /path/to/your/project
```

Wire a specific host instead of all agents:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /path/to/your/project --target claude
```

Project hook config paths:

| Target | Project config wired | Hook event |
|---|---|---|
| `claude` | `.claude/settings.json` | `PreToolUse` |
| `cursor` | `.cursor/hooks.json` | `preToolUse` |
| `gemini` | `.gemini/settings.json` (Deprecated) | `BeforeTool` |
| `codex` | `hooks/hooks.json` | `PreToolUse` |
| `antigravity` | `.agents/hooks.json` | `PreToolUse` |
| `antigravity-cli` | `.gemini/antigravity-cli/settings.json` | `BeforeTool` |
| `all-agents` | all of the above under `--dest` | — |

Hook wiring is idempotent — re-running bootstrap strips stale managed entries before writing fresh hooks.

From a clone:

```bash
git clone https://github.com/theocarranza/codex-workflows-plugin.git
cd codex-workflows-plugin
python3 -m scripts.installer.bootstrap --target all-agents --dest /path/to/your/project
```

### Dry-run

Preview the merged hook config without writing files:

```bash
python3 -m scripts.installer.cli --target claude --output /tmp/preview.json
```

### Updating the plugin

Re-run the one-step installer against the same `--dest`. It replaces `<dest>/.codex-workflows/`, refreshes discovery trees, and re-wires project hooks:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /path/to/your/project
```

### Uninstalling the plugin

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /path/to/your/project --uninstall
```

Removes managed project hooks, synced discovery/workflow assets, the plugin's orchestrator MCP entry, and `<dest>/.codex-workflows/` (unless `--keep-runtime`).


## Tests

```bash
python3 -m unittest discover -s test -p "test_*.py" -v
```

**179 tests**, all passing. Coverage spans: policy engine (including git safety checks), all 5 host adapters, ticket runtime, spec/resolution reflection, installer (one-step shell install, dry-run, live `--dest` write, and uninstall cleanup), orchestrator (state machine, MCP server, evaluator, hooks), profiles, and release packager.

CI also runs `python3 scripts/validate_plugin.py .` to verify the plugin manifest and skills layout.

---

## Release

```bash
python3 -m scripts.release_packager --output-dir dist/
```

Emits `dist/codex-workflows-plugin-<version>.zip`. Version is read from `.codex-plugin/plugin.json`. The archive includes plugin metadata, hooks, skills, commands, scripts, `install.sh`, and docs — `__pycache__` and test directories are excluded.

See [CHANGELOG.md](./CHANGELOG.md) for full version history.
