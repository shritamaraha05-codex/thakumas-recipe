"""Structured model-output schema for the Gemini extraction (M-10).

The model may only *select* request-local evidence ids. It must never return its
own character offsets, invented ingredient names, quantities or step text, so
those fields simply do not exist here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngredientSelection(BaseModel):
    """One selected ingredient and the quantity evidence attached to it."""

    ingredient_match_id: str = Field(
        description="Evidence id of an ingredient match from the supplied list."
    )
    quantity_match_ids: list[str] = Field(
        default_factory=list,
        description="Evidence ids of number/measure matches that form its quantity.",
    )


class SegmentSelection(BaseModel):
    """One segment's selections; arrays may be empty."""

    segment_index: int = Field(description="0-based index of the segment.")
    ingredients: list[IngredientSelection] = Field(default_factory=list)
    duration_match_ids: list[str] = Field(
        default_factory=list,
        description="Evidence ids of duration matches (and their adjacent numbers).",
    )


class LLMSelection(BaseModel):
    """Top-level structured response: selections grouped by segment."""

    segments: list[SegmentSelection] = Field(default_factory=list)


__all__ = ["IngredientSelection", "LLMSelection", "SegmentSelection"]
