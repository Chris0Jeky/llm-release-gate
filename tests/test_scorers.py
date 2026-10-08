"""Scorer + adapter behavior at the item level."""

import pytest

from llm_release_gate.adapters import build_adapter
from llm_release_gate.adapters.extraction import ExtractionAdapter
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem, ScorerConfig
from llm_release_gate.scorers import aggregate_scores, build_scorers
from llm_release_gate.scorers.abstention import AbstentionScorer
from llm_release_gate.scorers.citations import CitationScorer
from llm_release_gate.scorers.quality import FieldMatchScorer, KeywordQualityScorer
from llm_release_gate.scorers.schema import JsonSchemaScorer, validate_against_schema


def grounded_item(**expected) -> DatasetItem:
    return DatasetItem(
        id="i1",
        input={"question": "q", "documents": [{"id": "d1", "text": "t"}, {"id": "d2", "text": "u"}]},
        expected=expected,
    )


def parse_rag(text: str, item: DatasetItem):
    return build_adapter("rag").parse(text, item)


# ------------------------------------------------------------- adapters

def test_grounded_adapter_extracts_citations_and_abstention():
    item = grounded_item()
    out = parse_rag("Answer per [doc:d1] and [doc:d2].", item)
    assert out.citations == ["d1", "d2"] and out.abstained is False
    out = parse_rag("I don't know based on these sources.", item)
    assert out.abstained is True
    out = parse_rag("There is not enough information to answer.", item)
    assert out.abstained is True


def test_extraction_adapter_strips_fences_and_reports_parse_errors():
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    assert adapter.parse('{"a": 1}', item).json_obj == {"a": 1}
    assert adapter.parse('```json\n{"a": 1}\n```', item).json_obj == {"a": 1}
    bad = adapter.parse("sorry, here is the data: a=1", item)
    assert bad.json_obj is None and "not valid JSON" in bad.parse_error


# ------------------------------------------------------------- keyword quality

def test_keyword_quality_pass_fail_and_applicability():
    scorer = KeywordQualityScorer({})
    item = grounded_item(quality={"must_contain": ["Blue"], "must_not_contain": ["maybe"]})
    ok = scorer.score_item(item, parse_rag("The sky is blue. [doc:d1]", item))
    assert ok["quality.pass_rate"]["passed"] is True
    missing = scorer.score_item(item, parse_rag("The sky is red.", item))
    assert missing["quality.pass_rate"]["passed"] is False
    assert "missing expected terms" in missing["quality.pass_rate"]["detail"]
    forbidden = scorer.score_item(item, parse_rag("Maybe blue.", item))
    assert forbidden["quality.pass_rate"]["passed"] is False
    # should-abstain items are the abstention scorer's job
    abstain_item = grounded_item(should_abstain=True, quality={"must_contain": ["x"]})
    assert scorer.score_item(abstain_item, parse_rag("whatever", abstain_item))[
        "quality.pass_rate"]["applicable"] is False


def test_field_match_exact_and_mismatch():
    scorer = FieldMatchScorer({})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"},
                       expected={"fields": {"vendor": "Acme", "total": 310}})
    good = scorer.score_item(item, adapter.parse('{"vendor": "Acme", "total": 310.0}', item))
    assert good["quality.pass_rate"]["passed"] is True  # 310.0 == 310
    bad = scorer.score_item(item, adapter.parse('{"vendor": "ACME Inc", "total": 310}', item))
    assert bad["quality.pass_rate"]["passed"] is False
    assert "vendor" in bad["quality.pass_rate"]["detail"]
    unparsed = scorer.score_item(item, adapter.parse("no json here", item))
    assert unparsed["quality.pass_rate"]["passed"] is False


def test_field_match_missing_key_fails():
    scorer = FieldMatchScorer({})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"},
                       expected={"fields": {"vendor": "Acme", "total": 310}})
    result = scorer.score_item(item, adapter.parse('{"vendor": "Acme"}', item))
    assert result["quality.pass_rate"]["passed"] is False
    assert "total" in result["quality.pass_rate"]["detail"]
    assert "<missing>" in result["quality.pass_rate"]["detail"]


