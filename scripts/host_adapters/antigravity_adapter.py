from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_antigravity_payload(
    payload: dict[str, Any], *, project_root: str, **_ignored: Any
) -> CanonicalToolEvent:
    tool_call = payload.get("toolCall") or {}
    args = tool_call.get("args") or {}
    tool_name = tool_call.get("name") or ""
    command = args.get("CommandLine") or args.get("command")
    file_path = (
        args.get("AbsolutePath")
        or args.get("TargetFile")
        or args.get("path")
        or args.get("file")
    )
    return CanonicalToolEvent(
        client="antigravity",
        tool_name=tool_name,
        command=command,
        file_path=file_path,
        workspace_root=project_root,
    )


def format_antigravity_decision(decision: PolicyDecision) -> dict[str, Any]:
    response = {
        "decision": "deny" if decision.is_denied() else "allow",
    }
    if decision.reason:
        response["reason"] = decision.reason
    return response
