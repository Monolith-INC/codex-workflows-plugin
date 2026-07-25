"""Agent session discovery and continuation rules for the write gate."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .git_utils import _run_git_cmd

DEFAULT_MAX_SESSION_AGE = timedelta(hours=8)
_OPEN_NEXT_RE = re.compile(r"^next:\s*(null|['\"]['\"]|~|)\s*$", re.MULTILINE | re.IGNORECASE)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*", re.DOTALL)
_TIMESTAMP_KEYS = ("timestamp", "started", "created")


@dataclass(frozen=True)
class SessionRecord:
    path: Path
    content: str
    timestamp: datetime
    branch: str | None
    is_open: bool


@dataclass(frozen=True)
class SessionGateResult:
    active: bool
    reason: str | None = None


def session_directories(vault_dir: str) -> list[Path]:
    """Return Agent_Sessions directories under the vault root and Projects/*/."""
    root = Path(vault_dir)
    dirs: list[Path] = []
    primary = root / "Agent_Sessions"
    if primary.is_dir():
        dirs.append(primary)
    projects = root / "Projects"
    if projects.is_dir():
        for child in sorted(projects.iterdir()):
            candidate = child / "Agent_Sessions"
            if candidate.is_dir():
                dirs.append(candidate)
    return dirs


def parse_session_file(path: Path, *, now: datetime | None = None) -> SessionRecord | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    frontmatter = _parse_frontmatter(content)
    timestamp = _coerce_timestamp(frontmatter, path, now=now or datetime.now(timezone.utc))
    branch = frontmatter.get("branch")
    if isinstance(branch, str):
        branch = branch.strip() or None
    else:
        branch = None
    return SessionRecord(
        path=path,
        content=content,
        timestamp=timestamp,
        branch=branch,
        is_open=bool(_OPEN_NEXT_RE.search(content)),
    )


def evaluate_session_gate(
    vault_dir: str,
    workspace_root: str = "",
    *,
    max_age: timedelta = DEFAULT_MAX_SESSION_AGE,
    now: datetime | None = None,
    current_branch: str | None = None,
) -> SessionGateResult:
    """Allow writes when an open session can be continued; otherwise explain how to fix."""
    clock = now or datetime.now().astimezone()
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)

    open_sessions = [
        record
        for directory in session_directories(vault_dir)
        for record in _iter_session_records(directory, now=clock)
        if record.is_open
    ]
    if not open_sessions:
        vault_name = Path(vault_dir).name or "AI_Codex"
        return SessionGateResult(
            active=False,
            reason=(
                f"Write blocked. You must initialize today's Agent Session log in "
                f"{vault_name}/Agent_Sessions/ (or {vault_name}/Projects/<project>/Agent_Sessions/) "
                f"with `next: null` before making code modifications."
            ),
        )

    branch = current_branch
    if branch is None and workspace_root:
        branch = _run_git_cmd(["git", "branch", "--show-current"], workspace_root) or None

    open_sessions.sort(key=lambda item: item.timestamp, reverse=True)

    matching = [s for s in open_sessions if s.branch and branch and s.branch == branch]
    unscoped = [s for s in open_sessions if not s.branch]

    if matching:
        newest = matching[0]
    elif unscoped:
        newest = unscoped[0]
    else:
        other = open_sessions[0]
        return SessionGateResult(
            active=False,
            reason=(
                f"Write blocked. Open session `{other.path.name}` is for branch "
                f"`{other.branch}` but the workspace is on `{branch or 'DETACHED'}`. "
                "Close that session and open a new one for this workstream."
            ),
        )

    age = clock - newest.timestamp
    if age > max_age:
        return SessionGateResult(
            active=False,
            reason=(
                f"Write blocked. Open session `{newest.path.name}` is older than "
                f"{int(max_age.total_seconds() // 3600)} hours. Close it by setting `next` to a "
                f"follow-up reference (or removing `next: null`), then open a new Agent Session."
            ),
        )

    return SessionGateResult(active=True)


def has_continuable_session(vault_dir: str, workspace_root: str = "", **kwargs) -> bool:
    return evaluate_session_gate(vault_dir, workspace_root, **kwargs).active


def _iter_session_records(directory: Path, *, now: datetime) -> Iterable[SessionRecord]:
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    records: list[SessionRecord] = []
    for name in names:
        if not name.endswith(".md"):
            continue
        record = parse_session_file(directory / name, now=now)
        if record is not None:
            records.append(record)
    return records


def _parse_frontmatter(content: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def _coerce_timestamp(frontmatter: dict[str, str], path: Path, *, now: datetime) -> datetime:
    for key in _TIMESTAMP_KEYS:
        raw = frontmatter.get(key)
        if not raw:
            continue
        parsed = _parse_datetime(raw)
        if parsed is not None:
            return parsed

    # Filename patterns: 2026-07-25T16-43-25-0300.md, 2026-07-25T16-43-25.md,
    # 2026-07-25-120000-session.md, or 2026-07-25.md
    stem = path.stem
    candidates: list[tuple[str, str]] = [
        ("%Y-%m-%dT%H-%M-%S%z", _normalize_filename_tz(stem)),
        ("%Y-%m-%dT%H-%M-%S", stem[:19] if len(stem) >= 19 else stem),
    ]
    compact = _compact_datetime_from_stem(stem)
    if compact:
        candidates.append(("%Y-%m-%d%H%M%S", compact))
    candidates.append(("%Y-%m-%d", stem[:10]))

    for fmt, candidate in candidates:
        try:
            parsed = datetime.strptime(candidate, fmt)
            if parsed.tzinfo is None:
                # Naive filename/frontmatter times are interpreted in the local timezone.
                parsed = parsed.replace(tzinfo=now.astimezone().tzinfo if now.tzinfo else timezone.utc)
            # Date-only filenames have no clock time; use mtime for age when available.
            if fmt == "%Y-%m-%d":
                try:
                    return datetime.fromtimestamp(path.stat().st_mtime, tz=parsed.tzinfo)
                except OSError:
                    return parsed
            return parsed
        except ValueError:
            continue

    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=now.tzinfo or timezone.utc)
    except OSError:
        return now


def _compact_datetime_from_stem(stem: str) -> str | None:
    """Parse YYYY-MM-DD-HHMMSS… stems used by legacy session fixtures."""
    if len(stem) < 17 or stem[10] != "-":
        return None
    date_part = stem[:10]
    rest = stem[11:]
    digits = ""
    for ch in rest:
        if ch.isdigit():
            digits += ch
            if len(digits) == 6:
                break
        elif digits:
            break
    if len(digits) != 6:
        return None
    try:
        datetime.strptime(date_part, "%Y-%m-%d")
        datetime.strptime(digits, "%H%M%S")
    except ValueError:
        return None
    return date_part + digits


def _normalize_filename_tz(stem: str) -> str:
    # 2026-07-25T16-43-25-0300 -> 2026-07-25T16-43-25-0300 (strptime %z wants +0300)
    if len(stem) >= 24 and stem[-5] in "-+" and stem[-4:].isdigit():
        sign = "+" if stem[-5] == "-" and stem.count("-") >= 4 else stem[-5]
        # Our files use -0300 meaning UTC-3? Existing convention uses -0300 for America/Sao_Paulo (UTC-3),
        # which is unusual vs +0300. Treat trailing -HHMM as timezone offset with leading minus kept.
        body, tz = stem[:-5], stem[-5:]
        if tz.startswith("-") and tz[1:].isdigit():
            return body + tz  # -0300
        return body + sign + tz.lstrip("+-")
    return stem


def _parse_datetime(raw: str) -> datetime | None:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None
