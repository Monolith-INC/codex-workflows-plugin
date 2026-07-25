import unittest

from scripts.installer.cursor_hooks import desired_cursor_hooks, merge_cursor_hooks, strip_managed_cursor_hooks


class TestCursorHooks(unittest.TestCase):
    def test_desired_cursor_hooks_includes_policy_entry(self):
        config = desired_cursor_hooks("python3 /tmp/cursor_enforce_hook.py")
        self.assertEqual(config["version"], 1)
        self.assertEqual(len(config["hooks"]["preToolUse"]), 1)
        matcher = config["hooks"]["preToolUse"][0]["matcher"]
        self.assertIn("Shell|Read|Write|Grep|Delete|Task", matcher)
        self.assertIn("Write", matcher)

    def test_merge_cursor_hooks_deduplicates_by_command(self):
        existing = {
            "version": 1,
            "hooks": {
                "preToolUse": [{"command": "python3 /tmp/cursor_enforce_hook.py", "matcher": "Shell"}],
                "sessionStart": [{"command": ".cursor/hooks/bootstrap.sh"}],
            },
        }
        incoming = desired_cursor_hooks("python3 /tmp/cursor_enforce_hook.py")
        merged = merge_cursor_hooks(existing, incoming)
        self.assertEqual(len(merged["hooks"]["preToolUse"]), 1)
        self.assertEqual(len(merged["hooks"]["sessionStart"]), 1)

    def test_strip_managed_cursor_hooks_removes_policy_entry(self):
        config = {
            "version": 1,
            "hooks": {
                "preToolUse": [
                    {"command": "python3 /tmp/cursor_enforce_hook.py"},
                    {"command": ".cursor/hooks/custom.sh"},
                ]
            },
        }
        stripped = strip_managed_cursor_hooks(config, {"cursor_enforce_hook.py"})
        self.assertEqual(len(stripped["hooks"]["preToolUse"]), 1)
        self.assertEqual(stripped["hooks"]["preToolUse"][0]["command"], ".cursor/hooks/custom.sh")


if __name__ == "__main__":
    unittest.main()
