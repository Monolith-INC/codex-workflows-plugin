#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
for path in (REPO_ROOT, SCRIPTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts.hook_runtime import run  # noqa: E402

HOOK_CLIENT = os.environ.get("WORKFLOW_HOOK_CLIENT", "codex").strip().lower()


def install_hook() -> None:
    """Retained as a compatibility entry point; wiring is installer-owned."""
    print("Workflow hooks are wired by scripts.installer.bootstrap for the current project.")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ["--install", "install"]:
        install_hook()
        return 0

    try:
        input_data = json.load(sys.stdin)
    except Exception:
        from policy import PolicyDecision  # noqa: E402
        from scripts.hook_runtime import emit_decision  # noqa: E402

        emit_decision(HOOK_CLIENT, PolicyDecision.deny("Invalid hook payload"))
        return 0

    return run(HOOK_CLIENT, input_data)


if __name__ == "__main__":
    raise SystemExit(main())
