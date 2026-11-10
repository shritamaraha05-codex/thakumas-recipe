"""Consented, non-persistent speech-to-text for narrated recipes."""

from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from pydantic import BaseModel

from ..auth import AuthContext, get_auth_context
from ..config import Settings
from ..dependencies import get_settings
from ..errors import ApiError
from ..models import ErrorCode

router = APIRouter(tags=["narrations"])
_gnani_lock = asyncio.Lock()
MAX_SECONDS = 30
MAX_WAV_BYTES = 44 + (16_000 * 2 * MAX_SECONDS)
MOCK_TRANSCRIPT_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "mock_transcript_bn.txt"


class TranscriptionResponse(BaseModel):
    transcript: str
    detected_language_code: str | None = None
    mock: bool = False


def _validate_wav(content: bytes) -> None:
    try:
        with wave.open(io.BytesIO(content), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
            valid_format = (
                wav.getnchannels() == 1
                and wav.getsampwidth() == 2
                and wav.getframerate() == 16000
                and wav.getcomptype() == "NONE"
            )
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        raise ApiError(422, ErrorCode.INVALID_INPUT, "Audio must be a valid PCM WAV file.") from exc
    if not valid_format:
        raise ApiError(422, ErrorCode.INVALID_INPUT, "Audio must be mono 16 kHz PCM16 WAV.")
    if duration <= 0:
        raise ApiError(422, ErrorCode.INVALID_INPUT, "Audio is empty.")
    if duration > MAX_SECONDS:
        raise ApiError(422, ErrorCode.AUDIO_TOO_LONG, "Audio chunks must be 30 seconds or shorter.")


async def _transcribe_with_gnani(
    content: bytes,
    filename: str,
    language: str,
    previous_text: str | None,
    settings: Settings,
) -> TranscriptionResponse:
    if not settings.gnani_api_key:
        raise ApiError(
            503,
            ErrorCode.NO_API_KEY,
            "Speech transcription is not configured.",
            "Set GNANI_API_KEY and GNANI_MOCK=0 on the backend, or use manual text entry.",
        )

    form: dict[str, str] = {
        "language_code": language,
        "model": settings.gnani_stt_model,
        "format": "verbatim",
    }
    if previous_text:
        form["previous_text"] = previous_text[-600:]

    async with _gnani_lock:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=settings.gnani_stt_timeout) as client:
                    response = await client.post(
                        settings.gnani_stt_url,
                        headers={"X-API-Key-ID": settings.gnani_api_key},
                        data=form,
                        files={"audio_file": (filename, content, "audio/wav")},
                    )
            except httpx.TimeoutException as exc:
                raise ApiError(504, ErrorCode.UPSTREAM_BUSY, "Speech transcription timed out.", "Retry the chunk.") from exc
            except httpx.RequestError as exc:
                raise ApiError(503, ErrorCode.UPSTREAM_BUSY, "Speech transcription is temporarily unreachable.", "Retry the chunk.") from exc

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise ApiError(503, ErrorCode.UPSTREAM_BUSY, "Speech transcription is temporarily busy.", "Retry the chunk.")
            if response.status_code == 401:
                raise ApiError(503, ErrorCode.NO_API_KEY, "Speech transcription is not available for this account.", "Check the Gnani API key and account access.")
            if response.status_code == 402:
                raise ApiError(503, ErrorCode.UPSTREAM_ERROR, "Speech transcription credits are unavailable.", "Check the Gnani account balance.")
            if response.status_code == 403:
                raise ApiError(503, ErrorCode.UPSTREAM_ERROR, "The Gnani account is not permitted to use this transcription service.", "Check account scope and model access.")
            if response.status_code >= 400:
                raise ApiError(422, ErrorCode.INVALID_INPUT, "Speech transcription rejected this audio.", "Choose a supported audio file and retry.")

            try:
                payload = response.json()
                transcript = payload["transcript"]
                detected = payload.get("detected_language_code")
            except (ValueError, KeyError, TypeError) as exc:
                raise ApiError(502, ErrorCode.UPSTREAM_ERROR, "Speech service returned an invalid response.") from exc
            if not isinstance(transcript, str):
                raise ApiError(502, ErrorCode.UPSTREAM_ERROR, "Speech service returned an invalid transcript.")
            return TranscriptionResponse(transcript=transcript, detected_language_code=detected)

    raise ApiError(503, ErrorCode.UPSTREAM_BUSY, "Speech transcription is temporarily busy.")


@router.post("/narrations/transcribe", response_model=TranscriptionResponse)
async def transcribe_narration(
    audio: UploadFile = File(...),
    language: str = Form("indic-auto"),
    consent: bool = Form(False),
    previous_text: str | None = Form(None),
    settings: Settings = Depends(get_settings),
    _auth: AuthContext = Depends(get_auth_context),
    mock_transcript: str | None = Header(default=None, alias="X-Mock-Transcript"),
) -> TranscriptionResponse:
    if not consent:
        raise ApiError(403, ErrorCode.CONSENT_REQUIRED, "Speaker consent is required before transcription.")
    if audio.content_type not in ("audio/wav", "audio/x-wav", "application/octet-stream"):
        raise ApiError(422, ErrorCode.INVALID_INPUT, "Audio must be converted to WAV before transcription.")
    content = await audio.read(MAX_WAV_BYTES + 1)
    if len(content) > MAX_WAV_BYTES:
        raise ApiError(422, ErrorCode.AUDIO_TOO_LONG, "Audio chunks must be 30 seconds or shorter.")
    _validate_wav(content)

    if settings.gnani_mock:
        fixture_transcript = MOCK_TRANSCRIPT_PATH.read_text(encoding="utf-8").strip()
        transcript = mock_transcript if mock_transcript is not None else fixture_transcript if not previous_text else ""
        return TranscriptionResponse(transcript=transcript, detected_language_code=language, mock=True)
    return await _transcribe_with_gnani(content, audio.filename or "narration.wav", language, previous_text, settings)
