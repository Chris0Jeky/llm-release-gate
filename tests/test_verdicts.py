"""Threshold/verdict engine unit tests — the logic CI trusts."""

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.gate import evaluate_thresholds
from llm_release_gate.loading import ThresholdRule, Thresholds
from llm_release_gate.metrics import (
    HIGHER, LOWER, rate_metric, scalar_metric, unavailable_metric,
)


def thresholds(*rules: ThresholdRule) -> Thresholds:
    return Thresholds(rules=list(rules), path="t.json", sha256="sha256:test")


def aggs(**metrics) -> dict:
    base = {"errors.error_rate": rate_metric(0, 10, LOWER)}
    base.update(metrics)
    return base


def rule_for(verdicts: list[dict], metric: str) -> dict:
    return next(r for r in verdicts if r["metric"] == metric)


def test_max_drop_abs_boundary_pass_and_fail():
    t = thresholds(ThresholdRule("quality.pass_rate", {"max_drop_abs": 0.1}))
    baseline = aggs(**{"quality.pass_rate": rate_metric(8, 8, HIGHER)})
    # exactly at the boundary: 1.0 -> 0.9 is allowed
    cand_ok = aggs(**{"quality.pass_rate": rate_metric(9, 10, HIGHER)})
    v = rule_for(evaluate_thresholds(t, baseline, cand_ok), "quality.pass_rate")
    assert v["verdict"] == "pass"
    # over the boundary: 1.0 -> 0.875 is a 0.125 drop
    cand_bad = aggs(**{"quality.pass_rate": rate_metric(7, 8, HIGHER)})
    v = rule_for(evaluate_thresholds(t, baseline, cand_bad), "quality.pass_rate")
    assert v["verdict"] == "fail"
    assert "drop" in v["message"]


def test_improvement_never_breaches_drop_rule():
    t = thresholds(ThresholdRule("quality.pass_rate", {"max_drop_abs": 0.0}))
    baseline = aggs(**{"quality.pass_rate": rate_metric(7, 8, HIGHER)})
    cand = aggs(**{"quality.pass_rate": rate_metric(8, 8, HIGHER)})
    v = rule_for(evaluate_thresholds(t, baseline, cand), "quality.pass_rate")
    assert v["verdict"] == "pass"


def test_max_increase_pct_and_zero_baseline():
    t = thresholds(ThresholdRule("cost.total_usd", {"max_increase_pct": 25}))
    baseline = aggs(**{"cost.total_usd": scalar_metric(1.0, "usd", LOWER)})
    cand = aggs(**{"cost.total_usd": scalar_metric(1.30, "usd", LOWER)})
    assert rule_for(evaluate_thresholds(t, baseline, cand), "cost.total_usd")["verdict"] == "fail"
    cand = aggs(**{"cost.total_usd": scalar_metric(1.20, "usd", LOWER)})
    assert rule_for(evaluate_thresholds(t, baseline, cand), "cost.total_usd")["verdict"] == "pass"
    # zero baseline: any increase is an infinite percentage -> breach
    baseline0 = aggs(**{"cost.total_usd": scalar_metric(0.0, "usd", LOWER)})
    cand = aggs(**{"cost.total_usd": scalar_metric(0.01, "usd", LOWER)})
    assert rule_for(evaluate_thresholds(t, baseline0, cand), "cost.total_usd")["verdict"] == "fail"
    cand0 = aggs(**{"cost.total_usd": scalar_metric(0.0, "usd", LOWER)})
    assert rule_for(evaluate_thresholds(t, baseline0, cand0), "cost.total_usd")["verdict"] == "pass"


def test_neighboring_large_integer_ceiling_fails_closed():
    t = thresholds(ThresholdRule("tokens.total", {"max_value": 9007199254740995}))
    baseline = aggs(**{"tokens.total": scalar_metric(0, "tokens", LOWER)})
    candidate = aggs(**{"tokens.total": scalar_metric(9007199254740996, "tokens", LOWER)})
    verdict = rule_for(evaluate_thresholds(t, baseline, candidate), "tokens.total")
    assert verdict["verdict"] == "fail"
    assert verdict["checks"][0]["observed"] == 9007199254740996
    assert verdict["checks"][0]["threshold"] == 9007199254740995


