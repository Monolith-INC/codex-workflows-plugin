import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.orchestrator.engine import OrchestratorEngine
from scripts.orchestrator.mcp_server import process_message


class TestOrchestratorEngineE2E(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self.tempdir.name)
        self._write_skill(
            "mock-skill",
            {
                "name": "mock-skill",
                "description": "A mock skill for testing",
                "input_schema": {
                    "type": "object",
                    "properties": {"arg1": {"type": "string"}},
                    "required": ["arg1"],
                },
                "output_signature": {"type": "object", "properties": {}},
            },
            "# Mock skill\n\nDo the thing.\n",
        )
        self.engine = OrchestratorEngine(self.skills_dir, max_retries=2)

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_skill(self, name: str, manifest: dict, skill_md: str) -> None:
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    def test_start_ticket_handler_returns_ledger_path(self):
        start_dir = self.skills_dir / "start-ticket"
        start_dir.mkdir()
        (start_dir / "manifest.json").write_text(
            (Path(__file__).parent.parent / "skills" / "start-ticket" / "manifest.json").read_text(),
            encoding="utf-8",
        )
        (start_dir / "SKILL.md").write_text("# start-ticket\n", encoding="utf-8")

        engine = OrchestratorEngine(self.skills_dir)
        result = engine.run_tool_call("start-ticket", {"ticket_id": "6871"})
        self.assertTrue(result.ok, result.error)
        self.assertIn("active_ledger_path", result.output or {})
        self.assertIn("6871", result.output["active_ledger_path"])

    def test_missing_required_argument_fails_fast(self):
        result = self.engine.run_tool_call("mock-skill", {})
        self.assertFalse(result.ok)
        self.assertIn("Missing required argument 'arg1'", result.error or "")

    def test_instruction_skill_returns_prompt(self):
        result = self.engine.run_tool_call("mock-skill", {"arg1": "value"})
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.output.get("mode"), "instructions")
        self.assertIn("prompt", result.output)
        self.assertIn("Do the thing.", result.output["prompt"])
        self.assertEqual(result.output.get("attempt"), 1)

    def test_identical_retry_output_fails_fast(self):
        self._write_skill(
            "strict-skill",
            {
                "name": "strict-skill",
                "description": "Requires success flag",
                "input_schema": {"type": "object", "properties": {}},
                "output_signature": {
                    "type": "object",
                    "required": ["success"],
                    "properties": {"success": {"type": "boolean"}},
                },
            },
            "# strict\n",
        )
        engine = OrchestratorEngine(self.skills_dir, max_retries=2)
        result = engine.run_tool_call("strict-skill", {})
        self.assertFalse(result.ok)
        self.assertIn("success", result.error or "")

    def test_mcp_tools_call_round_trip(self):
        init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        listed = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        called = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "mock-skill", "arguments": {"arg1": "hello"}},
            }
        )

        init_res = json.loads(process_message(init, self.engine))
        list_res = json.loads(process_message(listed, self.engine))
        call_res = json.loads(process_message(called, self.engine))

        self.assertEqual(init_res["result"]["serverInfo"]["name"], "agentic-orchestrator")
        self.assertEqual(list_res["result"]["tools"][0]["name"], "mock-skill")
        payload = json.loads(call_res["result"]["content"][0]["text"])
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["output"]["inputs"]["arg1"], "hello")

    def test_write_spec_bad_draft_fails_orchestrator(self):
        repo_skills = Path(__file__).parent.parent / "skills"
        write_spec_dir = self.skills_dir / "write-spec"
        write_spec_dir.mkdir(parents=True)
        for name in ("manifest.json", "SKILL.md"):
            (write_spec_dir / name).write_text((repo_skills / "write-spec" / name).read_text(), encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_PROJECT_ROOT": tmp}):
                engine = OrchestratorEngine(self.skills_dir, max_retries=2)
                result = engine.run_tool_call(
                    "write-spec",
                    {
                        "ticket_id": "T-1",
                        "spec_kind": "tech-spec",
                        "draft_content": "TODO: fill this in later",
                    },
                )
                self.assertFalse(result.ok, result.error)
                self.assertIn("placeholder", (result.error or "").lower())

if __name__ == "__main__":
    unittest.main()
