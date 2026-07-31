from __future__ import annotations

from typing import Any

from policy.events import CanonicalToolEvent, PolicyDecision


def parse_antigravity_payload(payload: dict[str, Any], *, project_root: str, vault_dir: str) -> CanonicalToolEvent:
    tool_call = payload.get("toolCall") or {}
    args = tool_call.get("args") or {}
    tool_name = tool_call.get("name") or ""
    command = args.get("CommandLine") or args.get("command")
    file_path = args.get("AbsolutePath") or args.get("TargetFile") or args.get("path") or args.get("file")
    source_path, destination_path = _parse_ticket_paths(command or "")

    if not file_path and tool_name == "run_command" and source_path:
        file_path = source_path

    return CanonicalToolEvent(
        client="antigravity",
        tool_name=tool_name,
        command=command,
        file_path=file_path,
        source_path=source_path,
        destination_path=destination_path,
        workspace_root=project_root,
        vault_dir=vault_dir,
        is_bugfix_ticket=_infer_is_bugfix_ticket(file_path or source_path or ""),
    )


def format_antigravity_decision(decision: PolicyDecision) -> dict[str, Any]:
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
