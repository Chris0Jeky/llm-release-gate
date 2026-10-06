"""Float aggregation must not depend on the interpreter's built-in sum."""

import json
from pathlib import Path

import pytest

from llm_release_gate import runner
from llm_release_gate.cli import main
from llm_release_gate.runner import ItemRecord, _aggregate


def legacy_sum(values, start=0):
    """The ordinary left-fold float addition used before Python 3.12."""
    for value in values:
        start += value
    return start


@pytest.mark.parametrize("legacy", [False, True])
def test_float_aggregates_use_explicit_precision(monkeypatch, legacy):
    if legacy:
        monkeypatch.setattr(runner, "sum", legacy_sum, raising=False)
    records = [
        ItemRecord(item_id=str(i), status="ok", latency_ms=value,
                   cost_usd=value, prompt_tokens=10**30, completion_tokens=1)
        for i, value in enumerate([0.1, 0.2, 0.3])
    ]
    aggregates = _aggregate(records, [])
    assert aggregates["cost.total_usd"]["value"] == 0.6
    assert aggregates["latency.mean_ms"]["value"] == 0.6 / 3
    assert aggregates["tokens.total"]["value"] == 3 * (10**30 + 1)
    assert aggregates["cost.total_usd"]["n"] == 3


@pytest.mark.parametrize("values", [[1e308, 1e308], [float("inf"), -float("inf")]])
def test_unrepresentable_sums_stay_unavailable(values):
    records = [
        ItemRecord(item_id=str(i), status="ok", latency_ms=value, cost_usd=value)
        for i, value in enumerate(values)
    ]
    aggregates = _aggregate(records, [])
    for key in ("cost.total_usd", "latency.mean_ms"):
        assert aggregates[key]["available"] is False
        assert aggregates[key]["value"] is None
        assert "non-finite" in aggregates[key]["note"]


@pytest.mark.parametrize("scenario,exit_code,expected_baseline,expected_candidate", [
    ("rag-support-bot", 0, 0.060336, 0.067464),
    ("assistant-cheap-regression", 1, 0.101448, 0.0036864),
])
def test_public_report_costs_and_bytes_are_sum_version_independent(
    tmp_path, monkeypatch, scenario, exit_code, expected_baseline, expected_candidate,
):
    root = Path(__file__).resolve().parents[1]
    example = root / "examples" / scenario
    reports = []
    for legacy in (False, True):
        out = tmp_path / str(legacy)
        args = ["gate"]
        for key in ("dataset", "baseline", "candidate", "scorers", "thresholds"):
            args += [f"--{key}", str(example / f"{key}.json")]
        args += ["--pricing", str(root / "examples/pricing.json"), "--out", str(out)]
        if legacy:
            monkeypatch.setattr(runner, "sum", legacy_sum, raising=False)
        assert main(args) == exit_code
        reports.append({suffix: (out / f"report.{suffix}").read_bytes()
                        for suffix in ("json", "md", "html")})
    assert reports[0] == reports[1]
    report = json.loads(reports[0]["json"])
    assert report["metrics"]["cost.total_usd"]["baseline"]["value"] == expected_baseline
    assert report["metrics"]["cost.total_usd"]["candidate"]["value"] == expected_candidate
