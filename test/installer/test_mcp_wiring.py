"""Realistic coverage for installer MCP wiring across hosts and env injection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.installer.bootstrap import (
    _INTERACTIVE_AZURE_DEVOPS_ENV_VARS,
    _codex_mcp_server_config,
    _write_codex_mcp_config,
    default_install_dir,
    wire_orchestrator_mcp,
)

PLUGIN_ROOT = Path(__file__).parent.parent.parent


def _run_bootstrap(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.installer.bootstrap", *args],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
    )


def _azure_server(*, authentication: str | None = None) -> dict:
    args = ["-y", "@azure-devops/mcp", "contoso"]
    if authentication is not None:
        args.extend(["--authentication", authentication])
    return {"command": "npx", "args": args}


class TestWireOrchestratorMcp(unittest.TestCase):
    def test_wires_agentic_orchestrator_into_mcp_json_with_absolute_env(self):
        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            install_dir = project / ".codex-workflows"
            (install_dir / "skills").mkdir(parents=True)

            self.assertTrue(wire_orchestrator_mcp(install_dir, project))

            payload = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
            server = payload["mcpServers"]["agentic-orchestrator"]
            self.assertEqual(server["command"], "python3")
            self.assertEqual(server["args"], ["-m", "scripts.orchestrator.mcp_server"])
            self.assertEqual(server["env"]["PYTHONPATH"], str(install_dir.resolve()))
            self.assertEqual(
                server["env"]["ORCHESTRATOR_SKILLS_DIR"],
                str((install_dir / "skills").resolve()),
            )
            self.assertNotIn("env_vars", server)

    def test_syncs_preexisting_servers_to_codex_toml_and_preserves_tool_sections(self):
        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            install_dir = project / ".codex-workflows"
            (install_dir / "skills").mkdir(parents=True)
            (project / ".codex").mkdir()
            (project / ".codex" / "config.toml").write_text(
                "\n".join(
                    [
                        "[mcp_servers.azure-devops]",
                        'command = "old-npx"',
                        "",
                        "[mcp_servers.azure-devops.tools.core_list_projects]",
                        'approval_mode = "approve"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (project / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"azure-devops": _azure_server()}}),
                encoding="utf-8",
            )

            self.assertTrue(wire_orchestrator_mcp(install_dir, project))

            mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("azure-devops", mcp["mcpServers"])
            self.assertNotIn("env_vars", mcp["mcpServers"]["azure-devops"])

            toml = (project / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.azure-devops]", toml)
            self.assertIn('args = ["-y", "@azure-devops/mcp", "contoso"]', toml)
            self.assertIn(
                'env_vars = ["DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", '
                '"DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "BROWSER"]',
                toml,
            )
            self.assertIn("[mcp_servers.azure-devops.tools.core_list_projects]", toml)
            self.assertIn('approval_mode = "approve"', toml)
            self.assertNotIn('command = "old-npx"', toml)
            self.assertIn("[mcp_servers.agentic-orchestrator.env]", toml)

    def test_malformed_mcp_json_is_replaced_with_orchestrator_only(self):
        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            install_dir = project / ".codex-workflows"
            (install_dir / "skills").mkdir(parents=True)
            (project / ".mcp.json").write_text("{not-json", encoding="utf-8")

            self.assertTrue(wire_orchestrator_mcp(install_dir, project))

            payload = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
            self.assertEqual(set(payload["mcpServers"]), {"agentic-orchestrator"})

    def test_does_not_invent_azure_devops_server(self):
        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            install_dir = project / ".codex-workflows"
            (install_dir / "skills").mkdir(parents=True)

            wire_orchestrator_mcp(install_dir, project)

            payload = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
            self.assertNotIn("azure-devops", payload["mcpServers"])
            toml = (project / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertNotIn("azure-devops", toml)


class TestAzureEnvForwarding(unittest.TestCase):
    def test_interactive_auth_lists_session_var_names_without_values(self):
        enriched = _codex_mcp_server_config(_azure_server())
        self.assertEqual(enriched["env_vars"], list(_INTERACTIVE_AZURE_DEVOPS_ENV_VARS))
        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            _write_codex_mcp_config(project, {"azure-devops": enriched})
            toml = (project / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("env_vars = [", toml)
        for name in _INTERACTIVE_AZURE_DEVOPS_ENV_VARS:
            self.assertIn(f'"{name}"', toml)
            self.assertNotIn(f"{name} =", toml)

    def test_non_interactive_auth_is_left_unchanged(self):
        config = _azure_server(authentication="envvar")
        self.assertIs(_codex_mcp_server_config(config), config)

    def test_short_authentication_flag_is_honored(self):
        config = {
            "command": "npx",
            "args": ["-y", "@azure-devops/mcp", "contoso", "-a", "envvar"],
        }
        self.assertIs(_codex_mcp_server_config(config), config)

    def test_cursor_mcp_uses_env_interpolation_for_interactive_azure(self):
        from scripts.installer.bootstrap import _cursor_mcp_server_config, _write_cursor_mcp_config

        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            servers = {
                "azure-devops": _azure_server(),
                "agentic-orchestrator": {
                    "command": "python3",
                    "args": ["-m", "scripts.orchestrator.mcp_server"],
                    "env": {"PYTHONPATH": "/tmp/runtime"},
                },
            }
            _write_cursor_mcp_config(project, servers)
            cursor = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
            azure_env = cursor["mcpServers"]["azure-devops"]["env"]
            self.assertEqual(azure_env["DISPLAY"], "${env:DISPLAY}")
            self.assertEqual(azure_env["BROWSER"], "${env:BROWSER}")
            self.assertEqual(
                cursor["mcpServers"]["agentic-orchestrator"]["env"]["PYTHONPATH"],
                "/tmp/runtime",
            )
            non_interactive = _cursor_mcp_server_config(_azure_server(authentication="envvar"))
            self.assertNotIn("env", non_interactive)


class TestInstallMcpAcrossHarnesses(unittest.TestCase):
    def test_each_target_writes_same_project_mcp_json_shape(self):
        targets = ("claude", "codex", "cursor", "gemini", "antigravity")
        shapes: list[dict] = []

        for target in targets:
            with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as dest:
                home = Path(temp_home)
                project = Path(dest)
                (project / ".mcp.json").write_text(
                    json.dumps({"mcpServers": {"azure-devops": _azure_server()}}),
                    encoding="utf-8",
                )
                result = _run_bootstrap(home, "--dest", str(project), "--target", target)
                self.assertEqual(result.returncode, 0, f"{target}: {result.stdout + result.stderr}")

                mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
                runtime = default_install_dir(project)
                orchestrator = mcp["mcpServers"]["agentic-orchestrator"]
                shapes.append(
                    {
                        "target": target,
                        "servers": sorted(mcp["mcpServers"]),
                        "command": orchestrator["command"],
                        "args": orchestrator["args"],
                        "env_keys": sorted(orchestrator["env"]),
                        "has_cursor_mcp": (project / ".cursor" / "mcp.json").exists(),
                        "has_home_mcp": (home / ".mcp.json").exists(),
                        "has_home_codex": (home / ".codex" / "config.toml").exists(),
                        "has_home_cursor_mcp": (home / ".cursor" / "mcp.json").exists(),
                        "codex_has_env_vars": 'env_vars = ["DISPLAY"'
                        in (project / ".codex" / "config.toml").read_text(encoding="utf-8"),
                        "mcp_json_has_env_vars": "env_vars" in orchestrator
                        or "env_vars" in mcp["mcpServers"]["azure-devops"],
                        "cursor_has_azure_env_interpolation": (
                            json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
                            ["mcpServers"]["azure-devops"]
                            .get("env", {})
                            .get("DISPLAY")
                            == "${env:DISPLAY}"
                        ),
                        "claude_enabled_orchestrator": "agentic-orchestrator"
                        in json.loads(
                            (project / ".claude" / "settings.local.json").read_text(encoding="utf-8")
                        ).get("enabledMcpjsonServers", []),
                        "runtime_pythonpath": orchestrator["env"]["PYTHONPATH"] == str(runtime.resolve()),
                        "runtime_skills_dir": orchestrator["env"]["ORCHESTRATOR_SKILLS_DIR"]
                        == str((runtime / "skills").resolve()),
                    }
                )

        comparable = [{k: v for k, v in shape.items() if k != "target"} for shape in shapes]
        self.assertEqual(
            len({json.dumps(shape, sort_keys=True) for shape in comparable}),
            1,
            shapes,
        )
        sample = comparable[0]
        self.assertEqual(sample["servers"], ["agentic-orchestrator", "azure-devops"])
        self.assertEqual(sample["env_keys"], ["ORCHESTRATOR_SKILLS_DIR", "PYTHONPATH"])
        self.assertTrue(sample["has_cursor_mcp"])
        self.assertFalse(sample["has_home_mcp"])
        self.assertFalse(sample["has_home_codex"])
        self.assertFalse(sample["has_home_cursor_mcp"])
        self.assertTrue(sample["codex_has_env_vars"])
        self.assertFalse(sample["mcp_json_has_env_vars"])
        self.assertTrue(sample["cursor_has_azure_env_interpolation"])
        self.assertTrue(sample["claude_enabled_orchestrator"])
        self.assertTrue(sample["runtime_pythonpath"])
        self.assertTrue(sample["runtime_skills_dir"])

    def test_project_install_does_not_write_global_mcp_or_runtime(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as dest:
            home = Path(temp_home)
            project = Path(dest)
            result = _run_bootstrap(home, "--dest", str(project), "--target", "all-agents")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            self.assertTrue((project / ".mcp.json").exists())
            self.assertTrue((project / ".codex" / "config.toml").exists())
            self.assertTrue((project / ".cursor" / "mcp.json").exists())
            self.assertTrue((project / ".claude" / "settings.local.json").exists())
            self.assertFalse((home / ".mcp.json").exists())
            self.assertFalse((home / ".codex" / "config.toml").exists())
            self.assertFalse((home / ".codex-workflows").exists())
            self.assertFalse((home / ".cursor" / "mcp.json").exists())


class TestInstalledOrchestratorRuntime(unittest.TestCase):
    def test_installed_mcp_entry_launches_initialize_over_stdio(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as dest:
            home = Path(temp_home)
            project = Path(dest)
            result = _run_bootstrap(home, "--dest", str(project), "--target", "claude")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
            server = mcp["mcpServers"]["agentic-orchestrator"]

            # Keep installed PYTHONPATH, but use a tiny skills dir so startup stays fast.
            tiny_skills = project / "tiny-skills" / "mock-skill"
            tiny_skills.mkdir(parents=True)
            (tiny_skills / "manifest.json").write_text(
                json.dumps(
                    {
                        "name": "mock-skill",
                        "description": "mock",
                        "input_schema": {"type": "object", "properties": {}},
                        "output_signature": {"type": "object", "properties": {}},
                    }
                ),
                encoding="utf-8",
            )
            (tiny_skills / "SKILL.md").write_text("# mock\n", encoding="utf-8")

            child_env = {
                **os.environ,
                "PYTHONPATH": server["env"]["PYTHONPATH"],
                "ORCHESTRATOR_SKILLS_DIR": str(tiny_skills.parent),
            }
            request = (
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                + "\n"
                + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
                + "\n"
            )
            proc = subprocess.Popen(
                [server["command"], *server["args"]],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=child_env,
            )
            try:
                stdout, stderr = proc.communicate(input=request, timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                self.fail(f"MCP server timed out; stderr={stderr!r} stdout={stdout!r}")

            lines = [part for part in stdout.splitlines() if part.strip()]
            self.assertGreaterEqual(len(lines), 2, stderr)
            initialize = json.loads(lines[0])
            tools_list = json.loads(lines[1])
            self.assertEqual(initialize["result"]["serverInfo"]["name"], "agentic-orchestrator")
            self.assertEqual(tools_list["result"]["tools"][0]["name"], "mock-skill")


class TestUninstallMcpCleanup(unittest.TestCase):
    def test_uninstall_removes_orchestrator_keeps_other_servers_in_json_and_toml(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as dest:
            home = Path(temp_home)
            project = Path(dest)
            (project / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"azure-devops": _azure_server()}}),
                encoding="utf-8",
            )

            install = _run_bootstrap(home, "--dest", str(project), "--target", "claude")
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            self.assertIn(
                "agentic-orchestrator",
                json.loads((project / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"],
            )
            before_toml = (project / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.agentic-orchestrator]", before_toml)
            self.assertIn("[mcp_servers.azure-devops]", before_toml)

            uninstall = _run_bootstrap(home, "--uninstall", "--dest", str(project))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)

            mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
            self.assertNotIn("agentic-orchestrator", mcp["mcpServers"])
            self.assertIn("azure-devops", mcp["mcpServers"])

            after_toml = (project / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertNotIn("[mcp_servers.agentic-orchestrator]", after_toml)
            self.assertIn("[mcp_servers.azure-devops]", after_toml)

            cursor = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
            self.assertNotIn("agentic-orchestrator", cursor["mcpServers"])
            self.assertIn("azure-devops", cursor["mcpServers"])

            claude_local = json.loads(
                (project / ".claude" / "settings.local.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("agentic-orchestrator", claude_local.get("enabledMcpjsonServers", []))
            self.assertIn("azure-devops", claude_local.get("enabledMcpjsonServers", []))

    def test_uninstall_deletes_mcp_json_when_orchestrator_was_only_server(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as dest:
            home = Path(temp_home)
            project = Path(dest)
            install = _run_bootstrap(home, "--dest", str(project), "--target", "claude")
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            self.assertTrue((project / ".mcp.json").exists())
            self.assertTrue((project / ".cursor" / "mcp.json").exists())

            uninstall = _run_bootstrap(home, "--uninstall", "--dest", str(project))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
            self.assertFalse((project / ".mcp.json").exists())
            self.assertFalse((project / ".cursor" / "mcp.json").exists())


if __name__ == "__main__":
    unittest.main()
