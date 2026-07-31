#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
for path in (REPO_ROOT, SCRIPTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts.hook_runtime import get_project_root, get_vault_dir, run  # noqa: E402

HOOK_CLIENT = os.environ.get("WORKFLOW_HOOK_CLIENT", "codex").strip().lower()


def install_hook() -> None:
    script_path = os.path.abspath(__file__)
    skill_root = os.path.dirname(os.path.dirname(script_path))
    resources_dir = os.path.join(skill_root, "resources")
    rules_dir = os.path.join(skill_root, "rules")

    os.chmod(script_path, 0o755)

    project_root = get_project_root()
    target_workflows_dir = os.path.join(project_root, ".agent", "workflows")
    os.makedirs(target_workflows_dir, exist_ok=True)

    if os.path.exists(resources_dir):
        print(f"Syncing workflows from {resources_dir} to {target_workflows_dir}...")
        for name in os.listdir(resources_dir):
            if name.endswith(".md"):
                src = os.path.join(resources_dir, name)
                dst = os.path.join(target_workflows_dir, name)
                with open(src, "r", encoding="utf-8") as s_file:
                    content = s_file.read()
                with open(dst, "w", encoding="utf-8") as d_file:
                    d_file.write(content)
                print(f"  Synced workflow: {name}")

    target_rules_dir = os.path.join(project_root, ".agent", "rules")
    os.makedirs(target_rules_dir, exist_ok=True)

    if os.path.exists(rules_dir):
        print(f"Syncing rules from {rules_dir} to {target_rules_dir}...")
        for name in os.listdir(rules_dir):
            if name.endswith(".md"):
                src = os.path.join(rules_dir, name)
                dst = os.path.join(target_rules_dir, name)
                with open(src, "r", encoding="utf-8") as s_file:
                    content = s_file.read()
                with open(dst, "w", encoding="utf-8") as d_file:
                    d_file.write(content)
                print(f"  Synced rule: {name}")

    config_dir = os.path.expanduser("~/.gemini/config")
    os.makedirs(config_dir, exist_ok=True)
    hooks_json_path = os.path.join(config_dir, "hooks.json")

    hook_config = {
        "codex-enforcer": {
            "enabled": True,
            "PreToolUse": [
                {
                    "matcher": ".*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": script_path,
                            "timeout": 5,
                        }
                    ],
                }
            ],
        }
    }

    with open(hooks_json_path, "w", encoding="utf-8") as file:
        json.dump(hook_config, file, indent=2)
    print(f"Hooks registered successfully at {hooks_json_path}")
    print("Setup complete!")


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
