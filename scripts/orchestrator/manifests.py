from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

_SUPPORTED_TYPES = frozenset(
    {"string", "boolean", "number", "integer", "object", "array"}
)


@dataclass(frozen=True)
class ManifestDiagnostic:
    """One capability manifest rejected during discovery."""

    path: Path
    code: str
    message: str


@dataclass(frozen=True)
class ManifestDiscovery:
    """Valid manifests and deterministic diagnostics from one filesystem scan."""

    manifests: tuple[dict[str, Any], ...] = ()
    diagnostics: tuple[ManifestDiagnostic, ...] = ()


def validate_manifest(data: Any, path: str | Path) -> tuple[ManifestDiagnostic, ...]:
    """Validate the manifest subset consumed by the orchestrator."""
    manifest_path = Path(path)
    issues: list[ManifestDiagnostic] = []

    def reject(code: str, message: str) -> None:
        issues.append(ManifestDiagnostic(manifest_path, code, message))

    if not isinstance(data, dict):
        reject("root_not_object", "Manifest root must be an object.")
        return tuple(issues)

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        reject("invalid_name", "Manifest name must be a non-empty string.")

    description = data.get("description")
    if description is not None and not isinstance(description, str):
        reject("invalid_description", "Manifest description must be a string.")

    for field in ("input_schema", "output_signature"):
        schema = data.get(field)
        if schema is None:
            continue
        issues.extend(_validate_schema(schema, manifest_path, field))

    return tuple(issues)


def discover_manifests(skills_dir: str | Path) -> ManifestDiscovery:
    """Discover valid manifests while isolating and describing invalid ones."""
    base_path = Path(skills_dir)
    if not base_path.is_dir():
        return ManifestDiscovery()

    candidates: list[tuple[Path, dict[str, Any]]] = []
    diagnostics: list[ManifestDiagnostic] = []

    for skill_path in sorted(base_path.iterdir()):
        if not skill_path.is_dir():
            continue
        manifest_file = skill_path / "manifest.json"
        if not manifest_file.is_file():
            continue
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            diagnostics.append(
                ManifestDiagnostic(
                    manifest_file,
                    "invalid_json",
                    f"Manifest is not valid JSON: {exc.msg}.",
                )
            )
            continue
        except OSError as exc:
            diagnostics.append(
                ManifestDiagnostic(
                    manifest_file,
                    "unreadable",
                    f"Manifest could not be read: {exc}.",
                )
            )
            continue

        issues = validate_manifest(data, manifest_file)
        if issues:
            diagnostics.extend(issues)
            continue
        candidates.append((manifest_file, data))

    name_counts = Counter(data["name"] for _, data in candidates)
    manifests: list[dict[str, Any]] = []
    for path, data in candidates:
        if name_counts[data["name"]] > 1:
            diagnostics.append(
                ManifestDiagnostic(
                    path,
                    "duplicate_name",
                    f"Capability name '{data['name']}' is declared more than once.",
                )
            )
            continue
        manifests.append(data)

    return ManifestDiscovery(tuple(manifests), tuple(diagnostics))


def read_manifests(skills_dir: str | Path) -> list[dict[str, Any]]:
    """Compatibility view of the valid manifests discovered under ``skills_dir``."""
    discovery = discover_manifests(skills_dir)
    for diagnostic in discovery.diagnostics:
        logger.warning(
            "ignored capability manifest %s [%s]: %s",
            diagnostic.path,
            diagnostic.code,
            diagnostic.message,
        )
    return list(discovery.manifests)


def manifest_by_name(skills_dir: str | Path) -> dict[str, dict[str, Any]]:
    return {manifest["name"]: manifest for manifest in read_manifests(skills_dir)}


def load_skill_instructions(skills_dir: str | Path, skill_name: str) -> str:
    skill_md = Path(skills_dir) / skill_name / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"Missing SKILL.md for skill '{skill_name}'")
    return skill_md.read_text(encoding="utf-8")


def _validate_schema(
    schema: Any, path: Path, field: str
) -> tuple[ManifestDiagnostic, ...]:
    issues: list[ManifestDiagnostic] = []

    def reject(code: str, message: str) -> None:
        issues.append(ManifestDiagnostic(path, code, message))

    if not isinstance(schema, dict):
        reject("schema_not_object", f"{field} must be an object.")
        return tuple(issues)

    schema_type = schema.get("type", "object")
    if schema_type not in _SUPPORTED_TYPES:
        reject(
            "unsupported_schema_type",
            f"{field}.type '{schema_type}' is not supported.",
        )

    required = schema.get("required", [])
    if not isinstance(required, list) or not all(
        isinstance(item, str) and item for item in required
    ):
        reject(
            "invalid_required",
            f"{field}.required must be a list of non-empty strings.",
        )

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        reject("invalid_properties", f"{field}.properties must be an object.")
    else:
        for name, property_schema in properties.items():
            if not isinstance(name, str) or not name:
                reject(
                    "invalid_property_name",
                    f"{field} property names must be non-empty strings.",
                )
                continue
            if not isinstance(property_schema, dict):
                reject(
                    "invalid_property_schema",
                    f"{field}.properties.{name} must be an object.",
                )
                continue
            property_type = property_schema.get("type")
            if property_type is not None and property_type not in _SUPPORTED_TYPES:
                reject(
                    "unsupported_property_type",
                    f"{field}.properties.{name}.type '{property_type}' is not supported.",
                )

    additional = schema.get("additionalProperties", True)
    if not isinstance(additional, bool):
        reject(
            "invalid_additional_properties",
            f"{field}.additionalProperties must be a boolean when present.",
        )

    return tuple(issues)
