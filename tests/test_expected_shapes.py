"""Dataset ``expected``-block shapes are validated fail-closed at load time."""

from __future__ import annotations

import json

import pytest

from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import load_dataset


def _write(path, obj) -> str:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _dataset_doc(item: dict) -> dict:
    return {"name": "d", "version": "1", "task": "rag", "items": [item]}


@pytest.mark.parametrize(
    ("expected", "field"),
    [
        ({"quality": "x"}, "expected.quality"),
        ({"quality": {"must_contain": "ab"}}, "expected.quality.must_contain"),
        ({"quality": {"must_contain": ["a", 1]}}, "expected.quality.must_contain"),
        ({"quality": {"must_not_contain": "x"}}, "expected.quality.must_not_contain"),
        ({"must_cite": "d1"}, "expected.must_cite"),
        ({"must_cite": [1]}, "expected.must_cite"),
        ({"should_abstain": "false"}, "expected.should_abstain"),
        ({"should_abstain": 0}, "expected.should_abstain"),
        ({"should_abstain": None}, "expected.should_abstain"),
        ({"fields": "x"}, "expected.fields"),
        ({"fields": [1]}, "expected.fields"),
    ],
)
def test_expected_wrong_shapes_rejected(tmp_path, expected, field):
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"id": "r1", "input": {}, "expected": expected}),
    )
    with pytest.raises(GateConfigError, match=field.replace(".", r"\.")):
        load_dataset(path)


def test_expected_full_and_empty_blocks_accepted(tmp_path):
    full = {
        "quality": {"must_contain": ["a"], "must_not_contain": []},
        "must_cite": ["d1"],
        "should_abstain": False,
        "fields": {"k": 1},
        "_note": "free text",
    }
    path = _write(
        tmp_path / "dataset.json",
        _dataset_doc({"id": "r1", "input": {}, "expected": full}),
    )
    dataset = load_dataset(path)
    assert dataset.items[0].expected == full
    path = _write(tmp_path / "dataset.json", _dataset_doc({"id": "r1", "input": {}, "expected": {}}))
    assert load_dataset(path).items[0].expected == {}


def test_expected_bad_shape_exits_two_end_to_end(mini_gate):
    from conftest import gate_argv

    from llm_release_gate.cli import main

    bad_dataset = {
        "name": "d",
        "version": "1",
        "task": "rag",
        "items": [
            {
                "id": "r1",
                "input": {"question": "q", "documents": []},
                "expected": {"quality": {"must_contain": "ab"}},
            }
        ],
    }
    paths = mini_gate(dataset=bad_dataset)
    assert main(gate_argv(paths)) == 2
