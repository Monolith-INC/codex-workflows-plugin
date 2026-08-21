from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .targets import Target, target_config_paths

PLUGIN_NAME = "codex-workflows-plugin"
_MANAGED_HOOK_MARKERS = ("codex-workflows-plugin", "codex_workflows", "workflow-integrations")


@dataclass
class UninstallPlan:
    remove_paths: list[Path] = field(default_factory=list)
    prune_stops: dict[Path, Path] = field(default_factory=dict)
    write_json: dict[Path, dict[str, Any]] = field(default_factory=dict)
    write_text: dict[Path, str] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)


def uninstall(
    install_dir: Path,
    *,
    dest: Path,
    keep_runtime: bool = False,
    dry_run: bool = False,
) -> UninstallPlan:
    """Remove project-local install artifacts. Global/home cleanup is not performed."""
    plan = UninstallPlan()
    install_dir = install_dir.expanduser().resolve()
    project_root = dest.expanduser().resolve()

    for config_path in _project_hook_paths(project_root):
        _plan_clean_hook_config(plan, config_path, prune_stop=project_root)

    _plan_project_asset_cleanup(plan, project_root, install_dir)
    _plan_project_discovery_cleanup(plan, project_root, install_dir)
    _plan_mcp_cleanup(plan, project_root)
    _plan_codex_mcp_cleanup(plan, project_root)
    _plan_cursor_mcp_cleanup(plan, project_root)
    _plan_claude_mcp_enablement_cleanup(plan, project_root)

    if not keep_runtime:
        _plan_remove_path(plan, install_dir, prune_stop=install_dir.parent)

    if dry_run:
        plan.messages.insert(0, "DRY RUN: no filesystem changes applied.")
        return plan

    _apply_plan(plan)
    return plan


def strip_managed_hooks(config: dict[str, Any]) -> dict[str, Any]:
    return _strip_value(config)


def _strip_hook_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    command = entry.get("command")
    if isinstance(command, str) and _is_managed_command(command):
        return None

    if "hooks" not in entry or not isinstance(entry["hooks"], list):
        return dict(entry)

    hooks = []
    for hook in entry["hooks"]:
        if isinstance(hook, dict):
            command = hook.get("command")
            if isinstance(command, str) and _is_managed_command(command):
                continue
        hooks.append(hook)

    if not hooks:
        return None
    return {**entry, "hooks": hooks}


def _strip_value(value: Any) -> Any:
    if isinstance(value, dict):
        stripped_hook = _strip_hook_entry(value)
        if stripped_hook is None:
            return {}
        result = {}
        for key, child in stripped_hook.items():
            if key == "command":
                result[key] = child
                continue
            stripped = _strip_value(child)
            if not _is_empty(stripped):
                result[key] = stripped
        return result
    if isinstance(value, list):
        cleaned = []
        for entry in value:
            stripped = _strip_value(entry)
            if not _is_empty(stripped):
                cleaned.append(stripped)
        return cleaned
    return value


def _is_managed_command(command: str) -> bool:
    return any(marker in command for marker in _MANAGED_HOOK_MARKERS)


def _is_empty(value: Any) -> bool:
    if value == {} or value == []:
        return True
    return isinstance(value, dict) and set(value) <= {"enabled", "version"}


def _project_hook_paths(project_root: Path) -> list[Path]:
    paths = []
    for target in (
        Target.CODEX,
        Target.GEMINI,
        Target.ANTIGRAVITY,
        Target.ANTIGRAVITY_CLI,
        Target.CLAUDE,
        Target.CURSOR,
    ):
        for relative_path in target_config_paths(target):
            paths.append(project_root / relative_path)
    return paths


