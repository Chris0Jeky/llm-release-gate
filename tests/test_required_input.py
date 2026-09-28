"""Fail-closed on dataset items missing the task's prompt input.

A missing ``input.question`` (grounded tasks) or ``input.text`` (extraction)
is a configuration error (exit 2), never an empty-prompt run.
"""

import pytest

from conftest import gate_argv
from llm_release_gate.adapters import build_adapter
from llm_release_gate.cli import main
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem, RunConfig


def _rag_dataset(items):
    return {"name": "d", "version": "1", "task": "rag", "items": items}


def test_rag_item_without_input_key_exits_two(mini_gate, capsys):
    paths = mini_gate(dataset=_rag_dataset(
        [{"id": "r1", "expected": {}}]
    ))
    assert main(gate_argv(paths)) == 2
    err = capsys.readouterr().err
    assert "input.question" in err
    assert "r1" in err


def test_rag_item_with_blank_question_exits_two(mini_gate, capsys):
    paths = mini_gate(dataset=_rag_dataset(
        [{"id": "r1", "input": {"question": "   ", "documents": []}, "expected": {}}]
    ))
    assert main(gate_argv(paths)) == 2
    err = capsys.readouterr().err
    assert "input.question" in err
    assert "r1" in err


def test_rag_item_with_documents_but_no_question_exits_two(mini_gate, capsys):
    paths = mini_gate(dataset=_rag_dataset(
        [{"id": "r1",
          "input": {"documents": [{"id": "s1", "text": "The sky is blue."}]},
          "expected": {}}]
    ))
    assert main(gate_argv(paths)) == 2
    err = capsys.readouterr().err
    assert "input.question" in err
    assert "r1" in err


def test_extraction_item_without_text_raises_config_error():
    cfg = RunConfig(
        name="c", provider="fake", model="m", params={},
        prompt={"template": "$text"}, provider_options={},
        path="", sha256="",
    )
    with pytest.raises(GateConfigError, match=r"input\.text"):
        build_adapter("extraction").build_request(
            DatasetItem(id="x", input={}, expected={}), cfg
        )


def test_valid_items_build_identical_prompts():
    text_cfg = RunConfig(
        name="c", provider="fake", model="m", params={},
        prompt={"template": "$text"}, provider_options={},
        path="", sha256="",
    )
    req = build_adapter("extraction").build_request(
        DatasetItem(id="x", input={"text": "t"}, expected={}), text_cfg
    )
    assert req.prompt == "t"

    rag_cfg = RunConfig(
        name="c", provider="fake", model="m", params={},
        prompt={"template": "$question"}, provider_options={},
        path="", sha256="",
    )
    req = build_adapter("rag").build_request(
        DatasetItem(id="r1", input={"question": "q"}, expected={}), rag_cfg
    )
    assert req.prompt == "q"
