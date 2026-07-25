# AI Codex Workflows Plugin

A portable, multi-host workspace automation plugin that enforces session bootstrapping, ticket lifecycle governance, YouTrack state gating, and git safety checks across agent-driven development workflows.

> **v0.5.5** — Fixes Claude Code hook client detection (`hooks/hooks.json` now routes through `claude_enforce_hook.py`), adds authenticated `gh release download` fallback for private repo installs, and ships a per-repo `codex-workflow.config.json` so the markdown allowlist covers this plugin's own docs. **161 tests**, all passing.

## Purpose

To ensure that autonomous agents consistently follow strict repository governance protocols:
1. **Mandatory Session Bootstrap**: Blocks all codebase writes until today's session record is initialized in the vault.
2. **Structured Ticket Progression**: Validates and gates ticket folder transitions (`Ready -> Active -> Closed/Resolved`), enforcing YouTrack state synchronization at each step.
3. **Git Safety on Ticket Start**: Before activating a ticket, enforces that no other ticket is already active, the branch is not the base integration branch, the branch is synced with `origin/<base>`, and no unmerged commits from other feature branches are present.
4. **Destructive-Op Guard**: Prevents `rm`/`rmdir` against the Codex vault — status transitions must always be expressed as file moves.

## Architecture

```
scripts/
├── hook_runtime.py       # Entry point — orchestrates all policy checks
├── ticket_runtime.py     # Path extraction, YouTrack transcript scanner, bugfix inference
├── policy/               # Pure policy engine (engine.py, events.py, git_utils.py) — no I/O
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

Add to a project's `.mcp.json` (bootstrap does this automatically with `--dest`):

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
* **Mandatory Session Bootstrapping**: Write tools are blocked until `<vault>/Agent_Sessions/YYYY-MM-DD*.md` exists (with `next: null` frontmatter). Error messages include the actual vault directory name — no project names are hard-coded.
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

### One-step install

Install the latest release and wire all detected agent hosts:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh | bash
```

For private repository access, download the installer with authenticated `gh` first:

```bash
tmp=$(mktemp -d)
gh release download v0.5.3 -R theocarranza/codex-workflows-plugin -p install.sh -D "$tmp"
bash "$tmp/install.sh"
```

To also wire a specific project with project-level hooks, pass `--dest`:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh | bash -s -- --dest /path/to/your/project
```

No additional Python dependencies are needed — the plugin uses only the standard library.

Bootstrap does three things automatically:

1. **Installs the runtime** to `~/.codex-workflows/` (the stable location hook commands reference).
2. **Registers the plugin with Claude Code** by copying the `skills/`, `commands/`, and runtime `scripts/` trees into `~/.claude/plugins/cache/local/codex-workflows-plugin/<version>/` and adding an entry to `~/.claude/plugins/installed_plugins.json`. After this, the plugin appears in Claude's plugin manager and its skills/commands are available to any Claude session.
3. **Registers with Antigravity and Codex** marketplaces when those config directories exist on the machine.

> **After bootstrapping, restart your Claude session** (close and reopen the IDE panel or CLI) for the newly registered skills and commands to appear.

### Advanced install options

Pin a specific release:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh | CODEX_WORKFLOWS_VERSION=v0.5.2 bash
```

Wire a specific host instead of all agents:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh | bash -s -- --target claude
```

The plugin auto-discovers each host's config location:

| Target | Global config wired | Hook event |
|---|---|---|
| `claude` | `~/.claude/settings.json` | `PreToolUse` |
| `cursor` | `~/.cursor/hooks.json` | `preToolUse` |
| `gemini` | `~/.gemini/settings.json` (Deprecated) | `BeforeTool` |
| `codex` | `~/.gemini/config/hooks.json` | `PreToolUse` |
| `antigravity` | `<ide-install>/.agents/hooks.json` (auto-discovered) | `PreToolUse` |
| `antigravity-cli` | `~/.gemini/antigravity-cli/settings.json` | `BeforeTool` |
| `all-agents` | all six above (skips hosts not installed) | — |

Hook wiring is idempotent — re-running bootstrap strips any stale entries from previous installs before writing the fresh hook, so running it multiple times is safe.

If you prefer to work from a clone:

```bash
git clone https://github.com/theocarranza/codex-workflows-plugin.git
cd codex-workflows-plugin
python3 -m scripts.installer.bootstrap --target all-agents
```

Passing `--dest` also syncs `.agent/workflows/*.md` and `.agent/rules/*.md` into the project, and merges an `agentic-orchestrator` MCP server entry into the project's `.mcp.json`.

### Dry-run

Preview the merged hook config without writing any files:

```bash
python3 ~/.codex-workflows/scripts/installer/cli.py --target claude --output /tmp/preview.json
```

### Updating the plugin

Re-run the one-step installer. It replaces `~/.codex-workflows/`, refreshes the Claude plugin cache, and re-wires all hooks in one step:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh | bash
```

### Uninstalling the plugin

Run the cleanup path to remove managed host hooks, plugin caches, marketplace entries, and the installed runtime:

```bash
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh | bash -s -- --uninstall
```

Pass `--dest /path/to/project` to also remove generated project hook configs and `.agent` assets. Pass `--keep-runtime` only when you want to unwire hosts but keep `~/.codex-workflows/` for debugging.

---

## Tests

```bash
python3 -m unittest discover -s test -p "test_*.py" -v
```

**160 tests**, all passing. Coverage spans: policy engine (including git safety checks), all 5 host adapters, ticket runtime, spec/resolution reflection, installer (one-step shell install, dry-run, live `--dest` write, and uninstall cleanup), orchestrator (state machine, MCP server, evaluator, hooks), profiles, and release packager.

CI also runs `python3 scripts/validate_plugin.py .` to verify the plugin manifest and skills layout.

---

## Release

```bash
python3 -m scripts.release_packager --output-dir dist/
```

Emits `dist/codex-workflows-plugin-<version>.zip`. Version is read from `.codex-plugin/plugin.json`. The archive includes plugin metadata, hooks, skills, commands, scripts, `install.sh`, and docs — `__pycache__` and test directories are excluded.

See [CHANGELOG.md](./CHANGELOG.md) for full version history.
