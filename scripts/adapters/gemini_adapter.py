from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_gemini_payload(payload: dict[str, Any], *, project_root: str, vault_dir: str) -> CanonicalToolEvent:
    tool_name = payload.get("tool_name") or payload.get("tool") or payload.get("name") or ""
    arguments = payload.get("tool_input") or payload.get("arguments") or payload.get("args") or {}
    command = arguments.get("command") or arguments.get("CommandLine")
    file_path = arguments.get("AbsolutePath") or arguments.get("TargetFile") or arguments.get("path") or arguments.get("file")
    source_path, destination_path = _parse_ticket_paths(command or "")

    if not file_path and tool_name == "run_shell_command" and source_path:
        file_path = source_path

    return CanonicalToolEvent(
        client="gemini",
        tool_name=tool_name,
        command=command,
        file_path=file_path,
        source_path=source_path,
        destination_path=destination_path,
        workspace_root=project_root,
        vault_dir=vault_dir,
        is_bugfix_ticket=_infer_is_bugfix_ticket(file_path or source_path or ""),
    )


def format_gemini_decision(decision: PolicyDecision) -> dict[str, Any]:
    response = {
        "decision": "deny" if decision.is_denied() else "allow",
    }
    if decision.reason:
        response["reason"] = decision.reason
    return response


def _parse_ticket_paths(command: str) -> tuple[str | None, str | None]:
    tokens = command.split()
    ticket_paths = [token.strip("'\"") for token in tokens if "Tickets/" in token]
    if len(ticket_paths) < 2:
        return None, None
    return ticket_paths[0], ticket_paths[1]


def _infer_is_bugfix_ticket(path: str) -> bool:
    filename = path.rsplit("/", 1)[-1].lower()
    return "bug" in filename
