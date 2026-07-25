"""User-controlled ledger enforcement bypass (skip-ledger / resume-ledger)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

SKIP_FILENAME = ".codex_ledger_skip"


def skip_flag_path(vault_dir: str) -> Path:
    return Path(vault_dir) / SKIP_FILENAME


def is_ledger_skipped(vault_dir: str) -> bool:
    return skip_flag_path(vault_dir).is_file()


def enable_ledger_skip(vault_dir: str, *, reason: str = "user issued /skip-ledger") -> Path:
    path = skip_flag_path(vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    path.write_text(
        f"# Codex workflow ledger enforcement skipped\n"
        f"skipped_at: {stamp}\n"
        f"reason: {reason}\n"
        f"# Remove this file or run /resume-ledger to restore hooks.\n",
        encoding="utf-8",
    )
    return path


def disable_ledger_skip(vault_dir: str) -> bool:
    path = skip_flag_path(vault_dir)
    if not path.exists():
        return False
    path.unlink()
    return True
