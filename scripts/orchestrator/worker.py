from __future__ import annotations

from typing import Any

from .adapters import to_anthropic_dialect
from .handlers import get_handler
from .invocation import Invocation
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
    output = handler(
        Invocation(
            arguments=arguments,
            manifest=manifest.wire,
            instructions=instructions,
            attempt=_reflection_attempt(arguments, task),
        )
    )

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


def _reflection_attempt(arguments: dict[str, Any], task: Task) -> int:
    """Where this run sits in the reflection sequence.

    A caller resuming a stateless MCP round trip declares its own starting
    attempt; in-process retries advance from there. Both were previously folded
    into ``arguments`` by rewriting the caller's payload on each retry.
    """
    declared = arguments.get("attempt", 0)
    resumed = int(declared) if isinstance(declared, (int, float)) and not isinstance(declared, bool) else 0
    return resumed + task.retry_count
