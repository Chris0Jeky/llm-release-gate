"""Provider failure: recorded per item, surfaced as errors.error_rate, and the
implicit gate rule blocks candidates that only look good on the items that ran."""

import json

import pytest

from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError, ProviderError
from llm_release_gate.providers import ProviderRequest, build_provider

from conftest import CAND_MODEL, GOOD_RESPONSE, gate_argv, write_json


def _req(model: str, item_id: str) -> ProviderRequest:
    return ProviderRequest(model=model, system="", prompt="", params={}, item_id=item_id)


def test_missing_fixture_raises_provider_error(tmp_path):
    write_json(tmp_path / "fx.json", {"version": "1", "responses": {"m": {}}})
    provider = build_provider("fake", {"fixtures": "fx.json"}, str(tmp_path))
    with pytest.raises(ProviderError, match="no fixture for item 'x1'"):
        provider.complete(_req("m", "x1"))
    with pytest.raises(ProviderError, match="no fixtures for model"):
        provider.complete(_req("unknown-model", "x1"))


def test_provider_error_message_is_location_stable(tmp_path):
    # A missing-fixture error is recorded per item and lands in report.json;
    # embedding the absolute fixtures path would make result_hash depend on where
    # the repo is checked out (same class as the fixtures_path leak). The message
    # must use the config-relative reference instead.
    write_json(tmp_path / "fixtures" / "fx.json", {"version": "1", "responses": {"m": {}}})
    provider = build_provider("fake", {"fixtures": "fixtures/fx.json"}, str(tmp_path))
    with pytest.raises(ProviderError) as excinfo:
        provider.complete(_req("m", "x1"))
    msg = str(excinfo.value)
    assert "fixtures/fx.json" in msg      # location-stable config reference
    assert str(tmp_path) not in msg       # never the absolute checkout path


def test_simulated_error_entry(tmp_path):
    write_json(tmp_path / "fx.json", {
        "version": "1",
        "responses": {"m": {"x1": {"error": "rate limited (429)"}}},
    })
    provider = build_provider("fake", {"fixtures": "fx.json"}, str(tmp_path))
    with pytest.raises(ProviderError, match="rate limited"):
        provider.complete(_req("m", "x1"))


def test_missing_fixture_file_is_config_error(tmp_path):
    with pytest.raises(GateConfigError, match="not found"):
        build_provider("fake", {"fixtures": "nope.json"}, str(tmp_path))


def test_malformed_fixture_entries_are_config_errors(tmp_path):
    # negative tokens must never flow into cost totals as measured data
    write_json(tmp_path / "fx.json", {
        "version": "1",
        "responses": {"m": {"x1": {"text": "hi", "prompt_tokens": -5000}}},
    })
    with pytest.raises(GateConfigError, match="non-negative integer"):
        build_provider("fake", {"fixtures": "fx.json"}, str(tmp_path))
    # string tokens: clean config error, not a mid-run TypeError traceback
    write_json(tmp_path / "fx2.json", {
        "version": "1",
        "responses": {"m": {"x1": {"text": "hi", "prompt_tokens": "312"}}},
    })
    with pytest.raises(GateConfigError, match="non-negative integer"):
        build_provider("fake", {"fixtures": "fx2.json"}, str(tmp_path))
    # non-dict entry: named clearly instead of crashing on a substring check
    write_json(tmp_path / "fx3.json", {
        "version": "1",
        "responses": {"m": {"x1": "terror occurred"}},
    })
    with pytest.raises(GateConfigError, match="item 'x1'"):
        build_provider("fake", {"fixtures": "fx3.json"}, str(tmp_path))


def test_unknown_provider_is_config_error(tmp_path):
    with pytest.raises(GateConfigError, match="unknown provider"):
        build_provider("nonexistent", {}, str(tmp_path))


def test_candidate_provider_failure_blocks_gate_via_implicit_rule(mini_gate):
    # candidate answers r1/r3 well but errors on r2; thresholds say nothing about
    # errors -> the implicit errors.error_rate rule must fail the gate anyway
    degraded = {k: dict(v) for k, v in GOOD_RESPONSE.items()}
    degraded["r2"] = {"error": "upstream timeout"}
    paths = mini_gate(
        candidate_responses=degraded,
        thresholds={"rules": [{"metric": "quality.pass_rate", "max_drop_abs": 0.5}]},
    )
    assert main(gate_argv(paths)) == 1
    report = json.loads(open(f"{paths['out']}/report.json", encoding="utf-8").read())
    rule = next(r for r in report["rules"] if r["metric"] == "errors.error_rate")
    assert rule["implicit"] is True and rule["verdict"] == "fail"
    # the failure is recorded on the item, with the provider's message
    item = next(i for i in report["items"] if i["id"] == "r2")
    assert item["candidate"]["status"] == "error"
    assert "upstream timeout" in item["candidate"]["error"]
    # and the run carried on: the other items were still scored
    assert report["runs"]["candidate"]["n_ok"] == 2
    # gate notices call out the errors
    assert any("candidate run had 1/3" in n for n in report["gate"]["notices"])


def test_baseline_provider_error_notice_is_reported_everywhere(mini_gate):
    degraded = {k: dict(v) for k, v in GOOD_RESPONSE.items()}
    degraded["r2"] = {"error": "baseline upstream timeout"}
    paths = mini_gate(baseline_responses=degraded)

    assert main(gate_argv(paths)) == 1  # relative rules cannot compare unlike cohorts
    report = json.loads(open(f"{paths['out']}/report.json", encoding="utf-8").read())
    notice = (
        "baseline run had 1/3 provider errors; baseline aggregates cover only the answered items"
    )
    assert report["gate"]["notices"] == [notice]
    markdown = open(f"{paths['out']}/report.md", encoding="utf-8").read()
    html = open(f"{paths['out']}/report.html", encoding="utf-8").read()
    assert notice in markdown
    assert notice in html


def test_run_continues_when_every_item_fails(mini_gate):
    paths = mini_gate(
        candidate_responses={
            "r1": {"error": "boom"}, "r2": {"error": "boom"}, "r3": {"error": "boom"},
        },
        thresholds={"rules": [{"metric": "errors.error_rate", "max_value": 0.0}]},
    )
    assert main(gate_argv(paths)) == 1
    report = json.loads(open(f"{paths['out']}/report.json", encoding="utf-8").read())
    assert report["runs"]["candidate"]["n_ok"] == 0
    # score metrics have no applicable items -> unavailable, not fabricated zeros
    q = report["metrics"]["quality.pass_rate"]["candidate"]
    assert q["available"] is False
    for metric in ("latency.p50_ms", "latency.p95_ms", "latency.mean_ms"):
        latency = report["metrics"][metric]["candidate"]
        assert latency["available"] is False
        assert latency["value"] is None
        assert latency["note"] == "provider reported no latency"
