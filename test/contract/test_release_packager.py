import json
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from scripts.release_packager import build_release_package


class TestReleasePackager(unittest.TestCase):
    def test_builds_versioned_release_archive_from_repo_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = build_release_package(
                repo_root=Path(".").resolve(),
                output_dir=Path(tmpdir),
            )

            self.assertTrue(archive_path.name.startswith("codex-workflows-plugin-"))
            self.assertTrue(archive_path.suffix == ".zip")

            with zipfile.ZipFile(archive_path, "r") as archive:
                names = set(archive.namelist())
                expected_files = {
                    "codex-workflows-plugin.json",
                    "install.sh",
                    ".markdownlint-cli2.jsonc",
                    "package.json",
                    "package-lock.json",
                    "pyproject.toml",
                    "requirements-dev.txt",
                    "release-manifest.json",
                }
                expected_prefixes = (
                    "commands/",
                    "docs/",
                    "scripts/",
                    "skills/",
                )
                self.assertTrue(expected_files <= names)
                self.assertTrue(
                    all(
                        name in expected_files
                        or name.startswith(expected_prefixes)
                        or name in {"README.md", "CHANGELOG.md"}
                        for name in names
                    )
                )
                manifest = json.loads(
                    archive.read("release-manifest.json").decode("utf-8")
                )
                self.assertEqual(manifest["package_name"], "codex-workflows-plugin")
                self.assertIn("version", manifest)
                self.assertIsNotNone(
                    datetime.fromisoformat(manifest["generated_at"]).tzinfo
                )
                self.assertIn(
                    "skills/codex_workflows/resources/templates/epic-template.md",
                    names,
                )


if __name__ == "__main__":
    unittest.main()
