import json
import unittest
from unittest import mock

from scripts import quality


class QualityConfigurationTests(unittest.TestCase):
    def test_markdown_lint_scope_and_structural_rules_are_repository_owned(self):
        config = json.loads(
            (quality.ROOT / ".markdownlint-cli2.jsonc").read_text(encoding="utf-8")
        )
        self.assertEqual(
            config["globs"],
            [
                "README.md",
                "CHANGELOG.md",
                "CLAUDE.md",
                ".github/**/*.md",
                "commands/**/*.md",
                "docs/**/*.md",
                "skills/**/*.md",
            ],
        )
        rules = config["config"]
        self.assertEqual(
            {name for name, value in rules.items() if value is False},
            {"MD013", "MD029", "MD033"},
        )
        self.assertNotIn("MD032", rules)

    def test_fix_runs_safe_autofixers_then_the_full_check(self):
        with (
            mock.patch.object(quality, "_run_fix") as run_fix,
            mock.patch.object(quality, "_run") as run,
            mock.patch.object(quality, "check") as check,
        ):
            quality.fix()

        self.assertEqual(
            run_fix.call_args_list,
            [
                mock.call(
                    quality.sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--fix",
                    "scripts",
                    "test",
                ),
                mock.call("npm", "run", "fix:markdown"),
            ],
        )
        run.assert_called_once_with(
            quality.sys.executable, "-m", "ruff", "format", "scripts", "test"
        )
        check.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
