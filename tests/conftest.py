"""Shared test scaffolding: a tiny parameterizable gate setup on disk.

``mini_gate`` builds a 3-item grounded dataset (2 answerable, 1 must-abstain)
with a well-behaved baseline; tests override candidate fixtures/thresholds to
produce the exact failure they want to observe.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest


def _find_action_bash():
    if sys.platform == "win32":
        # WSL's bash.exe does not preserve the native environment used by these tests.
        git = shutil.which("git")
        candidates = [Path(git).resolve().parent.parent / "bin/bash.exe"] if git else []
        candidates.append(Path("C:/Program Files/Git/bin/bash.exe"))
        return next((str(path) for path in candidates if path.is_file()), None)
    return shutil.which("bash")


@pytest.fixture
def action_bash():
    bash = _find_action_bash()
    if bash is None:
        pytest.skip("Action requires Git Bash on Windows or Bash on POSIX")
    return bash

BASE_MODEL = "m-base"
CAND_MODEL = "m-cand"

GOOD_RESPONSE = {
    "r1": {"text": "The sky is blue. [doc:s1]", "prompt_tokens": 100,
           "completion_tokens": 20, "latency_ms": 500.0},
    "r2": {"text": "The capital of Freedonia is Fredville. [doc:s1]", "prompt_tokens": 110,
           "completion_tokens": 22, "latency_ms": 520.0},
    "r3": {"text": "The sources don't cover this, so I don't know.", "prompt_tokens": 90,
           "completion_tokens": 15, "latency_ms": 480.0},
}

DEFAULT_THRESHOLDS = {
    "rules": [
        {"metric": "quality.pass_rate", "max_drop_abs": 0.0},
        {"metric": "abstention.false_answer_rate", "max_value": 0.0},
        {"metric": "citations.valid_rate", "max_drop_abs": 0.0},
    ]
}


def write_json(path, obj) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(path)


def _dataset() -> dict:
    return {
        "name": "mini-golden",
        "version": "1.0.0",
        "task": "rag",
        "items": [
            {
                "id": "r1",
                "input": {"question": "What color is the sky?",
                          "documents": [{"id": "s1", "text": "The sky is blue."}]},
                "expected": {"should_abstain": False,
                             "quality": {"must_contain": ["blue"]},
                             "must_cite": ["s1"]},
            },
            {
                "id": "r2",
                "input": {"question": "What is the capital of Freedonia?",
                          "documents": [{"id": "s1", "text": "The capital of Freedonia is Fredville."}]},
                "expected": {"should_abstain": False,
                             "quality": {"must_contain": ["fredville"]},
                             "must_cite": ["s1"]},
            },
            {
                "id": "r3",
                "input": {"question": "What is the population of Freedonia?",
                          "documents": [{"id": "s1", "text": "The capital of Freedonia is Fredville."}]},
                "expected": {"should_abstain": True},
            },
        ],
    }


@pytest.fixture
def mini_gate(tmp_path):
    def build(
        candidate_responses: dict | None = None,
        baseline_responses: dict | None = None,
        thresholds: dict | None = None,
        include_pricing: bool = True,
        pricing: dict | None = None,
        scorers: dict | None = None,
        dataset: dict | None = None,
    ) -> dict:
        paths = {}
        paths["dataset"] = write_json(tmp_path / "dataset.json", dataset or _dataset())
        write_json(
            tmp_path / "fixtures" / "baseline.json",
            {"version": "1", "responses": {BASE_MODEL: baseline_responses or GOOD_RESPONSE}},
        )
        write_json(
            tmp_path / "fixtures" / "candidate.json",
            {"version": "1", "responses": {CAND_MODEL: candidate_responses or GOOD_RESPONSE}},
        )
        paths["baseline"] = write_json(tmp_path / "baseline.json", {
            "name": "baseline", "provider": "fake", "model": BASE_MODEL,
            "prompt": {"system": "answer from docs", "template": "$documents\n\n$question"},
            "provider_options": {"fixtures": "fixtures/baseline.json"},
        })
        paths["candidate"] = write_json(tmp_path / "candidate.json", {
            "name": "candidate", "provider": "fake", "model": CAND_MODEL,
            "prompt": {"system": "answer from docs", "template": "$documents\n\n$question"},
            "provider_options": {"fixtures": "fixtures/candidate.json"},
        })
        paths["scorers"] = write_json(tmp_path / "scorers.json", scorers or {
            "scorers": [
                {"type": "keyword_quality"}, {"type": "abstention"}, {"type": "citations"},
            ]
        })
        paths["thresholds"] = write_json(
            tmp_path / "thresholds.json", thresholds or DEFAULT_THRESHOLDS
        )
        if include_pricing:
            paths["pricing"] = write_json(tmp_path / "pricing.json", pricing or {
                "version": "test-1", "currency": "USD",
                "models": {
                    BASE_MODEL: {"input_per_mtok": 10.0, "output_per_mtok": 20.0},
                    CAND_MODEL: {"input_per_mtok": 1.0, "output_per_mtok": 2.0},
                },
            })
        paths["out"] = str(tmp_path / "out")
        paths["tmp"] = tmp_path
        return paths

    return build


def gate_argv(paths: dict) -> list[str]:
    argv = [
        "gate",
        "--dataset", paths["dataset"],
        "--baseline", paths["baseline"],
        "--candidate", paths["candidate"],
        "--scorers", paths["scorers"],
        "--thresholds", paths["thresholds"],
        "--out", paths["out"],
    ]
    if "pricing" in paths:
        argv += ["--pricing", paths["pricing"]]
    return argv
