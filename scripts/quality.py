"""Run the repository's deterministic check or safe autofix workflow."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def _run_fix(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=False)


def check() -> None:
    _run(sys.executable, "scripts/validate_plugin.py", ".")
    _run(sys.executable, "-m", "ruff", "check", "scripts", "test")
    _run(sys.executable, "-m", "ruff", "format", "--check", "scripts", "test")
    _run(sys.executable, "-m", "mypy")
    _run(
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "test",
        "-t",
        ".",
        "-p",
        "test_*.py",
    )
    _run("npm", "run", "lint:markdown")


def fix() -> None:
    _run_fix(sys.executable, "-m", "ruff", "check", "--fix", "scripts", "test")
    _run(sys.executable, "-m", "ruff", "format", "scripts", "test")
    _run_fix("npm", "run", "fix:markdown")
    check()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository quality gates.")
    parser.add_argument("mode", choices=("check", "fix"), nargs="?", default="check")
    args = parser.parse_args()
    if args.mode == "fix":
        fix()
    else:
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
