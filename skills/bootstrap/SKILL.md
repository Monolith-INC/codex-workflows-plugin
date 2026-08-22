---
name: bootstrap
description: Use when the user asks to install, wire, update, or uninstall the codex-workflows-plugin into a project, or to (re)configure tracker/SCM integrations.
---

# Bootstrap

## End-user install (preferred)

From the application repository the user wants to govern:

```bash
bash <(curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh)
```

That downloads the latest release, wires the selected agent host(s), and writes `.codex-workflows/integrations.json` (tracker, SCM, mappings, branch template with `{key}`). Do not ask the user to clone this plugin repo for normal installs.

CI / non-interactive:

```bash
curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /absolute/path/to/your-app
```

## Reconfigure an existing install

If the runtime is already present under `<project>/.codex-workflows/`, re-run the installer wizard or:

```bash
python3 -m scripts.installer.bootstrap --dest <project> --target all-agents \
  --tracker local_tracker --local-tracker-storage committed --scm github \
  --branch-template '{category}/{key}-{slug}'
```

Use `linear` or `azure_devops` instead when an external tracker is available. Local
tracker creates `.local-tracker/` state folders and stores Epic → Feature → User
Story → Task records and versioned artifacts there; `--local-tracker-storage
ignored` manages its `.gitignore` entry instead of committing the records.

Preserve `integrations.json` across reinstalls unless the user asks to reset it. Verify both `agentic-orchestrator` and `workflow-integrations` MCP servers after wiring. Restart the agent session when done.