def test_field_match_rejects_non_dict_json():
    scorer = FieldMatchScorer({})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"},
                       expected={"fields": {"vendor": "Acme"}})
    result = scorer.score_item(item, adapter.parse('[{"vendor":"Acme"}]', item))
    assert result["quality.pass_rate"]["passed"] is False
    assert result["quality.pass_rate"]["detail"] == "output is not a JSON object"
    result = scorer.score_item(item, adapter.parse('42', item))
    assert result["quality.pass_rate"]["passed"] is False
    assert result["quality.pass_rate"]["detail"] == "output is not a JSON object"


# ------------------------------------------------------------- abstention

def test_abstention_four_quadrants():
    scorer = AbstentionScorer({})
    should = grounded_item(should_abstain=True)
    should_not = grounded_item(should_abstain=False)
    abstained = parse_rag("I don't know.", should)
    answered = parse_rag("It is 42. [doc:d1]", should)

    r = scorer.score_item(should, abstained)
    assert r["abstention.false_answer_rate"]["passed"] is True
    r = scorer.score_item(should, answered)
    assert r["abstention.false_answer_rate"]["passed"] is False
    r = scorer.score_item(should_not, answered)
    assert r["abstention.over_abstention_rate"]["passed"] is True
    r = scorer.score_item(should_not, abstained)
    assert r["abstention.over_abstention_rate"]["passed"] is False
    # no expectation -> neither metric applies
    neither = grounded_item()
    r = scorer.score_item(neither, answered)
    assert r["abstention.false_answer_rate"]["applicable"] is False
    assert r["abstention.over_abstention_rate"]["applicable"] is False


# ------------------------------------------------------------- citations

def test_citation_validity_cases():
    scorer = CitationScorer({})
    item = grounded_item(should_abstain=False, must_cite=["d1"])
    ok = scorer.score_item(item, parse_rag("Fact. [doc:d1]", item))
    assert ok["citations.valid_rate"]["passed"] is True
    none = scorer.score_item(item, parse_rag("Fact with no marker.", item))
    assert none["citations.valid_rate"]["passed"] is False
    assert "no citations" in none["citations.valid_rate"]["detail"]
    ghost = scorer.score_item(item, parse_rag("Fact. [doc:d9]", item))
    assert "nonexistent" in ghost["citations.valid_rate"]["detail"]
    missed = scorer.score_item(item, parse_rag("Fact. [doc:d2]", item))
    assert "required sources not cited" in missed["citations.valid_rate"]["detail"]


def test_citation_ghost_source_fails():
    scorer = CitationScorer({})
    item = grounded_item(should_abstain=False, must_cite=["d1"])
    ghost = scorer.score_item(item, parse_rag("Fact. [doc:d9]", item))
    assert ghost["citations.valid_rate"]["passed"] is False
    assert "nonexistent" in ghost["citations.valid_rate"]["detail"]


def test_citation_missed_must_cite_fails():
    scorer = CitationScorer({})
    item = grounded_item(should_abstain=False, must_cite=["d1"])
    missed = scorer.score_item(item, parse_rag("Fact. [doc:d2]", item))
    assert missed["citations.valid_rate"]["passed"] is False
    assert "required sources not cited" in missed["citations.valid_rate"]["detail"]


def test_hedged_fabrication_is_an_answer_not_an_abstention():
    # "I don't know ... but here's a cited claim" must count as answering:
    # false_answer_rate records the violation and the citation gets validated.
    item = grounded_item(should_abstain=True)
    out = parse_rag(
        "I don't know the exact clause, but the notice period is 4 weeks [doc:hr-99].", item
    )
    assert out.abstained is False
    r = AbstentionScorer({}).score_item(item, out)
    assert r["abstention.false_answer_rate"]["passed"] is False
    c = CitationScorer({}).score_item(item, out)
    assert c["citations.valid_rate"]["applicable"] is True
    assert c["citations.valid_rate"]["passed"] is False
    # a hedge with no citation still reads as an abstention (documented limit)
    assert parse_rag("I don't know.", item).abstained is True


