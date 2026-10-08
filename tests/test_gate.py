"""Fail-dominates-warn regression tests (gate verdict precedence)."""

import pytest
from llm_release_gate.errors import GateConfigError
from llm_release_gate.gate import (
    _check_constraint,
    _escalate,
    build_report,
    evaluate_thresholds,
)
from llm_release_gate.loading import (
    Dataset,
    RunConfig,
    ScorerConfig,
    ThresholdRule,
    Thresholds,
    no_pricing,
)
from llm_release_gate.metrics import HIGHER, LOWER, rate_metric, scalar_metric, unavailable_metric
from llm_release_gate.runner import RunResult


def test_fail_dominates_warn():
    thresholds = Thresholds(
        rules=[
            ThresholdRule("quality.pass_rate", {"max_drop_abs": 0.1}),
            ThresholdRule(
                "latency.p95_ms", {"max_increase_pct": 10}, level="warn"
            ),
        ],
        path="t.json",
        sha256="sha256:test",
    )
    baseline_aggs = {
        "quality.pass_rate": rate_metric(8, 8, HIGHER),
        "latency.p95_ms": scalar_metric(1000, "ms", LOWER),
        "errors.error_rate": rate_metric(0, 10, LOWER),
    }
    candidate_aggs = {
        # 1.0 -> 0.875 is a 0.125 drop, breaching the fail rule.
        "quality.pass_rate": rate_metric(7, 8, HIGHER),
        # 100% increase, breaching the warn rule.
        "latency.p95_ms": scalar_metric(2000, "ms", LOWER),
        "errors.error_rate": rate_metric(0, 10, LOWER),
    }

    verdicts = evaluate_thresholds(thresholds, baseline_aggs, candidate_aggs)
    by_metric = {v["metric"]: v["verdict"] for v in verdicts}
    assert by_metric["quality.pass_rate"] == "fail"
    assert by_metric["latency.p95_ms"] == "warn"

    # Rank precedence itself: swapping fail/warn ranks must break these.
    assert _escalate("warn", "fail") == "fail"
    assert _escalate("fail", "warn") == "fail"

    dataset = Dataset(
        name="d", version="1", task="rag", items=[],
        path="d.json", sha256="sha256:test",
    )
    baseline_config = RunConfig(
        name="baseline", provider="fake", model="m-base",
        params={}, prompt={}, provider_options={},
        path="b.json", sha256="sha256:test",
    )
    candidate_config = RunConfig(
        name="candidate", provider="fake", model="m-cand",
        params={}, prompt={}, provider_options={},
        path="c.json", sha256="sha256:test",
    )
    scorer_config = ScorerConfig(scorers=[], path="s.json", sha256="sha256:test")
    report = build_report(
        dataset,
        RunResult(
            config=baseline_config, provider_info={}, adapter_info={},
            records=[], aggregates=baseline_aggs,
        ),
        RunResult(
            config=candidate_config, provider_info={}, adapter_info={},
            records=[], aggregates=candidate_aggs,
        ),
        scorer_config,
        [],
        thresholds,
        no_pricing(),
    )
    assert report["gate"]["verdict"] == "fail"
    assert report["gate"]["n_failed"] == 1
    assert report["gate"]["n_warned"] == 1


def test_evaluate_thresholds_asymmetric_aggregates_config_error():
    thresholds = Thresholds(rules=[ThresholdRule("quality.pass_rate", {"min_value": 0.5})], path="t.json", sha256="sha256:test")
    good = rate_metric(8, 8, HIGHER)
    err = rate_metric(0, 10, LOWER)
    base_full = {"quality.pass_rate": good, "errors.error_rate": err}
    cand_full = {"quality.pass_rate": good, "errors.error_rate": err}
    with pytest.raises(GateConfigError) as exc1:
        evaluate_thresholds(thresholds, base_full, {"errors.error_rate": err})
    assert "quality.pass_rate" in str(exc1.value) and "candidate" in str(exc1.value)
    with pytest.raises(GateConfigError) as exc2:
        evaluate_thresholds(thresholds, {"errors.error_rate": err}, cand_full)
    assert "quality.pass_rate" in str(exc2.value) and "baseline" in str(exc2.value)
    malformed = {"value": 0.9}
    with pytest.raises(GateConfigError):
        evaluate_thresholds(thresholds, {"quality.pass_rate": malformed, "errors.error_rate": err}, cand_full)


