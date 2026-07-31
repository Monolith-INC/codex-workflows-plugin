"""Install and wire codex-workflows-plugin into a project (local install only).

Usage
-----
From the release zip:
    python3 bootstrap.py codex-workflows-plugin-0.5.12.zip --target all-agents --dest /path/to/project

From source after cloning:
    python3 -m scripts.installer.bootstrap --target all-agents --dest /path/to/project

Uninstall from a project:
    python3 -m scripts.installer.bootstrap --uninstall --dest /path/to/project
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Iterator

# Script filenames that belong to this plugin — used to strip stale hook entries.
_MANAGED_HOOK_SCRIPTS = {
    "codex_enforce_hook.py",
    "gemini_enforce_hook.py",
    "antigravity_enforce_hook.py",
    "claude_enforce_hook.py",
    "cursor_enforce_hook.py",
}

_RUNTIME_DIRS = ["scripts", "skills", "commands", ".agent", "hooks", ".codex-plugin"]

_INTERACTIVE_AZURE_DEVOPS_ENV_VARS = [
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
    "BROWSER",
]


def default_install_dir(project_dest: Path) -> Path:
    """Project-local runtime root (never ~/.codex-workflows)."""
    return project_dest / ".codex-workflows"


def install_from_zip(zip_path: Path, dest: Path) -> None:
    """Extract a release zip to dest, replacing any prior installation."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)


