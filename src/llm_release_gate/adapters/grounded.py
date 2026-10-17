"""Grounded-answer adapters: RAG pipelines and source-grounded staff assistants.

Item input shape:

    {"question": "...", "documents": [{"id": "d1", "text": "..."}, ...]}

Output conventions (documented in docs/architecture.md, encoded once here):
- citations are inline markers  ``[doc:<id>]``
- an abstention is a reply that matches ABSTENTION_PATTERN (e.g. "I don't know",
  "not enough information") AND cites nothing — a hedged reply that still makes
  a cited claim ("I don't know the clause, but it's 4 weeks [doc:x]") is an
  answer, and its citations get validated. This is a convention the app's
  prompts must adopt. Known heuristic limit: a hedge followed by an UNcited
  claim still reads as an abstention.

The two adapters share mechanics; they differ in the field name the prompt
template sees ($documents vs $sources), matching how each app talks about its
grounding material.

Fail-closed documents contract: ``input.documents`` stays optional (absent
renders as ""), but when present it must be a list of ``{"id", "text"}``
objects with unique non-empty string ids and string text. A malformed entry raises
GateConfigError naming the item id, mirroring TaskAdapter.required_input, so
the gate exits 2 instead of escaping as KeyError/TypeError or silently running
a garbage prompt. Per-item continuation stays reserved for provider runtime
failures; a bad dataset is configuration, like a missing input.question. The
dataset file path is unavailable at this layer (DatasetItem carries
id/input/expected only; the path lives on Dataset), so the message names the
item id in the required_input style.
"""

from __future__ import annotations

import re

from ..loading import DatasetItem, _validate_grounded_documents
from . import ParsedOutput, TaskAdapter, register_adapter, require_prompt_str

CITATION_PATTERN = re.compile(r"\[doc:([^\]\s]+)\]")
ABSTENTION_PATTERN = re.compile(
    r"(?i)\b(i (?:do not|don't) know|cannot answer|can't answer|"
    r"not enough information|no supporting source)\b"
)


def _render_documents(item: DatasetItem, task: str) -> str:
    _validate_grounded_documents(item.input, f"dataset item '{item.id}': task '{task}'")
    docs = item.input.get("documents", [])
    return "\n\n".join(f"[doc:{d['id']}]\n{d['text']}" for d in docs)


def _parse_grounded(text: str, item: DatasetItem, task: str) -> ParsedOutput:
    _validate_grounded_documents(item.input, f"dataset item '{item.id}': task '{task}'")
    citations = CITATION_PATTERN.findall(text)
    abstained = bool(ABSTENTION_PATTERN.search(text)) and not citations
    return ParsedOutput(text=text, citations=citations, abstained=abstained)


class RagAdapter(TaskAdapter):
    name = "rag"
    version = "2"  # v2: a citing reply is never an abstention
    required_input = ("question",)

    def prompt_fields(self, item: DatasetItem) -> dict[str, str]:
        return {
            "question": require_prompt_str(item, self.name, "question"),
            "documents": _render_documents(item, self.name),
        }

    def parse(self, text: str, item: DatasetItem) -> ParsedOutput:
        return _parse_grounded(text, item, self.name)


class AssistantAdapter(TaskAdapter):
    name = "assistant"
    version = "2"  # v2: a citing reply is never an abstention
    required_input = ("question",)

    def prompt_fields(self, item: DatasetItem) -> dict[str, str]:
        return {
            "question": require_prompt_str(item, self.name, "question"),
            "sources": _render_documents(item, self.name),
        }

    def parse(self, text: str, item: DatasetItem) -> ParsedOutput:
        return _parse_grounded(text, item, self.name)


register_adapter("rag", RagAdapter)
register_adapter("assistant", AssistantAdapter)
