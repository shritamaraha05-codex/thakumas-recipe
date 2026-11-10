"""Parsing endpoint.

``POST /api/parse`` runs either the deterministic rules parser (M-08) or the
Gemini LLM parser (M-10) over the submitted narration and returns the public
:class:`ParseResult` (via :func:`parse.serialize.to_api_result`).

Modes (``docs/04_API.md``):
    * ``rules`` - the deterministic offline parser; makes no external call;
    * ``auto``  - the first *implemented* parser in the configured ``LLM_CHAIN``
      (walked in order; ``rules`` is the documented floor). It does not fall back
      after a provider is chosen: a chosen provider's failure is reported.
    * ``llm``   - an explicit request for the Gemini parser. It is never silently
      downgraded to ``rules``; every failure returns a documented ``ApiError``.

``hand_profile_id`` and ``servings`` are accepted for contract compatibility but
are not used: calibration and scaling are later tasks.
"""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable

from fastapi import APIRouter, Depends

from ..config import Settings
from ..dependencies import get_llm_provider_factory, get_settings
from ..errors import ApiError
from ..models import (
    ErrorCode,
    ErrorResponse,
    ParseMode,
    ParseRequest,
    ParseResolveRequest,
    ParseResult,
)
from ..parse.llm import parse_llm
from ..parse.normalize import normalize
from ..parse.rules import parse_rules
from ..parse.serialize import to_api_result
from ..providers import (
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
    StructuredLLMProvider,
)

router = APIRouter(tags=["parse"])

# Parsers this build can actually run. ``auto`` only ever selects from here.
IMPLEMENTED_PARSERS = frozenset({"rules", "gemini"})


def _resolve_parser(mode: ParseMode, settings: Settings) -> str:
    """Pick the parser for ``mode``.

    ``rules`` is returned directly. For ``auto`` the configured ``LLM_CHAIN`` is
    walked and the first implemented provider wins; ``rules`` is the last-resort
    floor, matching the configuration contract. An explicit ``llm`` request uses
    Gemini and is never downgraded to rules.
    """
    if mode is ParseMode.rules:
        return "rules"
    if mode is ParseMode.llm:
        return "gemini"
    for provider in settings.llm_chain_list:
        if provider in IMPLEMENTED_PARSERS:
            return provider
    return "rules"


def _provider_api_error(exc: ProviderError) -> ApiError:
    """Map a provider-neutral failure to a documented ``ApiError``."""
    if isinstance(exc, ProviderUnavailable):
        return ApiError(
            status_code=503,
            code=ErrorCode.LLM_UNAVAILABLE,
            message="The Gemini provider is not available.",
            hint="Set GEMINI_API_KEY (and GEMINI_MODEL), or use mode='rules'.",
        )
    if isinstance(exc, ProviderTimeout):
        return ApiError(
            status_code=504,
            code=ErrorCode.UPSTREAM_BUSY,
            message="The Gemini provider timed out.",
            hint="Try again, or use mode='rules' for the offline parser.",
        )
    if isinstance(exc, ProviderRateLimited):
        return ApiError(
            status_code=503,
            code=ErrorCode.UPSTREAM_BUSY,
            message="The Gemini provider is rate limited.",
            hint="Wait and retry, or use mode='rules' for the offline parser.",
        )
    return ApiError(
        status_code=502,
        code=ErrorCode.UPSTREAM_ERROR,
        message="The Gemini provider returned an unusable response.",
        hint="The structured output failed validation; no recipe was fabricated.",
    )


@router.post(
    "/parse",
    response_model=ParseResult,
    responses={
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def parse(
    request: ParseRequest,
    settings: Settings = Depends(get_settings),
    provider_factory: Callable[[Settings], StructuredLLMProvider] = Depends(
        get_llm_provider_factory
    ),
) -> ParseResult:
    parser = _resolve_parser(request.mode, settings)
    normalized = normalize(request.text)

    if parser == "rules":
        internal = parse_rules(normalized)
        return to_api_result(internal, original=normalized.original)

    try:
        provider = provider_factory(settings)
        internal = await parse_llm(normalized, provider)
    except ProviderError as exc:
        raise _provider_api_error(exc) from exc
    return to_api_result(internal, original=normalized.original)


@router.post("/parse/resolve", response_model=ParseResult)
async def resolve_parse(request: ParseResolveRequest) -> ParseResult:
    """Apply only explicit, offered answers to the user's parser draft.

    Spoon choices become canonical tsp/tbsp units. Cup choices are preserved
    as a resolution label because no sourced cup conversion is available yet.
    """
    draft = deepcopy(request.draft)
    available = {
        quantity.clarification.id: quantity
        for step in draft.recipe.steps
        for quantity in step.quantities
        if quantity.clarification is not None
    }
    answers: dict[str, str] = {}
    for item in request.answers:
        if item.clarification_id in answers:
            raise ApiError(422, ErrorCode.INVALID_INPUT, "A clarification can only be answered once.")
        quantity = available.get(item.clarification_id)
        if quantity is None:
            raise ApiError(422, ErrorCode.INVALID_INPUT, "The clarification is not present in this draft.")
        clarification = quantity.clarification
        if item.answer not in clarification.options:
            raise ApiError(422, ErrorCode.INVALID_INPUT, "Choose one of the options shown for this clarification.")
        if clarification.kind not in {"unit_spoon", "unit_cup"}:
            raise ApiError(422, ErrorCode.INVALID_INPUT, "This clarification type cannot be resolved yet.")
        answers[item.clarification_id] = item.answer

    resolved_steps = []
    for step in draft.recipe.steps:
        quantities = []
        for quantity in step.quantities:
            clarification = quantity.clarification
            answer = answers.get(clarification.id) if clarification else None
            if answer is None:
                quantities.append(quantity)
                continue
            unit = answer if clarification.kind == "unit_spoon" else quantity.unit
            quantities.append(quantity.model_copy(update={
                "unit": unit,
                "clarification": None,
                "resolution": answer,
            }))
        resolved_steps.append(step.model_copy(update={"quantities": quantities}))

    return draft.model_copy(update={
        "recipe": draft.recipe.model_copy(update={"steps": resolved_steps})
    })
