"""Malformed grounded documents fail closed as GateConfigError.

One bad ``input.documents`` entry (missing text, a bare string, or null) must
never escape ``prompt_fields``/``_render_documents`` as KeyError/TypeError.
The adapters validate each document shape per item and raise GateConfigError
naming the item id, mirroring the required_input style; valid items still
render. (pytest.raises(GateConfigError) fails the test if KeyError/TypeError
escapes instead.)
"""

import pytest

from llm_release_gate.adapters import build_adapter
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem, RunConfig

TASKS = ["rag", "assistant"]


def _config(task: str) -> RunConfig:
    field = "documents" if task == "rag" else "sources"
    return RunConfig(
        name="c", provider="fake", model="m", params={},
        prompt={"template": f"$question\n${field}"}, provider_options={},
        path="", sha256="",
    )


@pytest.mark.parametrize("task", TASKS)
def test_missing_text_entry_is_config_error(task):
    item = DatasetItem(id="r1", input={"question": "q", "documents": [{"id": "d1"}]}, expected={})
    with pytest.raises(GateConfigError, match=r"input\.documents") as excinfo:
        build_adapter(task).build_request(item, _config(task))
    assert "r1" in str(excinfo.value)


@pytest.mark.parametrize("task", TASKS)
def test_string_documents_is_config_error(task):
    item = DatasetItem(id="r1", input={"question": "q", "documents": "oops"}, expected={})
    with pytest.raises(GateConfigError, match=r"input\.documents") as excinfo:
        build_adapter(task).build_request(item, _config(task))
    assert "r1" in str(excinfo.value)


@pytest.mark.parametrize("task", TASKS)
def test_null_documents_is_config_error(task):
    item = DatasetItem(id="r1", input={"question": "q", "documents": None}, expected={})
    with pytest.raises(GateConfigError, match=r"input\.documents") as excinfo:
        build_adapter(task).build_request(item, _config(task))
    assert "r1" in str(excinfo.value)


@pytest.mark.parametrize("task", TASKS)
def test_valid_documents_still_render(task):
    item = DatasetItem(
        id="r1",
        input={"question": "q", "documents": [{"id": "d1", "text": "hello"}]},
        expected={},
    )
    fields = build_adapter(task).prompt_fields(item)
    rendered = fields["documents"] if task == "rag" else fields["sources"]
    assert "[doc:d1]" in rendered
    assert "hello" in rendered
    request = build_adapter(task).build_request(item, _config(task))
    assert "[doc:d1]" in request.prompt
