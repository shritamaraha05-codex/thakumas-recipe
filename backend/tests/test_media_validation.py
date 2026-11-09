"""Upload validation: MIME allow-lists, signature checks, size bounds, names."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.media.validation import (
    AUDIO_TYPES,
    IMAGE_TYPES,
    MediaTooLarge,
    UnsupportedMediaType,
    read_bounded,
    sanitise_filename,
    server_filename,
    sniff_family,
    validate_upload,
)
from backend.tests.media_samples import (
    AUDIO_CASES,
    IMAGE_CASES,
    JPEG,
    PNG,
    WEBM,
    UploadStub,
)

MIB = 1024 * 1024


@pytest.mark.parametrize(
    "data,family",
    [
        (JPEG, "jpeg"),
        (PNG, "png"),
        (IMAGE_CASES["webp"][0], "webp"),
        (AUDIO_CASES["ogg"][0], "ogg"),
        (WEBM, "webm"),
        (AUDIO_CASES["mp4"][0], "mp4"),
        (AUDIO_CASES["mp3"][0], "mp3"),
        (AUDIO_CASES["wav"][0], "wav"),
    ],
)
def test_sniff_family_recognises_supported_containers(data: bytes, family: str) -> None:
    assert sniff_family(data) == family


def test_sniff_family_returns_none_for_unknown_bytes() -> None:
    assert sniff_family(b"not a media file at all") is None
    assert sniff_family(b"short") is None


@pytest.mark.parametrize("case", list(IMAGE_CASES.values()))
def test_valid_images_pass(case) -> None:
    data, mime, _ = case
    result = validate_upload(
        media_type="image",
        content_type=mime,
        content=data,
        max_image_bytes=8 * MIB,
        max_audio_bytes=25 * MIB,
    )
    assert result.mime_type == mime
    assert result.size_bytes == len(data)


@pytest.mark.parametrize("case", list(AUDIO_CASES.values()))
def test_valid_audio_passes_including_codec_parameters(case) -> None:
    data, mime, _ = case
    result = validate_upload(
        media_type="audio",
        content_type=f"{mime}; codecs=opus",
        content=data,
        max_image_bytes=8 * MIB,
        max_audio_bytes=25 * MIB,
    )
    assert result.mime_type == mime


def test_declared_type_must_be_on_the_media_type_allow_list() -> None:
    with pytest.raises(UnsupportedMediaType):
        validate_upload(
            media_type="image",
            content_type="image/gif",
            content=JPEG,
            max_image_bytes=8 * MIB,
            max_audio_bytes=25 * MIB,
        )
    with pytest.raises(UnsupportedMediaType):
        validate_upload(
            media_type="audio",
            content_type="audio/flac",
            content=AUDIO_CASES["ogg"][0],
            max_image_bytes=8 * MIB,
            max_audio_bytes=25 * MIB,
        )


def test_content_must_match_the_declared_type() -> None:
    with pytest.raises(UnsupportedMediaType):
        validate_upload(
            media_type="image",
            content_type="image/png",
            content=JPEG,
            max_image_bytes=8 * MIB,
            max_audio_bytes=25 * MIB,
        )
    with pytest.raises(UnsupportedMediaType):
        validate_upload(
            media_type="audio",
            content_type="audio/webm",
            content=AUDIO_CASES["wav"][0],
            max_image_bytes=8 * MIB,
            max_audio_bytes=25 * MIB,
        )


def test_empty_and_unknown_media_type_are_rejected() -> None:
    with pytest.raises(UnsupportedMediaType):
        validate_upload(
            media_type="image",
            content_type="image/jpeg",
            content=b"",
            max_image_bytes=8 * MIB,
            max_audio_bytes=25 * MIB,
        )
    with pytest.raises(UnsupportedMediaType):
        validate_upload(
            media_type="video",
            content_type="image/jpeg",
            content=JPEG,
            max_image_bytes=8 * MIB,
            max_audio_bytes=25 * MIB,
        )


def test_oversized_uploads_are_rejected_per_media_type() -> None:
    with pytest.raises(MediaTooLarge):
        validate_upload(
            media_type="image",
            content_type="image/jpeg",
            content=JPEG + b"\x00" * (2 * MIB),
            max_image_bytes=1 * MIB,
            max_audio_bytes=25 * MIB,
        )
    with pytest.raises(MediaTooLarge):
        validate_upload(
            media_type="audio",
            content_type="audio/webm",
            content=WEBM + b"\x00" * (2 * MIB),
            max_image_bytes=8 * MIB,
            max_audio_bytes=1 * MIB,
        )


def test_read_bounded_stops_after_the_limit() -> None:
    assert asyncio.run(read_bounded(UploadStub(b"small"), 10)) == b"small"

    oversized = UploadStub(JPEG + b"\x00" * 64)
    with pytest.raises(MediaTooLarge):
        asyncio.run(read_bounded(oversized, 10))


def test_filenames_are_sanitised_and_paths_cannot_traverse() -> None:
    assert sanitise_filename("../../etc/pass wd!.JPEG") == "pass_wd_.JPEG"
    assert sanitise_filename("C:\\Users\\me\\rec.webm") == "rec.webm"
    assert sanitise_filename("..") is None
    assert sanitise_filename(None) is None


def test_server_filenames_are_generated_and_use_the_family_extension() -> None:
    first = server_filename("jpeg")
    second = server_filename("jpeg")
    assert first.endswith(".jpg") and second.endswith(".jpg")
    assert first != second
    assert first != "photo.jpg"


def test_allow_lists_cover_the_documented_types() -> None:
    assert set(IMAGE_TYPES) == {"image/jpeg", "image/png", "image/webp"}
    assert {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"} <= set(AUDIO_TYPES)
