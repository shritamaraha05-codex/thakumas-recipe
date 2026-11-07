"""Replaceable LLM provider abstraction (M-10).

The parsing layer depends only on the small :class:`StructuredLLMProvider`
protocol declared here, never on a vendor SDK. Provider failures are surfaced as
provider-neutral exceptions so the API layer can map them to the documented
``ApiError`` codes without importing any vendor code. This keeps a second
provider replaceable without touching the serializer.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ProviderError(Exception):
    """A controlled upstream-provider failure."""


class ProviderUnavailable(ProviderError):
    """The provider cannot be used (missing or rejected credentials)."""


class ProviderTimeout(ProviderError):
    """The provider did not answer within the configured timeout."""


class ProviderRateLimited(ProviderError):
    """The provider rejected the request because of a rate limit."""


class ProviderInvalidOutput(ProviderError):
    """The provider answered, but its output could not be validated safely."""


@runtime_checkable
class StructuredLLMProvider(Protocol):
    """A provider that returns a validated instance of a Pydantic schema.

    The model chooses relationships; it never supplies wording, numbers or
    offsets. ``response_schema`` is the structured-output schema the provider
    must fill.
    """

    name: str

    async def generate(
        self,
        *,
        system_instruction: str,
        prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """Return a validated ``response_schema`` instance."""
        ...


__all__ = [
    "ProviderError",
    "ProviderInvalidOutput",
    "ProviderRateLimited",
    "ProviderTimeout",
    "ProviderUnavailable",
    "StructuredLLMProvider",
]
