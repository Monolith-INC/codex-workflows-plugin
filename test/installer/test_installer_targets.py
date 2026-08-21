import unittest

from scripts.installer import install
from scripts.installer.cli import _plugin_root
from scripts.installer.merge import merge_hook_configs

SCRIPTS_DIR = _plugin_root() / "skills" / "codex_workflows" / "scripts"


def _expected_cmd(script_name: str) -> str:
    return f"python3 {SCRIPTS_DIR / script_name}"


class TestInstallerTargets(unittest.TestCase):
    def test_universal_target_installs_shared_assets_only(self):
        result = install(target="universal")

        self.assertFalse(result.written_codex_config)
        self.assertTrue(result.written_shared_assets)
        self.assertEqual(result.config_paths, ())

    def test_codex_target_installs_codex_config(self):
        result = install(target="codex")

        self.assertTrue(result.written_codex_config)
        self.assertTrue(result.written_shared_assets)
        self.assertTrue(result.written_target_config)
        self.assertEqual(result.config_paths, (".codex/hooks.json",))
        self.assertIsNotNone(result.merged_config)
        self.assertEqual(
            result.merged_config["hooks"]["PreToolUse"][0]["hooks"][0]["command"],
            _expected_cmd("codex_enforce_hook.py"),
        )

    def test_gemini_target_installs_project_settings(self):
        result = install(target="gemini")

        self.assertFalse(result.written_codex_config)
        self.assertTrue(result.written_shared_assets)
        self.assertTrue(result.written_target_config)
        self.assertEqual(result.config_paths, (".gemini/settings.json",))
        self.assertEqual(
            result.merged_config["hooks"]["BeforeTool"][0]["hooks"][0]["command"],
            _expected_cmd("gemini_enforce_hook.py"),
        )

    def test_antigravity_target_installs_hooks_json(self):
        result = install(target="antigravity")

        self.assertFalse(result.written_codex_config)
        self.assertTrue(result.written_shared_assets)
        self.assertTrue(result.written_target_config)
        self.assertEqual(result.config_paths, (".agents/hooks.json",))
        self.assertEqual(
            result.merged_config["codex-enforcer"]["PreToolUse"][0]["hooks"][0]["command"],
            _expected_cmd("antigravity_enforce_hook.py"),
        )

    def test_antigravity_cli_target_installs_project_settings(self):
        result = install(target="antigravity-cli")

        self.assertFalse(result.written_codex_config)
        self.assertTrue(result.written_shared_assets)
        self.assertTrue(result.written_target_config)
        self.assertEqual(result.config_paths, (".gemini/antigravity-cli/settings.json",))
        self.assertEqual(
            result.merged_config["hooks"]["BeforeTool"][0]["hooks"][0]["command"],
            _expected_cmd("antigravity_enforce_hook.py"),
        )

    def test_claude_target_installs_project_settings(self):
        result = install(target="claude")

        self.assertFalse(result.written_codex_config)
        self.assertTrue(result.written_shared_assets)
        self.assertTrue(result.written_target_config)
        self.assertEqual(result.config_paths, (".claude/settings.json",))
        self.assertEqual(
            result.merged_config["hooks"]["PreToolUse"][0]["hooks"][0]["command"],
            _expected_cmd("claude_enforce_hook.py"),
        )

    def test_cursor_target_installs_hooks_json(self):
        result = install(target="cursor")

        self.assertFalse(result.written_codex_config)
        self.assertTrue(result.written_shared_assets)
        self.assertTrue(result.written_target_config)
        self.assertEqual(result.config_paths, (".cursor/hooks.json",))
        self.assertEqual(
            result.merged_config["hooks"]["preToolUse"][0]["command"],
            _expected_cmd("cursor_enforce_hook.py"),
        )

    def test_merge_hook_configs_preserves_existing_hooks(self):
        existing = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "^Bash$",
                        "hooks": [
                            {"type": "command", "command": "echo existing"}
                        ],
                    }
                ]
            }
        }
        incoming = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "^(Bash|apply_patch)$",
                        "hooks": [
                            {"type": "command", "command": "echo incoming"}
                        ],
                    }
                ]
            }
        }

        merged = merge_hook_configs(existing, incoming)

        self.assertEqual(len(merged["hooks"]["PreToolUse"]), 2)
        self.assertEqual(merged["hooks"]["PreToolUse"][0]["matcher"], "^Bash$")
        self.assertEqual(
            merged["hooks"]["PreToolUse"][1]["matcher"],
            "^(Bash|apply_patch)$",
        )


if __name__ == "__main__":
    unittest.main()
