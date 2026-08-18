from __future__ import annotations

from typing import Any


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
}


def validate_inputs(arguments: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    """Validate tool arguments against a skill manifest input_schema."""
    critiques: list[str] = []
    schema = manifest.get("input_schema") or {}
    if schema.get("type", "object") != "object":
        return critiques
    if not isinstance(arguments, dict):
        return [f"Expected object arguments for skill '{manifest.get('name', '')}'"]

    for key in schema.get("required", []):
        if key not in arguments:
            critiques.append(f"Missing required argument '{key}'.")

    properties = schema.get("properties", {})
    for key, value in arguments.items():
        prop = properties.get(key)
        if prop is None:
            if schema.get("additionalProperties", True) is False:
                critiques.append(f"Unknown argument '{key}' is not allowed.")
            continue
        expected_type = prop.get("type")
        if expected_type and expected_type in _TYPE_CHECKS:
            if not _TYPE_CHECKS[expected_type](value):
                critiques.append(
                    f"Argument '{key}' should be {expected_type}, got {type(value).__name__}."
                )
    return critiques
