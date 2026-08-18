import unittest

from scripts.orchestrator.schema import validate_inputs


class TestInputSchema(unittest.TestCase):
    def test_required_and_type_validation(self):
        manifest = {
            "name": "review-pr",
            "input_schema": {
                "type": "object",
                "properties": {"pr_number": {"type": "string"}},
                "required": ["pr_number"],
            },
        }
        self.assertEqual(validate_inputs({}, manifest), ["Missing required argument 'pr_number'."])
        self.assertEqual(
            validate_inputs({"pr_number": 42}, manifest),
            ["Argument 'pr_number' should be string, got int."],
        )
        self.assertEqual(validate_inputs({"pr_number": "693"}, manifest), [])

    def test_unknown_arguments_remain_allowed_by_default(self):
        manifest = {
            "name": "compatible",
            "input_schema": {
                "type": "object",
                "properties": {"declared": {"type": "string"}},
            },
        }
        self.assertEqual(validate_inputs({"undeclared": 1}, manifest), [])

    def test_unknown_arguments_are_rejected_when_manifest_opts_in(self):
        manifest = {
            "name": "strict",
            "input_schema": {
                "type": "object",
                "properties": {"declared": {"type": "string"}},
                "additionalProperties": False,
            },
        }
        self.assertEqual(
            validate_inputs({"declared": "yes", "undeclared": 1}, manifest),
            ["Unknown argument 'undeclared' is not allowed."],
        )


if __name__ == "__main__":
    unittest.main()
