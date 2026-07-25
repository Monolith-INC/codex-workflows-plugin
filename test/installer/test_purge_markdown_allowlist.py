import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.installer.purge_markdown_allowlist import (
    purge_markdown_allowlist_artifacts,
    scan_markdown_allowlist_artifacts,
)


PLUGIN_ROOT = Path(__file__).parent.parent.parent


class TestPurgeMarkdownAllowlist(unittest.TestCase):
    def test_scan_and_purge_strips_hooks_and_removes_allowlist_config(self):
        with tempfile.TemporaryDirectory() as temp_home:
            home = Path(temp_home)
            project = home / "project"
            claude_dir = home / ".claude"
            claude_dir.mkdir(parents=True)
            project_claude = project / ".claude"
            project_claude.mkdir(parents=True)

            settings = claude_dir / "settings.json"
            settings.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {
                                    "matcher": ".*",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 /tmp/codex_enforce_hook.py",
                                        }
                                    ],
                                }
                            ]
                        },
                        "keep": True,
                    }
                ),
                encoding="utf-8",
            )

            allowlist_config = project_claude / "codex-workflow.config.json"
            allowlist_config.write_text(
                json.dumps(
                    {
                        "codex": {"folder": "AI_Codex"},
                        "markdownAllowlist": {"patterns": ["README.md"]},
                    }
                ),
                encoding="utf-8",
            )

            scan = scan_markdown_allowlist_artifacts(dest=project, home=home)
            self.assertTrue(scan.found_legacy)
            self.assertIn(settings, scan.hooks_with_managed_entries)
            self.assertIn(allowlist_config, scan.allowlist_configs_found)
            self.assertTrue(settings.exists())
            self.assertTrue(allowlist_config.exists())

            purged = purge_markdown_allowlist_artifacts(dest=project, home=home, dry_run=False)
            self.assertIn(settings, purged.hooks_stripped)
            self.assertIn(allowlist_config, purged.allowlist_configs_removed)
            self.assertFalse(allowlist_config.exists())

            remaining = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(remaining.get("keep"), True)
            blob = json.dumps(remaining)
            self.assertNotIn("codex_enforce_hook.py", blob)

    def test_bootstrap_purge_allowlist_scan_only(self):
        with tempfile.TemporaryDirectory() as temp_home:
            home = Path(temp_home)
            claude_dir = home / ".claude"
            claude_dir.mkdir(parents=True)
            settings = claude_dir / "settings.json"
            settings.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {
                                    "matcher": ".*",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 cursor_enforce_hook.py",
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.installer.bootstrap",
                    "--purge-allowlist",
                    "--scan-only",
                ],
                cwd=PLUGIN_ROOT,
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("managed enforce hook", result.stdout.lower())
            self.assertTrue(settings.exists())
            self.assertIn("cursor_enforce_hook.py", settings.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
