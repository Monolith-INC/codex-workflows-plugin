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
                [item["name"] for item in discovery.manifests], ["good-skill"]
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
            self.assertEqual(manifest_by_name(tmpdir)["good-skill"]["name"], "good-skill")

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
            self.assertEqual([item["name"] for item in discovery.manifests], ["good-skill"])
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
