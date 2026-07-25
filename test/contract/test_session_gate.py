import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts.policy.session_gate import evaluate_session_gate, session_directories


class TestSessionGate(unittest.TestCase):
    def _write_session(self, directory: Path, name: str, *, branch: str | None, timestamp: str, open_session: bool = True) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        branch_line = f"branch: {branch}\n" if branch is not None else ""
        next_line = "next: null\n" if open_session else "next: follow-up.md\n"
        path.write_text(
            f"---\n"
            f"timestamp: {timestamp}\n"
            f"{branch_line}"
            f"status: active\n"
            f"{next_line}"
            f"---\n\n# Session\n",
            encoding="utf-8",
        )
        return path

    def test_discovers_project_agent_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "AI_Codex"
            project_sessions = vault / "Projects" / "demo" / "Agent_Sessions"
            now = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
            self._write_session(
                project_sessions,
                "2026-07-25T15-00-00.md",
                branch="feature/demo",
                timestamp="2026-07-25T15:00:00+00:00",
            )

            dirs = session_directories(str(vault))
            result = evaluate_session_gate(
                str(vault),
                str(tmp),
                now=now,
                current_branch="feature/demo",
            )

            self.assertEqual(dirs, [project_sessions])
            self.assertTrue(result.active)

    def test_allows_open_session_within_max_age_same_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "AI_Codex"
            sessions = vault / "Agent_Sessions"
            now = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
            self._write_session(
                sessions,
                "2026-07-25T12-00-00.md",
                branch="feature/demo",
                timestamp="2026-07-25T12:00:00+00:00",
            )

            result = evaluate_session_gate(
                str(vault),
                str(tmp),
                now=now,
                current_branch="feature/demo",
            )

            self.assertTrue(result.active)
            self.assertIsNone(result.reason)

    def test_denies_stale_open_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "AI_Codex"
            sessions = vault / "Agent_Sessions"
            now = datetime(2026, 7, 25, 20, 0, tzinfo=timezone.utc)
            self._write_session(
                sessions,
                "2026-07-25T10-00-00.md",
                branch="feature/demo",
                timestamp="2026-07-25T10:00:00+00:00",
            )

            result = evaluate_session_gate(
                str(vault),
                str(tmp),
                now=now,
                max_age=timedelta(hours=8),
                current_branch="feature/demo",
            )

            self.assertFalse(result.active)
            self.assertIn("older than 8 hours", result.reason or "")

    def test_denies_branch_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "AI_Codex"
            sessions = vault / "Agent_Sessions"
            now = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
            self._write_session(
                sessions,
                "2026-07-25T15-00-00.md",
                branch="feature/other",
                timestamp="2026-07-25T15:00:00+00:00",
            )

            result = evaluate_session_gate(
                str(vault),
                str(tmp),
                now=now,
                current_branch="feature/demo",
            )

            self.assertFalse(result.active)
            self.assertIn("feature/other", result.reason or "")
            self.assertIn("feature/demo", result.reason or "")

    def test_allows_unscoped_open_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "AI_Codex"
            sessions = vault / "Agent_Sessions"
            now = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
            self._write_session(
                sessions,
                "2026-07-25T15-00-00.md",
                branch=None,
                timestamp="2026-07-25T15:00:00+00:00",
            )

            result = evaluate_session_gate(
                str(vault),
                str(tmp),
                now=now,
                current_branch="feature/demo",
            )

            self.assertTrue(result.active)

    def test_parses_compact_legacy_filename_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "AI_Codex"
            sessions = vault / "Agent_Sessions"
            sessions.mkdir(parents=True)
            now = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
            path = sessions / "2026-07-25-120000-session.md"
            path.write_text("---\nnext: null\n---\n\n# Session\n", encoding="utf-8")

            result = evaluate_session_gate(
                str(vault),
                str(tmp),
                now=now,
                current_branch="feature/demo",
            )

            self.assertTrue(result.active)

    def test_denies_when_no_open_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "AI_Codex"
            sessions = vault / "Agent_Sessions"
            now = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
            self._write_session(
                sessions,
                "2026-07-25T15-00-00.md",
                branch="feature/demo",
                timestamp="2026-07-25T15:00:00+00:00",
                open_session=False,
            )

            result = evaluate_session_gate(
                str(vault),
                str(tmp),
                now=now,
                current_branch="feature/demo",
            )

            self.assertFalse(result.active)
            self.assertIn("initialize", (result.reason or "").lower())


if __name__ == "__main__":
    unittest.main()
