"""Install and wire codex-workflows-plugin in one command.

Usage
-----
From the release zip:
    python3 bootstrap.py codex-workflows-plugin-0.2.4.zip --target all-agents --dest /path/to/project

From source after cloning:
    python3 -m scripts.installer.bootstrap --target claude --dest /path/to/project

Install only (no wiring):
    python3 bootstrap.py codex-workflows-plugin-0.2.4.zip

Full cleanup:
    python3 -m scripts.installer.bootstrap --uninstall
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

INSTALL_DIR = Path.home() / ".codex-workflows"

# Script filenames that belong to this plugin — used to strip stale hook entries.
_MANAGED_HOOK_SCRIPTS = {
    "codex_enforce_hook.py",
    "gemini_enforce_hook.py",
    "antigravity_enforce_hook.py",
    "claude_enforce_hook.py",
    "cursor_enforce_hook.py",
}

_RUNTIME_DIRS = ["scripts", "skills", "commands", ".agent", "hooks", ".codex-plugin"]


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
    """Remove hook entries whose command references any of the given script filenames.

    Walks the entire config recursively so it handles both Gemini-style
    (``hooks.BeforeTool``) and Antigravity-style (``codex-enforcer.PreToolUse``) shapes.
    """
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


def register_claude_plugin(install_dir: Path) -> bool:
    """Install the plugin into ~/.claude/plugins/cache/ and register it.

    Copies the plugin's ``skills/`` tree into the Claude plugin cache so Claude
    Code can discover and load the skills, then adds/updates a ``@local`` entry
    in ``installed_plugins.json``.  Returns True on success.
    """
    manifest_path = install_dir / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        manifest_path = install_dir / "plugin.json"
    if not manifest_path.exists():
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("name", "codex-workflows-plugin")
    version = manifest.get("version", "unknown")

    # Copy into the Claude plugin cache under a "local" marketplace bucket.
    cache_dir = Path.home() / ".claude" / "plugins" / "cache" / "local" / name / version
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir)
        except OSError:
            return False
    try:
        cache_dir.mkdir(parents=True)
    except OSError:
        return False

    # Copy skills directory.
    src_skills = install_dir / "skills"
    if src_skills.is_dir():
        try:
            shutil.copytree(src_skills, cache_dir / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        except OSError:
            return False

    # Copy commands directory (user-invocable slash commands).
    src_commands = install_dir / "commands"
    if src_commands.is_dir():
        try:
            shutil.copytree(src_commands, cache_dir / "commands", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        except OSError:
            return False

    src_scripts = install_dir / "scripts"
    if src_scripts.is_dir():
        try:
            shutil.copytree(src_scripts, cache_dir / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        except OSError:
            return False

    # Write a minimal plugin.json (no extra fields) matching the format Claude expects.
    clean_manifest = {k: manifest[k] for k in ("name", "description", "version", "author") if k in manifest}
    try:
        (cache_dir / "plugin.json").write_text(json.dumps(clean_manifest, indent=2), encoding="utf-8")
    except OSError:
        return False

    registry_path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    registry: dict = {"version": 2, "plugins": {}}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    plugin_key = f"{name}@local"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
    existing_entries = registry.setdefault("plugins", {}).get(plugin_key, [])
    installed_at = existing_entries[0].get("installedAt", now) if existing_entries else now

    registry["plugins"][plugin_key] = [{
        "scope": "user",
        "installPath": str(cache_dir),
        "version": version,
        "installedAt": installed_at,
        "lastUpdated": now,
    }]

    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def register_antigravity_plugin(install_dir: Path) -> bool:
    """Install the plugin into ~/.gemini/antigravity-ide/plugins/ for the Antigravity IDE.

    The Antigravity IDE discovers plugins by scanning that directory directly —
    there is no installed_plugins.json. Each subdirectory must contain a minimal
    ``plugin.json`` (name, description, disabled) and a ``skills/`` tree.
    Returns True if the IDE plugins directory exists and registration succeeded.
    """
    ide_plugins_dir = Path.home() / ".gemini" / "antigravity-ide" / "plugins"
    if not ide_plugins_dir.is_dir():
        return False

    manifest_path = install_dir / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        manifest_path = install_dir / "plugin.json"
    if not manifest_path.exists():
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("name", "codex-workflows-plugin")
    author = manifest.get("author", {}).get("name", "local") if isinstance(manifest.get("author"), dict) else "local"
    description = manifest.get("description", "")

    # Naming convention mirrors existing IDE plugins: Author.pluginName.pluginName
    plugin_dir = ide_plugins_dir / f"{author}.{name}.{name}"
    if plugin_dir.exists():
        try:
            shutil.rmtree(plugin_dir)
        except OSError:
            return False
    try:
        plugin_dir.mkdir(parents=True)
    except OSError:
        return False

    src_skills = install_dir / "skills"
    if src_skills.is_dir():
        try:
            shutil.copytree(src_skills, plugin_dir / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        except OSError:
            return False

    ide_manifest = {"name": name, "description": description, "disabled": False}
    try:
        (plugin_dir / "plugin.json").write_text(json.dumps(ide_manifest), encoding="utf-8")
    except OSError:
        return False
    return True


def register_antigravity_config_plugin(install_dir: Path) -> bool:
    """Install the plugin into ~/.gemini/config/plugins/ (Antigravity user-global plugin layer).

    This layer is shared across all Antigravity surfaces (IDE, CLI). Format mirrors
    the android-cli-plugin reference: plugin.json (fuller schema), installed_version.json,
    and skills/. Returns True if the directory exists and registration succeeded.
    """
    config_plugins_dir = Path.home() / ".gemini" / "config" / "plugins"
    if not config_plugins_dir.is_dir():
        return False

    manifest_path = install_dir / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        manifest_path = install_dir / "plugin.json"
    if not manifest_path.exists():
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("name", "codex-workflows-plugin")
    version = manifest.get("version", "unknown")

    plugin_dir = config_plugins_dir / name
    if plugin_dir.is_symlink():
        try:
            plugin_dir.unlink()
        except OSError:
            return False
    elif plugin_dir.exists():
        try:
            shutil.rmtree(plugin_dir)
        except OSError:
            return False
    try:
        plugin_dir.mkdir(parents=True)
    except OSError:
        return False

    src_skills = install_dir / "skills"
    if src_skills.is_dir():
        try:
            shutil.copytree(src_skills, plugin_dir / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        except OSError:
            return False

    # Full plugin.json matching the android-cli-plugin schema (name, version, description, author).
    clean_manifest = {k: manifest[k] for k in ("name", "version", "description", "author") if k in manifest}
    try:
        (plugin_dir / "plugin.json").write_text(json.dumps(clean_manifest, indent=2), encoding="utf-8")
        (plugin_dir / "installed_version.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    except OSError:
        return False
    return True


def register_codex_plugin(install_dir: Path) -> bool:
    """Register the plugin in ~/.agents/plugins/marketplace.json for Codex discovery.

    Codex discovers the personal marketplace at that path implicitly — no
    ``codex plugin marketplace add`` needed. After this function runs the user
    must run ``codex plugin add <name>@personal`` once to pull the plugin into
    Codex's cache. Returns True if marketplace.json was written successfully.
    """
    codex_manifest = install_dir / ".codex-plugin" / "plugin.json"
    if not codex_manifest.exists():
        return False

    manifest = json.loads(codex_manifest.read_text(encoding="utf-8"))
    name = manifest.get("name", "codex-workflows-plugin")
    category = manifest.get("interface", {}).get("category", "Productivity")

    marketplace_path = Path.home() / ".agents" / "plugins" / "marketplace.json"
    try:
        marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    if marketplace_path.exists():
        try:
            marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            marketplace = {}
    else:
        marketplace = {}

    marketplace.setdefault("name", "personal")
    marketplace.setdefault("interface", {"displayName": "Personal"})
    marketplace.setdefault("plugins", [])

    # Replace any stale entry for this plugin.
    marketplace["plugins"] = [p for p in marketplace["plugins"] if p.get("name") != name]
    marketplace["plugins"].append({
        "name": name,
        "source": {"source": "local", "path": str(install_dir)},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": category,
    })

    try:
        marketplace_path.write_text(json.dumps(marketplace, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def wire_orchestrator_mcp(install_dir: Path, project_dest: Path) -> bool:
    """Merge the agentic-orchestrator MCP server into a project's .mcp.json."""
    mcp_path = project_dest / ".mcp.json"
    existing: dict = {"mcpServers": {}}
    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {"mcpServers": {}}

    servers = existing.setdefault("mcpServers", {})
    skills_dir = (install_dir / "skills").resolve()
    servers["agentic-orchestrator"] = {
        "command": "python3",
        "args": ["-m", "scripts.orchestrator.mcp_server"],
        "env": {
            "PYTHONPATH": str(install_dir.resolve()),
            "ORCHESTRATOR_SKILLS_DIR": str(skills_dir),
        },
    }

    try:
        mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def wire(install_dir: Path, target: str, project_dest: str | None) -> int:
    """Run the hook-wiring installer from the installed location.

    When project_dest is None the installer writes to each host's machine-global
    config location (e.g. ~/.claude/settings.json, ~/Antigravity_IDE/.agents/hooks.json).
    When project_dest is given, it writes project-level hook configs under that path.

    Always purges legacy markdown-allowlist config files first so leftover
    marketplace companions cannot keep blocking agent markdown access.
    """
    from scripts.installer.purge_markdown_allowlist import (  # noqa: PLC0415
        purge_allowlist_config_files,
    )

    dest_path = Path(project_dest).expanduser().resolve() if project_dest else None
    purge_report = purge_allowlist_config_files(
        dest=dest_path,
        dry_run=False,
        include_cwd=True,
    )
    for message in purge_report.messages:
        print(message)

    # Load the installed cli module with its plugin_root resolved to install_dir.
    if str(install_dir) not in sys.path:
        sys.path.insert(0, str(install_dir))

    # Force a fresh load from the installed location regardless of cached modules.
    for mod_name in list(sys.modules):
        if mod_name.startswith("scripts.installer") or mod_name == "scripts":
            del sys.modules[mod_name]

    from scripts.installer.cli import install  # noqa: PLC0415
    from scripts.installer.cursor_hooks import (  # noqa: PLC0415
        desired_cursor_hooks,
        merge_cursor_hooks,
        strip_managed_cursor_hooks,
    )
    from scripts.installer.merge import merge_hook_configs  # noqa: PLC0415
    from scripts.installer.targets import Target, target_global_config_path  # noqa: PLC0415

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

    successful_wirings = []
    skipped_wirings = []
    failed_wirings = []

    for t in targets:
        client_name = client_names.get(t, t)
        if t == "cursor":
            hook_command = f"python3 {install_dir / 'skills/codex_workflows/scripts/cursor_enforce_hook.py'}"
            if project_dest is not None:
                config_path = Path(project_dest) / ".cursor" / "hooks.json"
            else:
                config_path = target_global_config_path(t)
            if config_path is None:
                failed_wirings.append((client_name, "Could not locate the Cursor hooks configuration path."))
                continue
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

        if project_dest is not None:
            # Local project install
            try:
                result = install(t, dest_root=project_dest, plugin_root=install_dir)
                if result.config_paths:
                    config_path = Path(project_dest) / result.config_paths[0]
                    cmd = result.merged_config and _extract_command(result.merged_config)
                    successful_wirings.append((client_name, str(config_path), cmd))
                else:
                    skipped_wirings.append((client_name, "No config paths defined for target"))
            except Exception as e:
                failed_wirings.append((client_name, f"Exception: {e}"))
        else:
            # Global machine install
            global_path = target_global_config_path(t)
            if global_path is None:
                if target != "all-agents":
                    failed_wirings.append((client_name, "Could not locate the global configuration path for this client."))
                elif t == "antigravity":
                    skipped_wirings.append(
                        (
                            client_name,
                            "Antigravity IDE install directory not found (optional; plugin assets were still registered under ~/.gemini/antigravity-ide/plugins/)",
                        )
                    )
                else:
                    skipped_wirings.append((client_name, "Client installation/directory not found on this machine"))
                continue

            if not global_path.parent.is_dir() and not global_path.exists():
                if target != "all-agents":
                    failed_wirings.append((client_name, f"Configuration directory '{global_path.parent}' does not exist."))
                elif t == "antigravity":
                    skipped_wirings.append(
                        (
                            client_name,
                            "Antigravity IDE install directory not found (optional; plugin assets were still registered under ~/.gemini/antigravity-ide/plugins/)",
                        )
                    )
                else:
                    skipped_wirings.append((client_name, f"Configuration directory '{global_path.parent}' does not exist."))
                continue

            try:
                # Compute desired config then write to the known global path.
                result = install(t, plugin_root=install_dir)  # dry-run to get merged_config
                on_disk = None
                if global_path.exists():
                    try:
                        on_disk = json.loads(global_path.read_text(encoding="utf-8"))
                    except Exception as parse_err:
                        raise ValueError(f"Existing configuration file contains invalid JSON: {parse_err}")

                # Strip stale entries from previous installs before merging.
                if on_disk:
                    on_disk = strip_managed_hooks(on_disk, _MANAGED_HOOK_SCRIPTS)

                final_config = merge_hook_configs(on_disk, result.merged_config)
                global_path.parent.mkdir(parents=True, exist_ok=True)
                global_path.write_text(json.dumps(final_config, indent=2), encoding="utf-8")
                
                cmd = _extract_command(final_config)
                successful_wirings.append((client_name, str(global_path), cmd))
            except Exception as e:
                failed_wirings.append((client_name, str(e)))

    # Print a beautiful summary of the wiring status
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
        print("Skipped Clients (not configured or missing):")
        for client, reason in skipped_wirings:
            print(f"  ✗ {client}")
            print(f"    Reason: {reason}")
            print()

    if failed_wirings:
        print("FAILED Clients (wiring encountered errors):")
        for client, error_msg in failed_wirings:
            print(f"  🛑 {client}")
            print(f"     Error: {error_msg}")
            print()

    # Further instructions or error exit
    if failed_wirings:
        print("Error: Wiring failed for one or more requested clients.")
        print("Please check the errors listed above and resolve them.")
        print("=" * 70 + "\n")
        return 1

    if project_dest is not None:
        dest_path = Path(project_dest)
        if wire_orchestrator_mcp(install_dir, dest_path):
            print(f"Wired agentic-orchestrator MCP server → {dest_path / '.mcp.json'}")
        else:
            print(
                f"Warning: Could not write agentic-orchestrator MCP config to {dest_path / '.mcp.json'}",
                file=sys.stderr,
            )

    # If --target all-agents was specified, but we could not wire anything, exit with an error.
    if target == "all-agents" and not successful_wirings:
        print("Error: None of the agent CLI clients could be successfully wired.", file=sys.stderr)
        print("We checked the global configuration paths but none of the CLI/IDE installs were detected.", file=sys.stderr)
        print("Please check your installations or install clients (e.g. Claude Code or Gemini CLI) first.", file=sys.stderr)
        print("=" * 70 + "\n")
        return 1

    print("Further Instructions:")
    print("  1. Restart your active CLI / IDE client session to load the new hooks.")
    print("  2. To wire a local project with workflows and rules guides, run:")
    print(f"     python3 -m scripts.installer.bootstrap --target all-agents --dest /path/to/project")
    print("  3. To scaffold ticket drafts and generate YouTrack registration payloads:")
    print("     python3 scripts/create_ticket.py --summary \"Your ticket title\"")
    print("=" * 70 + "\n")

    return 0


