"""Package acceptance must exercise new commands, not only legacy imports."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess

import pytest

from llm_release_gate.cli import main
from scripts import verify_dist


def source_cli_runner(calls, mutation=None):
    """Use real CLI behavior; production smoke substitutes isolated wheel Python."""
    def run(*args, expected=0):
        assert args[:2] == ("-m", "llm_release_gate")
        calls.append((args, expected))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args[2:]))
        result = subprocess.CompletedProcess(args, code, out.getvalue(), err.getvalue())
        assert code == expected, (args, code, result.stdout, result.stderr)
        target = Path(args[args.index("--out") + 1])
        if mutation:
            mutation(args, target, result)
        return result
    return run


def test_smoke_exercises_plan_binding_caps_and_diagnostic_policy(tmp_path):
    assert hasattr(verify_dist, "smoke_replay_features")
    calls = []
    verify_dist.smoke_replay_features(source_cli_runner(calls), tmp_path)
    assert {args[2] for args, _ in calls} == {"plan", "gate", "run"}
    assert any(args[2] == "plan" and code == 2 for args, code in calls)
    assert sum(args[2] == "gate" and code == 2 for args, code in calls) == 3
    assert any(args[2] == "run" and "--fail-on-errors" in args and code == 2
               for args, code in calls)
    assert any(args[2] == "run" and "--fail-on-errors" not in args and code == 0
               for args, code in calls)


@pytest.mark.parametrize("failure", ["plan-overwrite", "plan-identity", "bound-identity",
                                    "generic-refusal", "diagnostic-loss"])
def test_smoke_refuses_false_positive_evidence(tmp_path, failure):
    assert hasattr(verify_dist, "smoke_replay_features")
    def mutate(args, target, result):
        if failure == "plan-overwrite" and args[2] == "plan" and result.returncode == 2:
            (target / "plan.json").write_text('{}')
        if failure == "plan-identity" and args[2] == "plan" and result.returncode == 0:
            path = target / "plan.json"
            plan = json.loads(path.read_text())
            plan["requests"][0]["request_sha256"] = "sha256:" + "0" * 64
            path.write_text(json.dumps(plan))
        if failure == "bound-identity" and args[2] == "gate" and result.returncode == 0:
            path = target / "report.json"
            report = json.loads(path.read_text())
            report["runs"]["candidate"]["provider"].pop("request_binding", None)
            path.write_text(json.dumps(report))
        if failure == "generic-refusal" and args[2] == "gate" and result.returncode == 2:
            result.stderr = "configuration error: some unrelated failure"
        if failure == "diagnostic-loss" and args[2] == "run":
            (target / "run.json").unlink()
    with pytest.raises((AssertionError, FileNotFoundError, KeyError)):
        verify_dist.smoke_replay_features(source_cli_runner([], mutate), tmp_path)
