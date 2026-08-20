import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.orchestrator.invocation import Invocation
from scripts.orchestrator.handlers import handle_resolve_ticket


class TestResolveTicketHandler(unittest.TestCase):
    def test_resolve_ticket_directive_when_report_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_PROJECT_ROOT": tmp}):
                root = Path(tmp)
                spec_dir = root / "AI_Codex" / "Specs" / "feat-9"
                spec_dir.mkdir(parents=True)
                (spec_dir / "tech-spec.md").write_text("# Tech Spec\n", encoding="utf-8")
                result = handle_resolve_ticket(
                    Invocation(
                        arguments={"ticket_id": "FEAT-9"},
                        manifest={"name": "resolve-ticket"},
                        instructions="# resolve-ticket\n",
                    )
                )
                self.assertEqual(result.product["mode"], "instructions")
                self.assertTrue(result.product["resolution_required"])
                self.assertIsNotNone(result.product["resolve_directive"])
                self.assertIn("template", result.product)

    def test_resolve_ticket_critic_flags_thin_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_PROJECT_ROOT": tmp}):
                root = Path(tmp)
                spec_dir = root / "AI_Codex" / "Specs" / "feat-9"
                spec_dir.mkdir(parents=True)
                (spec_dir / "tech-spec.md").write_text("# Tech Spec\n", encoding="utf-8")
                result = handle_resolve_ticket(
                    Invocation(
                        arguments={
                            "ticket_id": "FEAT-9",
                            "draft_content": "too short",
                        },
                        manifest={"name": "resolve-ticket"},
                        instructions="# resolve-ticket\n",
                    )
                )
                self.assertTrue(result.product["critiques"])


if __name__ == "__main__":
    unittest.main()
