"""Task adapters: dataset item + run config -> provider request; raw text -> parsed output.

An adapter owns the conventions of one application shape (how documents are
rendered into the prompt, how citations/abstentions/JSON are read back out).
Scorers only ever see the ParsedOutput, so new tasks plug in without touching
scoring or comparison.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from string import Template
from typing import Callable, Optional

from ..errors import GateConfigError
from ..loading import DatasetItem, RunConfig
from ..providers import ProviderRequest


@dataclass
class ParsedOutput:
    text: str
    citations: list[str] = field(default_factory=list)  # doc ids the answer cited
    abstained: bool = False
    json_obj: Optional[object] = None    # parsed JSON body (extraction tasks)
    parse_error: Optional[str] = None    # set when structured parsing failed


class TaskAdapter(ABC):
    """Subclasses set ``name`` and ``version``; version lands in the manifest so a
    scoring-convention change is visible as a different run identity."""

    name: str = "abstract"
    version: str = "0"
    required_input: tuple[str, ...] = ()

    @abstractmethod
    def prompt_fields(self, item: DatasetItem) -> dict[str, str]:
        """Fields available to the config's prompt template ($question, $documents, ...)."""

    @abstractmethod
    def parse(self, text: str, item: DatasetItem) -> ParsedOutput:
        """Interpret raw model text under this task's output conventions."""

    def build_request(self, item: DatasetItem, config: RunConfig) -> ProviderRequest:
        for key in self.required_input:
            value = item.input.get(key)
            if not isinstance(value, str) or not value.strip():
                raise GateConfigError(
                    f"dataset item '{item.id}': task '{self.name}' requires "
                    f"input.{key} as a non-empty string"
                )
        fields = self.prompt_fields(item)
        template = Template(config.prompt.get("template", ""))
        # A typo'd placeholder would silently render literally and every request
        # would carry a garbage prompt — misconfiguration must fail, not run.
        unknown = set(template.get_identifiers()) - set(fields)
        if unknown:
            raise GateConfigError(
                f"config '{config.name}': prompt template references unknown "
                f"field(s) {sorted(unknown)}; task '{self.name}' provides {sorted(fields)}"
            )
        prompt = template.safe_substitute(fields)
        return ProviderRequest(
            model=config.model,
            system=config.prompt.get("system", ""),
            prompt=prompt,
            params=config.params,
            item_id=item.id,
        )

    def describe(self) -> dict:
        return {"name": self.name, "version": self.version}


_REGISTRY: dict[str, Callable[[], TaskAdapter]] = {}


def register_adapter(name: str, factory: Callable[[], TaskAdapter]) -> None:
    _REGISTRY[name] = factory


def build_adapter(task: str) -> TaskAdapter:
    if task not in _REGISTRY:
        raise GateConfigError(
            f"unknown task '{task}'; registered tasks: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[task]()


# Register built-ins on import.
from . import grounded as _grounded      # noqa: E402,F401
from . import extraction as _extraction  # noqa: E402,F401
