import unittest
from pathlib import Path
from unittest import mock

from scripts.adapters import (
    format_antigravity_decision,
    format_claude_decision,
    format_codex_decision,
    format_cursor_decision,
    format_gemini_decision,
    parse_antigravity_payload,
    parse_claude_payload,
    parse_codex_payload,
    parse_cursor_payload,
    parse_gemini_payload,
)
from scripts import hook_runtime
from scripts.hook_runtime import select_adapter
from scripts.policy.git_branch_guard import evaluate_git_branch_guard


class TestHookRuntime(unittest.TestCase):
    def test_select_adapter_maps_clients_to_expected_handlers(self):
        parser, formatter = select_adapter("codex")
        self.assertIs(parser, parse_codex_payload)
        self.assertIs(formatter, format_codex_decision)

        parser, formatter = select_adapter("gemini")
        self.assertIs(parser, parse_gemini_payload)
        self.assertIs(formatter, format_gemini_decision)

        parser, formatter = select_adapter("antigravity")
        self.assertIs(parser, parse_antigravity_payload)
        self.assertIs(formatter, format_antigravity_decision)

        parser, formatter = select_adapter("claude")
        self.assertIs(parser, parse_claude_payload)
        self.assertIs(formatter, format_claude_decision)

        parser, formatter = select_adapter("cursor")
        self.assertIs(parser, parse_cursor_payload)
        self.assertIs(formatter, format_cursor_decision)

    def test_gemini_run_shell_command_is_in_shell_tool_set(self):
        source = Path(hook_runtime.__file__).read_text(encoding="utf-8")
        self.assertIn('"run_shell_command"', source)

        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="master",
        ):
            decision = evaluate_git_branch_guard("git commit -m 'x'", "/tmp/repo")
        self.assertTrue(decision.is_denied())


if __name__ == "__main__":
    unittest.main()
