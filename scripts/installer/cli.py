from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cursor_hooks import desired_cursor_hooks, merge_cursor_hooks
from .merge import merge_hook_configs
from .targets import Target, normalize_target, target_config_paths, target_hook_command


@dataclass(frozen=True)
class InstallResult:
    """Result of a plugin installation pass."""

    target: Target
    written_codex_config: bool
    written_shared_assets: bool
    written_target_config: bool
    config_paths: tuple[str, ...] = ()
    merged_config: dict[str, Any] | None = None


def _plugin_root() -> Path:
    """The root directory of this plugin package."""
    return Path(__file__).parent.parent.parent


def _hook_command(target: Target, plugin_root: Path) -> str:
    """Returns the absolute path hook command for the given target."""
    script_names = {
        Target.CODEX: "codex_enforce_hook.py",
        Target.GEMINI: "gemini_enforce_hook.py",
        Target.ANTIGRAVITY: "antigravity_enforce_hook.py",
        Target.ANTIGRAVITY_CLI: "antigravity_enforce_hook.py",
        Target.CLAUDE: "claude_enforce_hook.py",
        Target.CURSOR: "cursor_enforce_hook.py",
    }
    script = plugin_root / "skills" / "codex_workflows" / "scripts" / script_names[target]
    return f"python3 {script}"


def sync_shared_assets(dest_root: str | Path, plugin_root: Path | None = None) -> None:
    """Copies workflow and rules markdown files from the plugin into a destination project.

    Prefers ``.agent/workflows`` and ``.agent/rules`` under the plugin root.
    Falls back to ``skills/codex_workflows/resources`` (workflows + templates)
    and ``skills/codex_workflows/rules`` when the canonical ``.agent/`` tree is absent.
    """
    plugin_root = plugin_root or _plugin_root()
    dest = Path(dest_root)

    workflow_src = plugin_root / ".agent" / "workflows"
    if not workflow_src.is_dir():
        workflow_src = plugin_root / "skills" / "codex_workflows" / "resources"
    if workflow_src.is_dir():
        dst_dir = dest / ".agent" / "workflows"
        dst_dir.mkdir(parents=True, exist_ok=True)
        for item in workflow_src.iterdir():
            if item.is_file() and item.suffix == ".md":
                shutil.copy2(item, dst_dir / item.name)
            elif item.is_dir():
                shutil.copytree(item, dst_dir / item.name, dirs_exist_ok=True)

    rules_src = plugin_root / ".agent" / "rules"
    if not rules_src.is_dir():
        rules_src = plugin_root / "skills" / "codex_workflows" / "rules"
    if rules_src.is_dir():
        dst_dir = dest / ".agent" / "rules"
        dst_dir.mkdir(parents=True, exist_ok=True)
        for item in rules_src.iterdir():
            if item.is_file() and item.suffix in {".md", ".ts"}:
                shutil.copy2(item, dst_dir / item.name)
            elif item.is_dir():
                shutil.copytree(item, dst_dir / item.name, dirs_exist_ok=True)


def sync_host_discovery_assets(dest_root: str | Path, plugin_root: Path | None = None) -> None:
    """Sync skills/commands into project-local Claude and Antigravity discovery trees.

    Claude discovers ``.claude/skills/*/SKILL.md`` and ``.claude/commands/*.md``.
    Antigravity discovers ``.agents/skills/<name>/``.
    """
    plugin_root = plugin_root or _plugin_root()
    dest = Path(dest_root)
    skills_src = plugin_root / "skills"
    if skills_src.is_dir():
        for skill_dir in skills_src.iterdir():
            if not skill_dir.is_dir():
                continue
            for target_root in (dest / ".claude" / "skills", dest / ".agents" / "skills"):
                target = target_root / skill_dir.name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(
                    skill_dir,
                    target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )

    commands_src = plugin_root / "commands"
    if commands_src.is_dir():
        commands_dst = dest / ".claude" / "commands"
        commands_dst.mkdir(parents=True, exist_ok=True)
        for item in commands_src.iterdir():
            if item.is_file() and item.suffix == ".md":
                shutil.copy2(item, commands_dst / item.name)


def write_target_config(
    merged_config: dict[str, Any],
    config_path: str,
    dest_root: str | Path,
) -> Path:
    """Writes the merged hook configuration JSON to the target config path.

    Creates any missing parent directories. Returns the path of the written file.
    """
    dest = Path(dest_root) / config_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(merged_config, indent=2), encoding="utf-8")
    return dest


