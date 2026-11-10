"""Authenticated Gnani Timbre speech synthesis for Cook Mode."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import hashlib

import requests
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from gnani.tts import AudioConfig, GnaniTTSClient
from gnani.tts.exceptions import APIError as GnaniAPIError
from gnani.tts.exceptions import AuthenticationError as GnaniAuthenticationError

from ..auth import AuthContext, get_auth_context
from ..config import Settings
from ..dependencies import get_settings
from ..errors import ApiError
from ..gnani import request_lock
from ..models import ErrorCode

router = APIRouter(tags=["speech"])
_tts_cache: OrderedDict[str, bytes] = OrderedDict()
_MAX_CACHE_ENTRIES = 128
_TTS_MODEL = "timbre-v3.0"
_TTS_VOICE = "Shivani"


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
        f"{_TTS_MODEL}\0{_TTS_VOICE}\0{language}\0{speed}\0{text}".encode()
    ).hexdigest()
    async with request_lock:
        cached = _tts_cache.get(cache_key)
        if cached is not None:
            _tts_cache.move_to_end(cache_key)
            return cached

        for attempt in range(2):
            try:
                audio = await asyncio.to_thread(_synthesize_with_sdk, text, language, speed, settings.gnani_api_key)
            except requests.Timeout as exc:
                raise ApiError(
                    503,
                    ErrorCode.UPSTREAM_BUSY,
                    "Gnani speech took too long to respond.",
                    "Retry this step or use the browser voice.",
                ) from exc
            except requests.RequestException as exc:
                raise ApiError(
                    503,
                    ErrorCode.UPSTREAM_BUSY,
                    "Gnani speech is temporarily unreachable.",
                    "Retry this step or use the browser voice.",
                ) from exc

            except GnaniAuthenticationError as exc:
                raise ApiError(503, ErrorCode.NO_API_KEY, "Gnani speech credentials were rejected.") from exc
            except GnaniAPIError as exc:
                if exc.status_code == 429 or exc.status_code >= 500:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    raise ApiError(
                        503,
                        ErrorCode.UPSTREAM_BUSY,
                        "Gnani speech is temporarily busy.",
                        "Retry this step or use the browser voice.",
                    ) from exc
                if exc.status_code == 402 or exc.status_code == 403:
                    raise ApiError(
                        503,
                        ErrorCode.UPSTREAM_ERROR,
                        "Gnani speech is unavailable for this account.",
                        "Check the Gnani account credits and Timbre access.",
                    ) from exc
                raise ApiError(
                    422,
                    ErrorCode.INVALID_INPUT,
                    "Gnani could not synthesize this step.",
                    "Review the step text or use the browser voice.",
                ) from exc

            if not audio:
                raise ApiError(502, ErrorCode.UPSTREAM_ERROR, "Gnani returned empty speech audio.")

            _tts_cache[cache_key] = audio
            _tts_cache.move_to_end(cache_key)
            while len(_tts_cache) > _MAX_CACHE_ENTRIES:
                _tts_cache.popitem(last=False)
            return audio

    raise ApiError(503, ErrorCode.UPSTREAM_BUSY, "Gnani speech is temporarily busy.")


def _synthesize_with_sdk(text: str, language: str, speed: float, api_key: str) -> bytes:
    """Run the synchronous Gnani SDK request outside the async event loop."""
    client = GnaniTTSClient(api_key=api_key)
    return client.synthesize(
        text,
        voice=_TTS_VOICE,
        model=_TTS_MODEL,
        language=language,
        speed=speed,
        audio_config=AudioConfig(container="wav", encoding="linear_pcm", sample_rate=48000),
    )


@router.post("/speak", response_class=Response)
async def speak(
    payload: SpeakRequest,
    _auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Return cached or newly synthesized Timbre WAV audio."""
    audio = await _synthesize(payload.text.strip(), payload.language, payload.speed, settings)
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})
