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
import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path

_MANAGED_HOOK_MARKERS = (
    "codex-workflows-plugin",
    "codex_workflows",
    "workflow-integrations",
)

_RUNTIME_DIRS = ["scripts", "skills", "commands"]

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
    preserved = _preserve_project_config(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    _restore_project_config(dest, preserved)


def install_from_source(source_root: Path, dest: Path) -> None:
    """Copy runtime directories from source_root to dest."""
    preserved = _preserve_project_config(dest)
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
    _restore_project_config(dest, preserved)


def _preserve_project_config(dest: Path) -> str | None:
    """Keep project integration choices while replacing managed runtime files."""
    path = dest / "integrations.json"
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else None
    except OSError:
        return None


def _restore_project_config(dest: Path, content: str | None) -> None:
    if content is None:
        return
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "integrations.json").write_text(content, encoding="utf-8")


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
                    h
                    for h in entry["hooks"]
                    if not any(s in h.get("command", "") for s in script_names)
                ]
                if fresh_hooks:
                    cleaned.append({**entry, "hooks": fresh_hooks})
            result[key] = cleaned
        else:
            result[key] = value
    return result


def wire_orchestrator_mcp(install_dir: Path, project_dest: Path) -> bool:
    """Wire the unchanged orchestrator and the separate integration gateway."""
    mcp_path = project_dest / ".mcp.json"
    existing: dict = {"mcpServers": {}}
    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {"mcpServers": {}}

    servers = existing.setdefault("mcpServers", {})
    install_root = install_dir.resolve()
    skills_dir = install_root / "skills"
    launcher = install_root / "scripts" / "orchestrator" / "run_mcp_server.py"
    gateway_launcher = install_root / "scripts" / "integrations" / "run_gateway.py"
    servers["agentic-orchestrator"] = {
        "command": "python3",
        "args": [str(launcher)],
        "env": {
            # Kept for hosts/tools that still import via ``python -m scripts…``.
            "PYTHONPATH": str(install_root),
            "ORCHESTRATOR_SKILLS_DIR": str(skills_dir),
        },
    }
    servers["workflow-integrations"] = {
        "command": "python3",
        "args": [str(gateway_launcher)],
        "env": {
            "PYTHONPATH": str(install_root),
            "CODEX_PROJECT_ROOT": str(project_dest.resolve()),
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


def configure_integrations(
    project_dest: Path,
    *,
    tracker: str,
    scm: str,
    branch_template: str,
    tracker_scope: str = "auto",
    config_source: Path | None = None,
    discover: bool = True,
    confirm_mappings: dict | None = None,
    runtime_dir: Path | None = None,
) -> Path:
    """Write provider-neutral setup while keeping provider details adapter-owned."""
    from scripts.integrations.discovery import (
        apply_discovery_to_config,
        discover_provider_capabilities,
        mapping_presets,
    )

    if config_source is not None:
        payload = json.loads(config_source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("integration config must be a JSON object")
        if (
            payload.get("schemaVersion") != 1
            or not isinstance(payload.get("branchTemplate"), str)
            or "{key}" not in payload["branchTemplate"]
        ):
            raise ValueError(
                "integration config must declare schemaVersion 1 and branchTemplate containing {key}"
            )
        if not isinstance(payload.get("tracker"), dict) or not payload["tracker"].get(
            "adapter"
        ):
            raise ValueError("integration config tracker.adapter is required")
        if not isinstance(payload.get("scm"), dict) or not payload["scm"].get(
            "adapter"
        ):
            raise ValueError("integration config scm.adapter is required")
    else:
        if "{key}" not in branch_template:
            raise ValueError("branch template must contain {key}")
        tracker_config = _default_tracker_config(
            tracker, tracker_scope, project_dest, runtime_dir
        )
        tracker_config["branchPattern"] = branch_template
        payload = {
            "schemaVersion": 1,
            "branchTemplate": branch_template,
            "tracker": tracker_config,
            "scm": _default_scm_config(scm, project_dest),
        }

    payload = _with_local_tracker_transport(
        payload, project_dest=project_dest, runtime_dir=runtime_dir
    )

    tracker_cfg = payload["tracker"]
    scm_cfg = payload["scm"]
    tracker_discovery = None
    scm_discovery = None
    discovery_errors: list[str] = []
    if discover:
        try:
            tracker_discovery = discover_provider_capabilities(
                kind="tracker",
                adapter=str(tracker_cfg.get("adapter")),
                connection=tracker_cfg.get("connection") or {},
                preferred_bindings=tracker_cfg.get("bindings") or {},
            )
        except Exception as exc:
            discovery_errors.append(f"tracker discovery failed: {exc}")
            tracker_discovery = None
        try:
            scm_discovery = discover_provider_capabilities(
                kind="scm",
                adapter=str(scm_cfg.get("adapter")),
                connection=scm_cfg.get("connection") or {},
                preferred_bindings=scm_cfg.get("bindings") or {},
            )
        except Exception as exc:
            discovery_errors.append(f"scm discovery failed: {exc}")
            scm_discovery = None
        if tracker_discovery is not None or scm_discovery is not None:
            payload = apply_discovery_to_config(
                payload,
                tracker_discovery=tracker_discovery,
                scm_discovery=scm_discovery,
            )
        if discovery_errors:
            payload = dict(payload)
            payload["discoveryErrors"] = discovery_errors
            print(
                "WARNING: provider capability discovery did not fully succeed:\n  - "
                + "\n  - ".join(discovery_errors),
                file=sys.stderr,
            )
    else:
        presets = mapping_presets(str(tracker_cfg.get("adapter")))
        tracker_cfg = dict(tracker_cfg)
        if not (tracker_cfg.get("mappings") or {}).get("kinds"):
            tracker_cfg["mappings"] = presets
        payload["tracker"] = tracker_cfg

    if confirm_mappings is not None:
        tracker_cfg = dict(payload["tracker"])
        tracker_cfg["mappings"] = confirm_mappings
        payload["tracker"] = tracker_cfg

    path = project_dest / ".codex-workflows" / "integrations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if payload["tracker"].get("adapter") == "local_tracker":
        _initialize_local_tracker(project_dest, payload["tracker"])
    return path


def _default_tracker_config(
    provider: str,
    scope: str,
    project_dest: Path | None = None,
    runtime_dir: Path | None = None,
) -> dict:
    from scripts.integrations.discovery import mapping_presets

    presets = mapping_presets(provider)
    if provider == "linear":
        return {
            "adapter": "linear",
            "scope": scope,
            "connection": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            },
            "mappings": presets,
            "bindings": {
                "get_work_item": "get_issue",
                "search_work_items": "list_issues",
                "create_work_item": "save_issue",
                "list_children": "list_issues",
                "transition_work_item": "save_issue",
                "publish_artifact": "save_comment",
                "list_artifacts": "list_comments",
                "link_development_artifact": "save_comment",
            },
        }
    if provider == "azure_devops":
        return {
            "adapter": "azure_devops",
            "scope": scope,
            "connection": {
                "command": "npx",
                "args": [
                    "-y",
                    "@azure-devops/mcp",
                    _azure_org_arg(project_dest),
                    "-d",
                    "core",
                    "work-items",
                    "repositories",
                ],
            },
            "mappings": presets,
            "bindings": {
                "get_work_item": "wit_get_work_item",
                "search_work_items": "wit_query_by_wiql",
                "create_work_item": "wit_create_work_item",
                "list_children": "wit_get_work_items",
                "transition_work_item": "wit_update_work_item",
                "publish_artifact": "wit_add_work_item_comment",
                "list_artifacts": "wit_get_work_item_comments",
                "link_development_artifact": "wit_add_artifact_link",
            },
        }
    if provider == "local_tracker":
        return {
            "adapter": "local_tracker",
            "root": ".local-tracker",
            "storagePolicy": "committed",
            "connection": _local_tracker_connection(
                project_dest or Path.cwd(), runtime_dir, ".local-tracker"
            ),
            "mappings": presets,
            "bindings": _local_tracker_bindings(),
        }
    raise ValueError(f"unsupported tracker: {provider}")


def _with_local_tracker_transport(
    payload: dict, *, project_dest: Path, runtime_dir: Path | None = None
) -> dict:
    tracker = payload.get("tracker")
    if not isinstance(tracker, dict) or tracker.get("adapter") != "local_tracker":
        return payload
    tracker = dict(tracker)
    root = str(tracker.get("root") or ".local-tracker")
    tracker.setdefault(
        "connection", _local_tracker_connection(project_dest, runtime_dir, root)
    )
    tracker["bindings"] = {
        **_local_tracker_bindings(),
        **(tracker.get("bindings") or {}),
    }
    result = dict(payload)
    result["tracker"] = tracker
    return result


def _local_tracker_connection(
    project_dest: Path, runtime_dir: Path | None, root: str
) -> dict:
    runtime = (runtime_dir or default_install_dir(project_dest)).resolve()
    return {
        "command": "python3",
        "args": [
            str(runtime / "scripts" / "integrations" / "run_local_tracker.py"),
            "--project-root",
            str(project_dest.resolve()),
            "--root",
            root,
        ],
    }


def _local_tracker_bindings() -> dict[str, str]:
    from scripts.integrations.local_tracker import LOCAL_TRACKER_BINDINGS

    return dict(LOCAL_TRACKER_BINDINGS)


def _initialize_local_tracker(project_dest: Path, tracker: dict) -> None:
    root = project_dest / str(tracker.get("root") or ".local-tracker")
    root.mkdir(parents=True, exist_ok=True)
    for state in ("backlog", "ready", "in_progress", "done", "canceled", "artifacts"):
        (root / state).mkdir(exist_ok=True)
    _set_local_tracker_ignore(
        project_dest, str(tracker.get("storagePolicy") or "committed") == "ignored"
    )


def _set_local_tracker_ignore(project_dest: Path, ignored: bool) -> None:
    path = project_dest / ".gitignore"
    start = "# codex-workflows-plugin local tracker (managed)"
    entry = ".local-tracker/"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = existing.splitlines()
    filtered: list[str] = []
    skip_next = False
    for line in lines:
        if line == start:
            skip_next = True
            continue
        if skip_next and line == entry:
            skip_next = False
            continue
        skip_next = False
        filtered.append(line)
    if ignored:
        if filtered and filtered[-1]:
            filtered.append("")
        filtered.extend((start, entry))
    content = "\n".join(filtered).rstrip() + "\n" if filtered else ""
    if content or path.exists():
        path.write_text(content, encoding="utf-8")


def _default_scm_config(provider: str, project_dest: Path) -> dict:
    if provider == "github":
        owner, repo = _github_remote(project_dest)
        return {
            "adapter": "github",
            "owner": owner,
            "repo": repo,
            "connection": {"command": "gh", "args": []},
            "bindings": {},
        }
    if provider == "azure_repos":
        org, project, repo = _azure_remote(project_dest)
        return {
            "adapter": "azure_repos",
            "organization": org,
            "project": project,
            "repository": repo,
            "connection": {
                "command": "npx",
                "args": [
                    "-y",
                    "@azure-devops/mcp",
                    _azure_org_arg(project_dest, fallback=org),
                    "-d",
                    "core",
                    "repositories",
                    "work-items",
                ],
            },
            "bindings": {
                "get_pull_request": "repo_get_pull_request_by_id",
                "create_pull_request": "repo_create_pull_request",
                "list_review_threads": "repo_list_pull_request_threads",
                "reply_to_thread": "repo_reply_to_comment",
                "link_work_item": "wit_link_work_item_to_pull_request",
            },
        }
    raise ValueError(f"unsupported SCM: {provider}")


def _azure_org_arg(project_dest: Path | None = None, *, fallback: str = "") -> str:
    """Resolve Azure org for MCP argv; expandvars still applies at client spawn."""
    env_org = os.environ.get("AZURE_DEVOPS_ORG", "").strip()
    if env_org:
        return env_org
    if fallback.strip():
        return fallback.strip()
    if project_dest is not None:
        org, _, _ = _azure_remote(project_dest)
        if org:
            return org
    return "${AZURE_DEVOPS_ORG}"


def _github_remote(project_dest: Path) -> tuple[str, str]:
    try:
        remote = subprocess.run(
            ["git", "-C", str(project_dest), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "", ""
    value = remote.removesuffix(".git")
    if "github.com" not in value:
        return "", value.rsplit("/", 1)[-1]
    tail = value.split("github.com", 1)[-1].lstrip(":/")
    parts = tail.split("/")
    return (
        (parts[-2], parts[-1]) if len(parts) >= 2 else ("", parts[-1] if parts else "")
    )


def _azure_remote(project_dest: Path) -> tuple[str, str, str]:
    try:
        remote = subprocess.run(
            ["git", "-C", str(project_dest), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "", "", ""
    value = remote.removesuffix(".git")
    if "dev.azure.com" in value:
        tail = value.split("dev.azure.com", 1)[-1].lstrip(":/")
        parts = [part for part in tail.split("/") if part and part != "_git"]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
    if "visualstudio.com" in value:
        host = value.split("://", 1)[-1]
        org = host.split(".visualstudio.com", 1)[0]
        tail = value.split(".visualstudio.com", 1)[-1].lstrip(":/")
        parts = [part for part in tail.split("/") if part and part != "_git"]
        if len(parts) >= 2:
            return org, parts[0], parts[1]
    return "", "", value.rsplit("/", 1)[-1]


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
        isinstance(arg, str) and arg.startswith("@azure-devops/mcp") for arg in args
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
    if (
        stripped.startswith("[[")
        or not stripped.startswith("[")
        or not stripped.endswith("]")
    ):
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
    lines = [f"[mcp_servers.{_toml_key(name)}]"]
    for key in (
        "command",
        "url",
        "args",
        "env_vars",
        "cwd",
        "enabled",
        "required",
        "startup_timeout_sec",
        "tool_timeout_sec",
    ):
        if key in config:
            lines.append(f"{key} = {_toml_value(config[key])}")
    env = config.get("env")
    if isinstance(env, dict) and env:
        lines.append("")
        lines.append(f"[mcp_servers.{_toml_key(name)}.env]")
        for key, value in sorted(env.items()):
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    return "\n".join(lines)


def _codex_mcp_server_config(config: dict) -> dict:
    """Forward the desktop session required by Azure interactive browser auth."""
    args = config.get("args")
    if not isinstance(args, list) or not any(
        isinstance(arg, str) and arg.startswith("@azure-devops/mcp") for arg in args
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
        from scripts.installer.cli import install
        from scripts.installer.cursor_hooks import (
            desired_cursor_hooks,
            merge_cursor_hooks,
            strip_managed_cursor_hooks,
        )
        from scripts.installer.targets import Target

        dest_path = Path(project_dest).expanduser().resolve()
        client_names = {
            "claude": "Claude CLI (claude-cli) & IDE plugin",
            "gemini": "Gemini CLI (gemini) [Deprecated]",
            "codex": "Codex CLI (codex-cli) & IDE plugin",
            "antigravity": "Antigravity IDE",
            "antigravity-cli": "Antigravity CLI (antigravity-cli)",
            "cursor": "Cursor IDE",
        }

        if target == "all-agents":
            targets = [
                t.value
                for t in Target
                if t not in {Target.UNIVERSAL, Target.ALL_AGENTS}
            ]
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
                        on_disk = strip_managed_cursor_hooks(
                            on_disk, set(_MANAGED_HOOK_MARKERS)
                        )
                    final_config = merge_cursor_hooks(
                        on_disk, desired_cursor_hooks(hook_command)
                    )
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    config_path.write_text(
                        json.dumps(final_config, indent=2) + "\n", encoding="utf-8"
                    )
                    successful_wirings.append(
                        (client_name, str(config_path), hook_command)
                    )
                except Exception as e:
                    failed_wirings.append((client_name, str(e)))
                continue

            try:
                result = install(t, dest_root=dest_path, plugin_root=install_dir)
                if result.config_paths:
                    config_path = dest_path / result.config_paths[0]
                    cmd = result.merged_config and _extract_command(
                        result.merged_config
                    )
                    successful_wirings.append((client_name, str(config_path), cmd))
                else:
                    skipped_wirings.append(
                        (client_name, "No config paths defined for target")
                    )
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
            print(
                f"  Claude MCP enablement → {dest_path / '.claude' / 'settings.local.json'}"
            )
        else:
            print(
                f"Warning: Could not write agentic-orchestrator MCP config to {dest_path / '.mcp.json'}",
                file=sys.stderr,
            )

        if target == "all-agents" and not successful_wirings:
            print(
                "Error: None of the agent clients could be successfully wired.",
                file=sys.stderr,
            )
            print("=" * 70 + "\n")
            return 1

        print("Further Instructions:")
        print("  1. Restart your active CLI / IDE client session in this project.")
        print(
            "  2. Claude discovers skills/commands under .claude/; Antigravity under .agents/skills/."
        )
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
                    for hook in (
                        entry.get("hooks", []) if isinstance(entry, dict) else []
                    ):
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
        "--tracker",
        choices=("linear", "azure_devops", "local_tracker"),
        help="Tracker adapter to configure.",
    )
    parser.add_argument(
        "--local-tracker-storage",
        choices=("committed", "ignored"),
        default="committed",
        help="Whether local tracker records are committed or ignored.",
    )
    parser.add_argument(
        "--scm", choices=("github", "azure_repos"), help="SCM adapter to configure."
    )
    parser.add_argument(
        "--tracker-scope", default="auto", help="Tracker workspace/project/team scope."
    )
    parser.add_argument(
        "--branch-template",
        default="{category}/{key}-{slug}",
        help="Branch format containing {key}.",
    )
    parser.add_argument(
        "--integration-config", type=Path, help="Validated integration JSON to install."
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip live provider tools/list discovery; still apply mapping presets.",
    )
    parser.add_argument(
        "--dest",
        help="Required project root for local install, wire, and uninstall.",
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
        help="With --uninstall, print planned changes without modifying files.",
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
    # the zip (when provided) before any ``scripts.*`` imports so uninstall
    # and wire can resolve the installed tree.
    script_dir = Path(__file__).parent.parent.parent.resolve()
    is_running_from_install_dir = script_dir == install_dir
    installed_runtime = False

    if zip_path is not None and not args.uninstall:
        print(f"Installing {zip_path} → {install_dir} ...")
        install_from_zip(zip_path, install_dir)
        print(f"Installed to {install_dir}")
        installed_runtime = True
    elif (
        zip_path is not None
        and args.uninstall
        and not (install_dir / "scripts").is_dir()
    ):
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
            from scripts.installer.uninstall import uninstall

            plan = uninstall(
                install_dir,
                dest=dest_path,
                keep_runtime=args.keep_runtime,
                dry_run=args.dry_run,
            )
            print(
                "\n".join(plan.messages)
                if plan.messages
                else "No managed plugin interventions found."
            )
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
                print(
                    f"error: runtime scripts missing under {install_dir}",
                    file=sys.stderr,
                )
                return 1
            result = wire(install_dir, args.target, dest_path)
            if result != 0:
                return result

        if args.tracker or args.scm or args.integration_config:
            if args.integration_config is not None:
                config_path = configure_integrations(
                    dest_path,
                    tracker=args.tracker or "linear",
                    scm=args.scm or "github",
                    branch_template=args.branch_template,
                    tracker_scope=args.tracker_scope,
                    config_source=args.integration_config,
                    discover=not args.skip_discovery,
                    runtime_dir=install_dir,
                )
            elif not args.tracker or not args.scm:
                print(
                    "error: --tracker and --scm are required when --integration-config is not supplied",
                    file=sys.stderr,
                )
                return 1
            else:
                config_path = configure_integrations(
                    dest_path,
                    tracker=args.tracker,
                    scm=args.scm,
                    branch_template=args.branch_template,
                    tracker_scope=args.tracker_scope,
                    discover=not args.skip_discovery,
                    runtime_dir=install_dir,
                )
            if args.tracker == "local_tracker":
                payload = json.loads(config_path.read_text(encoding="utf-8"))
                tracker = dict(payload["tracker"])
                tracker["storagePolicy"] = args.local_tracker_storage
                payload["tracker"] = tracker
                config_path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                _initialize_local_tracker(dest_path, tracker)
            print(f"Integration configuration written to {config_path}")

        print("\n" + "=" * 70)
        print("                  INSTALLATION COMPLETED SUCCESSFULLY                  ")
        print("=" * 70)
        print(f"Runtime installed to: {install_dir}")
        print("To wire agent hosts in this project, run:")
        print(
            f"  python3 -m scripts.installer.bootstrap --target all-agents --dest {dest_path}"
        )
        print("=" * 70 + "\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