def test_citation_scorer_skips_abstentions_but_checks_fabricated_answers():
    scorer = CitationScorer({})
    abstain_item = grounded_item(should_abstain=True)
    abstained = parse_rag("I don't know.", abstain_item)
    assert scorer.score_item(abstain_item, abstained)["citations.valid_rate"]["applicable"] is False
    fabricated = parse_rag("Policy says 4 weeks. [doc:hr-99]", abstain_item)
    r = scorer.score_item(abstain_item, fabricated)
    assert r["citations.valid_rate"]["applicable"] is True
    assert r["citations.valid_rate"]["passed"] is False


def test_citation_no_documents_with_must_cite_fails_closed():
    scorer = CitationScorer({})
    item = DatasetItem(
        id="i1",
        input={"question": "q", "documents": []},
        expected={"must_cite": ["d2"]},
    )
    cited = scorer.score_item(item, parse_rag("Fact. [doc:d2]", item))
    assert cited["citations.valid_rate"]["applicable"] is True
    assert cited["citations.valid_rate"]["passed"] is False
    uncited = scorer.score_item(item, parse_rag("Fact with no marker.", item))
    assert uncited["citations.valid_rate"]["applicable"] is True
    assert uncited["citations.valid_rate"]["passed"] is False


def test_citation_no_documents_abstention_stays_inapplicable():
    scorer = CitationScorer({})
    item = DatasetItem(
        id="i1",
        input={"question": "q", "documents": []},
        expected={"must_cite": ["d2"]},
    )
    abstained = parse_rag("I don't know.", item)
    assert abstained.abstained is True
    assert scorer.score_item(item, abstained)["citations.valid_rate"]["applicable"] is False


def test_citation_no_documents_without_must_cite_stays_inapplicable():
    scorer = CitationScorer({})
    bare = DatasetItem(id="i1", input={"question": "q", "documents": []}, expected={})
    out = parse_rag("Fact. [doc:d2]", bare)
    assert out.abstained is False
    assert scorer.score_item(bare, out)["citations.valid_rate"]["applicable"] is False
    empty_must_cite = DatasetItem(
        id="i1",
        input={"question": "q"},
        expected={"must_cite": []},
    )
    out = parse_rag("Fact. [doc:d2]", empty_must_cite)
    assert scorer.score_item(empty_must_cite, out)["citations.valid_rate"]["applicable"] is False


def test_citation_no_documents_should_abstain_stays_inapplicable():
    scorer = CitationScorer({})
    item = DatasetItem(
        id="i1",
        input={"question": "q", "documents": []},
        expected={"should_abstain": True, "must_cite": ["d2"]},
    )
    out = parse_rag("Fact. [doc:d2]", item)
    assert out.abstained is False
    assert scorer.score_item(item, out)["citations.valid_rate"]["applicable"] is False


# ------------------------------------------------------------- json schema

SCHEMA = {
    "type": "object",
    "required": ["vendor", "total"],
    "properties": {
        "vendor": {"type": "string"},
        "total": {"type": "number"},
        "currency": {"type": "string", "enum": ["USD", "EUR"]},
        "lines": {"type": "array", "items": {"type": "object", "required": ["sku"]}},
    },
    "additionalProperties": False,
}


