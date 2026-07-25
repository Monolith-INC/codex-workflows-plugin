from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluator import collect_critiques
from .hooks import authorization_hook, cli_ui_hook
from .manifests import manifest_by_name
from .schema import validate_inputs
from .state import Event, QueueState, Task, TaskState
from .stream import OrchestratorStream
from .worker import execute_skill


@dataclass(frozen=True)
class ToolCallResult:
    ok: bool
    output: dict[str, Any] | None
    error: str | None = None
    task_id: str | None = None
    state: str | None = None

    def to_mcp_content(self) -> list[dict[str, str]]:
        payload = (
            {
                "status": "completed",
                "task_id": self.task_id,
                "output": self.output,
            }
            if self.ok
            else {
                "status": "failed",
                "task_id": self.task_id,
                "state": self.state,
                "error": self.error,
            }
        )
        return [{"type": "text", "text": json.dumps(payload, indent=2)}]


class OrchestratorEngine:
    """Synchronous skill orchestrator: queue events, execute, evaluate, retry."""

    def __init__(
        self,
        skills_dir: str | Path,
        *,
        max_retries: int = 3,
        interactive: bool = False,
        quiet: bool = False,
    ):
        self.skills_dir = Path(skills_dir)
        self.max_retries = max_retries
        self.interactive = interactive
        self.quiet = quiet
        self._manifests = manifest_by_name(self.skills_dir)

    def _subscribe_hooks(self, stream: OrchestratorStream) -> None:
        if not self.quiet:
            stream.subscribe(cli_ui_hook)
        if self.interactive:
            stream.subscribe(authorization_hook)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": manifest.get("name"),
                "description": manifest.get("description"),
                "inputSchema": manifest.get("input_schema") or {"type": "object", "properties": {}},
            }
            for manifest in self._manifests.values()
        ]

    def run_tool_call(self, name: str, arguments: dict[str, Any] | None) -> ToolCallResult:
        arguments = arguments or {}
        manifest = self._manifests.get(name)
        if manifest is None:
            return ToolCallResult(ok=False, output=None, error=f"Unknown skill '{name}'")

        input_critiques = validate_inputs(arguments, manifest)
        if input_critiques:
            return ToolCallResult(ok=False, output=None, error="; ".join(input_critiques))

        task_id = f"{name}-{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, skill_name=name, inputs=arguments)
        stream = OrchestratorStream(QueueState(tasks={task_id: task}), max_retries=self.max_retries)
        self._subscribe_hooks(stream)
        stream.dispatch(Event(type="TaskSpawnedEvent", payload={"task_id": task_id}))

        last_output: dict[str, Any] | None = None
        last_critiques: list[str] = []

        while True:
            current = stream.state.tasks[task_id]
            try:
                output = execute_skill(
                    name,
                    arguments,
                    skills_dir=str(self.skills_dir),
                    manifest=manifest,
                    task=current,
                )
            except Exception as exc:
                stream.dispatch(
                    Event(type="TaskFailedEvent", payload={"task_id": task_id, "critique": str(exc)})
                )
                current = stream.state.tasks[task_id]
                if current.state == TaskState.BLOCKED_REQUIRES_REVIEW:
                    return ToolCallResult(
                        ok=False,
                        output=None,
                        error=str(exc),
                        task_id=task_id,
                        state=current.state.value,
                    )
                if current.state == TaskState.READY and current.retry_count < self.max_retries:
                    stream.dispatch(Event(type="TaskSpawnedEvent", payload={"task_id": task_id}))
                    continue
                return ToolCallResult(
                    ok=False,
                    output=None,
                    error=str(exc),
                    task_id=task_id,
                    state=current.state.value,
                )

            critiques = collect_critiques(output, manifest)
            if not critiques:
                stream.dispatch(
                    Event(type="TaskCompletedEvent", payload={"task_id": task_id, "output": output})
                )
                return ToolCallResult(ok=True, output=output, task_id=task_id, state=TaskState.COMPLETED.value)

            if critiques == last_critiques and output == last_output:
                stream.dispatch(
                    Event(
                        type="TaskFailedEvent",
                        payload={"task_id": task_id, "critique": "; ".join(critiques)},
                    )
                )
                current = stream.state.tasks[task_id]
                return ToolCallResult(
                    ok=False,
                    output=output,
                    error="; ".join(critiques),
                    task_id=task_id,
                    state=current.state.value,
                )

            last_output = output
            last_critiques = list(critiques)
            stream.dispatch(
                Event(
                    type="TaskFailedEvent",
                    payload={"task_id": task_id, "critique": "; ".join(critiques)},
                )
            )
            current = stream.state.tasks[task_id]
            if current.state == TaskState.BLOCKED_REQUIRES_REVIEW:
                return ToolCallResult(
                    ok=False,
                    output=output,
                    error="; ".join(critiques),
                    task_id=task_id,
                    state=current.state.value,
                )
            if current.state == TaskState.READY and current.retry_count < self.max_retries:
                stream.dispatch(Event(type="TaskSpawnedEvent", payload={"task_id": task_id}))
                reflection = output.get("reflection") if isinstance(output, dict) else None
                if isinstance(reflection, dict):
                    arguments = {
                        **arguments,
                        "attempt": reflection.get("attempt", current.retry_count),
                    }
                continue

            return ToolCallResult(
                ok=False,
                output=output,
                error="; ".join(critiques),
                task_id=task_id,
                state=current.state.value,
            )
