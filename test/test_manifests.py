import json
import tempfile
import unittest
from pathlib import Path

from scripts.orchestrator.manifests import (
    discover_manifests,
    manifest_by_name,
    read_manifests,
)


class TestManifests(unittest.TestCase):
    def test_malformed_json_is_isolated_with_a_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_dir = Path(tmpdir) / "bad-skill"
            bad_dir.mkdir()
            (bad_dir / "manifest.json").write_text("{not json", encoding="utf-8")

            good_dir = Path(tmpdir) / "good-skill"
            good_dir.mkdir()
            (good_dir / "manifest.json").write_text(
                json.dumps({"name": "good-skill"}), encoding="utf-8"
            )

            discovery = discover_manifests(tmpdir)
            self.assertEqual(
                [item.name for item in discovery.manifests], ["good-skill"]
            )
            self.assertEqual(
                [item.code for item in discovery.diagnostics], ["invalid_json"]
            )

    def test_ignores_non_object_manifest_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "bad-skill"
            skill_dir.mkdir()
            (skill_dir / "manifest.json").write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

            good_dir = Path(tmpdir) / "good-skill"
            good_dir.mkdir()
            (good_dir / "manifest.json").write_text(
                json.dumps({"name": "good-skill", "description": "ok"}),
                encoding="utf-8",
            )

            manifests = read_manifests(tmpdir)
            self.assertEqual(len(manifests), 1)
            self.assertEqual(manifest_by_name(tmpdir)["good-skill"].name, "good-skill")

    def test_malformed_schema_is_isolated_with_a_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_dir = Path(tmpdir) / "bad-skill"
            bad_dir.mkdir()
            (bad_dir / "manifest.json").write_text(
                json.dumps({"name": "bad-skill", "input_schema": ["not", "an", "object"]}),
                encoding="utf-8",
            )

            good_dir = Path(tmpdir) / "good-skill"
            good_dir.mkdir()
            (good_dir / "manifest.json").write_text(
                json.dumps({"name": "good-skill", "input_schema": {"type": "object"}}),
                encoding="utf-8",
            )

            discovery = discover_manifests(tmpdir)
            self.assertEqual([item.name for item in discovery.manifests], ["good-skill"])
            self.assertEqual([item.code for item in discovery.diagnostics], ["schema_not_object"])

    def test_duplicate_names_are_all_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for directory in ("first", "second"):
                skill_dir = Path(tmpdir) / directory
                skill_dir.mkdir()
                (skill_dir / "manifest.json").write_text(
                    json.dumps({"name": "duplicate"}), encoding="utf-8"
                )

            discovery = discover_manifests(tmpdir)
            self.assertEqual(discovery.manifests, ())
            self.assertEqual(
                [item.code for item in discovery.diagnostics],
                ["duplicate_name", "duplicate_name"],
            )

    def test_type_array_schemas_are_discovered_and_do_not_abort_the_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            union_dir = Path(tmpdir) / "union-skill"
            union_dir.mkdir()
            (union_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "name": "union-skill",
                        "input_schema": {
                            "type": "object",
                            "properties": {"note": {"type": ["string", "null"]}},
                        },
                    }
                ),
                encoding="utf-8",
            )

            sibling_dir = Path(tmpdir) / "plain-skill"
            sibling_dir.mkdir()
            (sibling_dir / "manifest.json").write_text(
                json.dumps({"name": "plain-skill"}), encoding="utf-8"
            )

            discovery = discover_manifests(tmpdir)
            self.assertEqual(
                sorted(item.name for item in discovery.manifests),
                ["plain-skill", "union-skill"],
            )
            self.assertEqual(discovery.diagnostics, ())

    def test_subschema_additional_properties_keeps_the_capability(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "open-skill"
            skill_dir.mkdir()
            (skill_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "name": "open-skill",
                        "input_schema": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            discovery = discover_manifests(tmpdir)
            self.assertEqual([item.name for item in discovery.manifests], ["open-skill"])
            self.assertEqual(discovery.diagnostics, ())

    def test_the_wire_form_still_serializes_to_the_manifest_on_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            body = {
                "name": "wire-skill",
                "description": "keeps its host projection",
                "input_schema": {
                    "type": "object",
                    "properties": {"ticket_id": {"type": "string"}},
                    "required": ["ticket_id"],
                },
            }
            skill_dir = Path(tmpdir) / "wire-skill"
            skill_dir.mkdir()
            (skill_dir / "manifest.json").write_text(json.dumps(body), encoding="utf-8")

            manifest = manifest_by_name(tmpdir)["wire-skill"]
            self.assertEqual(
                json.dumps(manifest.wire, sort_keys=True), json.dumps(body, sort_keys=True)
            )

    def test_invalid_nested_schema_shapes_are_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "bad"
            skill_dir.mkdir()
            (skill_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "name": "bad",
                        "input_schema": {
                            "type": "object",
                            "required": "argument",
                            "properties": {"argument": "string"},
                            "additionalProperties": "no",
                        },
                    }
                ),
                encoding="utf-8",
            )

            codes = {item.code for item in discover_manifests(tmpdir).diagnostics}
            self.assertEqual(
                codes,
                {"invalid_required", "invalid_property_schema", "invalid_additional_properties"},
            )


if __name__ == "__main__":
    unittest.main()
