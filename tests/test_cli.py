"""CLI exit-code contract and GitHub env integration — what CI actually sees."""

import json
import os

import pytest

from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.hashing import file_sha256
from llm_release_gate.loading import load_dataset, load_run_config, load_scorer_config

from conftest import GOOD_RESPONSE, gate_argv, write_json

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")


def _example_argv(name: str, out: str) -> list[str]:
    root = os.path.join(EXAMPLES, name)
    return [
        "gate",
        "--dataset", os.path.join(root, "dataset.json"),
        "--baseline", os.path.join(root, "baseline.json"),
        "--candidate", os.path.join(root, "candidate.json"),
        "--scorers", os.path.join(root, "scorers.json"),
        "--thresholds", os.path.join(root, "thresholds.json"),
        "--pricing", os.path.join(EXAMPLES, "pricing.json"),
        "--out", out,
    ]


def test_green_examples_exit_zero(tmp_path):
    assert main(_example_argv("rag-support-bot", str(tmp_path / "a"))) == 0
    assert main(_example_argv("extraction-api", str(tmp_path / "b"))) == 0


def test_red_example_exits_one_and_names_regressions(tmp_path, capsys):
    assert main(_example_argv("assistant-cheap-regression", str(tmp_path / "c"))) == 1
    out = capsys.readouterr().out
    assert "gate FAIL" in out
    assert "quality.pass_rate" in out
    assert "abstention.false_answer_rate" in out
    assert "citations.valid_rate" in out


@pytest.mark.parametrize("literal,expected_exit", [("1.0", 0), ("1e0", 0),
                                                  ("1.5", 1), ("true", 1)])
def test_integer_schema_gate_uses_numeric_value(mini_gate, literal, expected_exit):
    paths = mini_gate(
        dataset={"name": "integer-output", "version": "1", "task": "extraction", "items": [
            {"id": "x", "input": {"text": "one item"}},
        ]},
        baseline_responses={"x": {"text": '{"count": 1}'}},
        candidate_responses={"x": {"text": '{"count": ' + literal + '}'}},
        scorers={"scorers": [{"type": "json_schema", "options": {"schema": {
            "type": "object", "required": ["count"],
            "properties": {"count": {"type": "integer"}},
        }}}]},
        thresholds={"rules": [{"metric": "schema.valid_rate", "min_value": 1}]},
        include_pricing=False,
    )
    for role in ("baseline", "candidate"):
        with open(paths[role], encoding="utf-8") as stream:
            config = json.load(stream)
        config["prompt"]["template"] = "$text"
        write_json(paths["tmp"] / f"{role}.json", config)
    assert main(gate_argv(paths)) == expected_exit
    with open(f"{paths['out']}/report.json", encoding="utf-8") as stream:
        report = json.load(stream)
    metric = report["metrics"]["schema.valid_rate"]
    assert metric["baseline"]["value"] == 1
    assert metric["candidate"]["value"] == (1 if expected_exit == 0 else 0)
    assert metric["candidate"]["denominator"] == 1
    assert report["gate"]["verdict"] == ("pass" if expected_exit == 0 else "fail")


@pytest.mark.parametrize("metric,constraints,tokens,observed", [
    ("tokens.total", {"max_value": 9007199254740995}, 9007199254740996, 9007199254740996),
    ("cost.total_usd", {"max_increase_pct": 0}, 1, 1e-9),
], ids=["neighboring-large-integer-ceiling", "tiny-positive-cost-from-zero"])
def test_numeric_boundary_violation_exits_one(mini_gate, metric, constraints, tokens, observed):
    paths = mini_gate(
        dataset={"name": "d", "version": "1", "task": "rag", "items": [
            {"id": "x", "input": {"question": "q"},
             "expected": {"quality": {"must_contain": ["ok"]}}},
        ]},
        scorers={"scorers": [{"type": "keyword_quality"}]},
        baseline_responses={"x": {"text": "ok", "prompt_tokens": 0, "completion_tokens": 0}},
        candidate_responses={"x": {"text": "ok", "prompt_tokens": tokens, "completion_tokens": 0}},
        thresholds={"rules": [{"metric": metric, **constraints}]},
        pricing={"version": "1", "models": {
            model: {"input_per_mtok": 0.001, "output_per_mtok": 0}
            for model in ("m-base", "m-cand")
        }},
    )
    exit_code = main(gate_argv(paths))
    with open(f"{paths['out']}/report.json", encoding="utf-8") as stream:
        report = json.load(stream)
    assert report["metrics"][metric]["baseline"]["value"] == 0
    assert report["metrics"][metric]["candidate"]["value"] == observed
    assert exit_code == 1
    assert report["gate"]["verdict"] == "fail"
    rule = next(r for r in report["rules"] if r["metric"] == metric)
    assert rule["checks"][0]["status"] == "breached"


