"""Upload validation for recipe media.

Browser-supplied MIME types and extensions are not trusted. The declared
content type must be on the allow-list and the file's leading bytes must match
a recognised container signature for that type. Reads are bounded by the service
before this module sees the bytes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from .errors import MediaTooLarge, UnsupportedMediaType

MIB = 1024 * 1024

# Declared MIME type -> container family.
IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
}

AUDIO_TYPES: dict[str, str] = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
}

# Container family -> extension used for the server-generated filename.
EXTENSIONS: dict[str, str] = {
    "jpeg": ".jpg",
    "png": ".png",
    "webp": ".webp",
    "webm": ".webm",
    "ogg": ".ogg",
    "mp4": ".m4a",
    "mp3": ".mp3",
    "wav": ".wav",
}

MEDIA_TYPES = frozenset({"audio", "image"})

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


class ReadableUpload(Protocol):
    """The small part of ``UploadFile`` that validation needs."""

    filename: str | None
    content_type: str | None

    async def read(self, size: int) -> bytes: ...


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """A validated upload ready to be stored."""

    media_type: str
    mime_type: str
    family: str
    extension: str
    size_bytes: int


def sniff_family(data: bytes) -> str | None:
    """Return the container family inferred from leading bytes, if recognised."""
    if len(data) < 12:
        return None

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"RIFF"):
        if data[8:12] == b"WEBP":
            return "webp"
        if data[8:12] == b"WAVE":
            return "wav"
        return None
    if data.startswith(b"OggS"):
        return "ogg"
    if data.startswith(b"\x1a\x45\xdf\xa3"):  # EBML header (WebM/Matroska)
        return "webm"
    if data[4:8] == b"ftyp":  # ISO base media (MP4/M4A), after the box size
        return "mp4"
    if data.startswith(b"ID3") or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    return None


def normalise_content_type(content_type: str | None) -> str:
    """Strip parameters (e.g. ``; codecs=opus``) and normalise case."""
    return (content_type or "").split(";", 1)[0].strip().lower()


async def read_bounded(upload: ReadableUpload, max_bytes: int) -> bytes:
    """Read at most ``max_bytes``+1 so an oversized upload cannot exhaust memory."""
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise MediaTooLarge(f"The uploaded file exceeds the {max_bytes // MIB} MB limit.")
    return data


def validate_upload(
    *,
    media_type: str,
    content_type: str | None,
    content: bytes,
    max_image_bytes: int,
    max_audio_bytes: int,
) -> ValidatedUpload:
    """Validate the declared and detected type and the size of one upload."""
    if media_type == "image":
        allowed, max_bytes = IMAGE_TYPES, max_image_bytes
    elif media_type == "audio":
        allowed, max_bytes = AUDIO_TYPES, max_audio_bytes
    else:  # Refuse anything else instead of silently guessing a bucket.
        raise UnsupportedMediaType("media_type must be 'audio' or 'image'.")

    mime_type = normalise_content_type(content_type)
    if mime_type not in allowed:
        raise UnsupportedMediaType(
            f"{mime_type or 'Unknown'} is not a supported {media_type} type."
        )

    if not content:
        raise UnsupportedMediaType("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise MediaTooLarge(f"The uploaded file exceeds the {max_bytes // MIB} MB limit.")

    expected_family = allowed[mime_type]
    detected = sniff_family(content)
    if detected is None or detected != expected_family:
        raise UnsupportedMediaType("The file content does not match the declared content type.")

    return ValidatedUpload(
        media_type=media_type,
        mime_type=mime_type,
        family=expected_family,
        extension=EXTENSIONS[expected_family],
        size_bytes=len(content),
    )


def server_filename(family: str) -> str:
    """A server-generated, collision-resistant storage filename (never client input)."""
    return f"{uuid4().hex}{EXTENSIONS[family]}"


def sanitise_filename(filename: str | None) -> str | None:
    """Keep a harmless display copy of the original name (metadata only)."""
    if not filename:
        return None
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _SAFE_NAME.sub("_", base).strip("._-")
    return cleaned[:120] or None
