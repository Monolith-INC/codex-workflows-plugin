"""Idempotent artifact publication with bounded retry."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .contracts import ArtifactRef, IntegrationError


def publish_artifact_idempotent(
    *,
    list_fn: Callable[[], list[ArtifactRef]],
    create_fn: Callable[[], ArtifactRef],
    title: str,
    revision: str,
    max_attempts: int = 3,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Reuse an existing title+revision artifact or create one with retries."""
    existing = next((item for item in list_fn() if item.revision == revision and item.title == title), None)
    if existing is not None:
        return {"artifact": existing, "outcome": "reused", "attempts": 0}

    attempts = 0
    last_error: IntegrationError | None = None
    while attempts < max_attempts:
        attempts += 1
        try:
            created = create_fn()
            return {"artifact": created, "outcome": "created", "attempts": attempts}
        except IntegrationError as exc:
            last_error = exc
            if not exc.retryable or attempts >= max_attempts:
                raise
            sleep_fn(0.05 * attempts)
    assert last_error is not None
    raise last_error
