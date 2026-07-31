from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import zipfile
from typing import Iterable


def build_release_package(*, repo_root: Path, output_dir: Path) -> Path:
    manifest_path = repo_root / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package_name = manifest["name"]
    version = manifest["version"]

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{package_name}-{version}.zip"

    included_files = sorted(_iter_release_files(repo_root))

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in included_files:
            archive.write(file_path, file_path.relative_to(repo_root).as_posix())

        archive.writestr(
            "release-manifest.json",
            json.dumps(
                {
                    "package_name": package_name,
                    "version": version,
                    "generated_at": datetime.now().isoformat(),
                    "included_files": [path.relative_to(repo_root).as_posix() for path in included_files],
                },
                indent=2,
                sort_keys=True,
            ),
        )

    return archive_path


def _iter_release_files(repo_root: Path) -> Iterable[Path]:
    allow_dirs = [
        repo_root / ".codex-plugin",
        repo_root / ".claude-plugin",
        repo_root / ".cursor-plugin",
        repo_root / "commands",
        repo_root / "hooks",
        repo_root / "skills",
        repo_root / "scripts",
        repo_root / "docs" / "adr",
    ]
    allow_files = {
        repo_root / "README.md",
        repo_root / "install.sh",
        repo_root / ".mcp.json",
        repo_root / "docs" / "roadmap.md",
        repo_root / "AI_Codex" / "README.md",
    }

    for file_path in allow_files:
        if file_path.exists() and file_path.is_file():
            yield file_path

    for directory in allow_dirs:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a versioned release archive for codex-workflows-plugin.")
    parser.add_argument("--repo-root", default=".", help="Repository root to package")
    parser.add_argument("--output-dir", default="dist", help="Directory where the archive should be written")
    args = parser.parse_args()

    archive_path = build_release_package(
        repo_root=Path(args.repo_root).resolve(),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
