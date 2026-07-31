import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters import (
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
from policy.git_branch_guard import evaluate_git_branch_guard


class TestHookRuntime(unittest.TestCase):
    def test_allowed_decision_emits_no_output(self):
        stdout = StringIO()

        with redirect_stdout(stdout):
            hook_runtime.emit_decision("codex", hook_runtime.PolicyDecision.allow())

        self.assertEqual(stdout.getvalue(), "")

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
            "policy.git_branch_guard._run_git_cmd",
            return_value="master",
        ):
            decision = evaluate_git_branch_guard("git commit -m 'x'", "/tmp/repo")
        self.assertTrue(decision.is_denied())


if __name__ == "__main__":
    unittest.main()
