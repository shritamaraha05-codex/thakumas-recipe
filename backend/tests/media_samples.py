"""Deterministic in-memory media samples for tests (no real files or network)."""

from __future__ import annotations

from typing import Any

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 16
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00" + b"\x00" * 8
)
WEBP = b"RIFF" + (64).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00" * 40
WAV = b"RIFF" + (64).to_bytes(4, "little") + b"WAVEfmt " + b"\x00" * 40
OGG = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 24
WEBM = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04" + b"\x00" * 16
MP4 = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00" + b"\x00" * 24
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 24


class UploadStub:
    """The slice of ``UploadFile`` used by the media service."""

    def __init__(
        self,
        data: bytes,
        *,
        filename: str | None = "sample.bin",
        content_type: str | None = None,
    ) -> None:
        self._data = data
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int) -> bytes:
        return self._data[:size]


IMAGE_CASES: dict[str, tuple[bytes, str, str]] = {
    "jpeg": (JPEG, "image/jpeg", "photo.jpg"),
    "png": (PNG, "image/png", "photo.png"),
    "webp": (WEBP, "image/webp", "photo.webp"),
}

AUDIO_CASES: dict[str, tuple[bytes, str, str]] = {
    "webm": (WEBM, "audio/webm", "recording.webm"),
    "ogg": (OGG, "audio/ogg", "recording.ogg"),
    "mp4": (MP4, "audio/mp4", "recording.m4a"),
    "mp3": (MP3, "audio/mpeg", "recording.mp3"),
    "wav": (WAV, "audio/wav", "recording.wav"),
}


def payload(**overrides: Any) -> dict[str, Any]:
    """A minimal valid recipe create payload for seeding owned recipes."""
    body: dict[str, Any] = {
        "title": "Test recipe",
        "original_transcript": "টেস্ট ট্রান্সক্রিপ্ট",
        "draft": {"recipe": {"title": "Test recipe", "steps": []}, "meta": {}},
        "tags": [],
    }
    body.update(overrides)
    return body
