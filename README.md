# Codex Workflows Plugin

[![Release](https://img.shields.io/github/v/release/Monolith-INC/codex-workflows-plugin?display_name=tag&sort=semver)](https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/Monolith-INC/codex-workflows-plugin/ci.yml?branch=main&label=CI)](https://github.com/Monolith-INC/codex-workflows-plugin/actions)
[![License](https://img.shields.io/badge/license-see%20repo-lightgrey)](https://github.com/Monolith-INC/codex-workflows-plugin)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

Provider-neutral work-item workflows for Claude Code, Cursor, Codex, and related agent hosts.

The plugin installs into **the repository you are working on**. It wires skills, commands, hooks, and MCP servers for that project, then asks you which tracker and SCM to use. Durable ticket state can live in Linear, Azure DevOps Boards, or the repository-local tracker. Pull requests and review threads live in your SCM (GitHub or Azure Repos). The orchestrator stays instruction-only — it does not proxy vendor APIs.

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
3. Ask for tracker (Linear, Azure DevOps Boards, or local tracker) and SCM (GitHub or Azure Repos)
4. Confirm kind/state mappings and a branch template that contains `{key}`
5. Download the latest release, install the runtime under `<your-app>/.codex-workflows/`, wire hooks/MCP, and write `<your-app>/.codex-workflows/integrations.json`

### Non-interactive / CI

```bash
curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /absolute/path/to/your-app
```

Optional flags: `--target claude|cursor|codex|all-agents`, `--uninstall`.

Pin a release with `CODEX_WORKFLOWS_VERSION=v0.5.26`. Offline installs can set `CODEX_WORKFLOWS_RELEASE_ZIP=/path/to/codex-workflows-plugin-*.zip`.

### Requirements

- Python 3.10+
- `git`
- Network access to GitHub Releases (or a local zip via `CODEX_WORKFLOWS_RELEASE_ZIP`)
- For GitHub SCM: authenticated [`gh`](https://cli.github.com/)
- For Linear / Azure: the credentials your chosen MCP connection expects (configured during the wizard)
- For local tracker: no external credentials; work-item records are stored in `.local-tracker/`

After install, **restart the agent session** in that project so hooks and MCP reload.

---

## What you get

Codex Workflows turns an agent session from loose chat into a governed delivery
loop. The agent still writes code with you, but every meaningful change is tied
to an explicit work item, a branch convention, a specification artifact, a pull
request, and verification evidence. When the team does not want an external
tracker, the local tracker gives the same workflow a repository-native storage
model instead of forcing Linear or Azure DevOps.

The shipped system has five parts working together:

| Capability | What ships | Why it matters |
| --- | --- | --- |
| Workflow commands | `/start-ticket`, `/write-spec`, `/resolve-ticket`, `/review-pr`, feature stack commands, and tracker pause/resume commands. | The agent has named entry points for the important moments in delivery instead of inventing process in each conversation. |
| Enforced hooks | Branch naming, one-work-item mapping, logical state checks, spec prerequisites, completion evidence, and protected-branch Git safety. | Unverified code, missing specs, wrong branches, and silent tracker drift are blocked at the point of action. |
| Provider-neutral gateway | Tracker and SCM adapters behind the `workflow-integrations` MCP server. | Skills use one contract while Linear, Azure DevOps Boards, local tracker, GitHub, and Azure Repos keep their provider-specific payloads isolated. |
| Durable artifacts | Versioned specs, review reports, resolution reports, verification plans, and development links. | Decisions survive the chat window and can be audited from the tracker or from local repository files. |
| Repository quality gate | `scripts/quality.py check` and `scripts/quality.py fix` with Ruff, mypy, unit tests, plugin validation, and Markdown linting. | The plugin itself now ships through the same principle it enforces: no release without repeatable verification. |

The root `codex-workflows-plugin.json` file is the release package manifest
used for name/version validation. Bootstrap generates host-specific project
configuration in the governed repository: `.claude/`, `.cursor/`, `.agents/`,
`.codex/`, and the related hook/MCP files. Provider-specific logic belongs
under `scripts/integrations/`; host-specific hook payload parsing belongs under
`scripts/host_adapters/`.

### Commands and skills

Commands are the user-facing entry points. They work through the same skills
and integration contracts regardless of whether your tracker is Linear, Azure
DevOps Boards, or the local tracker.

| Command | Use it when | Example outcome |
| --- | --- | --- |
| `/bootstrap` | Installing or rewiring the plugin in a project. | Creates `.codex-workflows/integrations.json`, installs host hooks, and verifies tracker/SCM bindings. |
| `/start-ticket` | Beginning tracked work from a draft or existing item. | Creates or fetches `ENG-42`, creates/checks out the mapped branch, moves it to `in_progress`, and returns the spec plan. |
| `/write-spec` | Turning intent into durable implementation artifacts. | Publishes an implementation plan, RFC, ADR, or task spec as a versioned tracker artifact. |
| `/resolve-ticket` | Finishing a work item. | Publishes resolution and verification evidence, links the PR, and requests the logical `done` transition. |
| `/review-pr` | Processing review threads. | Reads SCM review comments, classifies them, applies accepted changes, and publishes a review artifact. |
| `/feature-implementation` | Starting a parent feature with child stories. | Builds a feature plan and stacked story branch order from Epic/Feature/User Story relationships. |
| `/reconcile-feature-stack` | A parent branch changed while child stories are open. | Replays ancestor changes through descendant story branches in order. |
| `/merge-story-stack-into-feature` | Stacked stories are ready to land into the feature. | Merges Story→Feature oldest→newest with merge commits only (never squash). |
| `/finish-feature-development` | All feature stories are complete. | Creates the feature-to-trunk closeout path and publishes final feature evidence. |
| `/skip-tracker` | You need untracked work without tracker enforcement. | Sets `tracking.mode` to `skipped`; tracker commands pause, SCM and Git safety stay on. |
| `/resume-tracker` | You are ready to enforce the saved tracker again. | Restores `tracking.mode: enforced` without rediscovering provider bindings. |
| `/tracking-status` | You need to know whether tracking is enforced. | Reports the current tracking mode and configured provider. |

Example single-ticket conversation:

```text
User: /start-ticket
Agent: asks for a draft location, or interviews for title, requirements, and
       acceptance criteria; creates ENG-42; creates story/ENG-42-add-login;
       moves ENG-42 to in_progress; and proposes the required specs.

User: implement it
Agent: drafts and publishes required specs first, then writes code only after
       the branch, state, and spec checks pass.

User: /resolve-ticket
Agent: publishes verification evidence, links the PR, and requests done.
```

### Hooks and guardrails

Hooks are intentionally strict during tracked work. Before governed writes,
they verify that the branch name matches the configured template, exactly one
work item key is present, the tracker item is in the logical `in_progress`
state, and required specification artifacts exist. Before completion, they
look for resolution and verification evidence.

For example, with this bootstrap branch template:

```text
story/{key}-{slug}
```

the branch `story/ENG-42-add-login` can map to `ENG-42`, but
`quick-fix-login` cannot. If tracking is paused with `/skip-tracker`, those
tracker-only requirements are bypassed, but protected-branch Git safety remains
active so broad SCM mistakes are still blocked.

That gives the workflow a fail-closed posture during normal development:

- A branch with no work-item key cannot start tracked implementation.
- A branch with two possible keys is rejected instead of guessing.
- A work item outside the logical `in_progress` state cannot receive governed
  code changes.
- A completion request without resolution and verification evidence is stopped
  before the tracker is moved to `done`.
- A paused tracker mode allows deliberate untracked work without turning off
  protected-branch Git safety.

### MCP servers

The release installs two MCP servers:

- `agentic-orchestrator` reads workflow manifests, expands the correct skill,
  and keeps orchestration instruction-only.
- `workflow-integrations` owns provider calls through adapters. Tracker
  adapters expose work-item operations; SCM adapters expose pull-request and
  review-thread operations.

This split matters: workflow skills depend on generic contracts, while vendor
payloads stay in `scripts/integrations/`. Agent-host payloads are a separate
boundary: Claude, Cursor, Codex, Gemini, and Antigravity hook input/output
formats live in `scripts/host_adapters/` because they describe how each host
calls the policy runtime, not how tracker or SCM providers behave.

For example, `/resolve-ticket` does not need to know whether a "done" operation
means a Linear workflow transition, an Azure DevOps state update, or moving a
local JSON record from `.local-tracker/in_progress/` to `.local-tracker/done/`.
The skill requests the logical transition; the selected adapter performs the
provider-specific operation.

### Configuration

Bootstrap writes `.codex-workflows/integrations.json` in the governed project.
It records adapters, provider bindings, logical kind/state mappings, the branch
template, and tracking mode. A representative local-tracker setup looks like:

```json
{
  "tracker": {
    "adapter": "local_tracker",
    "root": ".local-tracker",
    "storagePolicy": "committed",
    "connection": {
      "command": "python3",
      "args": [
        ".codex-workflows/scripts/integrations/run_local_tracker.py",
        "--project-root",
        "/path/to/app",
        "--root",
        ".local-tracker"
      ]
    },
    "bindings": {
      "get_work_item": "get_work_item",
      "search_work_items": "search_work_items",
      "create_work_item": "create_work_item",
      "list_children": "list_children",
      "transition_work_item": "transition_work_item",
      "publish_artifact": "publish_artifact",
      "list_artifacts": "list_artifacts",
      "link_development_artifact": "link_development_artifact"
    },
    "mappings": {
      "kinds": {
        "epic": "epic",
        "feature": "feature",
        "user_story": "user_story",
        "task": "task",
        "bug": "bug"
      },
      "states": {
        "backlog": "backlog",
        "ready": "ready",
        "in_progress": "in_progress",
        "done": "done",
        "canceled": "canceled"
      }
    }
  },
  "tracking": {
    "mode": "enforced"
  }
}
```

**Trackers:** Linear, Azure DevOps Boards, local tracker. **SCM:** GitHub (`gh`), Azure Repos (MCP).

### Local tracker

The local tracker is a first-class tracker adapter for teams or repositories
that do not want an external tracker. It supports the same gateway surface as
Linear and Azure DevOps Boards: create/fetch/search work items, transition
state, list children, publish artifacts, and persist development links. Its
adapter still goes through configured provider bindings; the provider is a
project-local MCP server at
`.codex-workflows/scripts/integrations/run_local_tracker.py`.

When selected during bootstrap, the plugin creates:

```text
.local-tracker/
  backlog/
  ready/
  in_progress/
  done/
  canceled/
  artifacts/
```

Work items are JSON records stored in the folder matching their current state.
Keys are stable and role-specific, for example `EPIC-0001`, `FEATURE-0001`,
`STORY-0001`, `TASK-0001`, and `BUG-0001`. Transitions move the record between
state folders. Artifacts are versioned under `.local-tracker/artifacts/<key>/`,
so `/write-spec`, `/review-pr`, and `/resolve-ticket` can publish durable local
evidence without any external account.

A local work item record is intentionally plain JSON so it can be reviewed,
diffed, and committed:

```json
{
  "id": "STORY-0001",
  "key": "STORY-0001",
  "role": "user_story",
  "title": "Add Markdown quality gate",
  "state": "in_progress",
  "parent": "FEATURE-0001",
  "children": ["TASK-0001"],
  "links": [
    {
      "type": "pull_request",
      "url": "https://github.com/acme/app/pull/17"
    }
  ]
}
```

The supported hierarchy is:

```text
Epic -> Feature -> User Story -> Task
                  -> Bug        -> Task
```

Committed storage is the default, which makes tracker state part of repository
history. During bootstrap, choose ignored storage when local records should be
private to the worktree; the installer will manage the `.gitignore` entry for
`.local-tracker/`.

### Quality gate

This release also ships the repository quality gate that caught the original
gap. The canonical commands are:

```bash
python3 scripts/quality.py check
python3 scripts/quality.py fix
```

`check` runs plugin validation, Ruff lint, Ruff format check, mypy, unit tests,
and Markdown lint. `fix` applies safe Ruff fixes, formats Python, runs
`markdownlint-cli2 --fix`, and then re-runs `check`. CI and tag-release
packaging install the pinned Python and Node toolchains, then call only this
runner before publishing.

---

## Day-to-day workflow

### Single work item

1. Run `/start-ticket` with a ticket, draft location, or short intent. If no
   draft exists, the agent asks for the title, requirements, acceptance
   criteria, constraints, and optional parent work item.
2. The skill creates or fetches the tracker item, creates/checks out the branch
   from the configured template, and moves the item to `in_progress`.
3. The skill publishes the accepted implementation plan or design artifact
   before code changes.
4. Implement and verify. Hooks keep the branch tied to that one work item.
5. Open a PR through the configured SCM adapter.
6. Run `/resolve-ticket` with test results and release notes. The skill
   publishes resolution evidence, links the PR, and requests the logical `done`
   transition.

### Feature stack

For larger work, model the parent and children in the tracker:

```text
EPIC-0001 Platform quality
  FEATURE-0001 Verified workflow gates
    STORY-0001 Add canonical quality runner
    STORY-0002 Add Markdown lint gate
    STORY-0003 Add local tracker bootstrap
```

Run `/feature-implementation` from the parent feature to plan the stack.
Implement each story on its own branch, target story PRs at the feature branch,
and use `/reconcile-feature-stack` whenever an ancestor branch changes. When
stories are ready to land, `/merge-story-stack-into-feature` merges them into
the feature in stack order with merge commits only. After all child stories are
in the feature, `/finish-feature-development` handles the feature-to-trunk
closeout and publishes the final evidence.

### Paused tracking

Use `/skip-tracker` for deliberate untracked work, for example emergency
documentation edits, repository cleanup, or investigation that should not move
a ticket. While paused:

- tracker commands fail with a paused-tracking explanation;
- tracker-dependent workflow skills are unavailable;
- tracker-only hook checks are bypassed;
- SCM workflows and protected-branch Git safety remain active.

Run `/resume-tracker` when the repository should return to enforced tracking.
The configured provider, mappings, and branch template are preserved.

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
python3 -m pip install -r requirements-dev.txt
npm ci
python3 scripts/quality.py check
python3 scripts/quality.py fix
```

Keep vendor payloads in `scripts/integrations/`; keep the orchestrator instruction-only. See [CLAUDE.md](CLAUDE.md) and [docs/adr/2026-06-07-host-adapter-architecture.md](docs/adr/2026-06-07-host-adapter-architecture.md).
