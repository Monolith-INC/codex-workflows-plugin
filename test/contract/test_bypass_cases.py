import json
import subprocess
import sys
import unittest
from pathlib import Path


HOOK_PATH = Path(__file__).resolve().parents[2] / "skills" / "codex_workflows" / "scripts" / "codex_enforce_hook.py"


class TestBypassCases(unittest.TestCase):
    def test_malformed_payload_fails_closed(self):
        process = subprocess.Popen(
            [sys.executable, str(HOOK_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, _ = process.communicate(input="{not-valid-json")

        response = json.loads(stdout.strip())

        self.assertEqual(
            response,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Invalid hook payload",
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
