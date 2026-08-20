from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_codex_payload(payload: dict[str, Any], *, project_root: str, **_ignored: Any) -> CanonicalToolEvent:
    tool_name = payload.get("tool_name") or payload.get("tool") or payload.get("name") or ""
    arguments = payload.get("tool_input") or payload.get("arguments") or payload.get("args") or {}
    command = arguments.get("command") or arguments.get("CommandLine")
    file_path = arguments.get("AbsolutePath") or arguments.get("TargetFile") or arguments.get("path") or arguments.get("file")
    return CanonicalToolEvent(
        client="codex",
        tool_name=tool_name,
        command=command,
        file_path=file_path,
        workspace_root=project_root,
    )


def format_codex_decision(decision: PolicyDecision) -> dict[str, Any]:
    if not decision.is_denied():
        return {}

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": decision.reason,
        }
    }