@pytest.mark.parametrize("value,fragment", [
    ({"total": 1}, "missing required property 'vendor'"),
    ({"vendor": "A", "total": "1"}, "expected number, got str"),
    ({"vendor": "A", "total": 1, "currency": "GBP"}, "not in enum"),
    ({"vendor": "A", "total": 1, "lines": [{}]}, "missing required property 'sku'"),
    ({"vendor": "A", "total": 1, "extra": 1}, "unexpected properties"),
    ({"vendor": "A", "total": True}, "expected number, got boolean"),
])
def test_schema_violations(value, fragment):
    errors = validate_against_schema(value, SCHEMA)
    assert any(fragment in e for e in errors), errors


def test_schema_valid_object_passes():
    value = {"vendor": "A", "total": 9.5, "currency": "EUR", "lines": [{"sku": "s"}]}
    assert validate_against_schema(value, SCHEMA) == []


def test_json_schema_scorer_requires_schema_option():
    with pytest.raises(GateConfigError, match="options.schema"):
        JsonSchemaScorer({})


def test_unenforceable_schemas_are_rejected_at_construction():
    # unsupported keyword: silently ignoring "minimum" would inflate valid_rate
    with pytest.raises(GateConfigError, match="minimum"):
        JsonSchemaScorer({"schema": {"type": "object", "properties": {
            "total": {"type": "number", "minimum": 0}}}})
    # union types crash the old validator mid-run; now a clean config error
    with pytest.raises(GateConfigError, match="union"):
        JsonSchemaScorer({"schema": {"type": "object", "properties": {
            "vendor": {"type": ["string", "null"]}}}})
    # schema-valued additionalProperties is not enforceable either
    with pytest.raises(GateConfigError, match="additionalProperties"):
        JsonSchemaScorer({"schema": {"type": "object",
                                     "additionalProperties": {"type": "string"}}})


def test_json_semantics_bool_is_not_int():
    # enum: JSON true must not satisfy an integer enum
    errors = validate_against_schema({"priority": True},
                                     {"properties": {"priority": {"enum": [0, 1, 2]}}})
    assert any("not in enum" in e for e in errors)
    # field_match: true is not an exact match for 1 (and 310.0 == 310 still holds)
    scorer = FieldMatchScorer({})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={"fields": {"quantity": 1}})
    r = scorer.score_item(item, adapter.parse('{"quantity": true}', item))
    assert r["quality.pass_rate"]["passed"] is False


def test_json_equal_keeps_bool_distinct_from_int_at_any_depth():
    from llm_release_gate.scorers import json_equal
    # bool != int inside nested lists and dicts (the top-level guard is not enough)
    assert json_equal([True, False], [1, 0]) is False
    assert json_equal({"flags": [True]}, {"flags": [1]}) is False
    assert json_equal({"a": {"b": False}}, {"a": {"b": 0}}) is False
    # genuine matches still hold, including int/float crossing at depth
    assert json_equal([1, 2.0], [1.0, 2]) is True
    assert json_equal({"a": [True, 3]}, {"a": [True, 3.0]}) is True
    assert json_equal({"x": 1}, {"x": 1, "y": 2}) is False  # differing key sets
    # field_match end-to-end: a nested bool-vs-int is a real mismatch, not a pass
    scorer = FieldMatchScorer({})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={"fields": {"flags": [True, False]}})
    r = scorer.score_item(item, adapter.parse('{"flags": [1, 0]}', item))
    assert r["quality.pass_rate"]["passed"] is False


def test_json_schema_scorer_counts_parse_failures_as_invalid():
    scorer = JsonSchemaScorer({"schema": {"type": "object"}})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    r = scorer.score_item(item, adapter.parse("not json", item))
    assert r["schema.valid_rate"]["passed"] is False


def test_json_schema_scorer_scores_object_violations():
    scorer = JsonSchemaScorer({"schema": SCHEMA})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    ok = scorer.score_item(item, adapter.parse('{"vendor": "A", "total": 1}', item))
    assert ok["schema.valid_rate"]["passed"] is True
    bad = scorer.score_item(item, adapter.parse('{"vendor": "A", "total": 1, "extra": 1}', item))
    assert bad["schema.valid_rate"]["passed"] is False
    assert "unexpected properties" in bad["schema.valid_rate"]["detail"]


