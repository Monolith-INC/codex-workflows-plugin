"""Scan and purge legacy markdown-allowlist artifacts and managed enforce hooks.

The markdown allowlist policy was removed from the runtime. This module finds
leftover host hook entries and ``codex-workflow.config.json`` allowlist files,
strips/deletes them, and reports what it found so upgrades cannot keep blocking
agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cursor_hooks import strip_managed_cursor_hooks
from .targets import Target, target_config_paths, target_global_config_path
from .uninstall import strip_managed_hooks as strip_managed_hooks_deep

MANAGED_HOOK_SCRIPTS = {
    "codex_enforce_hook.py",
    "gemini_enforce_hook.py",
    "antigravity_enforce_hook.py",
    "claude_enforce_hook.py",
    "cursor_enforce_hook.py",
}

ALLOWLIST_CONFIG_NAME = "codex-workflow.config.json"
_ALLOWLIST_CONFIG_REL = Path(".claude") / ALLOWLIST_CONFIG_NAME
_LEGACY_DENY_MARKER = "Markdown files not in CLAUDE.md allowlist"


@dataclass
class PurgeReport:
    scanned_configs: list[Path] = field(default_factory=list)
    hooks_with_managed_entries: list[Path] = field(default_factory=list)
    hooks_stripped: list[Path] = field(default_factory=list)
    allowlist_configs_found: list[Path] = field(default_factory=list)
    allowlist_configs_removed: list[Path] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    @property
    def found_legacy(self) -> bool:
        return bool(self.hooks_with_managed_entries or self.allowlist_configs_found)


def scan_markdown_allowlist_artifacts(
    *,
    dest: Path | None = None,
    home: Path | None = None,
) -> PurgeReport:
    """Report managed enforce hooks and allowlist config files without changing disk."""
    return _run_purge(dest=dest, home=home, dry_run=True, strip_hooks=True)


def purge_markdown_allowlist_artifacts(
    *,
    dest: Path | None = None,
    home: Path | None = None,
    dry_run: bool = False,
) -> PurgeReport:
    """Strip managed enforce hooks from host configs and delete allowlist config files.

    Callers that want current (allowlist-free) hooks reinstalled should run the
    normal bootstrap ``wire()`` step afterward.
    """
    return _run_purge(dest=dest, home=home, dry_run=dry_run, strip_hooks=True)


def purge_allowlist_config_files(
    *,
    dest: Path | None = None,
    dry_run: bool = False,
    include_cwd: bool = False,
) -> PurgeReport:
    """Delete ``.claude/codex-workflow.config.json`` allowlist companions."""
    report = PurgeReport()
    for path in _allowlist_config_candidates(dest, include_cwd=include_cwd):
        report.scanned_configs.append(path)
        if not path.is_file():
            continue
        if not _is_allowlist_config(path):
            continue
        report.allowlist_configs_found.append(path)
        report.messages.append(f"Found allowlist config: {path}")
        if dry_run:
            continue
        try:
            path.unlink()
        except OSError as exc:
            report.messages.append(f"Could not remove allowlist config {path}: {exc}")
            continue
        report.allowlist_configs_removed.append(path)
        report.messages.append(f"Removed allowlist config: {path}")
    return report


def _run_purge(
    *,
    dest: Path | None,
    home: Path | None,
    dry_run: bool,
    strip_hooks: bool,
) -> PurgeReport:
    report = PurgeReport()
    home_root = (home or Path.home()).expanduser().resolve()

    config_paths = _hook_config_paths(dest=dest, home=home_root)
    for config_path in config_paths:
        report.scanned_configs.append(config_path)
        if not config_path.is_file():
            continue
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report.messages.append(f"Skipped unreadable config: {config_path}")
            continue
        if not isinstance(raw, dict):
            continue

        has_managed = _config_references_managed_hooks(raw)
        has_legacy_marker = _LEGACY_DENY_MARKER in json.dumps(raw)
        if has_managed or has_legacy_marker:
            report.hooks_with_managed_entries.append(config_path)
            report.messages.append(f"Found managed enforce hook config: {config_path}")

        if not strip_hooks or not has_managed:
            continue

        if config_path.name == "hooks.json" and ".cursor" in config_path.parts:
            cleaned = strip_managed_cursor_hooks(raw, MANAGED_HOOK_SCRIPTS)
        else:
            cleaned = strip_managed_hooks_deep(raw)

        if cleaned == raw:
            continue
        report.messages.append(f"{'Would strip' if dry_run else 'Stripped'} managed hooks: {config_path}")
        if dry_run:
            continue
        if _is_effectively_empty(cleaned):
            config_path.unlink()
            report.messages.append(f"Removed empty hook config: {config_path}")
        else:
            config_path.write_text(json.dumps(cleaned, indent=2) + "\n", encoding="utf-8")
        report.hooks_stripped.append(config_path)

    config_report = purge_allowlist_config_files(
        dest=dest,
        dry_run=dry_run,
        include_cwd=dest is None,
    )
    report.allowlist_configs_found.extend(config_report.allowlist_configs_found)
    report.allowlist_configs_removed.extend(config_report.allowlist_configs_removed)
    report.messages.extend(config_report.messages)
    return report


def _hook_config_paths(*, dest: Path | None, home: Path) -> list[Path]:
    """Return hook config paths to scan.

    When ``dest`` is set (project-only install), only project-relative configs are
    considered. Home/global paths are skipped.
    """
    paths: list[Path] = []
    for target in (
        Target.CODEX,
        Target.GEMINI,
        Target.ANTIGRAVITY,
        Target.ANTIGRAVITY_CLI,
        Target.CLAUDE,
        Target.CURSOR,
    ):
        if dest is not None:
            project_root = dest.expanduser().resolve()
            for relative in target_config_paths(target):
                paths.append(project_root / relative)
            continue

        # Legacy scan without --dest (kept for library callers / migration tools).
        if target == Target.CLAUDE:
            paths.append(home / ".claude" / "settings.json")
        elif target == Target.CURSOR:
            paths.append(home / ".cursor" / "hooks.json")
        elif target == Target.GEMINI:
            paths.append(home / ".gemini" / "settings.json")
        elif target == Target.CODEX:
            paths.append(home / ".gemini" / "config" / "hooks.json")
        elif target == Target.ANTIGRAVITY_CLI:
            paths.append(home / ".gemini" / "antigravity-cli" / "settings.json")
        else:
            discovered = target_global_config_path(target)
            if discovered is not None:
                paths.append(discovered)

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _allowlist_config_candidates(dest: Path | None, *, include_cwd: bool = False) -> list[Path]:
    candidates: list[Path] = []
    if dest is not None:
        candidates.append(dest.expanduser().resolve() / _ALLOWLIST_CONFIG_REL)
    if include_cwd:
        cwd_candidate = Path.cwd() / _ALLOWLIST_CONFIG_REL
        if cwd_candidate not in candidates:
            candidates.append(cwd_candidate)
    return candidates


def _is_allowlist_config(path: Path) -> bool:
    if path.name != ALLOWLIST_CONFIG_NAME:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    if not isinstance(data, dict):
        return True
    return "markdownAllowlist" in data or "markdown_allowlist" in data


def _config_references_managed_hooks(config: dict[str, Any]) -> bool:
    blob = json.dumps(config)
    return any(script in blob for script in MANAGED_HOOK_SCRIPTS)


def _is_effectively_empty(value: Any) -> bool:
    if value in ({}, []):
        return True
    if isinstance(value, dict):
        if set(value) <= {"version", "enabled"}:
            return True
        return all(_is_effectively_empty(child) for child in value.values())
    if isinstance(value, list):
        return all(_is_effectively_empty(child) for child in value)
    return False
