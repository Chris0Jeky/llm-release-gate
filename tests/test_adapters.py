"""Adapter prompt-template placeholder rejection.

A typo'd ``$placeholder`` must fail closed with GateConfigError, never render
literally into every request prompt.
"""

import pytest

from llm_release_gate.adapters import build_adapter
from llm_release_gate.errors import GateConfigError
from llm_release_gate.loading import DatasetItem, RunConfig


def test_unknown_template_placeholder_fails():
    cfg = RunConfig(
        name="c", provider="fake", model="m", params={},
        prompt={"template": "$question $typo"}, provider_options={},
        path="", sha256="",
    )
    item = DatasetItem(id="r1", input={"question": "q"}, expected={})
    with pytest.raises(GateConfigError, match=r"unknown field.*typo"):
        build_adapter("rag").build_request(item, cfg)