def install_from_source(source_root: Path, dest: Path) -> None:
    """Copy runtime directories from source_root to dest."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for dirname in _RUNTIME_DIRS:
        src = source_root / dirname
        if not src.exists():
            continue
        shutil.copytree(
            src,
            dest / dirname,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def strip_managed_hooks(config: dict, script_names: set[str]) -> dict:
    """Remove hook entries whose command references any of the given script filenames."""
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = strip_managed_hooks(value, script_names)
        elif isinstance(value, list):
            cleaned = []
            for entry in value:
                if not isinstance(entry, dict) or "hooks" not in entry:
                    cleaned.append(entry)
                    continue
                fresh_hooks = [
                    h for h in entry["hooks"]
                    if not any(s in h.get("command", "") for s in script_names)
                ]
                if fresh_hooks:
                    cleaned.append({**entry, "hooks": fresh_hooks})
            result[key] = cleaned
        else:
            result[key] = value
    return result


def wire_orchestrator_mcp(install_dir: Path, project_dest: Path) -> bool:
    """Merge MCP servers into project JSON, Cursor, Claude enablement, and Codex TOML."""
    mcp_path = project_dest / ".mcp.json"
    existing: dict = {"mcpServers": {}}
    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {"mcpServers": {}}

    servers = existing.setdefault("mcpServers", {})
    install_root = install_dir.resolve()
    skills_dir = (install_root / "skills")
    launcher = install_root / "scripts" / "orchestrator" / "run_mcp_server.py"
    servers["agentic-orchestrator"] = {
        "command": "python3",
        "args": [str(launcher)],
        "env": {
            # Kept for hosts/tools that still import via ``python -m scripts…``.
            "PYTHONPATH": str(install_root),
            "ORCHESTRATOR_SKILLS_DIR": str(skills_dir),
        },
    }
    try:
        mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        _write_codex_mcp_config(project_dest, servers)
        _write_cursor_mcp_config(project_dest, servers)
        _enable_claude_project_mcp(project_dest, servers)
    except OSError:
        return False
    return True


def _write_cursor_mcp_config(project_dest: Path, servers: dict) -> None:
    """Mirror project MCP servers into Cursor's project mcp.json."""
    cursor_path = project_dest / ".cursor" / "mcp.json"
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {"mcpServers": {}}
    if cursor_path.exists():
        try:
            payload = json.loads(cursor_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                existing = payload
        except json.JSONDecodeError:
            existing = {"mcpServers": {}}

    cursor_servers = existing.setdefault("mcpServers", {})
    if not isinstance(cursor_servers, dict):
        cursor_servers = {}
        existing["mcpServers"] = cursor_servers

    for name, config in servers.items():
        if isinstance(config, dict):
            cursor_servers[name] = _cursor_mcp_server_config(config)

    cursor_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def _cursor_mcp_server_config(config: dict) -> dict:
    """Forward Azure interactive session vars via Cursor ${env:NAME} interpolation."""
    args = config.get("args")
    if not isinstance(args, list) or not any(
        isinstance(arg, str) and arg.startswith("@azure-devops/mcp")
        for arg in args
    ):
        return dict(config)

    authentication = _mcp_authentication_arg(args)
    if authentication not in {None, "interactive"}:
        return dict(config)

    env = dict(config["env"]) if isinstance(config.get("env"), dict) else {}
    for name in _INTERACTIVE_AZURE_DEVOPS_ENV_VARS:
        env.setdefault(name, f"${{env:{name}}}")
    return {**config, "env": env}


def _enable_claude_project_mcp(project_dest: Path, servers: dict) -> None:
    """Approve project .mcp.json servers in Claude local settings (not VCS-tracked)."""
    settings_path = project_dest / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if settings_path.exists():
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                existing = payload
        except json.JSONDecodeError:
            existing = {}

    names = sorted(name for name, value in servers.items() if isinstance(value, dict))
    enabled = existing.get("enabledMcpjsonServers")
    if not isinstance(enabled, list):
        enabled = []
    merged = list(enabled)
    for name in names:
        if name not in merged:
            merged.append(name)

    existing["enableAllProjectMcpServers"] = True
    existing["enabledMcpjsonServers"] = merged
    settings_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def _write_codex_mcp_config(project_dest: Path, servers: dict) -> None:
    config_path = project_dest / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    server_names = {name for name, value in servers.items() if isinstance(value, dict)}
    base = _strip_codex_mcp_server_sections(existing, server_names).rstrip()
    rendered = "\n\n".join(
        _render_codex_mcp_server(name, _codex_mcp_server_config(config))
        for name, config in sorted(servers.items())
        if isinstance(config, dict)
    )
    content = "\n\n".join(part for part in (base, rendered) if part).rstrip() + "\n"
    config_path.write_text(content, encoding="utf-8")


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


def _render_codex_mcp_server(name: str, config: dict) -> str:
    lines = [f'[mcp_servers.{_toml_key(name)}]']
    for key in ("command", "url", "args", "env_vars", "cwd", "enabled", "required", "startup_timeout_sec", "tool_timeout_sec"):
        if key in config:
            lines.append(f"{key} = {_toml_value(config[key])}")
    env = config.get("env")
    if isinstance(env, dict) and env:
        lines.append("")
        lines.append(f'[mcp_servers.{_toml_key(name)}.env]')
        for key, value in sorted(env.items()):
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    return "\n".join(lines)


def _codex_mcp_server_config(config: dict) -> dict:
    """Forward the desktop session required by Azure interactive browser auth."""
    args = config.get("args")
    if not isinstance(args, list) or not any(
        isinstance(arg, str) and arg.startswith("@azure-devops/mcp")
        for arg in args
    ):
        return config

    authentication = _mcp_authentication_arg(args)
    if authentication not in {None, "interactive"}:
        return config

    env_vars = config.get("env_vars", [])
    if not isinstance(env_vars, list):
        return config

    forwarded = [
        *env_vars,
        *(name for name in _INTERACTIVE_AZURE_DEVOPS_ENV_VARS if name not in env_vars),
    ]
    return {**config, "env_vars": forwarded}


def _mcp_authentication_arg(args: list) -> str | None:
    for index, arg in enumerate(args[:-1]):
        if arg in {"--authentication", "-a"}:
            value = args[index + 1]
            return value if isinstance(value, str) else None
    return None


def _toml_key(value: str) -> str:
    if value.replace("_", "").replace("-", "").isalnum():
        return value
    return json.dumps(value)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json.dumps(str(value))


@contextmanager
def _install_import_path(install_dir: Path) -> Iterator[None]:
    """Prefer the installed tree for ``scripts.*`` imports, then restore.

    ``install.sh`` / bootstrap may run against a project runtime that is not the
    source checkout. Clear cached ``scripts`` modules so a prior import cannot
    shadow the installed copy. Always restore ``sys.path`` and prior modules so
    in-process callers (and the unittest suite) are not left pointing at a
    temporary install tree that may already be deleted.
    """
    install_root = str(Path(install_dir).resolve())
    inserted = install_root not in sys.path
    if inserted:
        sys.path.insert(0, install_root)
    saved = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "scripts" or name.startswith("scripts.")
    }
    try:
        yield
    finally:
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts."):
                del sys.modules[name]
        if inserted:
            while install_root in sys.path:
                sys.path.remove(install_root)
        sys.modules.update(saved)


