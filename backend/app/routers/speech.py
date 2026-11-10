"""Authenticated Gnani Timbre speech synthesis for Cook Mode."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import hashlib

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..auth import AuthContext, get_auth_context
from ..config import Settings
from ..dependencies import get_settings
from ..errors import ApiError
from ..gnani import request_lock
from ..models import ErrorCode

router = APIRouter(tags=["speech"])
_tts_cache: OrderedDict[str, bytes] = OrderedDict()
_MAX_CACHE_ENTRIES = 128


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, strip_whitespace=True)
    language: str = Field(pattern=r"^(bn-IN|en-IN)$")
    speed: float = Field(default=1.0, ge=0.85, le=1.15)


async def _synthesize(text: str, language: str, speed: float, settings: Settings) -> bytes:
    if settings.gnani_mock:
        raise ApiError(
            503,
            ErrorCode.NO_API_KEY,
            "Gnani speech is in mock mode.",
            "Cook Mode will use the browser voice instead.",
        )
    if not settings.gnani_api_key:
        raise ApiError(
            503,
            ErrorCode.NO_API_KEY,
            "Gnani speech is not configured.",
            "Configure GNANI_API_KEY to enable Timbre speech.",
        )

    cache_key = hashlib.sha256(
        f"{settings.gnani_tts_model}\0{settings.gnani_voice}\0{language}\0{speed}\0{text}".encode()
    ).hexdigest()
    async with request_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
            return cached

        payload = {
            "text": text,
            "model": settings.gnani_tts_model,
            "voice": settings.gnani_voice,
            "language": language,
            "speed": speed,
            "audio_config": {
                "sample_rate": 48000,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        }
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=settings.gnani_tts_timeout) as client:
                    response = await client.post(
                        settings.gnani_tts_url,
                        headers={"X-API-Key-ID": settings.gnani_api_key},
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                raise ApiError(
                    503,
                    ErrorCode.UPSTREAM_BUSY,
                    "Gnani speech took too long to respond.",
                    "Retry this step or use the browser voice.",
                ) from exc
            except httpx.RequestError as exc:
                raise ApiError(
                    503,
                    ErrorCode.UPSTREAM_BUSY,
                    "Gnani speech is temporarily unreachable.",
                    "Retry this step or use the browser voice.",
                ) from exc

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise ApiError(
                    503,
                    ErrorCode.UPSTREAM_BUSY,
                    "Gnani speech is temporarily busy.",
                    "Retry this step or use the browser voice.",
                )
            if response.status_code == 401:
                raise ApiError(503, ErrorCode.NO_API_KEY, "Gnani speech credentials were rejected.")
            if response.status_code in (402, 403):
                raise ApiError(
                    503,
                    ErrorCode.UPSTREAM_ERROR,
                    "Gnani speech is unavailable for this account.",
                    "Check the Gnani account credits and Timbre access.",
                )
            if response.status_code >= 400:
                raise ApiError(
                    422,
                    ErrorCode.INVALID_INPUT,
                    "Gnani could not synthesize this step.",
                    "Review the step text or use the browser voice.",
                )
            if not response.content:
                raise ApiError(502, ErrorCode.UPSTREAM_ERROR, "Gnani returned empty speech audio.")
            if not response.headers.get("content-type", "").startswith("audio/"):
                raise ApiError(502, ErrorCode.UPSTREAM_ERROR, "Gnani returned an invalid speech-audio response.")

            audio = response.content
            _tts_cache[cache_key] = audio
            _tts_cache.move_to_end(cache_key)
            while len(_tts_cache) > _MAX_CACHE_ENTRIES:
                _tts_cache.popitem(last=False)
            return audio

    raise ApiError(503, ErrorCode.UPSTREAM_BUSY, "Gnani speech is temporarily busy.")


@router.post("/speak", response_class=Response)
async def speak(
    payload: SpeakRequest,
    _auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Return cached or newly synthesized Timbre WAV audio."""
    audio = await _synthesize(payload.text.strip(), payload.language, payload.speed, settings)
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})
