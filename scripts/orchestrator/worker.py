from __future__ import annotations

from typing import Any

from .adapters import to_anthropic_dialect
from .handlers import get_handler
from .manifests import CapabilityManifest, load_skill_instructions
from .schema import validate_inputs
from .state import Task, TaskState


def execute_skill(
    skill_name: str,
    arguments: dict[str, Any],
    *,
    skills_dir: str,
    manifest: CapabilityManifest,
    task: Task,
) -> dict[str, Any]:
    """Run a skill handler and return structured output for evaluation."""
    input_critiques = validate_inputs(arguments, manifest)
    if input_critiques:
        raise ValueError("; ".join(input_critiques))

    instructions = load_skill_instructions(skills_dir, skill_name)
    handler = get_handler(skill_name)
    output = handler(arguments, manifest.wire, instructions)

    if output.get("mode") == "instructions" or "prompt" not in output:
        reflection_critiques = (
            {"reflection_critiques": list(task.critiques)} if task.critiques else {}
        )
        output = {
            **output,
            "prompt": to_anthropic_dialect(instructions, task.copy_with(state=TaskState.IN_PROGRESS)),
            "attempt": task.retry_count + 1,
            **reflection_critiques,
        }
    return output
