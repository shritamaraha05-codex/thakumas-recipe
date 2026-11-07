"""Shared offline helpers for the M-10 Gemini provider tests.

Nothing here touches the network: :class:`FakeProvider` implements the
provider protocol and returns a canned (or computed) response, so the parsing
and API layers can be exercised without credentials or a live SDK client.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from backend.app.parse.lexicon import Category
from backend.app.parse.llm import Evidence


class FakeProvider:
    """A provider that records calls and returns a canned selection or error."""

    name = "gemini"

    def __init__(self, *, selection: Any = None, error: Exception | None = None) -> None:
        self.selection = selection
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        *,
        system_instruction: str,
        prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "prompt": prompt,
                "response_schema": response_schema,
            }
        )
        if self.error is not None:
            raise self.error
        if isinstance(self.selection, BaseModel):
            return self.selection
        return response_schema.model_validate(self.selection)


def find_id(evidence: Evidence, category: Category, surface: str | None = None) -> str:
    """Return the first evidence id of ``category`` (optionally by surface)."""
    for item_id, item in evidence.items.items():
        if item.match.category is category and (surface is None or item.match.surface == surface):
            return item_id
    raise AssertionError(f"no {category} evidence (surface={surface!r}) in {list(evidence.items)}")


def ids_by_category(evidence: Evidence, category: Category) -> list[str]:
    """Return every evidence id of one category, in id order."""
    return [item_id for item_id, item in evidence.items.items() if item.match.category is category]
