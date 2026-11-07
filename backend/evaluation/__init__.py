"""Evaluation package for Thakuma's Recipe (M-11).

Measures the deterministic rules parser (M-08) and the Gemini extraction parser
(M-10) against a manually curated golden dataset. Nothing here changes the
production parsers; the evaluator treats them as black boxes and compares their
internal ``parse.schema.ParseResult`` with the annotated expectations.

The evaluation schema is deliberately independent of the public API models in
``backend.app.models`` so it can evolve without touching the frozen contract.
"""

from __future__ import annotations

# Bump when dataset cases or their expected facts change.
DATASET_VERSION = "1.0.0"

__all__ = ["DATASET_VERSION"]
