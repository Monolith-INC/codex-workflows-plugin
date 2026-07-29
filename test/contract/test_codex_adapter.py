import unittest
import json
from pathlib import Path

from scripts.adapters import format_codex_decision, parse_codex_payload
from scripts.policy import PolicyDecision


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "codex_pretooluse.json"


class TestCodexAdapter(unittest.TestCase):
    def test_parses_current_codex_payload_shape(self):
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        event = parse_codex_payload(payload, project_root="/workspace/project", vault_dir="/workspace/project/AI_Codex")

        self.assertEqual(event.client, "codex")
        self.assertEqual(event.tool_name, "Bash")
        self.assertEqual(event.command, "mv /workspace/project/AI_Codex/Tickets/Active/task-123.md /workspace/project/AI_Codex/Tickets/Closed/task-123.md")
        self.assertEqual(event.source_path, "/workspace/project/AI_Codex/Tickets/Active/task-123.md")
        self.assertEqual(event.destination_path, "/workspace/project/AI_Codex/Tickets/Closed/task-123.md")

    def test_formats_codex_decision_with_hook_specific_output(self):
        decision = PolicyDecision.deny("Blocked by policy")

        response = format_codex_decision(decision)

        self.assertEqual(
            response,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Blocked by policy",
                }
            },
        )

    def test_formats_allowed_codex_decision_without_permission(self):
        self.assertEqual(format_codex_decision(PolicyDecision.allow()), {})


if __name__ == "__main__":
    unittest.main()
