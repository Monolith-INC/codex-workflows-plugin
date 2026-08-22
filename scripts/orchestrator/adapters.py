import json
from typing import Any

from .state import Task


def to_anthropic_dialect(instructions: str, task: Task) -> str:
    """Translates universal instructions into Anthropic's XML-heavy dialect."""
    prompt = "<system>\nYou are a specialized worker agent.\n</system>\n\n"

    prompt += "<instructions>\n"
    prompt += f"{instructions}\n"
    prompt += "</instructions>\n\n"

    prompt += "<task_payload>\n"
    prompt += json.dumps(task.inputs, indent=2) + "\n"
    prompt += "</task_payload>\n"

    if task.critiques:
        prompt += "\n<reflection>\n"
        prompt += "Previous attempts failed due to the following reasons. AVOID these mistakes:\n"
        for i, critique in enumerate(task.critiques):
            prompt += f'<critique index="{i}">{critique}</critique>\n'
        prompt += "</reflection>\n"

    return prompt


def to_openai_dialect(instructions: str, task: Task) -> str:
    """Translates universal instructions into OpenAI's JSON/Markdown system dialect."""
    prompt = "# SYSTEM ROLE\nYou are a specialized worker agent.\n\n"

    prompt += "## INSTRUCTIONS\n"
    prompt += f"{instructions}\n\n"

    prompt += "## TASK PAYLOAD\n"
    prompt += f"```json\n{json.dumps(task.inputs, indent=2)}\n```\n"

    if task.critiques:
        prompt += "\n## REFLECTION (CRITICAL CONSTRAINTS)\n"
        prompt += "Previous attempts failed. You MUST avoid the following mistakes:\n"
        for critique in task.critiques:
            prompt += f"- {critique}\n"

    return prompt


def to_anthropic_tool(manifest: dict[str, Any]) -> dict[str, Any]:
    """Translates a skill manifest into an Anthropic tool schema."""
    return {
        "name": manifest.get("name", "tool"),
        "description": manifest.get("description", ""),
        "input_schema": manifest.get("input_schema", {}),
    }


def to_openai_tool(manifest: dict[str, Any]) -> dict[str, Any]:
    """Translates a skill manifest into an OpenAI function schema."""
    return {
        "type": "function",
        "function": {
            "name": manifest.get("name", "tool"),
            "description": manifest.get("description", ""),
            "parameters": manifest.get("input_schema", {}),
        },
    }
