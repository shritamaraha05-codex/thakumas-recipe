"""ImageKit storage adapter.

The SDK is imported lazily and only when an upload/delete/sign operation runs, so
the application starts without ImageKit credentials (or even the SDK). Files are
uploaded as **private** and are only ever handed to clients as short-lived
signed URLs. The private key never leaves this module and is never logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.app.config import Settings

from .errors import MediaStorageFailure, MediaStorageUnavailable


@dataclass(frozen=True, slots=True)
class UploadedAsset:
    """The identifiers ImageKit returns for a stored file."""

    file_id: str
    url: str
    file_path: str
    name: str | None = None
    size: int | None = None


class MediaStorage(Protocol):
    """The storage surface the orchestration layer depends on (easy to fake)."""

    @property
    def enabled(self) -> bool: ...

    async def upload_private(
        self, *, content: bytes, file_name: str, folder: str
    ) -> UploadedAsset: ...

    async def delete_file(self, file_id: str) -> None: ...

    async def build_signed_url(self, *, file_path: str, expires_in: int) -> str: ...

    async def aclose(self) -> None: ...


class ImageKitMediaStorage:
    """Server-side ImageKit uploads with private files and signed delivery."""

    def __init__(
        self,
        *,
        private_key: str = "",
        url_endpoint: str = "",
        signed_url_ttl_seconds: int = 900,
        client: Any | None = None,
    ) -> None:
        self._private_key = private_key
        self._url_endpoint = url_endpoint
        self._signed_url_ttl_seconds = max(1, signed_url_ttl_seconds)
        self._client = client
        self._owns_client = client is None

    @classmethod
    def from_settings(cls, settings: Settings) -> ImageKitMediaStorage:
        return cls(
            private_key=settings.imagekit_private_key,
            url_endpoint=settings.imagekit_url_endpoint,
            signed_url_ttl_seconds=settings.imagekit_signed_url_ttl_seconds,
        )

    @property
    def enabled(self) -> bool:
        return bool(self._private_key and self._url_endpoint)

    @property
    def signed_url_ttl_seconds(self) -> int:
        return self._signed_url_ttl_seconds

    def _build_client(self) -> Any:
        if not self.enabled:
            raise MediaStorageUnavailable("Media storage is not configured.")
        if self._client is None:
            try:
                from imagekitio import AsyncImageKit
            except ImportError as exc:  # pragma: no cover - depends on environment
                raise MediaStorageUnavailable(
                    "The ImageKit SDK is not installed; install requirements.txt."
                ) from exc
            self._client = AsyncImageKit(private_key=self._private_key)
        return self._client

    async def upload_private(self, *, content: bytes, file_name: str, folder: str) -> UploadedAsset:
        client = self._build_client()
        try:
            response = await client.files.upload(
                file=content,
                file_name=file_name,
                folder=folder,
                is_private_file=True,
                use_unique_file_name=True,
            )
        except Exception as exc:  # noqa: BLE001 - translated, never exposed
            raise _translate(exc) from exc
        return UploadedAsset(
            file_id=_required(response, "file_id"),
            url=_required(response, "url"),
            file_path=_required(response, "file_path"),
            name=getattr(response, "name", None),
            size=getattr(response, "size", None),
        )

    async def delete_file(self, file_id: str) -> None:
        client = self._build_client()
        try:
            await client.files.delete(file_id)
        except Exception as exc:  # noqa: BLE001 - translated, never exposed
            if getattr(exc, "status_code", None) == 404:
                return  # Already gone: retries stay idempotent.
            raise _translate(exc) from exc

    async def build_signed_url(self, *, file_path: str, expires_in: int) -> str:
        client = self._build_client()
        try:
            return await client.helper.build_url(
                url_endpoint=self._url_endpoint,
                src=file_path,
                signed=True,
                expires_in=expires_in,
            )
        except Exception as exc:  # noqa: BLE001 - translated, never exposed
            raise _translate(exc) from exc

    async def aclose(self) -> None:
        client = self._client
        if client is None or not self._owns_client:
            return
        closer = getattr(client, "aclose", None) or getattr(client, "close", None)
        if closer is not None:
            result = closer()
            if hasattr(result, "__await__"):
                await result
        self._client = None


def _required(response: Any, attribute: str) -> str:
    value = getattr(response, attribute, None)
    if not isinstance(value, str) or not value:
        raise MediaStorageFailure("Media storage returned an incomplete response.")
    return value


def _translate(exc: Exception) -> MediaStorageUnavailable | MediaStorageFailure:
    """Map an SDK/transport failure to a safe application error (no raw message)."""
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return MediaStorageUnavailable(
            "Media storage rejected its credentials. Check IMAGEKIT_PRIVATE_KEY."
        )
    if status == 429:
        return MediaStorageUnavailable("Media storage is rate limited; try again shortly.")
    if isinstance(status, int) and status >= 500:
        return MediaStorageUnavailable("Media storage is temporarily unavailable.")
    return MediaStorageFailure("Media storage returned an error.")
