from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any, Callable

from scripts.adapters import (
    format_antigravity_decision,
    format_claude_decision,
    format_codex_decision,
    format_cursor_decision,
    format_gemini_decision,
    parse_antigravity_payload,
    parse_claude_payload,
    parse_codex_payload,
    parse_cursor_payload,
    parse_gemini_payload,
)
from scripts.payload_capture import capture_hook_payload
from scripts.ticket_runtime import (
    YouTrackCheckResult,
    check_youtrack_state_in_transcript,
    extract_ticket_paths,
    get_youtrack_issue_id_from_ticket,
    get_youtrack_issue_id_from_write,
    infer_is_bugfix_ticket,
)
from scripts.policy import CanonicalToolEvent, PolicyDecision, evaluate

LOG_FILE = "/tmp/codex_hook_debug.log"


AdapterParser = Callable[[dict[str, Any]], CanonicalToolEvent]
AdapterFormatter = Callable[[PolicyDecision], dict[str, Any]]


def log_debug(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"{datetime.now().isoformat()} - {msg}\n")
    except Exception:
        pass


def get_project_root() -> str:
    for key in ("CURSOR_PROJECT_DIR", "CODEX_PROJECT_ROOT", "CLAUDE_PROJECT_DIR"):
        value = os.environ.get(key, "").strip()
        if value and os.path.isdir(value):
            return value
    cwd = os.getcwd()
    while cwd != os.path.dirname(cwd):
        if os.path.exists(os.path.join(cwd, ".git")):
            return cwd
        cwd = os.path.dirname(cwd)
    return os.getcwd()


def get_vault_dir(project_root: str) -> str:
    for name in os.listdir(project_root):
        if name.startswith("AI_Codex") and os.path.isdir(os.path.join(project_root, name)):
            return os.path.join(project_root, name)
    return os.path.join(project_root, "AI_Codex")


def get_today_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def is_allowed_markdown(path: str, vault_dir: str, project_root: str) -> bool:
    normalized_path = os.path.abspath(path)
    basename = os.path.basename(normalized_path)
    if basename in ["CLAUDE.md", "GEMINI.md"]:
        return True
    if normalized_path.startswith(os.path.abspath(vault_dir)):
        return True
    agent_dir = os.path.join(project_root, ".agent")
    return normalized_path.startswith(os.path.abspath(agent_dir))


