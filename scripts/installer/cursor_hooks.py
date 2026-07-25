from __future__ import annotations

from copy import deepcopy
from typing import Any


def desired_cursor_hooks(hook_command: str) -> dict[str, Any]:
    """Return the Cursor hooks.json fragment for workflow policy enforcement."""
    return {
        "version": 1,
        "hooks": {
            "preToolUse": [
                {
                    "command": hook_command,
                    "matcher": "Shell|Read|Write|Grep|Delete|Task",
                    "timeout": 5,
                    "failClosed": True,
                }
            ]
        },
    }


def strip_managed_cursor_hooks(config: dict[str, Any], script_names: set[str]) -> dict[str, Any]:
    """Remove preToolUse entries whose command references a managed script."""
    result = deepcopy(config)
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return {"version": result.get("version", 1), "hooks": {}}

    cleaned: dict[str, list[Any]] = {}
    for event_name, entries in hooks.items():
        if not isinstance(entries, list):
            cleaned[event_name] = entries
            continue
        kept = []
        for entry in entries:
            if not isinstance(entry, dict):
                kept.append(entry)
                continue
            command = entry.get("command", "")
            if any(script_name in command for script_name in script_names):
                continue
            kept.append(entry)
        cleaned[event_name] = kept
    result["hooks"] = cleaned
    return result


def merge_cursor_hooks(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge Cursor hook configs, deduplicating preToolUse entries by command string."""
    if not existing:
        return deepcopy(incoming)

    result = deepcopy(existing)
    result.setdefault("version", incoming.get("version", 1))
    result_hooks = result.setdefault("hooks", {})
    incoming_hooks = incoming.get("hooks", {})

    if not isinstance(result_hooks, dict) or not isinstance(incoming_hooks, dict):
        return deepcopy(incoming)

    for event_name, incoming_entries in incoming_hooks.items():
        if not isinstance(incoming_entries, list):
            result_hooks[event_name] = deepcopy(incoming_entries)
            continue

        current_entries = result_hooks.get(event_name, [])
        if not isinstance(current_entries, list):
            current_entries = []

        seen_commands = {
            entry.get("command")
            for entry in current_entries
            if isinstance(entry, dict) and entry.get("command")
        }
        merged_entries = list(current_entries)
        for entry in incoming_entries:
            if not isinstance(entry, dict):
                merged_entries.append(entry)
                continue
            command = entry.get("command", "")
            if command and command in seen_commands:
                continue
            if command:
                seen_commands.add(command)
            merged_entries.append(entry)
        result_hooks[event_name] = merged_entries

    return result
