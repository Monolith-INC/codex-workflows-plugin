from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from artifact_profiles.resolution import resolution_profile
from artifact_profiles.spec import spec_profile
from artifact_reflection import ArtifactContext, ReflectionEngine, ReflectionState, load_mistakes
from resolution_runtime import load_resolution_template, plan_resolution
from policy.engine import validate_ticket_start
from policy.events import CanonicalToolEvent
from resolve_ticket_hook import on_resolve_ticket
from spec_runtime import load_template, plan_spec_generation, slug_ticket_id
from spec_start_hook import on_start_ticket

from .failures import PolicyDenied
from .invocation import HandlerResult, Invocation


def _project_root() -> Path | None:
    for key in ("CODEX_PROJECT_ROOT", "CURSOR_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        value = os.environ.get(key, "").strip()
        if value:
            return Path(value)
    return None


def _skills_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "skills"


def handle_write_spec(invocation: Invocation) -> HandlerResult:
    arguments, instructions = invocation.arguments, invocation.instructions
    ticket_id = arguments["ticket_id"]
    spec_kind = arguments.get("spec_kind", "tech-spec")
    vault = os.environ.get("CODEX_VAULT_FOLDER", "AI_Codex")
    root = _project_root()
    slug = slug_ticket_id(ticket_id)
    specs_dir = f"{vault}/Specs/{slug}"
    mistakes = load_mistakes(vault, root)

    plan = plan_spec_generation(root, vault_folder=vault, ticket_id=ticket_id)
    template = ""
    try:
        template = load_template(_skills_dir(), spec_kind)
    except FileNotFoundError:
        template = f"# {spec_kind}\n\n<!-- Template missing; use write-spec references. -->\n"

    draft = arguments.get("draft_content", "").strip()
    reflection = ReflectionState(attempt=invocation.attempt)
    engine = ReflectionEngine(spec_profile(spec_kind))
    context = ArtifactContext(
        skill_name="write-spec",
        artifact_kind=spec_kind,
        ticket_id=ticket_id,
        slug=slug,
        draft=draft,
        ground_truth=plan.source_hints,
        max_attempts=int(arguments.get("max_attempts", 3)),
    )
    decision = engine.run_with_mistakes(
        context,
        vault,
        root,
        state=reflection,
    )
    critiques = decision.critiques
    reflection = decision.reflection
    mode = decision.mode if draft else "instructions"

    return HandlerResult(
        product={
            "ticket_id": ticket_id,
            "spec_kind": spec_kind,
            "specs_dir": specs_dir,
            "template": template,
            "mistakes": mistakes[-10:],
            "source_hints": plan.source_hints,
            "critiques": "; ".join(critiques) if critiques else "",
            "mode": mode,
            "instructions": instructions,
        },
        reflection=reflection.to_dict(),
    )


def handle_start_ticket(invocation: Invocation) -> HandlerResult:
    arguments, instructions = invocation.arguments, invocation.instructions
    ticket_id = arguments["ticket_id"]
    vault = os.environ.get("CODEX_VAULT_FOLDER", "AI_Codex")
    slug = slug_ticket_id(ticket_id)
    rel_path = f"{vault}/Tickets/Active/{slug}.md"
    created = False

    root = _project_root()
    if root is not None:
        ledger_path = root / rel_path
        if not ledger_path.exists():
            decision = validate_ticket_start(
                CanonicalToolEvent(
                    client="orchestrator",
                    tool_name="Write",
                    file_path=str(ledger_path),
                    workspace_root=str(root),
                    vault_dir=str(root / vault),
                )
            )
            if decision.is_denied():
                raise PolicyDenied(decision.reason or "ticket start blocked by policy")
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not ledger_path.exists():
            ledger_path.write_text(
                f"---\ntype: ticket\nticket: {ticket_id}\n---\n\n# Ticket {ticket_id}\n",
                encoding="utf-8",
            )
            created = True

    spec_plan = plan_spec_generation(root, vault_folder=vault, ticket_id=ticket_id, ledger_rel=rel_path)
    write_spec_directive = on_start_ticket(spec_plan)

    return HandlerResult(
        product={
            "active_ledger_path": rel_path,
            "ticket_id": ticket_id,
            "created": created,
            "spec_plan": spec_plan.to_dict(),
            "write_spec_directive": write_spec_directive,
            "generation_required": spec_plan.generation_required,
            "mode": "instructions" if write_spec_directive or not created else "completed",
            "instructions": instructions,
        }
    )


def handle_resolve_ticket(invocation: Invocation) -> HandlerResult:
    arguments, instructions = invocation.arguments, invocation.instructions
    ticket_id = arguments["ticket_id"]
    vault = os.environ.get("CODEX_VAULT_FOLDER", "AI_Codex")
    root = _project_root()
    slug = slug_ticket_id(ticket_id)
    ledger_rel = f"{vault}/Tickets/Active/{slug}.md"

    plan = plan_resolution(root, vault_folder=vault, ticket_id=ticket_id, ledger_rel=ledger_rel)
    directive = on_resolve_ticket(plan)

    template = ""
    try:
        template = load_resolution_template(_skills_dir())
    except FileNotFoundError:
        template = "# Resolution Report\n\n<!-- Template missing. -->\n"

    ground_truth = plan.ground_truth()
    if arguments.get("implementation_summary"):
        ground_truth["implementation_summary"] = str(arguments["implementation_summary"])

    draft = arguments.get("draft_content", "").strip()
    reflection = ReflectionState(attempt=invocation.attempt)
    engine = ReflectionEngine(resolution_profile())
    context = ArtifactContext(
        skill_name="resolve-ticket",
        artifact_kind="resolution-report",
        ticket_id=ticket_id,
        slug=slug,
        draft=draft,
        ground_truth=ground_truth,
        max_attempts=int(arguments.get("max_attempts", 3)),
    )
    decision = engine.run_with_mistakes(context, vault, root, state=reflection)
    mistakes = load_mistakes(vault, root, skill_name="resolve-ticket")

    mode = decision.mode if draft else "instructions"
    if directive and not draft:
        mode = "instructions"

    return HandlerResult(
        product={
            "ticket_id": ticket_id,
            "active_ledger_path": ledger_rel,
            "resolution_report_path": plan.resolution_report_path,
            "specs_dir": plan.specs_dir,
            "spec_files": list(plan.spec_files),
            "template": template,
            "ground_truth": ground_truth,
            "mistakes": mistakes[-10:],
            "resolve_directive": directive,
            "resolution_required": plan.resolution_required,
            "critiques": "; ".join(decision.critiques) if decision.critiques else "",
            "mode": mode,
            "instructions": instructions,
        },
        reflection=decision.reflection.to_dict(),
    )


def handle_review_pr(invocation: Invocation) -> HandlerResult:
    arguments, instructions = invocation.arguments, invocation.instructions
    return HandlerResult(
        product={
            "pr_number": arguments["pr_number"],
            "mode": "instructions",
            "instructions": instructions,
        }
    )


def handle_instruction_only(invocation: Invocation) -> HandlerResult:
    arguments, manifest, instructions = (
        invocation.arguments,
        invocation.manifest,
        invocation.instructions,
    )
    return HandlerResult(
        product={
            "mode": "instructions",
            "skill": manifest.get("name", ""),
            "inputs": arguments,
            "instructions": instructions,
        }
    )


_HANDLERS: dict[str, Callable[[Invocation], HandlerResult]] = {
    "start-ticket": handle_start_ticket,
    "write-spec": handle_write_spec,
    "resolve-ticket": handle_resolve_ticket,
    "review-pr": handle_review_pr,
}


def get_handler(skill_name: str) -> Callable[[Invocation], HandlerResult]:
    return _HANDLERS.get(skill_name, handle_instruction_only)