def _plan_clean_hook_config(plan: UninstallPlan, config_path: Path, *, prune_stop: Path) -> None:
    if not config_path.exists():
        return
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        plan.messages.append(f"Skipped invalid JSON config: {config_path}")
        return
    if not isinstance(config, dict):
        return

    cleaned = strip_managed_hooks(config)
    if cleaned == config:
        return
    if _is_empty(cleaned):
        _plan_remove_path(plan, config_path, prune_stop=prune_stop)
    else:
        plan.write_json[config_path] = cleaned
        plan.messages.append(f"Write cleaned config: {config_path}")


def _plan_project_asset_cleanup(plan: UninstallPlan, project_root: Path, install_dir: Path) -> None:
    for rel, source_dir in _project_asset_sources(install_dir):
        project_dir = project_root / ".agent" / rel
        if not source_dir.is_dir() or not project_dir.exists():
            continue
        for source_file in source_dir.rglob("*"):
            if source_file.is_file():
                relative = source_file.relative_to(source_dir)
                _plan_remove_path(plan, project_dir / relative, prune_stop=project_root)


def _project_asset_sources(install_dir: Path) -> tuple[tuple[str, Path], ...]:
    asset_root = install_dir / ".agent"
    workflow_src = asset_root / "workflows"
    if not workflow_src.is_dir():
        workflow_src = install_dir / "skills" / "codex_workflows" / "resources"

    rules_src = asset_root / "rules"
    if not rules_src.is_dir():
        rules_src = install_dir / "skills" / "codex_workflows" / "rules"

    return (("workflows", workflow_src), ("rules", rules_src))


def _plan_project_discovery_cleanup(plan: UninstallPlan, project_root: Path, install_dir: Path) -> None:
    skills_src = install_dir / "skills"
    skill_names: set[str] = set()
    if skills_src.is_dir():
        skill_names = {p.name for p in skills_src.iterdir() if p.is_dir()}

    for root_name in (".claude/skills", ".agents/skills"):
        root = project_root / root_name
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and child.name in skill_names:
                _plan_remove_path(plan, child, prune_stop=project_root)

    commands_src = install_dir / "commands"
    commands_dst = project_root / ".claude" / "commands"
    if commands_src.is_dir() and commands_dst.is_dir():
        for item in commands_src.iterdir():
            if item.is_file() and item.suffix == ".md":
                _plan_remove_path(plan, commands_dst / item.name, prune_stop=project_root)


def _plan_mcp_cleanup(plan: UninstallPlan, project_root: Path) -> None:
    mcp_path = project_root / ".mcp.json"
    if not mcp_path.exists():
        return
    try:
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        plan.messages.append(f"Skipped invalid JSON MCP config: {mcp_path}")
        return
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict) or not ({"agentic-orchestrator", "workflow-integrations"} & set(servers)):
        return
    cleaned = dict(payload)
    cleaned_servers = dict(servers)
    cleaned_servers.pop("agentic-orchestrator", None)
    cleaned_servers.pop("workflow-integrations", None)
    cleaned["mcpServers"] = cleaned_servers
    if not cleaned_servers and set(cleaned) <= {"mcpServers"}:
        _plan_remove_path(plan, mcp_path, prune_stop=project_root)
    else:
        plan.write_json[mcp_path] = cleaned
        plan.messages.append(f"Write cleaned MCP config: {mcp_path}")


def _plan_codex_mcp_cleanup(plan: UninstallPlan, project_root: Path) -> None:
    config_path = project_root / ".codex" / "config.toml"
    if not config_path.exists():
        return
    cleaned = _strip_codex_mcp_server_sections(config_path.read_text(encoding="utf-8"), {"agentic-orchestrator", "workflow-integrations"})
    if cleaned:
        plan.write_text[config_path] = cleaned.rstrip() + "\n"
        plan.messages.append(f"Write cleaned Codex MCP config: {config_path}")
    else:
        _plan_remove_path(plan, config_path, prune_stop=project_root)


