from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_claude_payload(payload: dict[str, Any], *, project_root: str, vault_dir: str) -> CanonicalToolEvent:
    tool_call = payload.get("toolCall") or payload.get("tool_call") or {}
    tool_input = tool_call.get("args") or tool_call.get("input") or payload.get("tool_input") or payload.get("arguments") or {}
    tool_name = tool_call.get("name") or payload.get("tool_name") or payload.get("tool") or payload.get("name") or ""
    command = tool_input.get("CommandLine") or tool_input.get("command")
    file_path = (
        tool_input.get("AbsolutePath")
        or tool_input.get("TargetFile")
        or tool_input.get("path")
        or tool_input.get("file")
        or tool_input.get("file_path")
    )
    source_path, destination_path = _parse_ticket_paths(command or "")

    if not file_path and tool_name == "Bash" and source_path:
        file_path = source_path

    return CanonicalToolEvent(
        client="claude",
        tool_name=tool_name,
        command=command,
        file_path=file_path,
        source_path=source_path,
        destination_path=destination_path,
        workspace_root=project_root,
        vault_dir=vault_dir,
        is_bugfix_ticket=_infer_is_bugfix_ticket(file_path or source_path or ""),
    )


def format_claude_decision(decision: PolicyDecision) -> dict[str, Any]:
    hook_output = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny" if decision.is_denied() else "allow",
    }
    if decision.is_denied() and decision.reason:
        hook_output["permissionDecisionReason"] = decision.reason
    return {"hookSpecificOutput": hook_output}


def _parse_ticket_paths(command: str) -> tuple[str | None, str | None]:
    tokens = command.split()
    ticket_paths = [token.strip("'\"") for token in tokens if "Tickets/" in token]
    if len(ticket_paths) < 2:
        return None, None
    return ticket_paths[0], ticket_paths[1]


def _infer_is_bugfix_ticket(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1].lower()
    return "bug" in filename