def _extract_command(config: dict) -> str | None:
    """Pull the first hook command out of any supported config shape."""
    for section in ("hooks", "codex-enforcer"):
        block = config.get(section, {})
        for event_hooks in block.values():
            if isinstance(event_hooks, list):
                for entry in event_hooks:
                    for hook in entry.get("hooks", []):
                        if "command" in hook:
                            return hook["command"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install and wire codex-workflows-plugin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  # install + wire in one step\n"
            "  python3 bootstrap.py plugin.zip --target all-agents --dest /my/project\n\n"
            "  # install only\n"
            "  python3 bootstrap.py plugin.zip\n\n"
            "  # wire only (plugin already installed)\n"
            "  python3 bootstrap.py --target claude --dest /my/project\n\n"
            "  # scan/purge legacy markdown-allowlist hooks and configs\n"
            "  python3 -m scripts.installer.bootstrap --purge-allowlist --scan-only\n"
            "  python3 -m scripts.installer.bootstrap --purge-allowlist --target all-agents\n\n"
            "  # uninstall and remove runtime\n"
            "  python3 -m scripts.installer.bootstrap --uninstall"
        ),
    )
    parser.add_argument(
        "zip",
        nargs="?",
        help="Path to a release zip. Omit to install from the current source tree.",
    )
    parser.add_argument(
        "--install-dir",
        default=str(INSTALL_DIR),
        help=f"Where to install the plugin (default: {INSTALL_DIR})",
    )
    parser.add_argument(
        "--target",
        help="Agent host to wire: claude, codex, gemini, antigravity, cursor, all-agents.",
    )
    parser.add_argument(
        "--dest",
        help="Target project root to wire hooks into.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove managed host hooks, plugin registrations/caches, optional project assets, and the runtime install dir.",
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
            "Scan host configs for managed enforce hooks and delete legacy "
            "markdown-allowlist config (codex-workflow.config.json). "
            "Strips managed hook entries; pass --target to re-wire current hooks afterward."
        ),
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="With --purge-allowlist, only report findings (implies dry-run).",
    )
    args = parser.parse_args()

    # --dest is optional: omitting it wires the host's machine-global config location.

    install_dir = Path(args.install_dir).expanduser().resolve()

    if args.uninstall:
        from scripts.installer.uninstall import uninstall  # noqa: PLC0415

        plan = uninstall(
            install_dir,
            dest=Path(args.dest) if args.dest else None,
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

        dest_path = Path(args.dest).expanduser().resolve() if args.dest else None
        dry = args.dry_run or args.scan_only
        if args.scan_only:
            report = scan_markdown_allowlist_artifacts(dest=dest_path)
        else:
            report = purge_markdown_allowlist_artifacts(dest=dest_path, dry_run=dry)
        print("\n".join(report.messages) if report.messages else "No markdown-allowlist artifacts found.")
        if args.scan_only or dry or not args.target:
            return 0
        # Fall through to install/wire with --target after purge.

    # ── install step ──────────────────────────────────────────────────────────
    script_dir = Path(__file__).parent.parent.parent.resolve()
    is_running_from_install_dir = (script_dir == install_dir)

    if args.zip:
        zip_path = Path(args.zip).expanduser().resolve()
        if not zip_path.exists():
            print(f"error: zip not found: {zip_path}", file=sys.stderr)
            return 1
        print(f"Installing {zip_path} → {install_dir} ...")
        install_from_zip(zip_path, install_dir)
        print(f"Installed to {install_dir}")
    elif args.target and install_dir.exists() and is_running_from_install_dir:
        pass  # wire-only: skip install
    else:
        source_root = Path(__file__).parent.parent.parent
        print(f"Installing from source → {install_dir} ...")
        install_from_source(source_root, install_dir)
        print(f"Installed to {install_dir}")

    # ── plugin registration step ──────────────────────────────────────────────
    if register_claude_plugin(install_dir):
        print(f"Registered plugin with Claude Code        → {Path.home() / '.claude' / 'plugins' / 'cache' / 'local'}")
    else:
        print("Warning: Could not register plugin with Claude Code", file=sys.stderr)
    if register_antigravity_plugin(install_dir):
        print(f"Registered plugin with Antigravity IDE    → {Path.home() / '.gemini' / 'antigravity-ide' / 'plugins'}")
    if register_antigravity_config_plugin(install_dir):
        print(f"Registered plugin with Antigravity global → {Path.home() / '.gemini' / 'config' / 'plugins'}")
    if register_codex_plugin(install_dir):
        print(f"Registered plugin in Codex marketplace    → {Path.home() / '.agents' / 'plugins' / 'marketplace.json'}")
        print(f"  ⚠  Run once to activate Codex skills:  codex plugin add codex-workflows-plugin@personal")
    else:
        print("Warning: Could not register plugin in Codex marketplace", file=sys.stderr)

    # ── wire step ─────────────────────────────────────────────────────────────
    if args.target:
        dest_label = args.dest or "global config"
        print(f"\nWiring {args.target} → {dest_label} ...")
        return wire(install_dir, args.target, args.dest)
    else:
        # Better help message if no target is specified
        print("\n" + "=" * 70)
        print("                  INSTALLATION COMPLETED SUCCESSFULLY                  ")
        print("=" * 70)
        print(f"The plugin runtime assets have been installed to:")
        print(f"  {install_dir}")
        print()
        print("To wire the plugin to your agent hosts, run:")
        print(f"  python3 -m scripts.installer.bootstrap --target all-agents")
        print()
        print("To wire a specific local project repository (with rules and guides):")
        print(f"  python3 -m scripts.installer.bootstrap --target all-agents --dest /path/to/project")
        print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
