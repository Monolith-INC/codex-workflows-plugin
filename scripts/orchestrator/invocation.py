"""What one handler run receives.

Orchestration metadata used to be written into the caller's ``arguments`` dict
on every retry. That conflated two channels: a manifest declares what the caller
may send, and the engine was adding a key of its own on top -- which the strict
argument contract then had to be taught to ignore. The two channels are separate
fields here instead, so neither has to know about the other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .state import FrozenDict, deep_freeze


@dataclass(frozen=True)
class Invocation:
    """One handler call: the caller's payload plus this run's position."""

    arguments: Mapping[str, Any] = field(default_factory=FrozenDict)
    manifest: Mapping[str, Any] = field(default_factory=FrozenDict)
    instructions: str = ""
    attempt: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", deep_freeze(self.arguments))
        object.__setattr__(self, "manifest", deep_freeze(self.manifest))