def _plan_cursor_mcp_cleanup(plan: UninstallPlan, project_root: Path) -> None:
    cursor_path = project_root / ".cursor" / "mcp.json"
    if not cursor_path.exists():
        return
    try:
        payload = json.loads(cursor_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        plan.messages.append(f"Skipped invalid JSON Cursor MCP config: {cursor_path}")
        return
    servers = payload.get("mcpServers") if isinstance(payload, dict) else None
    if not isinstance(servers, dict) or not ({"agentic-orchestrator", "workflow-integrations"} & set(servers)):
        return
    cleaned = dict(payload)
    cleaned_servers = dict(servers)
    cleaned_servers.pop("agentic-orchestrator", None)
    cleaned_servers.pop("workflow-integrations", None)
    cleaned["mcpServers"] = cleaned_servers
    if not cleaned_servers and set(cleaned) <= {"mcpServers"}:
        _plan_remove_path(plan, cursor_path, prune_stop=project_root)
    else:
        plan.write_json[cursor_path] = cleaned
        plan.messages.append(f"Write cleaned Cursor MCP config: {cursor_path}")


def _plan_claude_mcp_enablement_cleanup(plan: UninstallPlan, project_root: Path) -> None:
    settings_path = project_root / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        plan.messages.append(f"Skipped invalid JSON Claude local settings: {settings_path}")
        return
    if not isinstance(payload, dict):
        return
    enabled = payload.get("enabledMcpjsonServers")
    if not isinstance(enabled, list) or not ({"agentic-orchestrator", "workflow-integrations"} & set(enabled)):
        return
    cleaned = dict(payload)
    cleaned["enabledMcpjsonServers"] = [name for name in enabled if name not in {"agentic-orchestrator", "workflow-integrations"}]
    if (
        not cleaned["enabledMcpjsonServers"]
        and cleaned.get("enableAllProjectMcpServers") is True
        and set(cleaned) <= {"enabledMcpjsonServers", "enableAllProjectMcpServers"}
    ):
        _plan_remove_path(plan, settings_path, prune_stop=project_root)
    else:
        plan.write_json[settings_path] = cleaned
        plan.messages.append(f"Write cleaned Claude MCP enablement: {settings_path}")


def _strip_codex_mcp_server_sections(content: str, server_names: set[str]) -> str:
    kept: list[str] = []
    skip = False
    for line in content.splitlines():
        header = _toml_header(line)
        if header is not None:
            skip = _replace_mcp_server_section(header, server_names)
        if not skip:
            kept.append(line)
    return "\n".join(kept).strip()


def _toml_header(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("[[") or not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    return stripped[1:-1].strip()


def _mcp_server_name_from_header(header: str) -> str | None:
    prefix = "mcp_servers."
    if not header.startswith(prefix):
        return None
    return header.removeprefix(prefix).split(".", 1)[0].strip('"')


def _replace_mcp_server_section(header: str, server_names: set[str]) -> bool:
    server_name = _mcp_server_name_from_header(header)
    if server_name not in server_names:
        return False
    rest = header.removeprefix("mcp_servers.").split(".", 1)
    return len(rest) == 1 or rest[1].strip('"') == "env"


def _plan_remove_path(plan: UninstallPlan, path: Path, *, prune_stop: Path) -> None:
    if path in plan.remove_paths:
        return
    if path.exists() or path.is_symlink():
        plan.remove_paths.append(path)
        plan.prune_stops[path] = prune_stop
        plan.messages.append(f"Remove: {path}")


def _apply_plan(plan: UninstallPlan) -> None:
    for path, content in plan.write_json.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, indent=2), encoding="utf-8")

    for path, content in plan.write_text.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    for path in sorted(plan.remove_paths, key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink() or path.is_file():
            path.unlink()
            _prune_empty_parents(path.parent, plan.prune_stops[path])
        elif path.is_dir():
            shutil.rmtree(path)
            _prune_empty_parents(path.parent, plan.prune_stops[path])


def _prune_empty_parents(start: Path, stop: Path) -> None:
    stop = stop.resolve()
    current = start
    while current.resolve() != stop and stop in current.resolve().parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
