import json
import tempfile
import unittest
import zipfile
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
                self.assertIn(".codex-plugin/plugin.json", names)
                self.assertIn(".claude-plugin/plugin.json", names)
                self.assertIn(".cursor-plugin/plugin.json", names)
                self.assertIn(".mcp.json", names)
                self.assertIn("hooks/hooks-cursor.json", names)
                self.assertIn("install.sh", names)
                self.assertTrue(any(name.startswith("commands/") for name in names))
                self.assertIn("release-manifest.json", names)
                manifest = json.loads(archive.read("release-manifest.json").decode("utf-8"))
                self.assertEqual(manifest["package_name"], "codex-workflows-plugin")
                self.assertIn("version", manifest)


if __name__ == "__main__":
    unittest.main()
