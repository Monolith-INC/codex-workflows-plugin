import unittest

from scripts.integrations.discovery import (
    TRACKER_BINDING_CANDIDATES,
    apply_discovery_to_config,
    discover_provider_capabilities,
    mapping_presets,
    resolve_bindings,
    validate_tracker_mappings,
    verify_integration_capabilities,
)


class DiscoveryTests(unittest.TestCase):
    def test_resolve_bindings_prefers_available_aliases(self):
        resolved, missing = resolve_bindings(
            ["get_issue", "create_issue", "update_issue", "create_comment", "list_comments"],
            TRACKER_BINDING_CANDIDATES,
            {"get_work_item": "missing_tool"},
        )
        self.assertEqual(resolved["get_work_item"], "get_issue")
        self.assertIn("search_work_items", missing)
        self.assertIn("list_children", missing)

    def test_mapping_presets_cover_required_keys(self):
        for adapter in ("linear", "azure_devops"):
            missing = validate_tracker_mappings(mapping_presets(adapter))
            self.assertEqual(missing, ())

    def test_discover_with_fixture_tools(self):
        tools = [
            "get_issue",
            "list_issues",
            "create_issue",
            "update_issue",
            "create_comment",
            "list_comments",
            "list_issue_children",
        ]
        result = discover_provider_capabilities(
            kind="tracker",
            adapter="linear",
            connection={"command": "true", "args": []},
            discovered_tools=tools,
        )
        self.assertEqual(result.resolved_bindings["list_children"], "list_issue_children")
        self.assertEqual(result.missing_capabilities, ())
        self.assertEqual(result.suggested_mappings["states"]["in_progress"], "In Progress")

    def test_apply_discovery_writes_bindings_and_mappings(self):
        discovery = discover_provider_capabilities(
            kind="tracker",
            adapter="linear",
            connection={"command": "true", "args": []},
            discovered_tools=["get_issue", "list_issues", "create_issue", "list_issue_children", "update_issue", "create_comment", "list_comments"],
        )
        payload = apply_discovery_to_config(
            {"tracker": {"adapter": "linear", "bindings": {}, "mappings": {"kinds": {}, "states": {}}}, "scm": {"adapter": "github"}},
            tracker_discovery=discovery,
        )
        self.assertEqual(payload["tracker"]["bindings"]["get_work_item"], "get_issue")
        self.assertTrue(payload["tracker"]["mappings"]["kinds"]["feature"])

    def test_verify_integration_capabilities_flags_empty_maps(self):
        problems = verify_integration_capabilities(
            {
                "tracker": {"adapter": "linear", "bindings": {}, "mappings": {"kinds": {}, "states": {}}},
                "scm": {"adapter": "github"},
            }
        )
        self.assertTrue(any("binding" in item for item in problems))
        self.assertTrue(any("mapping" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
