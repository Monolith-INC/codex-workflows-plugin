import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.installer.bootstrap import (
    _codex_mcp_server_config,
    _default_tracker_config,
    configure_integrations,
    default_install_dir,
    install_from_source,
    install_from_zip,
)
from scripts.installer.cli import sync_host_discovery_assets, sync_shared_assets

PLUGIN_ROOT = Path(__file__).parent.parent.parent


class TestInstallFromSource(unittest.TestCase):
    def setUp(self):
        self.dest = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dest)

    def test_copies_runtime_dirs(self):
        install_from_source(PLUGIN_ROOT, self.dest)

        self.assertTrue((self.dest / "scripts").is_dir())
        self.assertTrue((self.dest / "skills").is_dir())
        self.assertFalse((self.dest / ".codex-plugin").exists())

    def test_copies_hook_entrypoints(self):
        install_from_source(PLUGIN_ROOT, self.dest)

        hook = (
            self.dest
            / "skills"
            / "codex_workflows"
            / "scripts"
            / "antigravity_enforce_hook.py"
        )
        self.assertTrue(hook.exists())

    def test_copies_policy_engine(self):
        install_from_source(PLUGIN_ROOT, self.dest)

        self.assertTrue((self.dest / "scripts" / "policy" / "engine.py").exists())

    def test_excludes_pycache(self):
        install_from_source(PLUGIN_ROOT, self.dest)

        pycache_dirs = list(self.dest.rglob("__pycache__"))
        self.assertEqual(pycache_dirs, [], "no __pycache__ dirs should be copied")

    def test_replaces_existing_install(self):
        (self.dest / "stale.txt").write_text("stale")
        install_from_source(PLUGIN_ROOT, self.dest)

        self.assertFalse((self.dest / "stale.txt").exists())

    def test_installed_cli_hook_command_points_to_dest(self):
        install_from_source(PLUGIN_ROOT, self.dest)

        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "scripts.installer.cli", "--target", "antigravity"],
            capture_output=True,
            text=True,
            cwd=self.dest,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        cmd = output["mergedConfig"]["codex-enforcer"]["PreToolUse"][0]["hooks"][0][
            "command"
        ]
        self.assertIn(
            str(self.dest),
            cmd,
            "hook command should reference the installed dest, not the source repo",
        )

    def test_copies_commands_dir(self):
        install_from_source(PLUGIN_ROOT, self.dest)

        self.assertTrue((self.dest / "commands" / "review-pr.md").exists())
        self.assertTrue((self.dest / "commands" / "skip-tracker.md").exists())
        self.assertTrue(
            (
                self.dest
                / "skills"
                / "codex_workflows"
                / "resources"
                / "templates"
                / "epic-template.md"
            ).exists()
        )

    def test_local_tracker_bootstrap_creates_committed_or_ignored_layout(self):
        committed = Path(tempfile.mkdtemp())
        ignored = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, committed)
        self.addCleanup(shutil.rmtree, ignored)
        configure_integrations(
            committed,
            tracker="local_tracker",
            scm="github",
            branch_template="{category}/{key}-{slug}",
            discover=False,
        )
        config = json.loads(
            (committed / ".codex-workflows" / "integrations.json").read_text()
        )
        self.assertEqual(config["tracker"]["storagePolicy"], "committed")
        self.assertEqual(
            config["tracker"]["bindings"]["get_work_item"], "get_work_item"
        )
        self.assertEqual(
            config["tracker"]["bindings"]["publish_artifact"], "publish_artifact"
        )
        self.assertIn(
            "run_local_tracker.py", config["tracker"]["connection"]["args"][0]
        )
        for state in (
            "backlog",
            "ready",
            "in_progress",
            "done",
            "canceled",
            "artifacts",
        ):
            self.assertTrue((committed / ".local-tracker" / state).is_dir())
        self.assertFalse((committed / ".gitignore").exists())

        config_path = configure_integrations(
            ignored,
            tracker="local_tracker",
            scm="github",
            branch_template="{category}/{key}-{slug}",
            discover=False,
        )
        payload = json.loads(config_path.read_text())
        payload["tracker"]["storagePolicy"] = "ignored"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        from scripts.installer.bootstrap import _initialize_local_tracker

        _initialize_local_tracker(ignored, payload["tracker"])
        self.assertIn(".local-tracker/", (ignored / ".gitignore").read_text())


class TestSyncHostDiscoveryAssets(unittest.TestCase):
    def test_syncs_claude_and_agents_skills_and_commands(self):
        with (
            tempfile.TemporaryDirectory() as plugin,
            tempfile.TemporaryDirectory() as project,
        ):
            root = Path(plugin)
            (root / "skills" / "demo-skill").mkdir(parents=True)
            (root / "skills" / "demo-skill" / "SKILL.md").write_text(
                "# demo\n", encoding="utf-8"
            )
            (root / "commands").mkdir()
            (root / "commands" / "demo.md").write_text("# demo cmd\n", encoding="utf-8")

            dest = Path(project)
            sync_host_discovery_assets(dest, root)

            self.assertTrue(
                (dest / ".claude" / "skills" / "demo-skill" / "SKILL.md").exists()
            )
            self.assertTrue(
                (dest / ".agents" / "skills" / "demo-skill" / "SKILL.md").exists()
            )
            self.assertTrue((dest / ".claude" / "commands" / "demo.md").exists())


