"""Authenticated WAV transcription contract tests; never call Gnani."""

from __future__ import annotations

import io
import wave

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.tests.fakes import FakeStore, FakeTokenVerifier, build_test_app, make_user


def _wav(seconds: float = 1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\0\0" * int(16000 * seconds))
    return output.getvalue()


def _aac(seconds: float = 1) -> bytes:
    # Synthetic ADTS frames (no audio content); each frame is 1024 samples at 44.1 kHz.
    count = int(seconds * 44100 / 1024)
    frame = bytes((0xFF, 0xF1, 0x50, 0x00, 0x01, 0x00, 0x00, 0x55))
    return frame * count


def _client(*, mock: bool = True, api_key: str = "") -> TestClient:
    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="test-publishable-key",
        supabase_anon_key="",
        gnani_mock=mock,
        gnani_api_key=api_key,
        llm_chain="rules",
        gemini_api_key="",
        gemini_model="",
    )
    verifier = FakeTokenVerifier({"token": make_user("test-user")})
    return TestClient(build_test_app(settings, verifier, FakeStore()))


def test_transcribe_requires_authentication() -> None:
    with _client() as client:
        response = client.post(
            "/api/narrations/transcribe",
            data={"consent": "true"},
            files={"audio": ("clip.wav", _wav(), "audio/wav")},
        )
    assert response.status_code == 401


def test_transcribe_requires_speaker_consent() -> None:
    with _client() as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token"},
            data={"consent": "false"},
            files={"audio": ("clip.wav", _wav(), "audio/wav")},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_mock_transcription_is_explicit_and_never_calls_provider() -> None:
    with _client() as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token", "X-Mock-Transcript": "mock transcript"},
            data={"consent": "true", "language": "indic-auto"},
            files={"audio": ("clip.wav", _wav(), "audio/wav")},
        )
    assert response.status_code == 200
    assert response.json() == {
        "transcript": "mock transcript",
        "detected_language_code": "indic-auto",
        "mock": True,
    }


def test_mock_mode_returns_labeled_fixture_when_header_is_absent() -> None:
    with _client() as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token"},
            data={"consent": "true"},
            files={"audio": ("clip.wav", _wav(), "audio/wav")},
        )
    assert response.status_code == 200
    assert response.json()["mock"] is True
    assert response.json()["transcript"].startswith("এক চামচ তেল")


def test_mock_mode_returns_no_duplicate_fixture_for_following_chunk() -> None:
    with _client() as client:
        headers = {"Authorization": "Bearer token"}
        first = client.post(
            "/api/narrations/transcribe",
            headers=headers,
            data={"consent": "true"},
            files={"audio": ("first.wav", _wav(), "audio/wav")},
        )
        second = client.post(
            "/api/narrations/transcribe",
            headers=headers,
            data={"consent": "true", "previous_text": first.json()["transcript"]},
            files={"audio": ("second.wav", _wav(), "audio/wav")},
        )
    assert first.json()["transcript"]
    assert second.status_code == 200
    assert second.json()["transcript"] == ""
    assert second.json()["mock"] is True


def test_live_mode_without_api_key_returns_configuration_error() -> None:
    with _client(mock=False) as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token"},
            data={"consent": "true"},
            files={"audio": ("clip.wav", _wav(), "audio/wav")},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NO_API_KEY"


def test_live_mode_uses_documented_gnani_request(monkeypatch) -> None:
    from backend.app.routers import narrations

    captured = {}

    class StubResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"transcript": "real response from provider", "detected_language_code": "bn-IN"}

    class StubAsyncClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, data, files):
            captured.update(url=url, headers=headers, data=data, files=files)
            return StubResponse()

    monkeypatch.setattr(narrations.httpx, "AsyncClient", StubAsyncClient)
    with _client(mock=False, api_key="test-api-key") as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token"},
            data={"consent": "true", "previous_text": "earlier words", "language": "indic-auto"},
            files={"audio": ("clip.wav", _wav(), "audio/wav")},
        )
    assert response.status_code == 200
    assert response.json() == {
        "transcript": "real response from provider",
        "detected_language_code": "bn-IN",
        "mock": False,
    }
    assert captured["url"] == "https://api.vachana.ai/stt/v3"
    assert captured["headers"] == {"X-API-Key-ID": "test-api-key"}
    assert captured["data"] == {
        "language_code": "indic-auto",
        "model": "prisma-v3.0",
        "format": "verbatim",
        "previous_text": "earlier words",
    }
    assert "audio_file" in captured["files"]


def test_transcribe_rejects_audio_longer_than_30_seconds() -> None:
    with _client() as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token"},
            data={"consent": "true"},
            files={"audio": ("clip.wav", _wav(31), "audio/wav")},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AUDIO_TOO_LONG"


def test_mock_transcription_accepts_adts_aac() -> None:
    with _client() as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token", "X-Mock-Transcript": "aac mock"},
            data={"consent": "true"},
            files={"audio": ("recording.aac", _aac(), "audio/aac")},
        )
    assert response.status_code == 200
    assert response.json()["transcript"] == "aac mock"


def test_transcribe_rejects_adts_aac_longer_than_30_seconds() -> None:
    with _client() as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token"},
            data={"consent": "true"},
            files={"audio": ("recording.aac", _aac(31), "audio/aac")},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AUDIO_TOO_LONG"


def test_live_gnani_request_preserves_aac_format(monkeypatch) -> None:
    from backend.app.routers import narrations

    captured = {}

    class StubResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"transcript": "aac transcript"}

    class StubAsyncClient:
        def __init__(self, *, timeout): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, *, headers, data, files):
            captured["files"] = files
            return StubResponse()

    monkeypatch.setattr(narrations.httpx, "AsyncClient", StubAsyncClient)
    with _client(mock=False, api_key="test-api-key") as client:
        response = client.post(
            "/api/narrations/transcribe",
            headers={"Authorization": "Bearer token"},
            data={"consent": "true"},
            files={"audio": ("recording.aac", _aac(), "audio/aac")},
        )
    assert response.status_code == 200
    assert captured["files"]["audio_file"][0] == "recording.aac"
    assert captured["files"]["audio_file"][2] == "audio/aac"
