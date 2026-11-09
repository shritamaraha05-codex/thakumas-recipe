"""ImageKit adapter behaviour against a fake SDK client (no network)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.app.config import Settings
from backend.app.media.errors import MediaStorageFailure, MediaStorageUnavailable
from backend.app.media.imagekit_service import ImageKitMediaStorage


class _SdkError(Exception):
    """Mimics the SDK's APIError carrying an HTTP status code."""

    def __init__(self, status_code: int) -> None:
        super().__init__("sdk failure")
        self.status_code = status_code


class _FakeResponse:
    def __init__(self, *, file_id: str, url: str, file_path: str, name: str, size: int) -> None:
        self.file_id = file_id
        self.url = url
        self.file_path = file_path
        self.name = name
        self.size = size


class _FakeFiles:
    def __init__(self, owner: _FakeSdkClient) -> None:
        self._owner = owner

    async def upload(self, **kwargs: Any) -> _FakeResponse:
        self._owner.upload_kwargs = kwargs
        if self._owner.upload_error is not None:
            raise self._owner.upload_error
        path = f"{kwargs['folder']}/{kwargs['file_name']}"
        return _FakeResponse(
            file_id="file-123",
            url=f"https://ik.imagekit.io/test{path}",
            file_path=path,
            name=kwargs["file_name"],
            size=len(kwargs["file"]),
        )

    async def delete(self, file_id: str) -> None:
        self._owner.deleted.append(file_id)
        if self._owner.delete_error is not None:
            raise self._owner.delete_error


class _FakeHelper:
    def __init__(self, owner: _FakeSdkClient) -> None:
        self._owner = owner

    async def build_url(self, **kwargs: Any) -> str:
        self._owner.build_url_kwargs = kwargs
        return f"https://signed.example{kwargs['src']}?ik-s=signature"


class _FakeSdkClient:
    def __init__(self) -> None:
        self.files = _FakeFiles(self)
        self.helper = _FakeHelper(self)
        self.upload_kwargs: dict[str, Any] | None = None
        self.build_url_kwargs: dict[str, Any] | None = None
        self.deleted: list[str] = []
        self.upload_error: Exception | None = None
        self.delete_error: Exception | None = None


def _storage(client: _FakeSdkClient) -> ImageKitMediaStorage:
    return ImageKitMediaStorage(
        private_key="private-test-key",
        url_endpoint="https://ik.imagekit.io/test",
        signed_url_ttl_seconds=900,
        client=client,
    )


def test_upload_is_private_and_uses_the_server_folder() -> None:
    client = _FakeSdkClient()
    storage = _storage(client)

    asset = asyncio.run(
        storage.upload_private(
            content=b"binary-data",
            file_name="abc123.jpg",
            folder="/users/user-a/recipes/recipe-1/images",
        )
    )

    assert client.upload_kwargs is not None
    assert client.upload_kwargs["file"] == b"binary-data"
    assert client.upload_kwargs["file_name"] == "abc123.jpg"
    assert client.upload_kwargs["folder"] == "/users/user-a/recipes/recipe-1/images"
    assert client.upload_kwargs["is_private_file"] is True
    assert client.upload_kwargs["use_unique_file_name"] is True
    assert asset.file_id == "file-123"
    assert asset.file_path == "/users/user-a/recipes/recipe-1/images/abc123.jpg"
    assert asset.url.startswith("https://ik.imagekit.io/test/users/user-a")


def test_delete_uses_the_stored_file_id() -> None:
    client = _FakeSdkClient()
    storage = _storage(client)
    asyncio.run(storage.delete_file("file-abc"))
    assert client.deleted == ["file-abc"]


def test_delete_of_a_missing_file_is_idempotent() -> None:
    client = _FakeSdkClient()
    client.delete_error = _SdkError(404)
    asyncio.run(_storage(client).delete_file("already-gone"))


def test_signed_url_uses_the_configured_ttl() -> None:
    client = _FakeSdkClient()
    storage = _storage(client)
    url = asyncio.run(
        storage.build_signed_url(file_path="/users/u/recipes/r/images/x.jpg", expires_in=900)
    )
    assert url.startswith("https://signed.example/users/u/recipes/r/images/x.jpg")
    assert client.build_url_kwargs is not None
    assert client.build_url_kwargs["url_endpoint"] == "https://ik.imagekit.io/test"
    assert client.build_url_kwargs["src"] == "/users/u/recipes/r/images/x.jpg"
    assert client.build_url_kwargs["signed"] is True
    assert client.build_url_kwargs["expires_in"] == 900


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_credentials_map_to_unavailable(status: int) -> None:
    client = _FakeSdkClient()
    client.upload_error = _SdkError(status)
    with pytest.raises(MediaStorageUnavailable):
        asyncio.run(_storage(client).upload_private(content=b"x", file_name="x.jpg", folder="/f"))


def test_server_errors_map_to_unavailable_and_client_errors_to_failure() -> None:
    server = _FakeSdkClient()
    server.upload_error = _SdkError(500)
    with pytest.raises(MediaStorageUnavailable):
        asyncio.run(_storage(server).upload_private(content=b"x", file_name="x.jpg", folder="/f"))

    client = _FakeSdkClient()
    client.upload_error = _SdkError(400)
    with pytest.raises(MediaStorageFailure):
        asyncio.run(_storage(client).upload_private(content=b"x", file_name="x.jpg", folder="/f"))


def test_delete_server_error_is_reported_not_swallowed() -> None:
    client = _FakeSdkClient()
    client.delete_error = _SdkError(500)
    with pytest.raises(MediaStorageUnavailable):
        asyncio.run(_storage(client).delete_file("file-1"))


def test_storage_is_disabled_without_credentials_and_never_calls_the_sdk() -> None:
    storage = ImageKitMediaStorage()
    assert storage.enabled is False
    with pytest.raises(MediaStorageUnavailable):
        asyncio.run(storage.upload_private(content=b"x", file_name="x.jpg", folder="/f"))


def test_from_settings_reads_all_media_settings() -> None:
    settings = Settings(
        imagekit_private_key="key",
        imagekit_url_endpoint="https://ik.imagekit.io/test",
        imagekit_signed_url_ttl_seconds=123,
    )
    storage = ImageKitMediaStorage.from_settings(settings)
    assert storage.enabled is True
    assert storage.signed_url_ttl_seconds == 123