def wire(install_dir: Path, target: str, project_dest: str | Path) -> int:
    """Wire hooks and discovery assets into a project. Global install is not supported."""
    with _install_import_path(install_dir):
        from scripts.installer.purge_markdown_allowlist import (  # noqa: PLC0415
            purge_allowlist_config_files,
        )
        from scripts.installer.cli import install  # noqa: PLC0415
        from scripts.installer.cursor_hooks import (  # noqa: PLC0415
            desired_cursor_hooks,
            merge_cursor_hooks,
            strip_managed_cursor_hooks,
        )
        from scripts.installer.targets import Target  # noqa: PLC0415

        dest_path = Path(project_dest).expanduser().resolve()
        purge_report = purge_allowlist_config_files(
            dest=dest_path,
            dry_run=False,
            include_cwd=False,
        )
        for message in purge_report.messages:
            print(message)

        client_names = {
            "claude": "Claude CLI (claude-cli) & IDE plugin",
            "gemini": "Gemini CLI (gemini) [Deprecated]",
            "codex": "Codex CLI (codex-cli) & IDE plugin",
            "antigravity": "Antigravity IDE",
            "antigravity-cli": "Antigravity CLI (antigravity-cli)",
            "cursor": "Cursor IDE",
        }

        if target == "all-agents":
            targets = [t.value for t in Target if t not in {Target.UNIVERSAL, Target.ALL_AGENTS}]
        else:
            targets = [target]

        successful_wirings: list[tuple[str, str, str | None]] = []
        skipped_wirings: list[tuple[str, str]] = []
        failed_wirings: list[tuple[str, str]] = []

        for t in targets:
            client_name = client_names.get(t, t)
            if t == "cursor":
                hook_command = f"python3 {install_dir / 'skills/codex_workflows/scripts/cursor_enforce_hook.py'}"
                config_path = dest_path / ".cursor" / "hooks.json"
                try:
                    on_disk = None
                    if config_path.exists():
                        on_disk = json.loads(config_path.read_text(encoding="utf-8"))
                    if on_disk:
                        on_disk = strip_managed_cursor_hooks(on_disk, _MANAGED_HOOK_SCRIPTS)
                    final_config = merge_cursor_hooks(on_disk, desired_cursor_hooks(hook_command))
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    config_path.write_text(json.dumps(final_config, indent=2) + "\n", encoding="utf-8")
                    successful_wirings.append((client_name, str(config_path), hook_command))
                except Exception as e:
                    failed_wirings.append((client_name, str(e)))
                continue

            try:
                result = install(t, dest_root=dest_path, plugin_root=install_dir)
                if result.config_paths:
                    config_path = dest_path / result.config_paths[0]
                    cmd = result.merged_config and _extract_command(result.merged_config)
                    successful_wirings.append((client_name, str(config_path), cmd))
                else:
                    skipped_wirings.append((client_name, "No config paths defined for target"))
            except Exception as e:
                failed_wirings.append((client_name, f"Exception: {e}"))

        print("\n" + "=" * 70)
        print("                      WIRING INSTALLATION SUMMARY                      ")
        print("=" * 70)

        if successful_wirings:
            print("Successfully Wired Clients:")
            for client, path, cmd in successful_wirings:
                print(f"  ✔ {client}")
                print(f"    Config file: {path}")
                if cmd:
                    print(f"    Hook command: {cmd}")
                print()

        if skipped_wirings:
            print("Skipped Clients:")
            for client, reason in skipped_wirings:
                print(f"  ✗ {client}")
                print(f"    Reason: {reason}")
                print()

        if failed_wirings:
            print("FAILED Clients:")
            for client, error_msg in failed_wirings:
                print(f"  🛑 {client}")
                print(f"     Error: {error_msg}")
                print()
            print("Error: Wiring failed for one or more requested clients.")
            print("=" * 70 + "\n")
            return 1

        if wire_orchestrator_mcp(install_dir, dest_path):
            print(f"Wired agentic-orchestrator MCP server → {dest_path / '.mcp.json'}")
            print(f"  Codex MCP mirror → {dest_path / '.codex' / 'config.toml'}")
            print(f"  Cursor MCP mirror → {dest_path / '.cursor' / 'mcp.json'}")
            print(f"  Claude MCP enablement → {dest_path / '.claude' / 'settings.local.json'}")
        else:
            print(
                f"Warning: Could not write agentic-orchestrator MCP config to {dest_path / '.mcp.json'}",
                file=sys.stderr,
            )

        if target == "all-agents" and not successful_wirings:
            print("Error: None of the agent clients could be successfully wired.", file=sys.stderr)
            print("=" * 70 + "\n")
            return 1

        print("Further Instructions:")
        print("  1. Restart your active CLI / IDE client session in this project.")
        print("  2. Claude discovers skills/commands under .claude/; Antigravity under .agents/skills/.")
        print("=" * 70 + "\n")
        return 0


