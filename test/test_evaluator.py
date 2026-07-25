import unittest
from scripts.orchestrator.evaluator import collect_critiques, evaluate_output, skill_validation_critiques

class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "name": "start-ticket",
            "output_signature": {
                "type": "object",
                "required": ["success"],
                "properties": {
                    "active_ledger_path": {
                        "type": "string"
                    },
                    "success": {
                        "type": "boolean"
                    }
                }
            }
        }

    def test_evaluate_valid_output(self):
        valid_output = {
            "active_ledger_path": "/vault/Tickets/Active/TICKET-1.md",
            "success": True
        }
        critiques = evaluate_output(valid_output, self.manifest)
        self.assertEqual(len(critiques), 0, "Valid output should return 0 critiques")

    def test_evaluate_missing_property(self):
        invalid_output = {
            "active_ledger_path": "/vault/Tickets/Active/TICKET-1.md"
        }
        critiques = evaluate_output(invalid_output, self.manifest)
        self.assertEqual(len(critiques), 1)
        self.assertIn("Missing required output property 'success'", critiques[0])

    def test_evaluate_wrong_type(self):
        invalid_output = {
            "active_ledger_path": 12345,  # Should be string
            "success": "yes"              # Should be boolean
        }
        critiques = evaluate_output(invalid_output, self.manifest)
        self.assertEqual(len(critiques), 2)
        
        critique_texts = " ".join(critiques)
        self.assertIn("should be a string", critique_texts)
        self.assertIn("should be a boolean", critique_texts)

    def test_evaluate_integer_rejects_boolean(self):
        manifest = {
            "name": "count-skill",
            "output_signature": {
                "type": "object",
                "properties": {"count": {"type": "integer"}},
            },
        }
        critiques = evaluate_output({"count": True}, manifest)
        self.assertEqual(len(critiques), 1)
        self.assertIn("should be an integer", critiques[0])

    def test_evaluate_number_rejects_boolean(self):
        manifest = {
            "name": "ratio-skill",
            "output_signature": {
                "type": "object",
                "properties": {"ratio": {"type": "number"}},
            },
        }
        critiques = evaluate_output({"ratio": True}, manifest)
        self.assertEqual(len(critiques), 1)
        self.assertIn("should be a number", critiques[0])

    def test_evaluate_wrong_base_type(self):
        # The schema expects a dictionary/object, not a raw string
        invalid_output = "/vault/Tickets/Active/TICKET-1.md"
        critiques = evaluate_output(invalid_output, self.manifest)
        self.assertEqual(len(critiques), 1)
        self.assertIn("Expected output to be a dictionary/object", critiques[0])

    def test_skill_validation_critiques_from_actor_critic(self):
        output = {
            "ticket_id": "T-1",
            "spec_kind": "tech-spec",
            "specs_dir": "AI_Codex/Specs/t-1",
            "mode": "instructions",
            "critiques": "Draft contains placeholder tokens",
        }
        manifest = {
            "name": "write-spec",
            "output_signature": {
                "type": "object",
                "required": ["ticket_id", "spec_kind", "specs_dir", "mode"],
                "properties": {
                    "ticket_id": {"type": "string"},
                    "spec_kind": {"type": "string"},
                    "specs_dir": {"type": "string"},
                    "mode": {"type": "string"},
                    "critiques": {"type": "string"},
                },
            },
        }
        self.assertEqual(evaluate_output(output, manifest), [])
        self.assertEqual(skill_validation_critiques(output), ["Draft contains placeholder tokens"])
        self.assertEqual(collect_critiques(output, manifest), ["Draft contains placeholder tokens"])

    def test_skill_validation_skips_completed_mode(self):
        output = {"mode": "completed", "critiques": "stale"}
        self.assertEqual(skill_validation_critiques(output), [])

if __name__ == '__main__':
    unittest.main()
