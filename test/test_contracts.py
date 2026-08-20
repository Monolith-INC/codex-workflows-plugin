import unittest

from scripts.orchestrator.contracts import (
    ARGUMENT,
    AcceptExtras,
    AnyType,
    ConstrainExtras,
    JsonType,
    ObjectContract,
    OneOfTypes,
    Parsed,
    Rejected,
    RejectExtras,
    Unconstrained,
    check_value,
    parse_value_contract,
)


def parse(raw):
    result = parse_value_contract(raw, "input_schema")
    assert isinstance(result, Parsed), result
    return result.contract


def diagnostics(raw):
    result = parse_value_contract(raw, "input_schema")
    assert isinstance(result, Rejected), result
    return tuple(item.code for item in result.diagnostics)


class TestTypeContract(unittest.TestCase):
    def test_the_json_schema_type_array_form_is_a_type_union(self):
        contract = parse(
            {"type": "object", "properties": {"note": {"type": ["string", "null"]}}}
        )
        self.assertEqual(
            contract.properties["note"],
            OneOfTypes(frozenset({JsonType.STRING, JsonType.NULL})),
        )

    def test_a_union_typed_value_accepts_every_member(self):
        contract = parse(
            {"type": "object", "properties": {"note": {"type": ["string", "null"]}}}
        )
        self.assertEqual(check_value({"note": "text"}, contract, ARGUMENT, not_object_message="x"), ())
        self.assertEqual(check_value({"note": None}, contract, ARGUMENT, not_object_message="x"), ())
        self.assertEqual(
            check_value({"note": 3}, contract, ARGUMENT, not_object_message="x"),
            ("Argument 'note' should be one of null, string, got int.",),
        )

    def test_an_undeclared_property_type_is_unconstrained(self):
        contract = parse({"type": "object", "properties": {"anything": {}}})
        self.assertEqual(contract.properties["anything"], AnyType())

    def test_an_unknown_type_name_is_a_diagnostic_not_a_crash(self):
        self.assertEqual(diagnostics({"type": "sting"}), ("unsupported_schema_type",))
        self.assertEqual(
            diagnostics({"type": "object", "properties": {"a": {"type": ["string", "sting"]}}}),
            ("unsupported_property_type",),
        )

    def test_a_non_object_top_level_schema_constrains_nothing(self):
        self.assertEqual(parse({"type": "string"}), Unconstrained())
        self.assertEqual(parse({}), Unconstrained())
        self.assertEqual(parse(None), Unconstrained())


class TestExtraProperties(unittest.TestCase):
    """`additionalProperties` is one contract; its boolean spelling is sugar."""

    def test_absent_and_true_both_parse_to_accept(self):
        self.assertEqual(parse({"type": "object"}).extras, AcceptExtras())
        self.assertEqual(
            parse({"type": "object", "additionalProperties": True}).extras, AcceptExtras()
        )

    def test_false_parses_to_reject(self):
        self.assertEqual(
            parse({"type": "object", "additionalProperties": False}).extras, RejectExtras()
        )

    def test_a_subschema_parses_to_a_constraint_instead_of_dropping_the_capability(self):
        contract = parse(
            {"type": "object", "additionalProperties": {"type": "string"}}
        )
        self.assertEqual(
            contract.extras, ConstrainExtras(OneOfTypes(frozenset({JsonType.STRING})))
        )

    def test_a_constrained_extra_is_type_checked(self):
        contract = parse({"type": "object", "additionalProperties": {"type": "string"}})
        self.assertEqual(
            check_value({"free": "ok"}, contract, ARGUMENT, not_object_message="x"), ()
        )
        self.assertEqual(
            check_value({"free": 1}, contract, ARGUMENT, not_object_message="x"),
            ("Argument 'free' should be string, got int.",),
        )

    def test_a_non_schema_value_is_still_a_diagnostic(self):
        self.assertEqual(
            diagnostics({"type": "object", "additionalProperties": "no"}),
            ("invalid_additional_properties",),
        )


class TestCheckValue(unittest.TestCase):
    def test_an_unconstrained_contract_accepts_anything(self):
        self.assertEqual(
            check_value("not an object", Unconstrained(), ARGUMENT, not_object_message="x"),
            (),
        )

    def test_an_object_contract_reports_the_callers_wording_for_non_objects(self):
        self.assertEqual(
            check_value(
                "text", ObjectContract(), ARGUMENT, not_object_message="expected object"
            ),
            ("expected object",),
        )

    def test_required_keys_are_reported_in_declaration_order(self):
        contract = parse({"type": "object", "required": ["second", "first"]})
        self.assertEqual(
            check_value({}, contract, ARGUMENT, not_object_message="x"),
            (
                "Missing required argument 'second'.",
                "Missing required argument 'first'.",
            ),
        )


if __name__ == "__main__":
    unittest.main()
