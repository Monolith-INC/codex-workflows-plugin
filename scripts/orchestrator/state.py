from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class FrozenDict(dict):
    """A JSON-serializable dictionary that rejects mutation."""

    @staticmethod
    def _immutable(*args: Any, **kwargs: Any) -> None:
        raise TypeError("FrozenDict is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


def deep_freeze(value: Any) -> Any:
    """Recursively freeze common JSON-like containers."""
    if isinstance(value, FrozenDict):
        return value
    if isinstance(value, Mapping):
        return FrozenDict({key: deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(deep_freeze(item) for item in value)
    return value


class TaskState(Enum):
    READY = "Ready"
    IN_PROGRESS = "In_Progress"
    COMPLETED = "Completed"
    BLOCKED = "Blocked"
    BLOCKED_REQUIRES_REVIEW = "Blocked_Requires_Review"


@dataclass(frozen=True)
class Event:
    """An immutable record of a state change in the system."""

    type: str
    payload: Mapping[str, Any] = field(default_factory=FrozenDict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", deep_freeze(self.payload))


@dataclass(frozen=True)
class Task:
    """An immutable representation of a unit of work (a skill execution)."""

    id: str
    skill_name: str
    state: TaskState = TaskState.READY
    inputs: Mapping[str, Any] = field(default_factory=FrozenDict)
    dependencies: tuple[str, ...] = ()
    retry_count: int = 0
    critiques: tuple[str, ...] = ()
    output: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", deep_freeze(self.inputs))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "critiques", tuple(self.critiques))
        object.__setattr__(self, "output", deep_freeze(self.output))

    def copy_with(self, **kwargs: Any) -> "Task":
        """Return a new immutable task with the requested fields replaced."""
        return dataclasses.replace(self, **kwargs)


@dataclass(frozen=True)
class QueueState:
    """The immutable task graph and append-only event history."""

    tasks: Mapping[str, Task] = field(default_factory=FrozenDict)
    events_history: tuple[Event, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tasks", deep_freeze(self.tasks))
        object.__setattr__(self, "events_history", tuple(self.events_history))

    def copy_with(self, **kwargs: Any) -> "QueueState":
        """Return a new immutable queue with the requested fields replaced."""
        return dataclasses.replace(self, **kwargs)
