"""ExtractionAdapter rejects non-finite JSON constants fail-closed."""

import pytest

from llm_release_gate.adapters.extraction import ExtractionAdapter
from llm_release_gate.loading import DatasetItem
from llm_release_gate.scorers.schema import JsonSchemaScorer


def _item() -> DatasetItem:
    return DatasetItem(id="x", input={"text": "t"}, expected={})


@pytest.mark.parametrize(
    "text",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        '{"total": NaN}',
        '```json\n{"total": Infinity}\n```',
        "1e999",
        '{"total": -1e999}',
    ],
)
def test_nonfinite_literals_are_parse_errors(text):
    parsed = ExtractionAdapter().parse(text, _item())
    assert parsed.parse_error
    assert parsed.parse_error.startswith("not valid JSON")
    assert parsed.has_json is False


def test_nan_parse_does_not_pass_number_schema():
    parsed = ExtractionAdapter().parse("NaN", _item())
    result = JsonSchemaScorer({"schema": {"type": "number"}}).score_item(
        _item(), parsed
    )["schema.valid_rate"]
    assert result["passed"] is False


@pytest.mark.parametrize("text", ['{"total": 1.5}', "null", "0"])
def test_finite_json_still_parses(text):
    parsed = ExtractionAdapter().parse(text, _item())
    assert parsed.parse_error is None
    assert parsed.has_json is True