def test_unavailable_skip_yields_skipped():
    thresholds = Thresholds(
        rules=[
            ThresholdRule(
                "quality.pass_rate",
                {"max_drop_abs": 0.1, "min_value": 0.5},
                on_unavailable="skip",
            ),
        ],
        path="t.json",
        sha256="sha256:test",
    )
    baseline_aggs = {
        "quality.pass_rate": unavailable_metric("rate", HIGHER, "no applicable items"),
        "errors.error_rate": rate_metric(0, 10, LOWER),
    }
    candidate_aggs = {
        "quality.pass_rate": unavailable_metric("rate", HIGHER, "no applicable items"),
        "errors.error_rate": rate_metric(0, 10, LOWER),
    }

    verdicts = evaluate_thresholds(thresholds, baseline_aggs, candidate_aggs)
    rule = next(v for v in verdicts if v["metric"] == "quality.pass_rate")
    assert rule["verdict"] == "skipped"
    assert rule["checks"]
    assert all(c["status"] == "unavailable" for c in rule["checks"])


def test_nonfinite_available_metric_does_not_pass():
    from decimal import Decimal

    def _raw(value, direction, unit="rate"):
        return {
            "value": value,
            "available": True,
            "unit": unit,
            "direction": direction,
            "numerator": None,
            "denominator": None,
            "n": 1,
            "kind": "measured",
            "note": None,
        }

    def _rule_verdict(thresholds, baseline_q, candidate_q):
        err = rate_metric(0, 10, LOWER)
        baseline_aggs = {"q": baseline_q, "errors.error_rate": err}
        candidate_aggs = {"q": candidate_q, "errors.error_rate": err}
        verdicts = evaluate_thresholds(thresholds, baseline_aggs, candidate_aggs)
        return next(v for v in verdicts if v["metric"] == "q")

    drop_rule = Thresholds(
        rules=[ThresholdRule("q", {"max_drop_pct": 5})],
        path="t.json",
        sha256="sha256:test",
    )
    finite_candidate = _raw(0.5, HIGHER)
    # Non-finite baseline marked available must not pass a higher_better drop guard.
    for bad_baseline in (
        _raw(float("nan"), HIGHER),
        _raw(Decimal("NaN"), HIGHER),
        _raw(float("inf"), HIGHER),
        _raw(Decimal("Infinity"), HIGHER),
    ):
        rule = _rule_verdict(drop_rule, bad_baseline, finite_candidate)
        assert rule["verdict"] != "pass"
        assert all(c["status"] == "unavailable" for c in rule["checks"])

    # Non-finite candidate on a lower_better increase guard must not pass either.
    increase_rule = Thresholds(
        rules=[ThresholdRule("q", {"max_increase_pct": 5})],
        path="t.json",
        sha256="sha256:test",
    )
    rule = _rule_verdict(
        increase_rule,
        _raw(1000.0, LOWER, unit="ms"),
        _raw(float("nan"), LOWER, unit="ms"),
    )
    assert rule["verdict"] != "pass"
    assert all(c["status"] == "unavailable" for c in rule["checks"])

    # Finite behavior is unchanged: ~1% drop passes a 5% guard, 10% drop fails it.
    rule = _rule_verdict(drop_rule, _raw(1.0, HIGHER), _raw(0.99, HIGHER))
    assert rule["verdict"] == "pass"
    rule = _rule_verdict(drop_rule, _raw(1.0, HIGHER), _raw(0.90, HIGHER))
    assert rule["verdict"] != "pass"


def test_zero_baseline_pct():
    breached, observed, _ = _check_constraint("max_increase_pct", 10, 0, 0.5)
    assert breached is True
    assert observed is None

    breached, observed, _ = _check_constraint("max_increase_pct", 10, 0, 0)
    assert breached is False
    assert observed is None
