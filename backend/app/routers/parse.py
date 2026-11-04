"""Parsing endpoint.

This batch does **not** parse text yet. ``POST /api/parse`` returns the sample
fixture from ``docs/fixtures/parse_result.sample.json`` for every supported
mode, clearly labelled as mock data. No LLM or Gnani call is made, so the
endpoint works with no credentials and no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends

from ..config import REPO_ROOT, Settings
from ..dependencies import get_settings
from ..models import ParseRequest, ParseResult, ParserMode

router = APIRouter(tags=["parse"])


def load_fixture_result(path: Path) -> ParseResult:
    """Read and validate the fixture so contract drift fails loudly."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ParseResult.model_validate(raw)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


@router.post("/parse", response_model=ParseResult)
def parse(
    request: ParseRequest, settings: Settings = Depends(get_settings)
) -> ParseResult:
    result = load_fixture_result(settings.mock_fixture_path)

    # Honest metadata: no provider was invoked. parser_mode is "rules" because
    # the deterministic floor is the only implemented path; llm_provider is None.
    result.meta.parser_mode = ParserMode.rules
    result.meta.llm_provider = None
    result.meta.replayed = False
    result.meta.mock = True
    result.meta.mock_source = _display_path(settings.mock_fixture_path)
    return result
