import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.orchestrator import handlers
from scripts.orchestrator.engine import OrchestratorEngine
from scripts.orchestrator.failures import PolicyDenied
from scripts.orchestrator.invocation import HandlerResult
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

    def test_start_ticket_orchestrator_enforces_active_ticket_policy(self):
        start_dir = self.skills_dir / "start-ticket"
        start_dir.mkdir()
        (start_dir / "manifest.json").write_text(
            (Path(__file__).parent.parent / "skills" / "start-ticket" / "manifest.json").read_text(),
            encoding="utf-8",
        )
        (start_dir / "SKILL.md").write_text("# start-ticket\n", encoding="utf-8")

        vault = "AI_Codex"
        active_dir = Path(self.tempdir.name) / "project" / vault / "Tickets" / "Active"
        active_dir.mkdir(parents=True)
        (active_dir / "task-999.md").write_text("existing\n", encoding="utf-8")

        with mock.patch.dict(
            os.environ,
            {"CODEX_PROJECT_ROOT": str(Path(self.tempdir.name) / "project"), "CODEX_VAULT_FOLDER": vault},
        ):
            engine = OrchestratorEngine(self.skills_dir)
            result = engine.run_tool_call("start-ticket", {"ticket_id": "task-123"})
        self.assertFalse(result.ok)
        self.assertIn("already an active ticket", result.error or "")

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

    def test_engine_uses_an_explicit_semantic_evaluator(self):
        observed = []

        def evaluator(output, manifest):
            observed.append((output["skill"], manifest["name"]))
            return []

        engine = OrchestratorEngine(
            self.skills_dir, semantic_evaluator=evaluator
        )
        result = engine.run_tool_call("mock-skill", {"arg1": "value"})

        self.assertTrue(result.ok, result.error)
        self.assertEqual(observed, [("mock-skill", "mock-skill")])

    def test_identical_retry_output_fails_fast(self):
        self._write_skill(
            "strict-skill",
            {
                "name": "strict-skill",
                "description": "Requires success flag",
                "input_schema": {
                    "type": "object",
                    "properties": {"context": {"type": "string"}},
                },
                "output_signature": {
                    "type": "object",
                    "required": ["success"],
                    "properties": {"success": {"type": "boolean"}},
                },
            },
            "# strict\n",
        )
        engine = OrchestratorEngine(self.skills_dir, max_retries=25)
        result = engine.run_tool_call("strict-skill", {"context": "preserved"})
        self.assertFalse(result.ok)
        self.assertIn("success", result.error or "")
        self.assertEqual(result.state, "Blocked_Requires_Review")
        self.assertEqual(result.output.get("attempt"), 2)
        self.assertEqual(
            result.output.get("reflection_critiques"),
            ["Missing required output property 'success'."],
        )
        self.assertIn("<reflection>", result.output.get("prompt", ""))
        self.assertIn(
            "Missing required output property 'success'.",
            result.output.get("prompt", ""),
        )
        self.assertIn('"context": "preserved"', result.output.get("prompt", ""))

    def _stub_skill(self, name: str) -> None:
        self._write_skill(
            name,
            {
                "name": name,
                "description": "stub",
                "input_schema": {"type": "object", "properties": {}},
                "output_signature": {"type": "object", "properties": {}},
            },
            f"# {name}\n",
        )

    def test_stall_detection_sees_an_attempt_nested_in_reflection(self):
        """Handlers report their attempt inside `reflection`, not at the top level."""
        seen = []

        def handler(invocation):
            seen.append(invocation)
            return HandlerResult(
                product={"mode": "instructions", "critiques": "still wrong"},
                reflection={"attempt": invocation.attempt + 1, "blocked": False},
            )

        self._stub_skill("nested-skill")
        engine = OrchestratorEngine(self.skills_dir, max_retries=50)
        with mock.patch.dict(handlers._HANDLERS, {"nested-skill": handler}):
            result = engine.run_tool_call("nested-skill", {})

        self.assertEqual(
            len(seen), 2, "a deterministic handler must halt on the second identical result"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def test_the_attempt_counter_never_enters_the_caller_arguments(self):
        seen = []

        def handler(invocation):
            seen.append((invocation.attempt, dict(invocation.arguments)))
            return HandlerResult(
                product={
                    "mode": "instructions",
                    "critiques": f"attempt {invocation.attempt} rejected",
                },
                reflection={"attempt": invocation.attempt + 1},
            )

        self._stub_skill("counting-skill")
        engine = OrchestratorEngine(self.skills_dir, max_retries=3)
        with mock.patch.dict(handlers._HANDLERS, {"counting-skill": handler}):
            engine.run_tool_call("counting-skill", {"context": "preserved"})

        self.assertEqual([attempt for attempt, _ in seen], [0, 1, 2])
        for _, arguments in seen:
            self.assertEqual(arguments, {"context": "preserved"})

    def test_a_caller_supplied_attempt_resumes_the_reflection_sequence(self):
        seen = []

        def handler(invocation):
            seen.append(invocation.attempt)
            return HandlerResult(
                product={
                    "mode": "instructions",
                    "critiques": f"attempt {invocation.attempt} rejected",
                }
            )

        self._stub_skill("resuming-skill")
        engine = OrchestratorEngine(self.skills_dir, max_retries=3)
        with mock.patch.dict(handlers._HANDLERS, {"resuming-skill": handler}):
            engine.run_tool_call("resuming-skill", {"attempt": 4})

        self.assertEqual(seen, [4, 5, 6])

    def test_a_strict_manifest_survives_every_retry(self):
        """Nothing the engine adds may violate a contract the manifest declared."""
        self._write_skill(
            "strict-arguments",
            {
                "name": "strict-arguments",
                "description": "declares exactly its inputs",
                "input_schema": {
                    "type": "object",
                    "properties": {"context": {"type": "string"}},
                    "additionalProperties": False,
                },
                "output_signature": {"type": "object", "properties": {}},
            },
            "# strict-arguments\n",
        )

        attempts = []

        def handler(invocation):
            attempts.append(invocation.attempt)
            # Vary the result so the run uses its whole retry budget rather than
            # halting on the stall check; every retry must satisfy the contract.
            return HandlerResult(
                product={
                    "mode": "instructions",
                    "critiques": f"attempt {invocation.attempt} rejected",
                }
            )

        engine = OrchestratorEngine(self.skills_dir, max_retries=3)
        with mock.patch.dict(handlers._HANDLERS, {"strict-arguments": handler}):
            result = engine.run_tool_call("strict-arguments", {"context": "value"})

        self.assertEqual(attempts, [0, 1, 2])
        self.assertNotIn("Unknown argument", result.error or "")

    def test_a_strict_output_signature_ignores_what_the_worker_adds(self):
        """The envelope is presentation; only the work is held to the contract."""
        self._write_skill(
            "strict-output",
            {
                "name": "strict-output",
                "description": "declares exactly its output",
                "input_schema": {"type": "object", "properties": {}},
                "output_signature": {
                    "type": "object",
                    "required": ["mode"],
                    "properties": {"mode": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
            "# strict-output\n",
        )

        def handler(invocation):
            return HandlerResult(
                product={"mode": "completed"},
                reflection={"attempt": invocation.attempt + 1},
            )

        engine = OrchestratorEngine(self.skills_dir, max_retries=2)
        with mock.patch.dict(handlers._HANDLERS, {"strict-output": handler}):
            result = engine.run_tool_call("strict-output", {})

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.output["attempt"], 1)
        self.assertEqual(result.output["reflection"], {"attempt": 1})
        self.assertIn("prompt", result.output)

    def test_a_declared_deterministic_failure_halts_at_once(self):
        """A failure that says it will repeat is not retried at all."""
        raised = []

        def handler(invocation):
            raised.append(invocation.attempt)
            raise PolicyDenied("there is already an active ticket")

        self._stub_skill("refusing-skill")
        engine = OrchestratorEngine(self.skills_dir, max_retries=25)
        with mock.patch.dict(handlers._HANDLERS, {"refusing-skill": handler}):
            result = engine.run_tool_call("refusing-skill", {})

        self.assertEqual(raised, [0])
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "there is already an active ticket")
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def test_an_unclassified_failure_keeps_its_retry_budget(self):
        """Unknown failures are assumed transient: waste work, never abort early."""
        raised = []

        def handler(invocation):
            raised.append(invocation.attempt)
            raise ValueError("connection reset")

        self._stub_skill("flaky-skill")
        engine = OrchestratorEngine(self.skills_dir, max_retries=3)
        with mock.patch.dict(handlers._HANDLERS, {"flaky-skill": handler}):
            result = engine.run_tool_call("flaky-skill", {})

        self.assertEqual(raised, [0, 1, 2])
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def test_a_missing_skill_asset_halts_at_once(self):
        skill_dir = self.skills_dir / "no-instructions"
        skill_dir.mkdir()
        (skill_dir / "manifest.json").write_text(
            json.dumps({"name": "no-instructions"}), encoding="utf-8"
        )

        engine = OrchestratorEngine(self.skills_dir, max_retries=25)
        result = engine.run_tool_call("no-instructions", {})

        self.assertFalse(result.ok)
        self.assertIn("Missing SKILL.md", result.error or "")
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def test_a_handler_protocol_violation_halts_immediately(self):
        """Retrying the same code cannot fix the code."""
        calls = []

        def handler(invocation):
            calls.append(invocation.attempt)
            return {"mode": "completed"}

        self._stub_skill("legacy-shape")
        engine = OrchestratorEngine(self.skills_dir, max_retries=25)
        with mock.patch.dict(handlers._HANDLERS, {"legacy-shape": handler}):
            result = engine.run_tool_call("legacy-shape", {})

        self.assertEqual(calls, [0])
        self.assertFalse(result.ok)
        self.assertIn("must return a HandlerResult", result.error or "")
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def test_the_policy_denial_runs_the_handler_once(self):
        start_dir = self.skills_dir / "start-ticket"
        start_dir.mkdir()
        (start_dir / "manifest.json").write_text(
            (Path(__file__).parent.parent / "skills" / "start-ticket" / "manifest.json").read_text(),
            encoding="utf-8",
        )
        (start_dir / "SKILL.md").write_text("# start-ticket\n", encoding="utf-8")

        vault = "AI_Codex"
        active_dir = Path(self.tempdir.name) / "project" / vault / "Tickets" / "Active"
        active_dir.mkdir(parents=True)
        (active_dir / "task-999.md").write_text("existing\n", encoding="utf-8")

        attempts = []
        real = handlers.handle_start_ticket

        def counting(invocation):
            attempts.append(invocation.attempt)
            return real(invocation)

        with mock.patch.dict(
            os.environ,
            {
                "CODEX_PROJECT_ROOT": str(Path(self.tempdir.name) / "project"),
                "CODEX_VAULT_FOLDER": vault,
            },
        ):
            with mock.patch.dict(handlers._HANDLERS, {"start-ticket": counting}):
                engine = OrchestratorEngine(self.skills_dir)
                result = engine.run_tool_call("start-ticket", {"ticket_id": "task-123"})

        self.assertEqual(attempts, [0])
        self.assertFalse(result.ok)
        self.assertIn("already an active ticket", result.error or "")

    def test_an_unconditional_approver_still_terminates(self):
        """An approval restores the retry budget, so the hook has to bound them."""
        seen: list[int] = []

        def handler(invocation):
            seen.append(invocation.attempt)
            return HandlerResult(
                product={"mode": "instructions", "critiques": "identical every time"}
            )

        self._stub_skill("looping-skill")
        engine = OrchestratorEngine(
            self.skills_dir, max_retries=50, interactive=True, quiet=True
        )
        with mock.patch.dict(handlers._HANDLERS, {"looping-skill": handler}):
            with mock.patch(
                "builtins.input", return_value="IMPLEMENTATION APPROVED"
            ) as prompted:
                with contextlib.redirect_stderr(io.StringIO()):
                    result = engine.run_tool_call("looping-skill", {})

        self.assertEqual(prompted.call_count, 1, "one approval is honored by default")
        self.assertFalse(result.ok)
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def test_the_approval_budget_is_configurable(self):
        def handler(invocation):
            return HandlerResult(
                product={"mode": "instructions", "critiques": "identical every time"}
            )

        self._stub_skill("twice-approved")
        engine = OrchestratorEngine(
            self.skills_dir,
            max_retries=50,
            max_approvals=2,
            interactive=True,
            quiet=True,
        )
        with mock.patch.dict(handlers._HANDLERS, {"twice-approved": handler}):
            with mock.patch(
                "builtins.input", return_value="IMPLEMENTATION APPROVED"
            ) as prompted:
                with contextlib.redirect_stderr(io.StringIO()):
                    result = engine.run_tool_call("twice-approved", {})

        self.assertEqual(prompted.call_count, 2)
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def _skill_declaring_mode(self, name: str) -> None:
        self._write_skill(
            name,
            {
                "name": name,
                "description": "declares mode as its result",
                "input_schema": {"type": "object", "properties": {}},
                "output_signature": {
                    "type": "object",
                    "required": ["mode"],
                    "properties": {"mode": {"type": "string"}},
                },
            },
            f"# {name}\n",
        )

    def _run_until_settled(self, name: str, product_for) -> int:
        calls = []

        def handler(invocation):
            calls.append(invocation.attempt)
            return HandlerResult(product=product_for(len(calls)))

        engine = OrchestratorEngine(self.skills_dir, max_retries=25)
        with mock.patch.dict(handlers._HANDLERS, {name: handler}):
            engine.run_tool_call(name, {})
        return len(calls)

    def test_an_undeclared_field_cannot_defeat_stall_detection(self):
        """A value that changes without being part of the result is not progress."""
        self._skill_declaring_mode("declared-skill")
        invocations = self._run_until_settled(
            "declared-skill",
            lambda n: {
                "mode": "instructions",
                "critiques": "identical every time",
                "history": list(range(n)),
            },
        )
        self.assertEqual(invocations, 2)

    def test_a_declared_field_advancing_keeps_the_run_going(self):
        """The narrowing must not halt work that is still moving."""
        self._skill_declaring_mode("advancing-skill")
        invocations = self._run_until_settled(
            "advancing-skill",
            lambda n: {"mode": f"step-{n}", "critiques": "identical every time"},
        )
        self.assertEqual(invocations, 25)

    def test_a_manifest_declaring_no_output_compares_everything(self):
        """With no contract to narrow to, the conservative comparison stands."""
        self._stub_skill("undeclared-skill")
        invocations = self._run_until_settled(
            "undeclared-skill",
            lambda n: {
                "mode": "instructions",
                "critiques": "identical every time",
                "history": list(range(n)),
            },
        )
        self.assertEqual(invocations, 25)

    def test_a_recorded_mistake_cannot_mask_a_write_spec_stall(self):
        """`mistakes` grows mid-run and is undeclared, so it is not progress."""
        repo_skills = Path(__file__).parent.parent / "skills"
        write_spec_dir = self.skills_dir / "write-spec"
        write_spec_dir.mkdir(parents=True)
        for name in ("manifest.json", "SKILL.md"):
            (write_spec_dir / name).write_text(
                (repo_skills / "write-spec" / name).read_text(), encoding="utf-8"
            )

        sizes = []
        real = handlers.handle_write_spec

        def watching(invocation):
            result = real(invocation)
            sizes.append(len(result.product.get("mistakes", [])))
            return result

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CODEX_PROJECT_ROOT": tmp}):
                with mock.patch.dict(handlers._HANDLERS, {"write-spec": watching}):
                    engine = OrchestratorEngine(self.skills_dir, max_retries=50)
                    result = engine.run_tool_call(
                        "write-spec",
                        {
                            "ticket_id": "T-1",
                            "spec_kind": "tech-spec",
                            "draft_content": "TODO: fill this in later",
                            "max_attempts": 1,
                        },
                    )

        self.assertEqual(sizes, [0, 1], "the mistakes list must grow between attempts")
        self.assertEqual(len(sizes), 2, "the growth must not postpone the halt")
        self.assertFalse(result.ok)
        self.assertEqual(result.state, "Blocked_Requires_Review")

    def test_an_operator_approval_resumes_a_halted_run(self):
        stalled = {"mode": "instructions", "critiques": "identical every time"}
        scripted = [stalled, stalled, {"mode": "completed"}]
        seen: list[int] = []

        def handler(invocation):
            index = len(seen)
            seen.append(index)
            return HandlerResult(product=scripted[min(index, len(scripted) - 1)])

        self._stub_skill("approved-skill")
        engine = OrchestratorEngine(
            self.skills_dir, max_retries=50, interactive=True, quiet=True
        )
        with mock.patch.dict(handlers._HANDLERS, {"approved-skill": handler}):
            with mock.patch("builtins.input", return_value="IMPLEMENTATION APPROVED"):
                with contextlib.redirect_stderr(io.StringIO()):
                    result = engine.run_tool_call("approved-skill", {})

        self.assertEqual(len(seen), 3, "the approved task must run again")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.state, "Completed")

    def test_a_denied_approval_leaves_the_task_blocked(self):
        seen: list = []

        def handler(invocation):
            seen.append(None)
            return HandlerResult(
                product={"mode": "instructions", "critiques": "identical every time"}
            )

        self._stub_skill("denied-skill")
        engine = OrchestratorEngine(
            self.skills_dir, max_retries=50, interactive=True, quiet=True
        )
        with mock.patch.dict(handlers._HANDLERS, {"denied-skill": handler}):
            with mock.patch("builtins.input", return_value="no"):
                with contextlib.redirect_stderr(io.StringIO()):
                    result = engine.run_tool_call("denied-skill", {})

        self.assertEqual(len(seen), 2)
        self.assertFalse(result.ok)
        self.assertEqual(result.state, "Blocked_Requires_Review")

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
        self.assertEqual(payload["output"]["mode"], "instructions")
        self.assertEqual(payload["output"]["inputs"]["arg1"], "hello")
        self.assertIn("Do the thing.", payload["output"]["prompt"])
        self.assertEqual(payload["output"]["attempt"], 1)
        self.assertNotIn("reflection_critiques", payload["output"])

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
