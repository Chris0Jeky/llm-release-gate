"""Executable synthetic example and hosted Action exercise for request binding."""

import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

import pytest

from llm_release_gate.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/request-bound-replay"


def test_bound_demo_is_repeatable_and_refuses_stale_evidence(tmp_path):
    script = ROOT / "scripts/check_request_binding.py"
    assert script.is_file()
    artifacts = {}
    for _ in range(2):
        result = subprocess.run([sys.executable, str(script), "--out", str(tmp_path)],
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr + result.stdout
        current = {name: (tmp_path / name).read_bytes()
                   for name in ("report.json", "report.md", "report.html", "plan.json", "binding-check.json")}
        if artifacts:
            assert artifacts == current
        artifacts = current
    report = json.loads(artifacts["report.json"])
    assert report["gate"]["verdict"] == "pass"
    assert report["metrics"]["cost.total_usd"]["candidate"]["available"] is False
    assert json.loads(artifacts["binding-check.json"]) == {
        "synthetic": True, "valid_exit": 0, "stale_exit": 2, "request_binding": "sha256-v1"}


def test_committed_bound_example_works_via_gate(tmp_path):
    assert EXAMPLE.is_dir()
    argv = ["gate", "--out", str(tmp_path), "--require-request-binding"]
    for key in ("dataset", "baseline", "candidate", "scorers", "thresholds"):
        argv += ["--" + key, str(EXAMPLE / (key + ".json"))]
    assert main(argv) == 0


def test_ci_exercises_bound_and_downgraded_action_inputs():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert 'require-request-binding: "true"' in workflow
    assert '${{ steps.bound.outputs.verdict }}' in workflow
    assert '${{ steps.unbound.outcome }}' in workflow
    assert '${{ steps.unbound.outputs.verdict }}' in workflow
    assert "request-bound-replay" in workflow.split("  report-reproducibility:")[1]
    assert 'plan.json"' in workflow



@pytest.mark.skipif(shutil.which("bash") is None, reason="Action uses Bash; hosted Action jobs qualify it")
@pytest.mark.parametrize("value,accepted", [("true", True), ("false", True), ("", False),
                                           ("TRUE", False), ("$(touch injected)", False)])
def test_action_binding_boolean_is_literal_not_shell_code(tmp_path, value, accepted):
    action = (ROOT / "action.yml").read_text()
    step = action.split("    - name: Run gate\n", 1)[1]
    body = step.split("      run: |\n", 1)[1].split("\n    #", 1)[0]
    script = "\n".join(line[8:] for line in body.splitlines())
    shim = tmp_path / "python"
    shim.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGV_OUTPUT"\n')
    shim.chmod(0o755)
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
               IN_REQUIRE_BINDING=value, IN_MAX_INPUT_BYTES="", IN_PRICING="",
               GITHUB_OUTPUT=str(tmp_path / "outputs"), ARGV_OUTPUT=str(tmp_path / "argv"))
    for key in ("DATASET", "BASELINE", "CANDIDATE", "SCORERS", "THRESHOLDS", "OUT"):
        env["IN_" + key] = "file with spaces"
    result = subprocess.run([shutil.which("bash"), "-c", script], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0  # enforcement is deferred to the Action's final step
    assert not (tmp_path / "injected").exists()
    assert (tmp_path / "outputs").read_text().strip() == ("cli-exit=0" if accepted else "cli-exit=2")
    if accepted:
        args = (tmp_path / "argv").read_text().splitlines()
        assert ("--require-request-binding" in args) == (value == "true")
        assert args.count("file with spaces") == 6
    else:
        assert not (tmp_path / "argv").exists()