@pytest.mark.parametrize("cap", [0, 25, 1e308])
def test_tiny_positive_cost_from_zero_fails_closed(cap):
    t = thresholds(ThresholdRule("cost.total_usd", {"max_increase_pct": cap}))
    baseline = aggs(**{"cost.total_usd": scalar_metric(0.0, "usd", LOWER)})
    candidate = aggs(**{"cost.total_usd": scalar_metric(1e-9, "usd", LOWER)})
    verdict = rule_for(evaluate_thresholds(t, baseline, candidate), "cost.total_usd")
    assert verdict["verdict"] == "fail"
    assert verdict["checks"][0]["status"] == "breached"


def test_min_and_max_value_look_at_candidate_only():
    t = thresholds(
        ThresholdRule("schema.valid_rate", {"min_value": 0.95}),
        ThresholdRule("abstention.false_answer_rate", {"max_value": 0.0}),
    )
    # baseline unavailable must not matter for candidate-only constraints
    baseline = aggs(**{
        "schema.valid_rate": unavailable_metric("rate", HIGHER, "no applicable items"),
        "abstention.false_answer_rate": unavailable_metric("rate", LOWER, "no applicable items"),
    })
    cand = aggs(**{
        "schema.valid_rate": rate_metric(19, 20, HIGHER),
        "abstention.false_answer_rate": rate_metric(1, 2, LOWER),
    })
    verdicts = evaluate_thresholds(t, baseline, cand)
    assert rule_for(verdicts, "schema.valid_rate")["verdict"] == "pass"
    assert rule_for(verdicts, "abstention.false_answer_rate")["verdict"] == "fail"


def test_warn_level_never_fails_rule():
    t = thresholds(ThresholdRule("latency.p95_ms", {"max_increase_pct": 10}, level="warn"))
    baseline = aggs(**{"latency.p95_ms": scalar_metric(1000, "ms", LOWER)})
    cand = aggs(**{"latency.p95_ms": scalar_metric(2000, "ms", LOWER)})
    v = rule_for(evaluate_thresholds(t, baseline, cand), "latency.p95_ms")
    assert v["verdict"] == "warn"


@pytest.mark.parametrize("policy,expected", [("fail", "fail"), ("warn", "warn"), ("skip", "skipped")])
def test_on_unavailable_policies(policy, expected):
    t = thresholds(
        ThresholdRule("cost.total_usd", {"max_increase_pct": 25}, on_unavailable=policy)
    )
    baseline = aggs(**{"cost.total_usd": scalar_metric(1.0, "usd", LOWER)})
    cand = aggs(**{"cost.total_usd": unavailable_metric("usd", LOWER, "no token usage")})
    v = rule_for(evaluate_thresholds(t, baseline, cand), "cost.total_usd")
    assert v["verdict"] == expected
    assert "no token usage" in v["message"]


def test_unavailable_baseline_also_triggers_policy_for_comparative_constraints():
    t = thresholds(ThresholdRule("cost.total_usd", {"max_increase_pct": 25}))
    baseline = aggs(**{"cost.total_usd": unavailable_metric("usd", LOWER, "model not in pricing table")})
    cand = aggs(**{"cost.total_usd": scalar_metric(1.0, "usd", LOWER)})
    v = rule_for(evaluate_thresholds(t, baseline, cand), "cost.total_usd")
    assert v["verdict"] == "fail"
    assert "baseline" in v["message"]


