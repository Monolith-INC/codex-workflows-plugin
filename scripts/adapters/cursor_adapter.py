from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_cursor_payload(payload: dict[str, Any], *, project_root: str, vault_dir: str) -> CanonicalToolEvent:
    tool_name = payload.get("tool_name") or payload.get("toolName") or payload.get("tool") or ""
    tool_input = (
        payload.get("tool_input")
        or payload.get("toolInput")
        or payload.get("input")
        or payload.get("arguments")
        or {}
    )
    command = tool_input.get("command") or tool_input.get("CommandLine") or ""
    file_path = (
        tool_input.get("path")
        or tool_input.get("file")
        or tool_input.get("AbsolutePath")
        or tool_input.get("TargetFile")
    )
    source_path, destination_path = _parse_ticket_paths(command or "")

    normalized_tool = str(tool_name)
    if not file_path and normalized_tool in {"Shell", "Bash"} and source_path:
        file_path = source_path

    return CanonicalToolEvent(
        client="cursor",
        tool_name=normalized_tool,
        command=command,
        file_path=file_path,
        source_path=source_path,
        destination_path=destination_path,
        workspace_root=project_root,
        vault_dir=vault_dir,
        is_bugfix_ticket=_infer_is_bugfix_ticket(file_path or source_path or ""),
    )


def format_cursor_decision(decision: PolicyDecision) -> dict[str, Any]:
    if decision.is_denied():
        response: dict[str, Any] = {"permission": "deny"}
        if decision.reason:
            response["agent_message"] = decision.reason
            response["user_message"] = decision.reason
        return response
    return {"permission": "allow"}


def _parse_ticket_paths(command: str) -> tuple[str | None, str | None]:
    tokens = command.split()
    ticket_paths = [token.strip("'\"") for token in tokens if "Tickets/" in token]
    if len(ticket_paths) < 2:
        return None, None
    return ticket_paths[0], ticket_paths[1]


def _infer_is_bugfix_ticket(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1].lower()
    return "bug" in filename
