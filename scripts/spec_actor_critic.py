"""Backward-compatible shim — prefer artifact_reflection."""

from __future__ import annotations

import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from artifact_profiles.spec import SPEC_REQUIRED_HEADINGS, spec_profile
from artifact_reflection import (
    ReflectionState,
    advance_reflection,
    append_mistake as _append_mistake,
    load_mistakes,
    mistakes_path,
)


def append_mistake(
    vault_folder: str,
    project_root,
    *,
    flaw: str,
    ticket_id: str = "",
    spec_kind: str | None = None,
    artifact_kind: str | None = None,
    skill_name: str = "write-spec",
) -> bool:
    kind = artifact_kind or spec_kind or "unknown"
    return _append_mistake(
        vault_folder,
        project_root,
        flaw=flaw,
        skill_name=skill_name,
        artifact_kind=kind,
        ticket_id=ticket_id,
    )

REQUIRED_HEADINGS = SPEC_REQUIRED_HEADINGS


def critic_review(
    draft: str,
    *,
    spec_kind: str,
    mistakes: list | None = None,
) -> list[str]:
    from artifact_reflection import ArtifactContext

    profile = spec_profile(spec_kind)
    context = ArtifactContext(
        skill_name="write-spec",
        artifact_kind=spec_kind,
        ticket_id="",
        slug="",
        draft=draft,
    )
    return profile.evaluate(draft, context, mistakes or [])


def actor_critic_loop(
    draft: str,
    *,
    spec_kind: str,
    mistakes: list | None = None,
    state: ReflectionState | None = None,
    max_attempts: int = 3,
) -> tuple[list[str], ReflectionState, bool]:
    from artifact_reflection import ArtifactContext, ReflectionEngine

    engine = ReflectionEngine(spec_profile(spec_kind))
    context = ArtifactContext(
        skill_name="write-spec",
        artifact_kind=spec_kind,
        ticket_id="",
        slug="",
        draft=draft,
        max_attempts=max_attempts,
    )
    decision = engine.evaluate_draft(context, state=state, mistakes=mistakes)
    done = not decision.critiques or decision.blocked
    return decision.critiques, decision.reflection, done
