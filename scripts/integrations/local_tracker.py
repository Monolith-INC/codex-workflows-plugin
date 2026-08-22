"""Filesystem-backed implementation of the provider-neutral tracker contract."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import (
    TrackerAdapter,
    _encode_artifact_envelope,
    _parse_artifact_envelope,
)
from .contracts import (
    WORK_ITEM_ROLES,
    ArtifactRef,
    IntegrationError,
    LogicalState,
    WorkItem,
    WorkItemKind,
)

_PREFIXES = {
    WorkItemKind.EPIC: "EPIC",
    WorkItemKind.FEATURE: "FEATURE",
    WorkItemKind.USER_STORY: "STORY",
    WorkItemKind.TASK: "TASK",
    WorkItemKind.BUG: "BUG",
}


class LocalTrackerAdapter(TrackerAdapter):
    """Store work items and workflow artifacts below ``.local-tracker``."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        project_root = Path(str(config.get("projectRoot") or Path.cwd())).resolve()
        candidate = Path(str(config.get("root") or ".local-tracker"))
        root = (
            (project_root / candidate).resolve()
            if not candidate.is_absolute()
            else candidate.resolve()
        )
        try:
            root.relative_to(project_root)
        except ValueError as exc:
            raise IntegrationError(
                "invalid_config", "local tracker root must be inside the project."
            ) from exc
        self.root = root
        self.artifacts_root = root / "artifacts"
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        for state in LogicalState:
            (self.root / state.value).mkdir(parents=True, exist_ok=True)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

    def get_work_item(self, ref: str) -> WorkItem:
        _path, record = self._find_record(ref)
        return self._work_item(record)

    def search_work_items(
        self, query: str, cursor: str | None = None
    ) -> dict[str, Any]:
        needle = query.strip().lower()
        matches = [
            self._work_item(record)
            for _path, record in self._records()
            if not needle
            or needle in str(record.get("key", "")).lower()
            or needle in str(record.get("title", "")).lower()
            or needle in str(record.get("description", "")).lower()
        ]
        matches.sort(key=lambda item: item.key)
        start = int(cursor or 0)
        page = matches[start : start + 50]
        next_cursor = (
            str(start + len(page)) if start + len(page) < len(matches) else None
        )
        return {"items": [item.__dict__ for item in page], "nextCursor": next_cursor}

    def create_work_item(
        self,
        kind: str,
        title: str,
        description: str,
        parent_ref: str | None = None,
    ) -> WorkItem:
        try:
            work_kind = WorkItemKind(kind)
        except ValueError as exc:
            raise IntegrationError(
                "invalid_work_item", f"Unsupported work-item kind: {kind}"
            ) from exc
        parent_id: str | None = None
        if parent_ref:
            _parent_path, parent = self._find_record(parent_ref)
            parent_kind = WorkItemKind(str(parent["kind"]))
            if work_kind not in WORK_ITEM_ROLES[parent_kind].child_kinds:
                raise IntegrationError(
                    "invalid_hierarchy",
                    f"{parent_kind.value} work items cannot contain {work_kind.value} work items.",
                )
            parent_id = str(parent["id"])
        key = self._next_key(work_kind)
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": key,
            "key": key,
            "title": title,
            "kind": work_kind.value,
            "state": LogicalState.BACKLOG.value,
            "description": description,
            "parentId": parent_id,
            "createdAt": now,
            "updatedAt": now,
            "links": [],
        }
        self._write_record(
            self.root / LogicalState.BACKLOG.value / f"{key}.json", record
        )
        return self._work_item(record)

    def transition_work_item(self, ref: str, state: str) -> WorkItem:
        try:
            target_state = LogicalState(state)
        except ValueError as exc:
            raise IntegrationError(
                "invalid_state", f"Unsupported logical state: {state}"
            ) from exc
        path, record = self._find_record(ref)
        record["state"] = target_state.value
        record["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self._write_record(path, record)
        target = self.root / target_state.value / path.name
        if target != path:
            path.replace(target)
        return self._work_item(record)

    def list_children(self, ref: str) -> list[WorkItem]:
        _path, parent = self._find_record(ref)
        return [
            self._work_item(record)
            for _child_path, record in self._records()
            if str(record.get("parentId") or "") == str(parent["id"])
        ]

    def publish_artifact(
        self,
        ref: str,
        kind: str,
        title: str,
        content: str,
        revision: str,
    ) -> ArtifactRef:
        _path, record = self._find_record(ref)
        existing = next(
            (
                artifact
                for artifact in self.list_artifacts(str(record["id"]), kind)
                if artifact.title == title and artifact.revision == revision
            ),
            None,
        )
        if existing is not None:
            return ArtifactRef(
                existing.id,
                existing.kind,
                existing.title,
                existing.revision,
                existing.url,
                existing.provider_data,
                "reused",
                0,
            )
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-") or "artifact"
        safe_kind = re.sub(r"[^A-Za-z0-9._-]+", "-", kind).strip("-") or "artifact"
        filename = f"{safe_kind}--{safe_title}--r{revision}.md"
        path = self.artifacts_root / str(record["key"]) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _encode_artifact_envelope(
                kind=kind, title=title, revision=revision, content=content
            ),
            encoding="utf-8",
        )
        return self._artifact(
            path,
            kind=kind,
            title=title,
            revision=revision,
            outcome="created",
            attempts=1,
        )

    def list_artifacts(self, ref: str, kind: str | None = None) -> list[ArtifactRef]:
        _path, record = self._find_record(ref)
        directory = self.artifacts_root / str(record["key"])
        if not directory.is_dir():
            return []
        artifacts: list[ArtifactRef] = []
        for path in sorted(directory.glob("*.md")):
            parsed = _parse_artifact_envelope(path.read_text(encoding="utf-8"))
            if parsed is None or (kind is not None and parsed["kind"] != kind):
                continue
            artifacts.append(self._artifact(path, **parsed))
        return artifacts

    def link_development_artifact(
        self,
        ref: str,
        artifact_url: str,
        artifact_type: str = "pull_request",
    ) -> dict[str, Any]:
        path, record = self._find_record(ref)
        link = {"url": artifact_url, "type": artifact_type}
        links = list(record.get("links") or [])
        if link not in links:
            links.append(link)
            record["links"] = links
            record["updatedAt"] = datetime.now(timezone.utc).isoformat()
            self._write_record(path, record)
        return {
            "linked": True,
            "mechanism": "local-record",
            "workItem": record["key"],
            **link,
        }

    def _records(self) -> list[tuple[Path, dict[str, Any]]]:
        records: list[tuple[Path, dict[str, Any]]] = []
        for state in LogicalState:
            for path in (self.root / state.value).glob("*.json"):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise IntegrationError(
                        "local_storage_error",
                        f"Could not read local work item {path}: {exc}",
                    ) from exc
                if isinstance(value, dict):
                    records.append((path, value))
        return records

    def _find_record(self, ref: str) -> tuple[Path, dict[str, Any]]:
        normalized = str(ref)
        for path, record in self._records():
            if normalized in {str(record.get("id")), str(record.get("key"))}:
                return path, record
        raise IntegrationError(
            "work_item_not_found", f"Local work item not found: {ref}"
        )

    def _next_key(self, kind: WorkItemKind) -> str:
        prefix = _PREFIXES[kind]
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
        numbers = [
            int(match.group(1))
            for _path, record in self._records()
            if (match := pattern.fullmatch(str(record.get("key") or ""))) is not None
        ]
        return f"{prefix}-{max(numbers, default=0) + 1:04d}"

    def _write_record(self, path: Path, record: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _work_item(self, record: dict[str, Any]) -> WorkItem:
        return WorkItem(
            str(record["id"]),
            str(record["key"]),
            str(record["title"]),
            WorkItemKind(str(record["kind"])),
            LogicalState(str(record["state"])),
            str(record["key"]),
            str(record.get("description") or ""),
            str(record["parentId"]) if record.get("parentId") else None,
            dict(record),
        )

    def _artifact(
        self,
        path: Path,
        *,
        kind: str,
        title: str,
        revision: str,
        content: str | None = None,
        outcome: str | None = None,
        attempts: int | None = None,
    ) -> ArtifactRef:
        relative = path.relative_to(self.root).as_posix()
        return ArtifactRef(
            relative,
            kind,
            title,
            revision,
            relative,
            {"content": content or "", "path": relative},
            outcome,
            attempts,
        )
