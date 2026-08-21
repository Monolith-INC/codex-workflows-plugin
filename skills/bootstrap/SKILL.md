---
name: bootstrap
description: >-
  Use when the user asks to install, wire, update, or uninstall the
  codex-workflows-plugin into a project (local --dest install only).
---

# bootstrap

Install this plugin into a **project** with `--dest`. Global install is not supported.

```bash
  python3 -m scripts.installer.bootstrap --target all-agents --dest /path/to/project \\
    --tracker linear --scm github --branch-template '{category}/{key}-{slug}'
```

Runtime lands at `<dest>/.codex-workflows/`. The wizard offers Linear or Azure DevOps Boards, GitHub or Azure Repos, and branch presets plus `other`; custom templates must contain `{key}`. It writes `.codex-workflows/integrations.json` and wires both `agentic-orchestrator` and `workflow-integrations` MCP servers. Discovery trees are `.claude/skills`, `.claude/commands`, and `.agents/skills`.
