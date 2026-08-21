# Codex Workflows Plugin

[![Release](https://img.shields.io/github/v/release/Monolith-INC/codex-workflows-plugin?display_name=tag&sort=semver)](https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/Monolith-INC/codex-workflows-plugin/ci.yml?branch=main&label=CI)](https://github.com/Monolith-INC/codex-workflows-plugin/actions)
[![License](https://img.shields.io/badge/license-see%20repo-lightgrey)](https://github.com/Monolith-INC/codex-workflows-plugin)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

Provider-neutral work-item workflows for Claude Code, Cursor, Codex, and related agent hosts.

The plugin installs into **the repository you are working on**. It wires skills, commands, hooks, and MCP servers for that project, then asks you which tracker and SCM to use. Durable ticket state lives in your tracker (Linear or Azure DevOps Boards). Pull requests and review threads live in your SCM (GitHub or Azure Repos). The orchestrator stays instruction-only — it does not proxy vendor APIs.

---

## Install

**One command.** Run it from a terminal while your application repository is the current directory (or pass `--dest` in CI). You do **not** need to clone this plugin repository.

### Interactive (recommended)

```bash
bash <(curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh)
```

The wizard will:

1. Confirm the project folder (defaults to your current directory — that is *your app*, not this plugin's clone)
2. Ask which agent host(s) to wire (`all-agents`, Claude, Cursor, Codex, …)
3. Ask for tracker (Linear or Azure DevOps Boards) and SCM (GitHub or Azure Repos)
4. Confirm kind/state mappings and a branch template that contains `{key}`
5. Download the latest release, install the runtime under `<your-app>/.codex-workflows/`, wire hooks/MCP, and write `<your-app>/.codex-workflows/integrations.json`

### Non-interactive / CI

```bash
curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /absolute/path/to/your-app
```

Optional flags: `--target claude|cursor|codex|all-agents`, `--uninstall`.

Pin a release with `CODEX_WORKFLOWS_VERSION=v0.5.21`. Offline installs can set `CODEX_WORKFLOWS_RELEASE_ZIP=/path/to/codex-workflows-plugin-*.zip`.

### Requirements

- Python 3.10+
- `git`
- Network access to GitHub Releases (or a local zip via `CODEX_WORKFLOWS_RELEASE_ZIP`)
- For GitHub SCM: authenticated [`gh`](https://cli.github.com/)
- For Linear / Azure: the credentials your chosen MCP connection expects (configured during the wizard)

After install, **restart the agent session** in that project so hooks and MCP reload.

---

## What you get

| Surface | Purpose |
| --- | --- |
| Skills / commands | `bootstrap`, `start-ticket`, `write-spec`, `resolve-ticket`, `review-pr`, feature start / finish / reconcile, … |
| Hooks | Fail-closed gates: branch naming, one mapped work item, `in_progress`, spec artifacts, completion evidence |
| MCP | `agentic-orchestrator` (instructions) + `workflow-integrations` (tracker/SCM gateway) |
| Config | `.codex-workflows/integrations.json` — adapters, bindings, mappings, branch template |

**Trackers:** Linear, Azure DevOps Boards. **SCM:** GitHub (`gh`), Azure Repos (MCP).

---

## Day-to-day workflow

1. **Start work** — `/start-ticket`: map the current branch to one work item, move it to logical `in_progress`, plan specs.
2. **Specify** — `/write-spec`: publish versioned specification artifacts on the tracker (Actor–Critic review).
3. **Implement** — hooks allow governed edits only when the branch maps to that item, state is `in_progress`, and an accepted spec exists.
4. **Ship** — create/link a PR via the SCM adapter; `/resolve-ticket` publishes resolution + verification evidence, then request logical `done`.
5. **Features** — `/feature-implementation`, `/reconcile-feature-stack`, `/finish-feature-development` stack stories on the same contracts.

Branch names must match the template chosen at install (must include `{key}`), for example `feature/ENG-42-add-login`.

Recovery and responsibility boundaries: [docs/provider-neutral-workflow.md](docs/provider-neutral-workflow.md).

---

## Uninstall

```bash
curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /absolute/path/to/your-app --uninstall
```

Or re-run the interactive installer and choose uninstall. Reinstall keeps `integrations.json` unless you delete it.

---

## Develop this plugin

```bash
git clone https://github.com/Monolith-INC/codex-workflows-plugin.git
cd codex-workflows-plugin
python3 -m unittest discover -s test -t . -p 'test_*.py'
```

Keep vendor payloads in `scripts/integrations/`; keep the orchestrator instruction-only. See [CLAUDE.md](CLAUDE.md) and [docs/adr/2026-06-07-host-adapter-architecture.md](docs/adr/2026-06-07-host-adapter-architecture.md).
