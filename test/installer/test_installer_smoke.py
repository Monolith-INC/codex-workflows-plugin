import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.installer.cli import _plugin_root

CLI = [sys.executable, "-m", "scripts.installer.cli"]
SCRIPTS_DIR = _plugin_root() / "skills" / "codex_workflows" / "scripts"


def _expected_cmd(script_name: str) -> str:
    return f"python3 {SCRIPTS_DIR / script_name}"


class TestInstallerSmoke(unittest.TestCase):
    def _run_installer(self, target: str, output_path: Path) -> dict:
        completed = subprocess.run(
            CLI
            + [
                "--target",
                target,
                "--profile",
                "generic",
                "--output",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_codex_target_writes_hooks_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "hooks.json"
            result = self._run_installer("codex", output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(result["configPaths"], [".codex/hooks.json"])
            content = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                content["hooks"]["PreToolUse"][0]["hooks"][0]["command"],
                _expected_cmd("codex_enforce_hook.py"),
            )

    def test_gemini_target_writes_settings_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "settings.json"
            result = self._run_installer("gemini", output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(result["configPaths"], [".gemini/settings.json"])
            content = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                content["hooks"]["BeforeTool"][0]["hooks"][0]["command"],
                _expected_cmd("gemini_enforce_hook.py"),
            )

    def test_antigravity_target_writes_hooks_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "hooks.json"
            result = self._run_installer("antigravity", output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(result["configPaths"], [".agents/hooks.json"])
            content = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                content["codex-enforcer"]["PreToolUse"][0]["hooks"][0]["command"],
                _expected_cmd("antigravity_enforce_hook.py"),
            )

    def test_antigravity_cli_target_writes_settings_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "settings.json"
            result = self._run_installer("antigravity-cli", output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(
                result["configPaths"], [".gemini/antigravity-cli/settings.json"]
            )
            content = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                content["hooks"]["BeforeTool"][0]["hooks"][0]["command"],
                _expected_cmd("antigravity_enforce_hook.py"),
            )

    def test_claude_target_writes_settings_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "settings.json"
            result = self._run_installer("claude", output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(result["configPaths"], [".claude/settings.json"])
            content = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                content["hooks"]["PreToolUse"][0]["hooks"][0]["command"],
                _expected_cmd("claude_enforce_hook.py"),
            )

    def test_cursor_target_writes_hooks_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "hooks.json"
            result = self._run_installer("cursor", output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(result["configPaths"], [".cursor/hooks.json"])
            content = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(content["version"], 1)
            self.assertEqual(
                content["hooks"]["preToolUse"][0]["command"],
                _expected_cmd("cursor_enforce_hook.py"),
            )

    def test_install_with_dest_syncs_workflows_to_agent_dir(self):
        """When --dest is provided, .agent/workflows/ files are synced to the target."""
        with tempfile.TemporaryDirectory() as tempdir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.installer.cli",
                    "--target",
                    "gemini",
                    "--dest",
                    tempdir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["target"], "gemini")
            workflows_dir = Path(tempdir) / ".agent" / "workflows"
            self.assertTrue(
                workflows_dir.is_dir(), "workflows dir should have been created"
            )
            md_files = list(workflows_dir.glob("*.md"))
            self.assertGreater(
                len(md_files), 0, "at least one workflow file should be synced"
            )

    def test_install_with_dest_syncs_workflows_subdirectories(self):
        """When --dest is provided, workflows subdirectories (like templates/) are copied recursively."""
        with tempfile.TemporaryDirectory() as tempdir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.installer.cli",
                    "--target",
                    "gemini",
                    "--dest",
                    tempdir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["target"], "gemini")
            templates_dir = Path(tempdir) / ".agent" / "workflows" / "templates"
            self.assertTrue(
                templates_dir.is_dir(), "templates subdirectory should have been copied"
            )
            template_files = list(templates_dir.glob("*.md"))
            self.assertGreater(
                len(template_files),
                0,
                "template files should be present in synced templates dir",
            )

    def test_install_with_dest_writes_target_config_in_place(self):
        """When --dest is provided, the hook config is written at the correct relative path."""
        with tempfile.TemporaryDirectory() as tempdir:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.installer.cli",
                    "--target",
                    "antigravity",
                    "--dest",
                    tempdir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            hooks_file = Path(tempdir) / ".agents" / "hooks.json"
            self.assertTrue(
                hooks_file.exists(), ".agents/hooks.json should have been written"
            )
            content = json.loads(hooks_file.read_text(encoding="utf-8"))
            self.assertIn("codex-enforcer", content)

    def test_install_with_dest_writes_codex_claude_and_cursor_configs(self):
        cases = [
            (
                "codex",
                ".codex/hooks.json",
                ("hooks", "PreToolUse", 0, "hooks", 0, "command"),
                "codex_enforce_hook.py",
            ),
            (
                "claude",
                ".claude/settings.json",
                ("hooks", "PreToolUse", 0, "hooks", 0, "command"),
                "claude_enforce_hook.py",
            ),
            (
                "cursor",
                ".cursor/hooks.json",
                ("hooks", "preToolUse", 0, "command"),
                "cursor_enforce_hook.py",
            ),
        ]

        for target, relative_path, command_path, script_name in cases:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tempdir:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.installer.cli",
                        "--target",
                        target,
                        "--dest",
                        tempdir,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                result = json.loads(completed.stdout)
                config_path = Path(tempdir) / relative_path
                content = json.loads(config_path.read_text(encoding="utf-8"))
                command = content
                for key in command_path:
                    command = command[key]

                self.assertEqual(result["target"], target)
                self.assertEqual(result["configPaths"], [relative_path])
                self.assertTrue(config_path.exists())
                self.assertEqual(command, _expected_cmd(script_name))


if __name__ == "__main__":
    unittest.main()
