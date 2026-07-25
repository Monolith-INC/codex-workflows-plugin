import io
import os
import tempfile
import unittest
import contextlib
from pathlib import Path

from scripts.hook_runtime import run


class TestCursorDeleteGuard(unittest.TestCase):
    def setUp(self):
        self._prev_cursor_dir = os.environ.get("CURSOR_PROJECT_DIR")
        self._tmpdir = tempfile.mkdtemp()
        self.vault = os.path.join(self._tmpdir, "AI_Codex")
        self.ticket = os.path.join(self.vault, "Tickets", "Active", "task-123.md")
        os.makedirs(os.path.dirname(self.ticket))
        Path(self.ticket).write_text("# ticket", encoding="utf-8")
        os.environ["CURSOR_PROJECT_DIR"] = self._tmpdir

    def tearDown(self):
        if self._prev_cursor_dir is None:
            os.environ.pop("CURSOR_PROJECT_DIR", None)
        else:
            os.environ["CURSOR_PROJECT_DIR"] = self._prev_cursor_dir
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_denies_delete_on_vault_markdown(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run(
                "cursor",
                {
                    "tool_name": "Delete",
                    "tool_input": {"path": self.ticket},
                },
            )

        response = buf.getvalue().strip()
        self.assertIn('"permission": "deny"', response)
        self.assertIn("Destructive deletions", response)
        self.assertTrue(os.path.exists(self.ticket))


if __name__ == "__main__":
    unittest.main()
