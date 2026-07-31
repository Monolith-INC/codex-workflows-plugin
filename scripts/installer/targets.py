from __future__ import annotations

from enum import Enum
from pathlib import Path


class Target(str, Enum):
    CODEX = "codex"
    GEMINI = "gemini"
    ANTIGRAVITY = "antigravity"
    ANTIGRAVITY_CLI = "antigravity-cli"
    CLAUDE = "claude"
    CURSOR = "cursor"
    UNIVERSAL = "universal"
    ALL_AGENTS = "all-agents"


def normalize_target(target: str | Target) -> Target:
    if isinstance(target, Target):
        return target
    normalized = target.strip().lower().replace("_", "-")
    for candidate in Target:
        if candidate.value == normalized:
            return candidate
    raise ValueError(f"Unsupported installer target: {target}")


def target_config_paths(target: str | Target) -> tuple[str, ...]:
    """Project-relative config paths written when --dest is given."""
    normalized = normalize_target(target)
    if normalized == Target.CODEX:
        # Codex project layer loads ``<project>/.codex/hooks.json`` (not repo-root
        # ``hooks/hooks.json``, which remains the marketplace plugin default).
        return (".codex/hooks.json",)
    if normalized == Target.GEMINI:
        return (".gemini/settings.json",)
    if normalized == Target.ANTIGRAVITY:
        return (".agents/hooks.json",)
    if normalized == Target.ANTIGRAVITY_CLI:
        return (".gemini/antigravity-cli/settings.json",)
    if normalized == Target.CLAUDE:
        return (".claude/settings.json",)
    if normalized == Target.CURSOR:
        return (".cursor/hooks.json",)
    if normalized in {Target.UNIVERSAL, Target.ALL_AGENTS}:
        return ()
    return ()


def target_global_config_path(target: str | Target) -> Path | None:
    """Deprecated: former machine-global hook path helper.

    Project-only install wires via ``target_config_paths`` under ``--dest``.
    Kept for optional legacy purge scans when ``dest`` is omitted.
    """
    home = Path.home()
    normalized = normalize_target(target)
    if normalized == Target.CLAUDE:
        return home / ".claude" / "settings.json"
    if normalized == Target.CURSOR:
        return home / ".cursor" / "hooks.json"
    if normalized == Target.GEMINI:
        return home / ".gemini" / "settings.json"
    if normalized == Target.CODEX:
        return home / ".gemini" / "config" / "hooks.json"
    if normalized == Target.ANTIGRAVITY:
        return _discover_antigravity_hooks(home)
    if normalized == Target.ANTIGRAVITY_CLI:
        return home / ".gemini" / "antigravity-cli" / "settings.json"
    return None


def _discover_antigravity_hooks(home: Path) -> Path | None:
    """Locate the Antigravity IDE install dir and return its .agents/hooks.json path."""
    candidates = [
        home / "Antigravity_IDE",
        home / "antigravity-ide",
        home / ".local" / "share" / "Antigravity_IDE",
        Path("/opt/Antigravity_IDE"),
        Path("/opt/antigravity"),
    ]
    for candidate in candidates:
        if (candidate / "antigravity-ide").is_file() or (candidate / ".agents").is_dir():
            return candidate / ".agents" / "hooks.json"
    return None


def target_hook_command(target: str | Target) -> str | None:
    normalized = normalize_target(target)
    if normalized == Target.CODEX:
        return "python3 skills/codex_workflows/scripts/codex_enforce_hook.py"
    if normalized == Target.GEMINI:
        return "python3 skills/codex_workflows/scripts/gemini_enforce_hook.py"
    if normalized == Target.ANTIGRAVITY:
        return "python3 skills/codex_workflows/scripts/antigravity_enforce_hook.py"
    if normalized == Target.ANTIGRAVITY_CLI:
        return "python3 skills/codex_workflows/scripts/antigravity_enforce_hook.py"
    if normalized == Target.CLAUDE:
        return "python3 skills/codex_workflows/scripts/claude_enforce_hook.py"
    if normalized == Target.CURSOR:
        return "python3 skills/codex_workflows/scripts/cursor_enforce_hook.py"
    return None
