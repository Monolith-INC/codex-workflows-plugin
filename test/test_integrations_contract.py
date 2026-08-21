import json
import tempfile
import unittest
from pathlib import Path

from scripts.integrations.adapters import tracker_adapter
from scripts.integrations.config import load_config
from scripts.integrations.gateway import process_message


class IntegrationContractTests(unittest.TestCase):
    def _config(self, root: Path) -> None:
        path = root / ".codex-workflows" / "integrations.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "schemaVersion": 1,
            "branchTemplate": "{category}/{key}-{slug}",
            "tracker": {"adapter": "linear", "connection": {"command": "true", "args": []}, "bindings": {}},
            "scm": {"adapter": "github", "connection": {"command": "true", "args": []}},
        }))

    def test_branch_convention_maps_linear_and_azure_keys(self):
        adapter = tracker_adapter({"adapter": "linear", "branchPattern": "{category}/{key}-{slug}", "connection": {"command": "true", "args": []}})
        self.assertEqual(adapter.resolve_branch_key("feature/ENG-42-work"), "ENG-42")
        self.assertEqual(adapter.resolve_branch_key("bug/123-fix"), "123")
        self.assertIsNone(adapter.resolve_branch_key("feature/no-key"))

    def test_config_requires_generic_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._config(root)
            config = load_config(root)
            self.assertEqual(config.branch_template, "{category}/{key}-{slug}")

    def test_gateway_advertises_tracker_and_scm_boundaries(self):
        response = json.loads(process_message(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})))
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertIn("tracker_create_work_item", names)
        self.assertIn("tracker_publish_artifact", names)
        self.assertIn("tracker_list_children", names)
        self.assertIn("scm_create_pull_request", names)
        self.assertIn("scm_list_review_threads", names)


if __name__ == "__main__":
    unittest.main()
