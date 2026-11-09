"""Google Gemini provider using the official ``google-genai`` SDK (M-10).

This is the only module that knows about the Gemini API. It asks the model for
*structured output* against a Pydantic schema (:mod:`backend.app.parse.llm_schema`)
and returns the validated instance; it never parses free-form Markdown.

Key handling and lifecycle
    * the API key comes from settings and is never logged, echoed or committed;
    * the SDK is imported lazily so importing this module (and running the test
      suite) never requires the SDK or any credentials;
    * a client is created only when :meth:`GeminiProvider.generate` is called and
      is always closed afterwards;
    * no retries are added here: the caller decides the policy so API costs
      cannot multiply unexpectedly.

Errors are translated into the provider-neutral exceptions in
:mod:`backend.app.providers`; raw SDK exceptions are never exposed to clients.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import BaseModel

from . import (
    ProviderError,
    ProviderInvalidOutput,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
)

# Configured default model (docs/04_API.md / .env.example). Kept as a named
# constant so the value is visible and never hard-coded at a call site.
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Matches the per-provider timeout documented in docs/08_LLM_PROVIDERS.md.
DEFAULT_TIMEOUT_MS = 12_000


class GeminiProvider:
    """Async structured-output provider backed by ``google-genai``."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        if not api_key:
            raise ProviderUnavailable("Gemini API key is not configured.")
        if not model:
            raise ProviderUnavailable("Gemini model is not configured.")
        self._api_key = api_key
        self._model = model
        self._timeout_ms = timeout_ms

    @property
    def model(self) -> str:
        """The configured model id sent to the API (never the API key)."""
        return self._model

    async def generate(
        self,
        *,
        system_instruction: str,
        prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """Call Gemini and return an instance of ``response_schema``."""
        genai, types, errors = _sdk()
        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=self._timeout_ms),
        )
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.0,
            )
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except errors.APIError as exc:
            raise _map_api_error(exc) from exc
        except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
            raise ProviderTimeout("Gemini request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Gemini request failed.") from exc
        finally:
            await _close(client)

        parsed = getattr(response, "parsed", None)
        if parsed is None:
            raise ProviderInvalidOutput("Gemini returned no structured output.")
        if not isinstance(parsed, response_schema):
            raise ProviderInvalidOutput("Gemini output did not match the requested schema.")
        return parsed


def _sdk() -> tuple[Any, Any, Any]:
    """Import the SDK lazily so the module loads without ``google-genai``."""
    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ProviderUnavailable(
            "The google-genai SDK is not installed; install requirements.txt."
        ) from exc
    return genai, types, errors


def _map_api_error(exc: Any) -> ProviderError:
    """Translate an SDK ``APIError`` without leaking its raw message."""
    code = getattr(exc, "code", None)
    if code == 429:
        return ProviderRateLimited("Gemini rate limit reached.")
    if code in (401, 403):
        return ProviderUnavailable("Gemini credentials were rejected.")
    return ProviderError("Gemini returned an error.")


async def _close(client: Any) -> None:
    """Close the SDK client, ignoring a close failure of an already-dead client."""
    try:
        await client.aio.aclose()
    except Exception:  # cleanup must never mask the real result
        pass


def build_provider(settings: Any) -> GeminiProvider:
    """Build the Gemini provider from settings, or raise if it is not usable."""
    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model or DEFAULT_MODEL,
    )