def test_missing_input_file_exits_two(tmp_path, capsys):
    argv = _example_argv("rag-support-bot", str(tmp_path / "d"))
    argv[argv.index("--dataset") + 1] = "does-not-exist.json"
    assert main(argv) == 2
    assert "configuration error" in capsys.readouterr().err


def test_invalid_threshold_rule_exits_two(mini_gate, capsys):
    paths = mini_gate(thresholds={"rules": [{"metric": "quality.pass_rate"}]})
    assert main(gate_argv(paths)) == 2
    assert "no constraint" in capsys.readouterr().err


def test_metric_without_scorer_exits_two(mini_gate, capsys):
    # thresholds gate on schema validity but no json_schema scorer is configured
    paths = mini_gate(thresholds={"rules": [{"metric": "schema.valid_rate", "min_value": 1.0}]})
    assert main(gate_argv(paths)) == 2
    assert "schema.valid_rate" in capsys.readouterr().err


def test_github_summary_and_outputs_written(mini_gate, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    outputs = tmp_path / "outputs.txt"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0
    assert "llm-release-gate" in summary.read_text(encoding="utf-8")
    out_text = outputs.read_text(encoding="utf-8")
    assert "verdict=pass" in out_text
    assert "exit-code=0" in out_text
    assert "result-hash=sha256:" in out_text


@pytest.mark.parametrize("variable", ["GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"])
def test_github_delivery_failure_reports_threshold_verdict_and_exit_two(
    mini_gate, monkeypatch, tmp_path, capsys, variable,
):
    summary = tmp_path / "summary.md"
    outputs = tmp_path / "outputs.txt"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    failed_path = outputs if variable == "GITHUB_OUTPUT" else summary
    real_open = os.open

    def failing_open(path, flags, *args, **kwargs):
        if os.fspath(path) == str(failed_path) and flags & os.O_APPEND:
            raise PermissionError("synthetic command-file write failure")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", failing_open)
    paths = mini_gate()
    assert main(gate_argv(paths)) == 2
    captured = capsys.readouterr()
    message = "gate PASS (threshold verdict), but output delivery failed: exit 2"
    assert message in captured.out
    assert "llm-release-gate: gate PASS\n" not in captured.out
    assert f"{variable} command file could not be written" in captured.err
    assert "Traceback" not in captured.err
    with open(f"{paths['out']}/report.json", encoding="utf-8") as stream:
        assert json.load(stream)["gate"]["verdict"] == "pass"
    if variable == "GITHUB_OUTPUT":
        assert message in summary.read_text(encoding="utf-8")


def test_no_github_env_no_files(mini_gate, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0  # simply must not crash


def test_hash_command_matches_library(tmp_path, capsys):
    p = tmp_path / "f.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert main(["hash", str(p)]) == 0
    out = capsys.readouterr().out
    assert file_sha256(str(p)) in out


def test_run_command_writes_run_json(mini_gate, tmp_path):
    paths = mini_gate()
    argv = [
        "run",
        "--dataset", paths["dataset"],
        "--config", paths["baseline"],
        "--scorers", paths["scorers"],
        "--pricing", paths["pricing"],
        "--out", str(tmp_path / "runout"),
    ]
    assert main(argv) == 0
    payload = json.loads(open(tmp_path / "runout" / "run.json", encoding="utf-8").read())
    assert payload["run"]["n_items"] == 3
    assert payload["run"]["aggregates"]["quality.pass_rate"]["value"] == 1.0


def test_missing_or_typoed_prompt_template_exits_two(mini_gate, capsys, tmp_path):
    # omitted template -> config error at load time
    paths = mini_gate()
    write_json(tmp_path / "candidate.json", {
        "name": "candidate", "provider": "fake", "model": "m-cand",
        "prompt": {"system": "answer"},
        "provider_options": {"fixtures": "fixtures/candidate.json"},
    })
    assert main(gate_argv(paths)) == 2
    assert "prompt.template" in capsys.readouterr().err
    # typo'd placeholder -> config error instead of a silent garbage prompt
    write_json(tmp_path / "candidate.json", {
        "name": "candidate", "provider": "fake", "model": "m-cand",
        "prompt": {"system": "answer", "template": "$documents\n\n$questoin"},
        "provider_options": {"fixtures": "fixtures/candidate.json"},
    })
    assert main(gate_argv(paths)) == 2
    assert "questoin" in capsys.readouterr().err


def test_breached_warn_rule_annotates_but_passes(mini_gate):
    # candidate is 3x slower; the only rule on latency is level=warn ->
    # exit 0, gate verdict pass, and the warning visible in the markdown
    from conftest import GOOD_RESPONSE
    slow = {k: {**v, "latency_ms": v["latency_ms"] * 3} for k, v in GOOD_RESPONSE.items()}
    paths = mini_gate(
        candidate_responses=slow,
        thresholds={"rules": [
            {"metric": "quality.pass_rate", "max_drop_abs": 0.0},
            {"metric": "latency.p95_ms", "max_increase_pct": 50, "level": "warn"},
        ]},
    )
    assert main(gate_argv(paths)) == 0
    report = json.loads(open(f"{paths['out']}/report.json", encoding="utf-8").read())
    assert report["gate"]["verdict"] == "pass"
    assert report["gate"]["n_warned"] == 1
    md = open(f"{paths['out']}/report.md", encoding="utf-8").read()
    assert "WARN" in md and "latency.p95_ms" in md


def test_malformed_dataset_exits_two(mini_gate, capsys):
    dup = {
        "name": "d", "version": "1", "task": "rag",
        "items": [
            {"id": "r1", "input": {"question": "q", "documents": []}, "expected": {}},
            {"id": "r1", "input": {"question": "q", "documents": []}, "expected": {}},
        ],
    }
    paths = mini_gate(dataset=dup)
    assert main(gate_argv(paths)) == 2
    assert "duplicate item id" in capsys.readouterr().err
    paths = mini_gate(dataset={"name": "d", "version": "1", "task": "rag", "items": []})
    assert main(gate_argv(paths)) == 2
    assert "non-empty list" in capsys.readouterr().err


def test_internal_errors_exit_two_not_one(mini_gate, monkeypatch, capsys):
    paths = mini_gate()
    import llm_release_gate.cli as cli_mod

    def boom(*a, **k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(cli_mod, "build_report", boom)
    assert main(gate_argv(paths)) == 2
    assert "internal error" in capsys.readouterr().err


def test_empty_must_contain_rejected(tmp_path):
    path = write_json(tmp_path / "dataset.json", {
        "name": "d", "version": "1", "task": "rag",
        "items": [
            {"id": "r1", "input": {}, "expected": {"quality": {"must_contain": [""]}}},
        ],
    })
    with pytest.raises(GateConfigError, match=r"expected\.quality\.must_contain"):
        load_dataset(path)


def test_whitespace_must_not_contain_rejected(tmp_path):
    path = write_json(tmp_path / "dataset.json", {
        "name": "d", "version": "1", "task": "rag",
        "items": [
            {"id": "r1", "input": {}, "expected": {"quality": {"must_not_contain": ["  "]}}},
        ],
    })
    with pytest.raises(GateConfigError, match=r"expected\.quality\.must_not_contain"):
        load_dataset(path)


def test_valid_quality_terms_still_load(tmp_path):
    path = write_json(tmp_path / "dataset.json", {
        "name": "d", "version": "1", "task": "rag",
        "items": [
            {"id": "r1", "input": {},
             "expected": {"quality": {"must_contain": ["blue"], "must_not_contain": ["red"]}}},
        ],
    })
    dataset = load_dataset(path)
    assert dataset.items[0].expected == {
        "quality": {"must_contain": ["blue"], "must_not_contain": ["red"]}
    }


def test_scorer_options_nan_rejected(tmp_path):
    path = write_json(tmp_path / "scorers.json", {
        "scorers": [{"type": "field_match", "options": {"threshold": float("nan")}}],
    })
    with pytest.raises(GateConfigError, match=r"finite"):
        load_scorer_config(path)


def test_scorer_options_infinity_rejected(tmp_path):
    path = write_json(tmp_path / "scorers.json", {
        "scorers": [{"type": "field_match",
                     "options": {"nested": {"values": [1.0, float("inf")]}}}],
    })
    with pytest.raises(GateConfigError, match=r"finite"):
        load_scorer_config(path)


def test_run_params_nan_rejected(tmp_path):
    path = write_json(tmp_path / "candidate.json", {
        "name": "candidate", "provider": "fake", "model": "m-cand",
        "prompt": {"system": "answer", "template": "$question"},
        "params": {"temperature": float("nan")},
    })
    with pytest.raises(GateConfigError, match=r"finite"):
        load_run_config(path, "candidate")


def test_finite_options_still_load(tmp_path):
    scorers_path = write_json(tmp_path / "scorers.json", {
        "scorers": [{"type": "field_match",
                     "options": {"threshold": 0.5, "nested": {"values": [1.0, 2]}}}],
    })
    scorers = load_scorer_config(scorers_path)
    assert scorers.scorers[0]["options"]["threshold"] == 0.5
    run_path = write_json(tmp_path / "candidate.json", {
        "name": "candidate", "provider": "fake", "model": "m-cand",
        "prompt": {"system": "answer", "template": "$question"},
        "params": {"temperature": 0.5},
        "provider_options": {"limit": 10},
    })
    run = load_run_config(run_path, "candidate")
    assert run.params["temperature"] == 0.5
