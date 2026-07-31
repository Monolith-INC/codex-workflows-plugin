"""Tests for the interactive installer wizard."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.installer.interactive as interactive_mod
from scripts.installer.interactive import (
    WizardAnswers,
    WizardIO,
    collect_answers,
    detect_software_project,
    run_wizard,
    verify_install,
)


class TestDetectSoftwareProject(unittest.TestCase):
    def test_detects_common_markers(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            (root / "package.json").write_text("{}", encoding="utf-8")
            ok, markers = detect_software_project(root)
            self.assertTrue(ok)
            self.assertIn("package.json", markers)

    def test_empty_directory_is_not_a_project(self):
        with tempfile.TemporaryDirectory() as dest:
            ok, markers = detect_software_project(Path(dest))
            self.assertFalse(ok)
            self.assertEqual(markers, [])


class TestCollectAnswers(unittest.TestCase):
    def test_uses_cwd_when_user_accepts_detected_project(self):
        responses = iter(
            [
                "install",  # mode
                "y",  # use cwd
                "1",  # all-agents
                "y",  # proceed
            ]
        )

        def ask(prompt, default=None):
            return next(responses)

        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            io_ = WizardIO(stdin=io.StringIO(), stdout=io.StringIO(), ask=ask)
            answers = collect_answers(io_, cwd=root)
            self.assertEqual(answers.dest, root.resolve())
            self.assertEqual(answers.target, "all-agents")
            self.assertFalse(answers.uninstall)


class TestVerifyInstall(unittest.TestCase):
    def test_reports_missing_runtime_as_remediable(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            (root / ".git").mkdir()
            checks = verify_install(root, "claude")
            by_name = {check.name: check for check in checks}
            self.assertFalse(by_name["runtime-dir"].ok)
            self.assertTrue(by_name["runtime-dir"].remediable)
            self.assertEqual(by_name["runtime-dir"].remedy_key, "rewire")

    def test_passes_core_paths_after_bootstrap_wire(self):
        from scripts.installer.bootstrap import install_from_source, wire

        plugin_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            (root / ".git").mkdir()
            runtime = root / ".codex-workflows"
            install_from_source(plugin_root, runtime)
            self.assertEqual(wire(runtime, "claude", root), 0)
            checks = verify_install(root, "claude")
            failed = [check.name for check in checks if not check.ok and check.name != "python-version"]
            self.assertEqual(failed, [], failed)


class TestWizardRemediation(unittest.TestCase):
    def test_success_path_runs_verification_without_retry_prompt(self):
        responses = []

        def ask(prompt, default=None):
            responses.append(prompt)
            if default is not None:
                return default
            return "y"

        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            (root / ".git").mkdir()
            runtime = root / ".codex-workflows"
            runtime.mkdir()
            (runtime / "skills" / "codex_workflows" / "scripts").mkdir(parents=True)
            (runtime / "skills" / "codex_workflows" / "scripts" / "claude_enforce_hook.py").write_text(
                "# hook\n", encoding="utf-8"
            )
            (runtime / "scripts" / "orchestrator").mkdir(parents=True)
            (runtime / "scripts" / "__init__.py").write_text("", encoding="utf-8")
            (runtime / "scripts" / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
            (runtime / "scripts" / "orchestrator" / "mcp_server.py").write_text(
                "def main():\n    return None\n", encoding="utf-8"
            )
            (root / ".claude").mkdir()
            (root / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
            (root / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "agentic-orchestrator": {
                                "command": "python3",
                                "args": ["-m", "scripts.orchestrator.mcp_server"],
                                "env": {
                                    "PYTHONPATH": str(runtime.resolve()),
                                    "ORCHESTRATOR_SKILLS_DIR": str((runtime / "skills").resolve()),
                                },
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (root / ".cursor").mkdir()
            (root / ".cursor" / "mcp.json").write_text(
                json.dumps({"mcpServers": {"agentic-orchestrator": {"command": "python3"}}}),
                encoding="utf-8",
            )
            (root / ".claude" / "settings.local.json").write_text(
                json.dumps(
                    {
                        "enableAllProjectMcpServers": True,
                        "enabledMcpjsonServers": ["agentic-orchestrator"],
                    }
                ),
                encoding="utf-8",
            )

            # Avoid hard-failing this suite on hosts still running Python 3.10.
            checks_by_name = {check.name: check for check in verify_install(root, "claude")}
            for name, check in checks_by_name.items():
                if name == "python-version":
                    continue
                self.assertTrue(check.ok, f"{name}: {check.detail}")

            io_ = WizardIO(stdin=io.StringIO(), stdout=io.StringIO(), ask=ask)
            with mock.patch.object(
                interactive_mod,
                "collect_answers",
                return_value=WizardAnswers(dest=root, target="claude"),
            ), mock.patch.object(interactive_mod, "run_bootstrap", return_value=0), mock.patch.object(
                interactive_mod,
                "verify_install",
                return_value=[
                    interactive_mod.CheckResult(name="python3", ok=True, detail="ok"),
                    interactive_mod.CheckResult(name="runtime-dir", ok=True, detail="ok"),
                ],
            ):
                code = run_wizard(zip_path=None, cwd=root, io=io_)
            self.assertEqual(code, 0)
            self.assertIn("All checks passed.", io_.stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
