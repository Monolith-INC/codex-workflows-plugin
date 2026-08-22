from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


def _is_hook_group_list(val: Any) -> bool:
    """True if val is a list of hook-group dicts (each has a 'hooks' key)."""
    return (
        isinstance(val, list)
        and bool(val)
        and all(isinstance(item, dict) and "hooks" in item for item in val)
    )


def _is_flat_hook_list(val: Any) -> bool:
    """True if val is a list of Cursor-style flat hook dicts (each has a 'command' key)."""
    return (
        isinstance(val, list)
        and bool(val)
        and all(
            isinstance(item, dict) and "command" in item and "hooks" not in item
            for item in val
        )
    )


def _merge_flat_hook_lists(base: list, override: list) -> list:
    """Merge two flat hook lists, deduplicating entries by command string."""
    seen: set[str] = set()
    result = []
    for entry in base + override:
        if not isinstance(entry, dict):
            result.append(entry)
            continue
        cmd = entry.get("command", "")
        if cmd in seen:
            continue
        seen.add(cmd)
        result.append(entry)
    return result


def _merge_hook_group_lists(base: list, override: list) -> list:
    """Merge two hook-group lists, deduplicating entries by command string."""
    seen: set[str] = set()
    result = []
    for entry in base + override:
        if not isinstance(entry, dict):
            result.append(entry)
            continue
        fresh = []
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if cmd not in seen:
                seen.add(cmd)
                fresh.append(hook)
        if fresh:
            result.append({**entry, "hooks": fresh})
    return result


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = deepcopy(dict(base))
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, Mapping)
        ):
            result[key] = deep_merge(result[key], value)
        elif (
            key in result
            and _is_hook_group_list(result[key])
            and _is_hook_group_list(value)
        ):
            result[key] = _merge_hook_group_lists(result[key], value)
        elif (
            key in result
            and _is_flat_hook_list(result[key])
            and _is_flat_hook_list(value)
        ):
            result[key] = _merge_flat_hook_lists(result[key], value)
        elif (
            key in result and isinstance(result[key], list) and isinstance(value, list)
        ):
            result[key] = deepcopy(result[key]) + deepcopy(value)
        else:
            result[key] = deepcopy(value)
    return result


def merge_hook_configs(
    existing: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    if not existing:
        return deepcopy(incoming)
    return deep_merge(existing, incoming)
