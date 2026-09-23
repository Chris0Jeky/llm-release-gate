"""Scorer registry behavior: aggregation, construction, and helpers.

Pins the contract in ``llm_release_gate/scorers/__init__.py``: rates are
computed over applicable items only, unknown/duplicate scorer wiring is a
config error, and ``item_result``/``json_equal`` keep their edge semantics.
"""

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import ScorerConfig
from llm_release_gate.scorers import (
    aggregate_scores,
    build_scorers,
    item_result,
    json_equal,
)
from llm_release_gate.scorers.abstention import AbstentionScorer
from llm_release_gate.scorers.quality import KeywordQualityScorer


def scorer_config(*entries: dict) -> ScorerConfig:
    return ScorerConfig(scorers=list(entries), path="s.json", sha256="sha256:test")


# ------------------------------------------------------------- aggregate_scores


def test_aggregate_pass_rate_excludes_inapplicable_items():
    scorer = KeywordQualityScorer({})
    scored = [
        {"quality.pass_rate": item_result(True, True)},
        {"quality.pass_rate": item_result(True, False)},
        {"quality.pass_rate": item_result(False)},
    ]
    agg = aggregate_scores([scorer], scored)["quality.pass_rate"]
    assert agg["value"] == pytest.approx(0.5)
    assert agg["numerator"] == 1
    assert agg["denominator"] == 2
    assert agg["available"] is True


def test_aggregate_violation_rate_excludes_inapplicable_items():
    scorer = AbstentionScorer({})
    scored = [
        {"abstention.false_answer_rate": item_result(True, True),
         "abstention.over_abstention_rate": item_result(False)},
        {"abstention.false_answer_rate": item_result(True, False),
         "abstention.over_abstention_rate": item_result(False)},
        {"abstention.false_answer_rate": item_result(False),
         "abstention.over_abstention_rate": item_result(False)},
    ]
    agg = aggregate_scores([scorer], scored)["abstention.false_answer_rate"]
    # violation_rate: numerator counts not-passed (the one False), over 2 applicable.
    assert agg["value"] == pytest.approx(0.5)
    assert agg["numerator"] == 1
    assert agg["denominator"] == 2
    assert agg["available"] is True


def test_aggregate_all_inapplicable_is_unavailable():
    scorers = [KeywordQualityScorer({}), AbstentionScorer({})]
    scored = [
        {"quality.pass_rate": item_result(False),
         "abstention.false_answer_rate": item_result(False),
         "abstention.over_abstention_rate": item_result(False)},
        {"quality.pass_rate": item_result(False),
         "abstention.false_answer_rate": item_result(False),
         "abstention.over_abstention_rate": item_result(False)},
    ]
    aggs = aggregate_scores(scorers, scored)
    for key in ("quality.pass_rate", "abstention.false_answer_rate",
                "abstention.over_abstention_rate"):
        assert aggs[key]["available"] is False
        assert aggs[key]["value"] is None
        assert aggs[key]["numerator"] is None
        assert aggs[key]["denominator"] is None
        assert aggs[key]["note"] == "no applicable items"


def test_aggregate_empty_scored_items_is_unavailable():
    aggs = aggregate_scores([KeywordQualityScorer({})], [])
    agg = aggs["quality.pass_rate"]
    assert agg == {
        "value": None,
        "available": False,
        "unit": "rate",
        "direction": "higher_better",
        "numerator": None,
        "denominator": None,
        "n": None,
        "kind": "heuristic_rate",
        "note": "no applicable items",
    }


def test_aggregate_unknown_mode_is_config_error():
    from llm_release_gate.scorers import Scorer

    class BogusModeScorer(Scorer):
        name = "bogus"
        version = "1"
        metrics = {"bogus.rate": {"direction": "higher_better",
                                  "kind": "rate", "mode": "median_rate"}}

        def score_item(self, item, output):
            return {"bogus.rate": item_result(True, True)}

    with pytest.raises(GateConfigError, match="unknown mode for 'bogus.rate'"):
        aggregate_scores([BogusModeScorer({})],
                         [{"bogus.rate": item_result(True, True)}])


# ------------------------------------------------------------- build_scorers


def test_build_scorers_unknown_type_is_config_error():
    config = scorer_config({"type": "no_such_scorer", "options": {}})
    with pytest.raises(GateConfigError,
                       match="unknown scorer type 'no_such_scorer'"):
        build_scorers(config)


def test_build_scorers_unknown_type_lists_registered_scorers():
    config = scorer_config({"type": "nope", "options": {}})
    with pytest.raises(GateConfigError, match="keyword_quality"):
        build_scorers(config)


def test_build_scorers_duplicate_metric_owner_is_config_error():
    config = scorer_config(
        {"type": "keyword_quality", "options": {}},
        {"type": "field_match", "options": {}},
    )
    with pytest.raises(GateConfigError,
                       match="metric 'quality.pass_rate'.*exactly one owner"):
        build_scorers(config)


def test_build_scorers_single_owner_builds_both_scorer_kinds():
    config = scorer_config(
        {"type": "keyword_quality", "options": {}},
        {"type": "abstention", "options": {}},
    )
    scorers = build_scorers(config)
    assert [type(s) for s in scorers] == [KeywordQualityScorer, AbstentionScorer]
    assert scorers[0].describe() == {"name": "keyword_quality",
                                     "version": "1", "options": {}}


def test_build_scorers_empty_options_default_to_empty_dict():
    scorers = build_scorers(scorer_config({"type": "citations", "options": {}}))
    assert len(scorers) == 1
    assert scorers[0].options == {}


# ------------------------------------------------------------- item_result


def test_item_result_defaults_are_none():
    assert item_result(False) == {"applicable": False, "passed": None, "detail": None}
    assert item_result(True) == {"applicable": True, "passed": None, "detail": None}


def test_item_result_keeps_explicit_passed_and_detail():
    assert item_result(True, True, None) == {"applicable": True,
                                             "passed": True, "detail": None}
    assert item_result(True, False, "missing expected terms: ['x']") == {
        "applicable": True, "passed": False,
        "detail": "missing expected terms: ['x']"}


# ------------------------------------------------------------- json_equal


def test_json_equal_bool_is_not_int():
    assert json_equal(True, 1) is False
    assert json_equal(False, 0) is False
    assert json_equal(True, True) is True
    assert json_equal(False, False) is True
    assert json_equal(True, False) is False


def test_json_equal_numbers_compare_across_int_float():
    assert json_equal(310, 310.0) is True
    assert json_equal(1, 2) is False
    assert json_equal("a", "a") is True
    assert json_equal("a", "b") is False
    assert json_equal(None, None) is True
    assert json_equal(None, 0) is False


def test_json_equal_nested_bool_int_distinction():
    assert json_equal([True, False], [1, 0]) is False
    assert json_equal({"flags": [True]}, {"flags": [1]}) is False
    assert json_equal({"a": {"b": False}}, {"a": {"b": 0}}) is False
    assert json_equal([1, 2.0], [1.0, 2]) is True
    assert json_equal({"a": [True, 3]}, {"a": [True, 3.0]}) is True


def test_json_equal_collection_boundaries():
    assert json_equal([], []) is True
    assert json_equal({}, {}) is True
    assert json_equal([1], [1, 2]) is False
    assert json_equal({"x": 1}, {"x": 1, "y": 2}) is False
    assert json_equal({"x": 1}, {"y": 1}) is False
    assert json_equal([1, 2], (1, 2)) is False
    assert json_equal({"a": 1}, {"a": 1}) is True