class TestSyncSharedAssets(unittest.TestCase):
    def test_syncs_markdown_and_typescript_rules(self):
        with (
            tempfile.TemporaryDirectory() as plugin,
            tempfile.TemporaryDirectory() as project,
        ):
            root = Path(plugin)
            rules = root / ".agent" / "rules"
            workflows = root / ".agent" / "workflows"
            rules.mkdir(parents=True)
            workflows.mkdir(parents=True)
            (rules / "rules-demo.md").write_text("# md\n", encoding="utf-8")
            (rules / "rules-demo.ts").write_text(
                "export const rules = [] as const;\n", encoding="utf-8"
            )
            (workflows / "workflows-demo.md").write_text("# wf\n", encoding="utf-8")

            dest = Path(project)
            sync_shared_assets(dest, root)

            self.assertTrue((dest / ".agent" / "rules" / "rules-demo.md").exists())
            self.assertTrue((dest / ".agent" / "rules" / "rules-demo.ts").exists())
            self.assertTrue(
                (dest / ".agent" / "workflows" / "workflows-demo.md").exists()
            )


class TestInstallFromZip(unittest.TestCase):
    def setUp(self):
        self.dest = Path(tempfile.mkdtemp())
        self.zip_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dest)
        shutil.rmtree(self.zip_dir)

    def _make_zip(self, files: dict[str, str]) -> Path:
        zip_path = self.zip_dir / "plugin.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return zip_path

    def test_extracts_zip_contents(self):
        zip_path = self._make_zip(
            {
                "scripts/hook_runtime.py": "# runtime",
                "skills/codex_workflows/scripts/antigravity_enforce_hook.py": "# hook",
                "codex-workflows-plugin.json": json.dumps({"name": "test"}),
            }
        )
        install_from_zip(zip_path, self.dest)

        self.assertTrue((self.dest / "scripts" / "hook_runtime.py").exists())
        self.assertTrue(
            (
                self.dest
                / "skills"
                / "codex_workflows"
                / "scripts"
                / "antigravity_enforce_hook.py"
            ).exists()
        )

    def test_replaces_existing_install(self):
        (self.dest / "stale.txt").write_text("stale")
        zip_path = self._make_zip({"scripts/foo.py": "# new"})
        install_from_zip(zip_path, self.dest)

        self.assertFalse((self.dest / "stale.txt").exists())
        self.assertTrue((self.dest / "scripts" / "foo.py").exists())