def _extract_command(config: dict) -> str | None:
    """Pull the first hook command out of any supported config shape."""
    for section in ("hooks", "codex-enforcer"):
        block = config.get(section, {})
        for event_hooks in block.values():
            if isinstance(event_hooks, list):
                for entry in event_hooks:
                    if isinstance(entry, dict) and "command" in entry:
                        return entry["command"]
                    for hook in entry.get("hooks", []) if isinstance(entry, dict) else []:
                        if "command" in hook:
                            return hook["command"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install and wire codex-workflows-plugin into a project (local only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 -m scripts.installer.bootstrap --target all-agents --dest /my/project\n"
            "  python3 bootstrap.py plugin.zip --target all-agents --dest /my/project\n"
            "  python3 -m scripts.installer.bootstrap --uninstall --dest /my/project\n"
            "  python3 -m scripts.installer.bootstrap --purge-allowlist --dest /my/project --target all-agents\n"
        ),
    )
    parser.add_argument(
        "zip",
        nargs="?",
        help="Path to a release zip. Omit to install from the current source tree.",
    )
    parser.add_argument(
        "--install-dir",
        default=None,
        help="Runtime install path (default: <dest>/.codex-workflows).",
    )
    parser.add_argument(
        "--target",
        help="Agent host to wire: claude, codex, gemini, antigravity, cursor, all-agents.",
    )
    parser.add_argument(
        "--dest",
        help="Required project root for local install, wire, uninstall, and purge re-wire.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove project hooks, discovery assets, optional MCP entry, and runtime install dir.",
    )
    parser.add_argument(
        "--keep-runtime",
        action="store_true",
        help="With --uninstall, leave the runtime install dir in place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --uninstall or --purge-allowlist, print planned changes without modifying files.",
    )
    parser.add_argument(
        "--purge-allowlist",
        action="store_true",
        help=(
            "Scan/strip legacy markdown-allowlist artifacts under --dest. "
            "Pass --target to re-wire afterward."
        ),
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="With --purge-allowlist, only report findings (implies dry-run).",
    )
    args = parser.parse_args()

    if not args.dest:
        print(
            "error: --dest PROJECT is required (local/project install only; global install was removed).",
            file=sys.stderr,
        )
        return 1

    dest_path = Path(args.dest).expanduser().resolve()
    install_dir = (
        Path(args.install_dir).expanduser().resolve()
        if args.install_dir
        else default_install_dir(dest_path).resolve()
    )

    zip_path: Path | None = None
    if args.zip:
        zip_path = Path(args.zip).expanduser().resolve()
        if not zip_path.exists():
            print(f"error: zip not found: {zip_path}", file=sys.stderr)
            return 1

    # install.sh runs this file from a temp path with no package context. Install
    # the zip (when provided) before any ``scripts.*`` imports so uninstall/purge
    # and wire can resolve the installed tree.
    script_dir = Path(__file__).parent.parent.parent.resolve()
    is_running_from_install_dir = script_dir == install_dir
    installed_runtime = False

    if zip_path is not None and not args.uninstall:
        print(f"Installing {zip_path} → {install_dir} ...")
        install_from_zip(zip_path, install_dir)
        print(f"Installed to {install_dir}")
        installed_runtime = True
    elif zip_path is not None and args.uninstall and not (install_dir / "scripts").is_dir():
        # Need uninstall helpers from the zip when no prior project runtime exists.
        install_from_zip(zip_path, install_dir)
        installed_runtime = True

    import_path_cm = (
        _install_import_path(install_dir)
        if (install_dir / "scripts").is_dir()
        else nullcontext()
    )

    with import_path_cm:
        if args.uninstall:
            from scripts.installer.uninstall import uninstall  # noqa: PLC0415

            plan = uninstall(
                install_dir,
                dest=dest_path,
                keep_runtime=args.keep_runtime,
                dry_run=args.dry_run,
            )
            print("\n".join(plan.messages) if plan.messages else "No managed plugin interventions found.")
            return 0

        if args.purge_allowlist:
            from scripts.installer.purge_markdown_allowlist import (  # noqa: PLC0415
                purge_markdown_allowlist_artifacts,
                scan_markdown_allowlist_artifacts,
            )

            dry = args.dry_run or args.scan_only
            if args.scan_only:
                report = scan_markdown_allowlist_artifacts(dest=dest_path)
            else:
                report = purge_markdown_allowlist_artifacts(dest=dest_path, dry_run=dry)
            print("\n".join(report.messages) if report.messages else "No markdown-allowlist artifacts found.")
            if args.scan_only or dry or not args.target:
                return 0

        if not installed_runtime:
            if args.target and install_dir.exists() and is_running_from_install_dir:
                pass  # wire-only from already-installed tree
            else:
                source_root = Path(__file__).parent.parent.parent
                print(f"Installing from source → {install_dir} ...")
                install_from_source(source_root, install_dir)
                print(f"Installed to {install_dir}")

        if args.target:
            print(f"\nWiring {args.target} → {dest_path} ...")
            # Re-enter install import path after source install may have created scripts/.
            if not (install_dir / "scripts").is_dir():
                print(f"error: runtime scripts missing under {install_dir}", file=sys.stderr)
                return 1
            return wire(install_dir, args.target, dest_path)

        print("\n" + "=" * 70)
        print("                  INSTALLATION COMPLETED SUCCESSFULLY                  ")
        print("=" * 70)
        print(f"Runtime installed to: {install_dir}")
        print("To wire agent hosts in this project, run:")
        print(f"  python3 -m scripts.installer.bootstrap --target all-agents --dest {dest_path}")
        print("=" * 70 + "\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