def install(
    target: str | Target,
    profile: str = "generic",
    *,
    existing_hooks: dict[str, Any] | None = None,
    dest_root: str | Path | None = None,
    plugin_root: Path | None = None,
) -> InstallResult:
    """Computes (and optionally writes) plugin installation artifacts for a host target.

    When [dest_root] is provided, actually writes the hook config and syncs
    shared assets to the filesystem. When omitted, the function operates in
    dry-run mode and only returns the computed [InstallResult].
    """
    plugin_root = plugin_root or _plugin_root()
    normalized_target = normalize_target(target)
    shared_assets = normalized_target in {Target.UNIVERSAL, Target.ALL_AGENTS}
    codex_config = normalized_target in {Target.CODEX, Target.ALL_AGENTS}
    target_config = normalized_target in {
        Target.CODEX,
        Target.GEMINI,
        Target.ANTIGRAVITY,
        Target.ANTIGRAVITY_CLI,
        Target.CLAUDE,
        Target.CURSOR,
    }
    config_paths = target_config_paths(normalized_target)
    merged_config = None

    desired_hooks: dict[str, Any] | None = None
    if target_config:
        hook_command = _hook_command(normalized_target, plugin_root)
        if normalized_target == Target.CURSOR:
            desired_hooks = desired_cursor_hooks(hook_command)
        elif normalized_target == Target.ANTIGRAVITY:
            desired_hooks = {
                "codex-enforcer": {
                    "enabled": True,
                    "PreToolUse": [
                        {
                            "matcher": ".*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": hook_command,
                                    "timeout": 5,
                                }
                            ],
                        }
                    ],
                }
            }
        elif normalized_target == Target.GEMINI:
            # Gemini CLI timeouts are milliseconds (docs: timeout 5000 == 5s).
            desired_hooks = {
                "hooks": {
                    "BeforeTool": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "name": "codex-workflows-enforce",
                                    "type": "command",
                                    "command": hook_command,
                                    "timeout": 5000,
                                }
                            ],
                        }
                    ]
                }
            }
        elif normalized_target == Target.ANTIGRAVITY_CLI:
            # Antigravity CLI inherits Gemini-style BeforeTool hooks (ms timeout).
            desired_hooks = {
                "hooks": {
                    "BeforeTool": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "name": "codex-workflows-enforce",
                                    "type": "command",
                                    "command": hook_command,
                                    "timeout": 5000,
                                }
                            ],
                        }
                    ]
                }
            }
        elif normalized_target == Target.CLAUDE:
            desired_hooks = {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": hook_command,
                                    "timeout": 5,
                                }
                            ],
                        }
                    ]
                }
            }
        elif normalized_target == Target.CURSOR:
            desired_hooks = {
                "version": 1,
                "hooks": {
                    "preToolUse": [
                        {
                            "command": hook_command,
                            "matcher": "Shell|Read|Write|Grep|Delete|Task",
                            "timeout": 5,
                            "failClosed": True,
                        }
                    ]
                },
            }
        else:
            desired_hooks = {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "^(Bash|apply_patch)$",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": hook_command,
                                    "timeout": 5,
                                    "statusMessage": "Checking workflow policy",
                                }
                            ],
                        }
                    ]
                }
            }
        merged_config = (
            merge_cursor_hooks(existing_hooks, desired_hooks)
            if normalized_target == Target.CURSOR
            else merge_hook_configs(existing_hooks, desired_hooks)
        )

    if dest_root is not None:
        sync_shared_assets(dest_root, plugin_root)
        sync_host_discovery_assets(dest_root, plugin_root)
        if merged_config is not None and config_paths:
            write_target_config(merged_config, config_paths[0], dest_root)

    return InstallResult(
        target=normalized_target,
        written_codex_config=codex_config,
        written_shared_assets=shared_assets or target_config,
        written_target_config=target_config,
        config_paths=config_paths,
        merged_config=merged_config,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Codex workflow assets for a specific client target.")
    parser.add_argument("--target", default="codex", help="Target client: codex, gemini, antigravity, claude, cursor, universal, all-agents")
    parser.add_argument("--profile", default="generic", help="Installer profile name")
    parser.add_argument(
        "--output",
        help="Optional path to write the merged hooks config (dry-run; does not sync workflows)",
    )
    parser.add_argument(
        "--dest",
        help="Destination project root. When set, writes hook config and syncs .agent/, .claude/, and .agents/ discovery assets.",
    )
    args = parser.parse_args()

    result = install(args.target, profile=args.profile, dest_root=args.dest)

    if args.output and result.merged_config is not None:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result.merged_config, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "target": result.target.value,
                "writtenCodexConfig": result.written_codex_config,
                "writtenSharedAssets": result.written_shared_assets,
                "writtenTargetConfig": result.written_target_config,
                "configPaths": list(result.config_paths),
                "mergedConfig": result.merged_config,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
