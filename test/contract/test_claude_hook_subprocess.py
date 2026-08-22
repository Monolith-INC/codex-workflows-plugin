import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "codex_workflows"
    / "scripts"
    / "claude_enforce_hook.py"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestClaudeHookSubprocess(unittest.TestCase):
    def _run_hook(self, payload: dict) -> str:
        process = subprocess.Popen(
            [sys.executable, str(HOOK_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT,
        )
        stdout, stderr = process.communicate(input=json.dumps(payload))

        self.assertEqual(process.returncode, 0, stderr)
        return stdout

    def test_bash_allow_emits_no_output(self):
        stdout = self._run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
        )

        self.assertEqual(stdout, "")

    def test_markdown_read_outside_former_allowlist_is_allowed(self):
        stdout = self._run_hook(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": str(PROJECT_ROOT / "docs" / "private.md")},
            }
        )

        self.assertEqual(stdout, "")


if __name__ == "__main__":
    unittest.main()
