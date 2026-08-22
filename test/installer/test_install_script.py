import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestInstallScript(unittest.TestCase):
    def _make_release_zip(self, directory: Path) -> Path:
        zip_path = directory / "codex-workflows-plugin-test.zip"
        bootstrap = """
from __future__ import annotations

import os
import sys
from pathlib import Path

Path(os.environ["CODEX_WORKFLOWS_TEST_ARGV_OUT"]).write_text("\\n".join(sys.argv[1:]), encoding="utf-8")
"""
        interactive = """
from __future__ import annotations

import os
import sys
from pathlib import Path

Path(os.environ["CODEX_WORKFLOWS_TEST_ARGV_OUT"]).write_text(
    "interactive\\n" + "\\n".join(sys.argv[1:]),
    encoding="utf-8",
)
"""
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("scripts/__init__.py", "")
            archive.writestr("scripts/installer/__init__.py", "")
            archive.writestr("scripts/installer/bootstrap.py", bootstrap)
            archive.writestr("scripts/installer/interactive.py", interactive)
        return zip_path

    def _run_install_script(
        self, *args: str, expect_success: bool = True
    ) -> tuple[list[str] | None, subprocess.CompletedProcess[str]]:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            zip_path = self._make_release_zip(root)
            argv_path = root / "argv.txt"
            env = {
                **os.environ,
                "CODEX_WORKFLOWS_RELEASE_ZIP": str(zip_path),
                "CODEX_WORKFLOWS_TEST_ARGV_OUT": str(argv_path),
            }

            result = subprocess.run(
                ["bash", str(REPO_ROOT / "install.sh"), *args],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )

            if expect_success:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return argv_path.read_text(encoding="utf-8").splitlines(), result
            return None, result

    def test_no_dest_launches_interactive_module(self):
        argv, result = self._run_install_script()
        self.assertIsNotNone(argv)
        self.assertEqual(argv[0], "interactive")
        self.assertTrue(argv[1] == "--zip")
        self.assertTrue(argv[2].endswith(".zip"))
        self.assertEqual(argv[3], "--cwd")
        self.assertEqual(argv[4], str(REPO_ROOT))
        self.assertNotIn("--dest", result.stdout + result.stderr)

    def test_defaults_to_all_agents_when_no_target_is_supplied(self):
        argv, _ = self._run_install_script("--dest", "/tmp/project")

        self.assertTrue(argv[0].endswith(".zip"))
        self.assertEqual(argv[1:], ["--target", "all-agents", "--dest", "/tmp/project"])

    def test_preserves_explicit_target(self):
        argv, _ = self._run_install_script(
            "--target", "claude", "--dest", "/tmp/project"
        )

        self.assertEqual(argv[1:], ["--target", "claude", "--dest", "/tmp/project"])

    def test_uninstall_does_not_add_default_target(self):
        argv, _ = self._run_install_script(
            "--uninstall", "--keep-runtime", "--dest", "/tmp/project"
        )

        self.assertEqual(
            argv[1:], ["--uninstall", "--keep-runtime", "--dest", "/tmp/project"]
        )

    def test_uses_gh_release_download_when_no_local_zip_is_supplied(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            argv_path = root / "argv.txt"
            calls_path = root / "gh-calls.txt"
            release_zip = self._make_release_zip(root)
            gh = fake_bin / "gh"
            gh.write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> {calls_path}
dest="."
while (($#)); do
  if [[ "$1" == "-D" ]]; then
    dest="$2"
    shift 2
    continue
  fi
  shift
done
cp {release_zip} "$dest/codex-workflows-plugin-test.zip"
""",
                encoding="utf-8",
            )
            gh.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "CODEX_WORKFLOWS_TEST_ARGV_OUT": str(argv_path),
            }

            result = subprocess.run(
                [
                    "bash",
                    str(REPO_ROOT / "install.sh"),
                    "--target",
                    "claude",
                    "--dest",
                    "/tmp/project",
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("release download", calls_path.read_text(encoding="utf-8"))
            self.assertEqual(
                argv_path.read_text(encoding="utf-8").splitlines()[1:],
                ["--target", "claude", "--dest", "/tmp/project"],
            )


if __name__ == "__main__":
    unittest.main()
