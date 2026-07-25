---
name: bootstrap
description: >-
  Use when the user asks to install, wire, update, or uninstall the
  codex-workflows-plugin into a project (local --dest install only).
---

# bootstrap

Install this plugin into a **project** with `--dest`. Global install is not supported.

```bash
python3 -m scripts.installer.bootstrap --target all-agents --dest /path/to/project
```

Runtime lands at `<dest>/.codex-workflows/`. Discovery trees: `.claude/skills`, `.claude/commands`, `.agents/skills`.
