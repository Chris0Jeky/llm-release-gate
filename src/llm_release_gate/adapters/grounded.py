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
"""

from __future__ import annotations

import re

from ..loading import DatasetItem
from . import ParsedOutput, TaskAdapter, register_adapter

CITATION_PATTERN = re.compile(r"\[doc:([^\]\s]+)\]")
ABSTENTION_PATTERN = re.compile(
    r"(?i)\b(i (?:do not|don't) know|cannot answer|can't answer|"
    r"not enough information|no supporting source)\b"
)


def _render_documents(item: DatasetItem) -> str:
    docs = item.input.get("documents", [])
    return "\n\n".join(f"[doc:{d['id']}]\n{d['text']}" for d in docs)


def _parse_grounded(text: str) -> ParsedOutput:
    citations = CITATION_PATTERN.findall(text)
    abstained = bool(ABSTENTION_PATTERN.search(text)) and not citations
    return ParsedOutput(text=text, citations=citations, abstained=abstained)


class RagAdapter(TaskAdapter):
    name = "rag"
    version = "2"  # v2: a citing reply is never an abstention
    required_input = ("question",)

    def prompt_fields(self, item: DatasetItem) -> dict[str, str]:
        return {
            "question": str(item.input.get("question", "")),
            "documents": _render_documents(item),
        }

    def parse(self, text: str, item: DatasetItem) -> ParsedOutput:
        return _parse_grounded(text)


class AssistantAdapter(TaskAdapter):
    name = "assistant"
    version = "2"  # v2: a citing reply is never an abstention
    required_input = ("question",)

    def prompt_fields(self, item: DatasetItem) -> dict[str, str]:
        return {
            "question": str(item.input.get("question", "")),
            "sources": _render_documents(item),
        }

    def parse(self, text: str, item: DatasetItem) -> ParsedOutput:
        return _parse_grounded(text)


register_adapter("rag", RagAdapter)
register_adapter("assistant", AssistantAdapter)
