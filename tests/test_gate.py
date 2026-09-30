"""Fail-dominates-warn regression tests (gate verdict precedence)."""

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
from llm_release_gate.metrics import HIGHER, LOWER, rate_metric, scalar_metric
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


def test_zero_baseline_pct():
    breached, observed, _ = _check_constraint("max_increase_pct", 10, 0, 0.5)
    assert breached is True
    assert observed is None

    breached, observed, _ = _check_constraint("max_increase_pct", 10, 0, 0)
    assert breached is False
    assert observed is None