def test_json_schema_scorer_item_pass_and_fail():
    scorer = JsonSchemaScorer({"schema": {"type": "object", "required": ["vendor"]}})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    ok = scorer.score_item(item, adapter.parse('{"vendor": "A"}', item))
    assert ok["schema.valid_rate"]["passed"] is True
    assert ok["schema.valid_rate"]["detail"] is None
    missing = scorer.score_item(item, adapter.parse('{}', item))
    assert missing["schema.valid_rate"]["passed"] is False
    assert "missing required property" in missing["schema.valid_rate"]["detail"]


@pytest.mark.parametrize("text", ["null", "```json\nnull\n```"])
def test_json_schema_scorer_passes_extraction_null_against_null_schema(text):
    scorer = JsonSchemaScorer({"schema": {"type": "null"}})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    r = scorer.score_item(item, adapter.parse(text, item))
    assert r["schema.valid_rate"]["passed"] is True


def test_json_schema_scorer_fails_extraction_null_against_object_schema():
    scorer = JsonSchemaScorer({"schema": {"type": "object"}})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    r = scorer.score_item(item, adapter.parse("null", item))
    assert r["schema.valid_rate"]["passed"] is False


@pytest.mark.parametrize("task", ["rag", "assistant"])
def test_json_schema_scorer_rejects_unstructured_text_against_null_schema(task):
    scorer = JsonSchemaScorer({"schema": {"type": "null"}})
    item = grounded_item()
    r = scorer.score_item(item, build_adapter(task).parse("null", item))
    assert r["schema.valid_rate"]["passed"] is False
    assert "no JSON" in r["schema.valid_rate"]["detail"]


def test_json_schema_scorer_reports_parse_error_detail():
    scorer = JsonSchemaScorer({"schema": {"type": "object"}})
    adapter = ExtractionAdapter()
    item = DatasetItem(id="x", input={"text": "t"}, expected={})
    r = scorer.score_item(item, adapter.parse("{bad", item))
    assert r["schema.valid_rate"]["passed"] is False
    assert "not valid JSON" in r["schema.valid_rate"]["detail"]


def test_build_scorers_rejects_duplicate_metric_owner():
    config = ScorerConfig(
        scorers=[
            {"type": "keyword_quality", "options": {}},
            {"type": "keyword_quality", "options": {}},
        ],
        path="test",
        sha256="test",
    )
    with pytest.raises(GateConfigError, match="exactly one owner"):
        build_scorers(config)


def test_aggregate_pass_and_violation_rates():
    quality = KeywordQualityScorer({})
    abstention = AbstentionScorer({})
    scorers = [quality, abstention]
    a1 = grounded_item(quality={"must_contain": ["alpha"]})
    a2 = grounded_item(quality={"must_contain": ["alpha"]})
    a3 = grounded_item()
    b1 = grounded_item(should_abstain=True)
    b2 = grounded_item(should_abstain=True)
    scored_items = []
    for item, text in [(a1, "alpha is here"), (a2, "nothing"), (a3, "alpha is here"), (b1, "The capital is Paris."), (b2, "I don't know")]:
        parsed = parse_rag(text, item)
        merged: dict = {}
        merged.update(quality.score_item(item, parsed))
        merged.update(abstention.score_item(item, parsed))
        scored_items.append(merged)
    assert scored_items[2]["quality.pass_rate"]["applicable"] is False
    agg = aggregate_scores(scorers, scored_items)
    assert agg["quality.pass_rate"]["value"] == 0.5
    assert agg["quality.pass_rate"]["numerator"] == 1
    assert agg["quality.pass_rate"]["denominator"] == 2
    assert agg["abstention.false_answer_rate"]["value"] == 0.5
    assert agg["abstention.false_answer_rate"]["numerator"] == 1
    assert agg["abstention.false_answer_rate"]["denominator"] == 2
