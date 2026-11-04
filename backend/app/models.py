"""Pydantic v2 models for the public API contract.

These models mirror ``docs/04_API.md`` and ``docs/fixtures/parse_result.sample.json``.
The sample fixture must always validate against :class:`ParseResult`; a test
enforces that so the contract cannot drift silently.

Terminology note: a *quantity* is what she said (e.g. ``1 muthi``); a *range* is
the deterministic code's honest interval estimate for it (e.g. ``33-44 g``). The
model keeps them separate so an LLM can never produce a gram value.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Basis(str, Enum):
    """Where a range's numbers come from (``docs/06``)."""

    exact = "exact"
    yours = "yours"
    typical = "typical"


class Source(str, Enum):
    """Which parser stage produced a quantity."""

    rules = "rules"
    llm = "llm"
    both = "both"


class ParserMode(str, Enum):
    """Persisted parser mode (``docs/03`` recipe_version.parser_mode)."""

    rules = "rules"
    llm = "llm"
    hybrid = "hybrid"


class ParseMode(str, Enum):
    """Requested mode for ``POST /api/parse``."""

    auto = "auto"
    rules = "rules"
    llm = "llm"


class Clarification(BaseModel):
    """One question the UI must answer instead of guessing (golden rule 3)."""

    id: str
    kind: str
    question: str
    options: list[str] = Field(default_factory=list)


class QuantityRange(BaseModel):
    """An honest interval in a concrete unit (``g``/``ml``)."""

    lo: float
    hi: float
    unit: str
    basis: Basis


class Quantity(BaseModel):
    """One ingredient/measure as spoken, plus code-derived range."""

    id: str
    ingredient: str | None = None
    ingredient_class: str | None = None
    qty: float | None = None
    qty_max: float | None = None
    unit: str | None = None
    to_taste: bool = False
    raw_phrase: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: Source
    range: QuantityRange | None = None
    clarification: Clarification | None = None


class CookingStep(BaseModel):
    """An ordered step; ``text`` keeps her original words (golden rule 5)."""

    idx: int
    text: str
    timer_seconds: int | None = None
    quantities: list[Quantity] = Field(default_factory=list)


class Recipe(BaseModel):
    """The parsed recipe. ``base_servings`` stays ``None`` when not stated."""

    title: str
    language: str | None = None
    base_servings: float | None = None
    steps: list[CookingStep] = Field(default_factory=list)


class Metadata(BaseModel):
    """Provenance for a parse result.

    ``mock`` is ``True`` whenever the response is fixture/mock data rather than
    output of a real parser or provider. ``mock_source`` names that source.
    """

    parser_mode: ParserMode
    llm_provider: str | None = None
    replayed: bool = False
    mock: bool = False
    mock_source: str | None = None


class ParseResult(BaseModel):
    """Full ``POST /api/parse`` response."""

    recipe: Recipe
    meta: Metadata


class ParseRequest(BaseModel):
    """``POST /api/parse`` request body.

    ``hand_profile_id`` and ``servings`` are part of the frozen contract but are
    not acted on in this batch (no hand calibration or serving scaling yet).
    """

    text: str = Field(min_length=1)
    mode: ParseMode = ParseMode.auto
    hand_profile_id: int | None = None
    servings: float | None = Field(default=None, gt=0)


class ErrorCode(str, Enum):
    """Documented API error codes (``docs/04_API.md``)."""

    INVALID_INPUT = "INVALID_INPUT"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    NO_API_KEY = "NO_API_KEY"
    UPSTREAM_BUSY = "UPSTREAM_BUSY"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    NOT_FOUND = "NOT_FOUND"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    hint: str | None = None


class ErrorResponse(BaseModel):
    """The only error shape the API returns."""

    error: ErrorDetail


class DbStatus(BaseModel):
    """Actual database state; nothing is opened in this batch."""

    status: str = "not_initialized"
    path: str | None = None
    note: str | None = None


class GnaniStatus(BaseModel):
    configured: bool
    mock: bool


class LlmProviderStatus(BaseModel):
    """Configuration and *probed* health of one provider.

    ``healthy`` is ``None`` when the provider was not probed. It is never set to
    ``True`` merely because a key exists.
    """

    name: str
    configured: bool
    healthy: bool | None = None
    note: str | None = None


class LlmStatus(BaseModel):
    chain: list[str] = Field(default_factory=list)
    healthy: list[str] = Field(default_factory=list)
    providers: list[LlmProviderStatus] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """``GET /api/health``. ``ok`` means the app is up, not that providers work."""

    ok: bool
    db: DbStatus
    gnani: GnaniStatus
    llm: LlmStatus
