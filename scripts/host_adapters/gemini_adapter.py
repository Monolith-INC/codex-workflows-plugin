from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_gemini_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    tool_name = (
        payload.get("tool_name") or payload.get("tool") or payload.get("name") or ""
    )
    arguments = (
        payload.get("tool_input")
        or payload.get("arguments")
        or payload.get("args")
        or {}
    )
    command = arguments.get("command") or arguments.get("CommandLine")
    file_path = (
        arguments.get("AbsolutePath")
        or arguments.get("TargetFile")
        or arguments.get("path")
        or arguments.get("file")
    )
    return CanonicalToolEvent(
        client="gemini",
        tool_name=tool_name,
        command=command,
        file_path=file_path,
        workspace_root=project_root,
    )


def format_gemini_decision(decision: PolicyDecision) -> dict[str, Any]:
    response = {
        "decision": "deny" if decision.is_denied() else "allow",
    }
    if decision.reason:
        response["reason"] = decision.reason
    return response
