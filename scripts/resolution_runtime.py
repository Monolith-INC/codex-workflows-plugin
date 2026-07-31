from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from spec_runtime import (
    list_existing_specs,
    read_ticket_ledger,
    slug_ticket_id,
    spec_dir_for_ticket,
)

RESOLUTION_REPORT = "resolution-report.md"


@dataclass(frozen=True)
class ResolutionPlan:
    ticket_id: str
    slug: str
    specs_dir: str
    resolution_report_path: str
    spec_files: tuple[str, ...]
    spec_texts: dict[str, str]
    resolution_required: bool
    specs_missing: bool
    source_hints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "slug": self.slug,
            "specs_dir": self.specs_dir,
            "resolution_report_path": self.resolution_report_path,
            "spec_files": list(self.spec_files),
            "resolution_required": self.resolution_required,
            "specs_missing": self.specs_missing,
            "source_hints": dict(self.source_hints),
        }

    def ground_truth(self) -> dict[str, Any]:
        return {
            "spec_files": list(self.spec_files),
            "spec_texts": dict(self.spec_texts),
            "requirements": self.source_hints.get("requirements", ""),
            "implementation_summary": self.source_hints.get("implementation_summary", ""),
            "description": self.source_hints.get("description", ""),
        }


def _extract_resolution_hints(ledger_text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    for label, pattern in (
        ("requirements", r"(?im)^(?:##\s*)?requirements?\s*[:\n](.+?)(?:\n##|\Z)"),
        ("description", r"(?im)^(?:##\s*)?description\s*[:\n](.+?)(?:\n##|\Z)"),
        ("implementation_summary", r"(?im)^(?:##\s*)?implementation\s+(?:summary|walkthrough)\s*[:\n](.+?)(?:\n##|\Z)"),
        ("verification", r"(?im)^(?:##\s*)?verification\s*[:\n](.+?)(?:\n##|\Z)"),
    ):
        match = re.search(pattern, ledger_text, re.DOTALL)
        if match:
            hints[label] = match.group(1).strip()[:4000]
    return hints


def _load_spec_texts(spec_dir: Path | None, spec_files: list[str]) -> dict[str, str]:
    if spec_dir is None or not spec_dir.is_dir():
        return {}
    texts: dict[str, str] = {}
    for name in spec_files:
        path = spec_dir / name
        if path.is_file():
            try:
                texts[name] = path.read_text(encoding="utf-8")[:8000]
            except OSError:
                continue
    return texts


def plan_resolution(
    project_root: Path | None,
    *,
    vault_folder: str,
    ticket_id: str,
    ledger_rel: str | None = None,
) -> ResolutionPlan:
    slug = slug_ticket_id(ticket_id)
    rel_specs_dir = f"{vault_folder}/Specs/{slug}"
    spec_dir = spec_dir_for_ticket(vault_folder, project_root, slug)
    ledger_path = ledger_rel or f"{vault_folder}/Tickets/Active/{slug}.md"
    ledger_text = read_ticket_ledger(project_root, ledger_path)
    hints = _extract_resolution_hints(ledger_text)

    spec_files = list_existing_specs(spec_dir) if spec_dir is not None else []
    spec_files = [f for f in spec_files if f != RESOLUTION_REPORT]
    specs_missing = not spec_files

    report_rel = f"{rel_specs_dir}/{RESOLUTION_REPORT}"
    report_exists = False
    if project_root is not None and spec_dir is not None:
        report_exists = (spec_dir / RESOLUTION_REPORT).is_file()

    resolution_required = specs_missing or not report_exists
    spec_texts = _load_spec_texts(spec_dir, spec_files)

    return ResolutionPlan(
        ticket_id=ticket_id,
        slug=slug,
        specs_dir=rel_specs_dir,
        resolution_report_path=report_rel,
        spec_files=tuple(spec_files),
        spec_texts=spec_texts,
        resolution_required=resolution_required,
        specs_missing=specs_missing,
        source_hints=hints,
    )


def template_path(skills_dir: Path) -> Path:
    return skills_dir / "resolve-ticket" / "references" / "templates" / RESOLUTION_REPORT


def load_resolution_template(skills_dir: Path) -> str:
    path = template_path(skills_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Missing resolution template: {path}")
    return path.read_text(encoding="utf-8")
