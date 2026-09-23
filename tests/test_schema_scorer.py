"""JsonSchemaScorer.score_item + validate_schema_definition fail-closed branches.

Pins current behaviour of src/llm_release_gate/scorers/schema.py (2026-09-23):
score_item paths go through the scorer (not validate_against_schema directly);
schema-definition errors raise GateConfigError fail-closed at construction.
"""

import pytest

from llm_release_gate.adapters import ParsedOutput
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem
from llm_release_gate.scorers.schema import JsonSchemaScorer, validate_schema_definition


SCHEMA = {
    "type": "object",
    "required": ["vendor", "total"],
    "properties": {
        "vendor": {"type": "string"},
        "total": {"type": "number"},
    },
    "additionalProperties": False,
}


def _item() -> DatasetItem:
    return DatasetItem(id="x", input={"text": "t"}, expected={})


def _score(json_obj, parse_error=None) -> dict:
    scorer = JsonSchemaScorer({"schema": SCHEMA})
    output = ParsedOutput(text="raw", json_obj=json_obj, parse_error=parse_error)
    return scorer.score_item(_item(), output)["schema.valid_rate"]


# ------------------------------------------------------------- score_item


def test_score_item_valid_object_passes_with_none_detail():
    assert _score({"vendor": "A", "total": 9.5}) == {
        "applicable": True,
        "passed": True,
        "detail": None,
    }


def test_score_item_invalid_object_fails_with_violation_detail():
    result = _score({"total": 1})
    assert result["applicable"] is True
    assert result["passed"] is False
    assert result["detail"] == "$: missing required property 'vendor'"


def test_score_item_invalid_object_boundary_empty_object_lists_all_missing():
    result = _score({})
    assert result["passed"] is False
    assert result["detail"] == (
        "$: missing required property 'vendor'; "
        "$: missing required property 'total'"
    )


def test_score_item_unparseable_output_fails_with_parse_error_detail():
    result = _score(None, parse_error="oops: not valid JSON")
    assert result == {
        "applicable": True,
        "passed": False,
        "detail": "oops: not valid JSON",
    }


def test_score_item_unparseable_output_boundary_no_parse_error_uses_fallback():
    result = _score(None, parse_error=None)
    assert result == {
        "applicable": True,
        "passed": False,
        "detail": "no JSON object in output",
    }


def test_score_item_non_object_json_value_fails_with_type_mismatch():
    result = _score([1, 2])
    assert result["applicable"] is True
    assert result["passed"] is False
    assert result["detail"] == "$: expected object, got list"


def test_score_item_non_object_json_value_boundary_scalar():
    result = _score("just a string")
    assert result["passed"] is False
    assert result["detail"] == "$: expected object, got str"


# ------------------------------------------------------------- validate_schema_definition


def test_validate_schema_definition_rejects_non_dict_schema():
    with pytest.raises(GateConfigError, match="must be an object"):
        validate_schema_definition(["type", "object"])


def test_validate_schema_definition_rejects_non_dict_boundary_none():
    with pytest.raises(GateConfigError, match=r"schema at \$ must be an object"):
        validate_schema_definition(None)


def test_validate_schema_definition_rejects_bad_required_string():
    with pytest.raises(GateConfigError, match="'required'.*must be a list of strings"):
        validate_schema_definition({"type": "object", "required": "vendor"})


def test_validate_schema_definition_rejects_bad_required_boundary_non_string_member():
    with pytest.raises(GateConfigError, match="'required'.*must be a list of strings"):
        validate_schema_definition({"type": "object", "required": ["vendor", 1]})


def test_validate_schema_definition_rejects_bad_enum_non_list():
    with pytest.raises(GateConfigError, match="'enum'.*must be a list"):
        validate_schema_definition({"type": "string", "enum": "USD"})


def test_validate_schema_definition_rejects_bad_enum_boundary_none():
    with pytest.raises(GateConfigError, match="'enum'.*must be a list"):
        validate_schema_definition({"type": "string", "enum": None})


def test_validate_schema_definition_rejects_bad_additional_properties_string():
    with pytest.raises(GateConfigError, match="'additionalProperties'.*must be true or false"):
        validate_schema_definition({"type": "object", "additionalProperties": "no"})


def test_validate_schema_definition_rejects_bad_additional_properties_boundary_int():
    # 1 is truthy but not a bool; the validator requires an actual boolean.
    with pytest.raises(GateConfigError, match="'additionalProperties'.*must be true or false"):
        validate_schema_definition({"type": "object", "additionalProperties": 1})
