#!/usr/bin/env python3
"""Cwd-independent launcher for the agentic-orchestrator MCP stdio server.

Cursor and Claude Code spawn plugin MCP servers without putting the plugin root
on ``PYTHONPATH`` or using it as cwd. Host ``.mcp.json`` must invoke this file
(not ``python -m scripts.orchestrator.mcp_server``). Both hosts expand
``${CLAUDE_PLUGIN_ROOT}`` in plugin MCP ``args``/``env`` to the install dir, so
plugin manifests use:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator/run_mcp_server.py

This script then inserts the plugin root on ``sys.path`` before importing
``scripts.orchestrator``.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_SCRIPTS_DIR)

for _path in (_REPO_ROOT, _SCRIPTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from scripts.orchestrator.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    main()