def has_active_session_today(vault_dir: str) -> bool:
    sessions_dir = os.path.join(vault_dir, "Agent_Sessions")
    if not os.path.exists(sessions_dir):
        log_debug(f"Sessions directory {sessions_dir} does not exist.")
        return False

    today_prefix = get_today_date_str()
    log_debug(f"Checking for sessions starting with {today_prefix}")

    for filename in os.listdir(sessions_dir):
        if filename.startswith(today_prefix) and filename.endswith(".md"):
            filepath = os.path.join(sessions_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    content = file.read()
                if re.search(r"next:\s*(null|['\"]['\"]|~|)\s*$", content, re.MULTILINE):
                    log_debug(f"Found active session record: {filename}")
                    return True
            except Exception as exc:
                log_debug(f"Error reading session file {filename}: {exc}")

    return False


def select_adapter(client: str) -> tuple[Callable[[dict[str, Any], str, str], CanonicalToolEvent], AdapterFormatter]:
    normalized = client.strip().lower()
    if normalized == "gemini":
        return parse_gemini_payload, format_gemini_decision
    if normalized == "antigravity" or normalized == "antigravity-cli":
        return parse_antigravity_payload, format_antigravity_decision
    if normalized == "claude":
        return parse_claude_payload, format_claude_decision
    if normalized == "cursor":
        return parse_cursor_payload, format_cursor_decision
    return parse_codex_payload, format_codex_decision


def emit_decision(client: str, decision: PolicyDecision) -> None:
    _, formatter = select_adapter(client)
    print(json.dumps(formatter(decision)))


def run(client: str, input_data: dict[str, Any]) -> int:
    if input_data.get("transcript_path") and not input_data.get("transcriptPath"):
        input_data = {**input_data, "transcriptPath": input_data["transcript_path"]}

    project_root = get_project_root()
    vault_dir = get_vault_dir(project_root)
    capture_dir = os.environ.get("CODEX_WORKFLOW_CAPTURE_DIR")
    if capture_dir:
        try:
            capture_hook_payload(
                client=client,
                payload=input_data,
                capture_dir=capture_dir,
                project_root=project_root,
            )
        except Exception as exc:
            log_debug(f"Capture skipped: {exc}")
    parser, _ = select_adapter(client)
    codex_event = parser(input_data, project_root=project_root, vault_dir=vault_dir)
    tool_name = codex_event.tool_name
    arguments = (
        input_data.get("tool_input")
        or input_data.get("toolInput")
        or input_data.get("arguments")
        or input_data.get("args")
        or {}
    )
    file_path = codex_event.file_path or arguments.get("AbsolutePath") or arguments.get("TargetFile") or arguments.get("path") or arguments.get("file") or ""

    if tool_name in {"run_command", "Shell", "Bash"}:
        cmd = codex_event.command or arguments.get("CommandLine") or arguments.get("command") or ""
        destructive_decision = evaluate(
            CanonicalToolEvent(
                client=client,
                tool_name=tool_name,
                command=cmd,
                workspace_root=project_root,
                vault_dir=vault_dir,
            )
        )
        if destructive_decision.is_denied():
            log_debug(f"DENIED: {destructive_decision.reason}")
            emit_decision(client, PolicyDecision.deny(destructive_decision.reason or "Denied"))
            return 0

        cmd_tokens = cmd.split()
        if any(m in cmd_tokens for m in ["mv", "git"]):
            src_path, dst_path = extract_ticket_paths(cmd)
        else:
            src_path, dst_path = None, None

        if src_path and dst_path:
            abs_src = os.path.abspath(os.path.join(project_root, src_path))
            abs_dst = os.path.abspath(os.path.join(project_root, dst_path))
            is_bugfix = codex_event.is_bugfix_ticket or infer_is_bugfix_ticket(abs_src)
            if "Tickets/Ready/" in abs_src and "Tickets/Active/" in abs_dst:
                issue_id = get_youtrack_issue_id_from_ticket(abs_src)
                if issue_id:
                    transcript_path = input_data.get("transcriptPath")
                    yt_result = check_youtrack_state_in_transcript(transcript_path, issue_id, ["In Progress"], expected_timer="Start")
                    if not yt_result.verified:
                        try:
                            subprocess.run(
                                [
                                    "youtrack",
                                    "update_issue",
                                    "--issueId",
                                    issue_id,
                                    "--customFields",
                                    "{\"State\":\"In Progress\",\"Timer\":\"Start\"}",
                                ],
                                check=False,
                            )
                            log_debug(f"Auto-updated YouTrack issue {issue_id} to In Progress and started timer")
                        except Exception as exc:
                            log_debug(f"Auto-update failed for issue {issue_id}: {exc}")

            decision = evaluate(
                CanonicalToolEvent(
                    client=client,
                    tool_name=tool_name,
                    command=cmd,
                    source_path=abs_src,
                    destination_path=abs_dst,
                    workspace_root=project_root,
                    vault_dir=vault_dir,
                    is_bugfix_ticket=is_bugfix,
                )
            )
            if decision.is_denied():
                log_debug(f"DENIED: {decision.reason}")
                emit_decision(client, PolicyDecision.deny(decision.reason or "Denied"))
                return 0

            issue_id = get_youtrack_issue_id_from_ticket(abs_src)
            if issue_id:
                transcript_path = input_data.get("transcriptPath")
                if "Tickets/Active/" in abs_dst:
                    yt_result = check_youtrack_state_in_transcript(
                        transcript_path, issue_id, ["In Progress"], expected_timer="Start"
                    )
                    if not yt_result.verified:
                        detail = (
                            "transcript not found in conversation context"
                            if yt_result.reason == "transcript_missing"
                            else "state not set to 'In Progress' or timer not set to 'Start' in transcript"
                        )
                        reason = (
                            f"Move blocked. You must update YouTrack issue {issue_id} state to "
                            f"'In Progress' and set 'Timer' to 'Start' via call_mcp_tool before "
                            f"moving the ticket to Active ({detail})."
                        )
                        log_debug(f"DENIED: {reason}")
                        emit_decision(client, PolicyDecision.deny(reason))
                        return 0
                elif "Tickets/Resolved/" in abs_dst or "Tickets/Closed/" in abs_dst:
                    yt_result = check_youtrack_state_in_transcript(
                        transcript_path, issue_id, ["Done", "Fixed"], expected_timer="Stop", require_spent_time=True
                    )
                    if not yt_result.verified:
                        detail = (
                            "transcript not found in conversation context"
                            if yt_result.reason == "transcript_missing"
                            else "state not set to 'Done'/'Fixed', timer not stopped, or spent time not recorded in transcript"
                        )
                        reason = (
                            f"Move blocked. You must update YouTrack issue {issue_id} state to "
                            f"'Done' or 'Fixed', set 'Timer' to 'Stop', and set 'Spent time' via call_mcp_tool before "
                            f"moving the ticket to Resolved/Closed ({detail})."
                        )
                        log_debug(f"DENIED: {reason}")
                        emit_decision(client, PolicyDecision.deny(reason))
                        return 0

    markdown_allowed = is_allowed_markdown(file_path, vault_dir, project_root)
    file_decision = evaluate(
        CanonicalToolEvent(
            client=client,
            tool_name=tool_name,
            file_path=file_path,
            workspace_root=project_root,
            vault_dir=vault_dir,
            markdown_allowed=markdown_allowed,
            session_active=has_active_session_today(vault_dir),
            is_bugfix_ticket=infer_is_bugfix_ticket(file_path, arguments.get("CodeContent")),
        )
    )
    if file_decision.is_denied():
        log_debug(f"DENIED: {file_decision.reason}")
        emit_decision(client, PolicyDecision.deny(file_decision.reason or "Denied"))
        return 0
 
    write_tools = ["write_to_file", "replace_file_content", "multi_replace_file_content", "Write", "StrReplace", "Edit"]
    if tool_name in write_tools:
        write_decision = evaluate(
            CanonicalToolEvent(
                client=client,
                tool_name=tool_name,
                file_path=file_path,
                workspace_root=project_root,
                vault_dir=vault_dir,
                markdown_allowed=markdown_allowed,
                session_active=has_active_session_today(vault_dir),
                is_bugfix_ticket=infer_is_bugfix_ticket(file_path, arguments.get("CodeContent")),
            )
        )
        if write_decision.is_denied():
            log_debug(f"DENIED: {write_decision.reason}")
            emit_decision(client, PolicyDecision.deny(write_decision.reason or "Denied"))
            return 0

        abs_file_path = os.path.abspath(file_path)
        if any(marker in abs_file_path for marker in ["Tickets/Active/", "Tickets/Closed/", "Tickets/Resolved/"]):
            issue_id = get_youtrack_issue_id_from_write(abs_file_path, arguments)
            if issue_id:
                transcript_path = input_data.get("transcriptPath")
                if "Tickets/Active/" in abs_file_path:
                    expected_states = ["In Progress"]
                    expected_timer = "Start"
                    require_spent_time = False
                    state_desc = "'In Progress' and set 'Timer' to 'Start'"
                else:
                    expected_states = ["Done", "Fixed"]
                    expected_timer = "Stop"
                    require_spent_time = True
                    state_desc = "'Done' or 'Fixed', set 'Timer' to 'Stop', and set 'Spent time'"
                yt_result = check_youtrack_state_in_transcript(
                    transcript_path, issue_id, expected_states, expected_timer=expected_timer, require_spent_time=require_spent_time
                )
                if not yt_result.verified:
                    detail = (
                        "transcript not found in conversation context"
                        if yt_result.reason == "transcript_missing"
                        else f"fields not set correctly (expected State in {expected_states}, Timer='{expected_timer}', and Spent time recorded)"
                    )
                    reason = (
                        f"Write blocked. You must update YouTrack issue {issue_id} state to "
                        f"{state_desc} via call_mcp_tool before saving/moving the ticket ({detail})."
                    )
                    log_debug(f"DENIED: {reason}")
                    emit_decision(client, PolicyDecision.deny(reason))
                    return 0


    log_debug("ALLOWED")
    emit_decision(client, PolicyDecision.allow())
    return 0