class TestInstallCLI(unittest.TestCase):
    def _run(self, *args) -> tuple[int, str]:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "scripts.installer.bootstrap", *args],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout + result.stderr

    def test_requires_dest(self):
        code, output = self._run("--target", "claude")
        self.assertNotEqual(code, 0)
        self.assertIn("--dest", output)

    def test_local_tracker_cli_applies_ignored_storage_policy(self):
        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            code, output = self._run(
                "--dest",
                str(project),
                "--target",
                "claude",
                "--tracker",
                "local_tracker",
                "--local-tracker-storage",
                "ignored",
                "--scm",
                "github",
            )
            self.assertEqual(code, 0, output)
            payload = json.loads(
                (project / ".codex-workflows" / "integrations.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["tracker"]["storagePolicy"], "ignored")
            self.assertEqual(
                payload["tracker"]["bindings"]["create_work_item"],
                "create_work_item",
            )
            self.assertIn(
                "run_local_tracker.py", payload["tracker"]["connection"]["args"][0]
            )
            self.assertIn(
                ".local-tracker/",
                (project / ".gitignore").read_text(encoding="utf-8"),
            )
            self.assertTrue((project / ".local-tracker" / "backlog").is_dir())

    def test_missing_zip_returns_error(self):
        with tempfile.TemporaryDirectory() as dest:
            code, output = self._run("/nonexistent/plugin.zip", "--dest", dest)
            self.assertNotEqual(code, 0)
            self.assertIn("not found", output)

    def test_install_from_source_via_cli_uses_project_runtime(self):
        with tempfile.TemporaryDirectory() as dest:
            project = Path(dest)
            code, output = self._run("--dest", str(project), "--target", "claude")
            self.assertEqual(code, 0, output)
            runtime = default_install_dir(project)
            self.assertTrue((runtime / "scripts").is_dir())
            self.assertTrue((project / ".claude" / "settings.json").exists())
            self.assertTrue((project / ".claude" / "skills").is_dir())
            self.assertTrue((project / ".agents" / "skills").is_dir())
            self.assertTrue((project / ".claude" / "commands").is_dir())

    def test_project_install_does_not_write_home_hooks(self):
        import os
        import subprocess

        with (
            tempfile.TemporaryDirectory() as temp_home,
            tempfile.TemporaryDirectory() as dest,
        ):
            home = Path(temp_home)
            project = Path(dest)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.installer.bootstrap",
                    "--dest",
                    str(project),
                    "--target",
                    "all-agents",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((home / ".claude" / "settings.json").exists())
            self.assertFalse((home / ".cursor" / "hooks.json").exists())
            self.assertFalse((home / ".codex-workflows").exists())
            self.assertFalse(
                (home / ".claude" / "plugins" / "installed_plugins.json").exists()
            )
            self.assertTrue((project / ".claude" / "settings.json").exists())
            self.assertTrue((project / ".cursor" / "hooks.json").exists())

    def test_project_install_writes_codex_mcp_config_from_project_mcp_json(self):
        import os
        import subprocess

        with (
            tempfile.TemporaryDirectory() as temp_home,
            tempfile.TemporaryDirectory() as dest,
        ):
            home = Path(temp_home)
            project = Path(dest)
            mcp_path = project / ".mcp.json"
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
            mcp_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "azure-devops": {
                                "command": "npx",
                                "args": [
                                    "-y",
                                    "@azure-devops/mcp",
                                    "bhave-tecnologia-comportamental",
                                ],
                            },
                            "agile-workflow-orchestrator": {
                                "command": "/usr/bin/python3",
                                "args": ["-m", "orchestrator_core", "mcp"],
                                "env": {
                                    "PYTHONPATH": "/opt/agile-workflow",
                                    "CODEX_PROJECT_ROOT": str(project),
                                },
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.installer.bootstrap",
                    "--dest",
                    str(project),
                    "--target",
                    "claude",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            config = (project / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.azure-devops]", config)
            self.assertIn(
                'args = ["-y", "@azure-devops/mcp", "bhave-tecnologia-comportamental"]',
                config,
            )
            self.assertIn(
                'env_vars = ["DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "BROWSER"]',
                config,
            )
            self.assertIn("[mcp_servers.azure-devops.tools.core_list_projects]", config)
            self.assertIn('approval_mode = "approve"', config)
            self.assertNotIn('command = "old-npx"', config)
            self.assertIn("[mcp_servers.agile-workflow-orchestrator.env]", config)
            self.assertIn(f'CODEX_PROJECT_ROOT = "{project}"', config)
            self.assertIn("[mcp_servers.agentic-orchestrator.env]", config)
            self.assertIn(
                f'ORCHESTRATOR_SKILLS_DIR = "{project / ".codex-workflows" / "skills"}"',
                config,
            )

    def test_codex_azure_browser_env_is_added_only_for_interactive_auth(self):
        interactive = _codex_mcp_server_config(
            {
                "command": "npx",
                "args": ["-y", "@azure-devops/mcp", "contoso"],
                "env_vars": ["HOME", "DISPLAY"],
            }
        )
        non_interactive = {
            "command": "npx",
            "args": [
                "-y",
                "@azure-devops/mcp",
                "contoso",
                "--authentication",
                "envvar",
            ],
        }

        self.assertEqual(
            interactive["env_vars"],
            [
                "HOME",
                "DISPLAY",
                "WAYLAND_DISPLAY",
                "XAUTHORITY",
                "DBUS_SESSION_BUS_ADDRESS",
                "XDG_RUNTIME_DIR",
                "BROWSER",
            ],
        )
        self.assertIs(_codex_mcp_server_config(non_interactive), non_interactive)

    def test_linear_default_bindings_use_current_mcp_tool_names(self):
        config = _default_tracker_config("linear", "auto")

        self.assertEqual(config["bindings"]["create_work_item"], "save_issue")
        self.assertEqual(config["bindings"]["transition_work_item"], "save_issue")
        self.assertEqual(config["bindings"]["publish_artifact"], "save_comment")
        self.assertEqual(
            config["bindings"]["link_development_artifact"], "save_comment"
        )


class TestStandaloneBootstrapZipInstall(unittest.TestCase):
    """Mirror install.sh: extract bootstrap.py and run it outside the package tree."""

    def test_standalone_bootstrap_wires_from_zip(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            staging = root / "staging"
            project = root / "project"
            project.mkdir()
            install_from_source(PLUGIN_ROOT, staging)

            zip_path = root / "codex-workflows-plugin-test.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in staging.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(staging).as_posix())

            bootstrap_path = root / "bootstrap.py"
            with zipfile.ZipFile(zip_path) as archive:
                bootstrap_path.write_bytes(
                    archive.read("scripts/installer/bootstrap.py")
                )

            result = subprocess.run(
                [
                    sys.executable,
                    str(bootstrap_path),
                    str(zip_path),
                    "--target",
                    "claude",
                    "--dest",
                    str(project),
                ],
                capture_output=True,
                text=True,
                cwd=root,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            runtime = default_install_dir(project)
            self.assertTrue(
                (runtime / "scripts" / "installer" / "bootstrap.py").exists()
            )
            self.assertTrue((project / ".claude" / "settings.json").exists())
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertNotIn("No module named 'scripts'", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
