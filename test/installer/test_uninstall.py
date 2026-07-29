import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).parent.parent.parent


def _run_bootstrap(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.installer.bootstrap", *args],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
    )


class TestBootstrapUninstall(unittest.TestCase):
    def test_uninstall_requires_dest(self):
        with tempfile.TemporaryDirectory() as temp_home:
            home = Path(temp_home)
            result = _run_bootstrap(home, "--uninstall")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--dest", result.stdout + result.stderr)

    def test_uninstall_dest_removes_generated_project_assets_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_project:
            home = Path(temp_home)
            project = Path(temp_project)
            install_dir = project / ".codex-workflows"

            custom_rule = project / ".agent" / "rules" / "custom.md"
            custom_rule.parent.mkdir(parents=True)
            custom_rule.write_text("keep me\n", encoding="utf-8")

            install = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--target",
                "all-agents",
                "--dest",
                str(project),
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            self.assertTrue((project / ".agent" / "workflows").is_dir())
            self.assertTrue((project / ".claude" / "skills").is_dir())
            self.assertTrue((project / ".agents" / "skills").is_dir())
            self.assertTrue((project / ".claude" / "commands").is_dir())
            self.assertTrue((install_dir / "skills" / "codex_workflows" / "resources").is_dir())
            if (install_dir / ".agent").exists():
                shutil.rmtree(install_dir / ".agent")
            claude_config = project / ".claude" / "settings.json"
            claude_settings = json.loads(claude_config.read_text(encoding="utf-8"))
            claude_settings["hooks"]["PreToolUse"].append(
                {
                    "matcher": "custom",
                    "hooks": [{"type": "command", "command": "echo keep"}],
                }
            )
            claude_config.write_text(json.dumps(claude_settings), encoding="utf-8")

            uninstall = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--uninstall",
                "--dest",
                str(project),
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)

            self.assertTrue(custom_rule.exists())
            self.assertEqual(custom_rule.read_text(encoding="utf-8"), "keep me\n")
            self.assertFalse((project / ".agent" / "workflows").exists())
            self.assertFalse(install_dir.exists())
            self.assertFalse((project / ".cursor" / "hooks.json").exists())

            cleaned_claude = json.loads(claude_config.read_text(encoding="utf-8"))
            self.assertEqual(cleaned_claude["hooks"]["PreToolUse"][0]["matcher"], "custom")

    def test_keep_runtime_leaves_runtime_dir(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_project:
            home = Path(temp_home)
            project = Path(temp_project)
            install_dir = project / ".codex-workflows"

            install = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--target",
                "claude",
                "--dest",
                str(project),
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            uninstall = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--uninstall",
                "--keep-runtime",
                "--dest",
                str(project),
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
            self.assertTrue(install_dir.is_dir())

    def test_uninstall_removes_only_plugin_codex_mcp_entry(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_project:
            home = Path(temp_home)
            project = Path(temp_project)
            install_dir = project / ".codex-workflows"
            (project / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "azure-devops": {
                                "command": "npx",
                                "args": ["-y", "@azure-devops/mcp", "bhave-tecnologia-comportamental"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            install = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--target",
                "claude",
                "--dest",
                str(project),
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)

            uninstall = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--uninstall",
                "--dest",
                str(project),
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)

            mcp_servers = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
            self.assertEqual(set(mcp_servers), {"azure-devops"})
            config = (project / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.azure-devops]", config)
            self.assertNotIn("agentic-orchestrator", config)

    def test_dry_run_does_not_change_filesystem(self):
        with tempfile.TemporaryDirectory() as temp_home, tempfile.TemporaryDirectory() as temp_project:
            home = Path(temp_home)
            project = Path(temp_project)
            install_dir = project / ".codex-workflows"

            install = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--target",
                "claude",
                "--dest",
                str(project),
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            before_settings = (project / ".claude" / "settings.json").read_text(encoding="utf-8")

            uninstall = _run_bootstrap(
                home,
                "--install-dir",
                str(install_dir),
                "--uninstall",
                "--dry-run",
                "--dest",
                str(project),
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout + uninstall.stderr)
            self.assertTrue(install_dir.is_dir())
            self.assertEqual((project / ".claude" / "settings.json").read_text(encoding="utf-8"), before_settings)
            self.assertIn("DRY RUN", uninstall.stdout)


if __name__ == "__main__":
    unittest.main()