def test_mixed_constraints_partial_availability():
    # min_value is evaluable (candidate available) and passes, but the comparative
    # constraint cannot be evaluated -> policy (warn) escalates the rule to warn.
    t = thresholds(
        ThresholdRule(
            "quality.pass_rate", {"max_drop_abs": 0.05, "min_value": 0.5},
            on_unavailable="warn",
        )
    )
    baseline = aggs(**{"quality.pass_rate": unavailable_metric("rate", HIGHER, "no applicable items")})
    cand = aggs(**{"quality.pass_rate": rate_metric(9, 10, HIGHER)})
    v = rule_for(evaluate_thresholds(t, baseline, cand), "quality.pass_rate")
    assert v["verdict"] == "warn"
    statuses = {c["constraint"]: c["status"] for c in v["checks"]}
    assert statuses == {"max_drop_abs": "unavailable", "min_value": "pass"}


def test_implicit_error_rule_added_and_fails_on_candidate_errors():
    t = thresholds(ThresholdRule("quality.pass_rate", {"max_drop_abs": 1.0}))
    baseline = {
        "quality.pass_rate": rate_metric(8, 8, HIGHER),
        "errors.error_rate": rate_metric(0, 10, LOWER),
    }
    cand = {
        "quality.pass_rate": rate_metric(8, 8, HIGHER),
        "errors.error_rate": rate_metric(2, 10, LOWER),
    }
    verdicts = evaluate_thresholds(t, baseline, cand)
    implicit = rule_for(verdicts, "errors.error_rate")
    assert implicit["implicit"] is True
    assert implicit["verdict"] == "fail"


def test_explicit_error_rule_replaces_implicit():
    t = thresholds(ThresholdRule("errors.error_rate", {"max_value": 0.5}))
    baseline = aggs()
    cand = {"errors.error_rate": rate_metric(2, 10, LOWER)}
    verdicts = evaluate_thresholds(t, baseline, cand)
    assert len([r for r in verdicts if r["metric"] == "errors.error_rate"]) == 1
    v = rule_for(verdicts, "errors.error_rate")
    assert v["implicit"] is False
    assert v["verdict"] == "pass"


def test_unknown_metric_is_config_error():
    t = thresholds(ThresholdRule("quality.typo_rate", {"max_drop_abs": 0.1}))
    with pytest.raises(GateConfigError, match="quality.typo_rate"):
        evaluate_thresholds(t, aggs(), aggs())


def test_direction_mismatched_constraints_are_config_errors():
    # a drop-guard on a lower-is-better metric can never fire -> must be rejected
    t = thresholds(ThresholdRule("latency.p95_ms", {"max_drop_pct": 10}))
    baseline = aggs(**{"latency.p95_ms": scalar_metric(500, "ms", LOWER)})
    cand = aggs(**{"latency.p95_ms": scalar_metric(5000, "ms", LOWER)})
    with pytest.raises(GateConfigError, match="max_increase"):
        evaluate_thresholds(t, baseline, cand)
    # and an increase-guard on a higher-is-better metric likewise
    t = thresholds(ThresholdRule("quality.pass_rate", {"max_increase_abs": 0.1}))
    baseline = aggs(**{"quality.pass_rate": rate_metric(8, 8, HIGHER)})
    cand = aggs(**{"quality.pass_rate": rate_metric(1, 8, HIGHER)})
    with pytest.raises(GateConfigError, match="max_drop"):
        evaluate_thresholds(t, baseline, cand)


def test_percentile_is_nearest_rank():
    from llm_release_gate.metrics import percentile

    values = [100.0, 200.0, 300.0, 400.0, 500.0]
    assert percentile(values, 50) == 300.0   # ceil(2.5) = 3rd, the true median
    assert percentile(values, 95) == 500.0   # ceil(4.75) = 5th
    assert percentile(values, 100) == 500.0
    assert percentile([42.0], 50) == 42.0    # n=1: the only sample
    thirteen = [float(i) for i in range(1, 14)]
    assert percentile(thirteen, 95) == 13.0  # ceil(12.35) = 13th, keeps the worst
    with pytest.raises(ValueError):
        percentile([], 50)
