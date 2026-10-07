"""Opt-in safety controls must not change the released default contract."""

import io
import json
from pathlib import Path

import pytest

from llm_release_gate import loading
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from conftest import gate_argv


def run_args(paths):
    return ["run", "--dataset", paths["dataset"], "--config", paths["candidate"],
            "--scorers", paths["scorers"], "--out", paths["out"]]


def test_bounded_gate_preserves_existing_report_bytes(mini_gate):
    paths = mini_gate()
    assert main(gate_argv(paths)) == 0
    before = (Path(paths["out"]) / "report.json").read_bytes()
    assert main(gate_argv(paths) + ["--max-input-bytes", "100000"]) == 0
    assert (Path(paths["out"]) / "report.json").read_bytes() == before
    manifest = json.loads((Path(paths["out"]) / "manifest.json").read_text())
    assert manifest["execution_options"]["max_input_bytes"] == 100000


@pytest.mark.parametrize("target", ["dataset.json", "baseline.json", "candidate.json",
    "scorers.json", "thresholds.json", "pricing.json", "fixtures/baseline.json", "fixtures/candidate.json"])
def test_each_gate_input_obeys_raw_byte_cap(mini_gate, target, capsys):
    paths = mini_gate()
    path = paths["tmp"] / target
    path.write_bytes(path.read_bytes() + b" " * 10001)
    assert main(gate_argv(paths) + ["--max-input-bytes", "10000"]) == 2
    err = capsys.readouterr().err
    assert "exceeds max input size of 10000 bytes" in err
    assert "Traceback" not in err
    assert not Path(paths["out"]).exists()


@pytest.mark.parametrize("extra, allowed", [(0, True), (1, False)])
def test_limit_counts_utf8_source_bytes_not_characters(tmp_path, extra, allowed):
    assert hasattr(loading, "input_byte_limit")
    path = tmp_path / "utf8.json"
    raw = '{"value":"é"}\r\n'.encode("utf-8")
    path.write_bytes(raw + b" " * extra)
    with loading.input_byte_limit(len(raw)):
        if allowed:
            assert loading._load_json_file(str(path), "test")[0] == {"value": "é"}
        else:
            with pytest.raises(GateConfigError, match="exceeds max input size"):
                loading._load_json_file(str(path), "test")


def test_cap_is_scoped_and_restored_after_nested_failure(tmp_path):
    assert hasattr(loading, "input_byte_limit")
    path = tmp_path / "data.json"
    path.write_text('{"key":42}')
    with loading.input_byte_limit(100):
        with pytest.raises(GateConfigError):
            with loading.input_byte_limit(1):
                loading._load_json_file(str(path), "test")
        assert loading._load_json_file(str(path), "test")[0] == {"key": 42}
    assert loading._load_json_file(str(path), "test")[0] == {"key": 42}


def test_limited_reader_never_uses_unbounded_read(monkeypatch):
    assert hasattr(loading, "input_byte_limit")
    reads = []
    class Source(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            assert 0 < size <= 65536
            return super().read(size)
    monkeypatch.setattr(loading, "open", lambda *a, **kw: Source(b'{}' + b' ' * 100000), raising=False)
    with loading.input_byte_limit(70000):
        with pytest.raises(GateConfigError, match="exceeds max input size"):
            loading._load_json_file("data.json", "test")
    assert sum(reads) == 70001


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "100"])
def test_api_rejects_invalid_byte_caps(value):
    assert hasattr(loading, "input_byte_limit")
    with pytest.raises(GateConfigError, match="positive integer"):
        with loading.input_byte_limit(value):
            pass


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "nonsense", "$(touch injected)"])
def test_cli_rejects_invalid_byte_caps(mini_gate, value, capsys):
    paths = mini_gate()
    with pytest.raises(SystemExit) as err:
        main(gate_argv(paths) + ["--max-input-bytes", value])
    assert err.value.code == 2
    assert "positive integer" in capsys.readouterr().err
    assert not Path(paths["out"]).exists()


@pytest.mark.parametrize("n_errors", [0, 1, 3])
def test_run_error_policy_is_opt_in_and_preserves_diagnostics(mini_gate, n_errors, capsys):
    paths = mini_gate()
    fixture = paths["tmp"] / "fixtures/candidate.json"
    data = json.loads(fixture.read_text())
    for i in range(n_errors):
        data["responses"]["m-cand"][f"r{i+1}"] = {"error": "test failure"}
    fixture.write_text(json.dumps(data))
    assert main(run_args(paths)) == 0
    output = Path(paths["out"]) / "run.json"
    before = output.read_bytes()
    assert main(run_args(paths) + ["--fail-on-errors"]) == (2 if n_errors else 0)
    assert output.read_bytes() == before
    assert json.loads(output.read_text())["run"]["n_errors"] == n_errors
    err = capsys.readouterr().err
    assert "Traceback" not in err
    if n_errors:
        assert "--fail-on-errors" in err


def test_limited_run_includes_transitive_fixture(mini_gate, capsys):
    paths = mini_gate()
    fixture = paths["tmp"] / "fixtures/candidate.json"
    fixture.write_bytes(fixture.read_bytes() + b' ' * 10001)
    assert main(run_args(paths) + ["--max-input-bytes", "10000"]) == 2
    assert "fake provider fixture" in capsys.readouterr().err
    assert not Path(paths["out"]).exists()


def test_limit_isolated_between_contexts(tmp_path):
    from contextvars import Context
    path = tmp_path / "data.json"
    path.write_text('{"key":42}')
    independent = Context()
    with loading.input_byte_limit(1):
        assert independent.run(loading._load_json_file, str(path), "test")[0] == {"key": 42}
        with pytest.raises(GateConfigError, match="exceeds max input size"):
            loading._load_json_file(str(path), "test")


def test_action_passes_size_limit_as_quoted_argument():
    action = (Path(__file__).resolve().parents[1] / "action.yml").read_text()
    assert "IN_MAX_INPUT_BYTES: ${{ inputs.max-input-bytes }}" in action
    assert 'args+=(--max-input-bytes "$IN_MAX_INPUT_BYTES")' in action
    assert "--max-input-bytes ${{" not in action


def test_action_self_test_covers_bounded_acceptance_and_refusal():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
    assert 'max-input-bytes: "1048576"' in workflow
    assert 'max-input-bytes: "1"' in workflow
    assert '${{ steps.oversize.outcome }}' in workflow
    assert '${{ steps.oversize.outputs.verdict }}' in workflow
