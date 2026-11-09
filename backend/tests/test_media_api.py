"""Authenticated recipe media API: ownership, validation, URLs and consistency."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.db import DatabaseFailure
from backend.app.media import (
    ImageKitMediaStorage,
    MediaStorageFailure,
    MediaStorageUnavailable,
)
from backend.tests.fakes import (
    FakeMediaStorage,
    FakeStore,
    FakeTokenVerifier,
    build_test_app,
    make_user,
)
from backend.tests.media_samples import (
    AUDIO_CASES,
    IMAGE_CASES,
    JPEG,
    WEBM,
    payload,
)

MIB = 1024 * 1024


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "supabase_url": "https://project.supabase.co",
        "supabase_publishable_key": "test-publishable-key",
        "supabase_anon_key": "",
        "gnani_api_key": "",
        "gnani_mock": True,
        "llm_chain": "rules",
        "gemini_api_key": "",
        "gemini_model": "",
        "imagekit_private_key": "",
        "imagekit_url_endpoint": "",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier(
        {
            "token-a": make_user("user-a", name="Alice"),
            "token-b": make_user("user-b", name="Bob"),
        }
    )


@pytest.fixture
def storage() -> FakeMediaStorage:
    return FakeMediaStorage()


@pytest.fixture
def client(
    store: FakeStore, verifier: FakeTokenVerifier, storage: FakeMediaStorage
) -> Iterator[TestClient]:
    with TestClient(
        build_test_app(_settings(), verifier, store, media_storage=storage)
    ) as test_client:
        yield test_client


def _auth(token: str = "token-a") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_recipe(client: TestClient, token: str = "token-a", title: str = "Test recipe") -> str:
    response = client.post("/api/recipes", headers=_auth(token), json=payload(title=title))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload(
    client: TestClient,
    recipe_id: str,
    *,
    token: str = "token-a",
    media_type: str = "image",
    filename: str = "photo.jpg",
    content: bytes = JPEG,
    content_type: str = "image/jpeg",
):
    return client.post(
        f"/api/recipes/{recipe_id}/media",
        headers=_auth(token),
        data={"media_type": media_type},
        files={"file": (filename, content, content_type)},
    )


def _seed_media(store: FakeStore, recipe_id: str, *, path: str) -> str:
    media_id = str(uuid4())
    store.media[media_id] = {
        "id": media_id,
        "recipe_id": recipe_id,
        "recipe_version_id": None,
        "media_type": "image",
        "imagekit_file_id": "file-seeded",
        "imagekit_url": "https://ik.imagekit.io/test/x.jpg",
        "imagekit_file_path": path,
        "mime_type": "image/jpeg",
        "size_bytes": 10,
        "original_filename": "x.jpg",
        "created_at": store.now(),
    }
    return media_id


def test_upload_requires_authentication(client: TestClient) -> None:
    recipe_id = _create_recipe(client)
    response = client.post(
        f"/api/recipes/{recipe_id}/media",
        data={"media_type": "image"},
        files={"file": ("photo.jpg", JPEG, "image/jpeg")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_user_can_upload_a_private_image_to_their_recipe(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    response = _upload(client, recipe_id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id",
        "recipe_id",
        "recipe_version_id",
        "media_type",
        "mime_type",
        "size_bytes",
        "original_filename",
        "created_at",
    }
    assert body["recipe_id"] == recipe_id
    assert body["media_type"] == "image"
    assert body["mime_type"] == "image/jpeg"
    assert body["size_bytes"] == len(JPEG)
    assert body["original_filename"] == "photo.jpg"
    assert body["recipe_version_id"] == store.versions[recipe_id][0]["id"]
    assert "imagekit" not in response.text
    assert "private-test-key" not in response.text

    row = store.media[body["id"]]
    assert row["imagekit_file_id"] == "file_1"
    assert row["imagekit_file_path"].startswith(f"/users/user-a/recipes/{recipe_id}/images/")
    assert row["imagekit_url"].startswith("https://ik.imagekit.io/test/")
    assert storage.uploads[0]["folder"] == f"/users/user-a/recipes/{recipe_id}/images"
    assert storage.uploads[0]["content"] == JPEG


def test_user_cannot_upload_to_another_users_recipe(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client, "token-a")
    response = _upload(client, recipe_id, token="token-b")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert store.media == {}
    assert storage.uploads == []


@pytest.mark.parametrize("data,mime,filename", list(IMAGE_CASES.values()))
def test_valid_image_formats(client: TestClient, data: bytes, mime: str, filename: str) -> None:
    recipe_id = _create_recipe(client)
    response = _upload(client, recipe_id, filename=filename, content=data, content_type=mime)
    assert response.status_code == 201, response.text
    assert response.json()["mime_type"] == mime


@pytest.mark.parametrize("data,mime,filename", list(AUDIO_CASES.values()))
def test_valid_audio_formats(client: TestClient, data: bytes, mime: str, filename: str) -> None:
    recipe_id = _create_recipe(client)
    response = _upload(
        client,
        recipe_id,
        media_type="audio",
        filename=filename,
        content=data,
        content_type=mime,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["media_type"] == "audio"
    assert body["mime_type"] == mime


def test_unsupported_mime_type_is_415(client: TestClient) -> None:
    recipe_id = _create_recipe(client)
    response = _upload(
        client,
        recipe_id,
        filename="x.gif",
        content=b"GIF89a" + b"\x00" * 20,
        content_type="image/gif",
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_mime_and_content_mismatch_is_415(client: TestClient) -> None:
    recipe_id = _create_recipe(client)
    response = _upload(client, recipe_id, filename="x.png", content=JPEG, content_type="image/png")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_unknown_media_type_is_422(client: TestClient) -> None:
    recipe_id = _create_recipe(client)
    response = _upload(client, recipe_id, media_type="video")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_oversized_image_is_413(
    store: FakeStore, verifier: FakeTokenVerifier, storage: FakeMediaStorage
) -> None:
    app = build_test_app(
        _settings(imagekit_max_image_upload_mb=1), verifier, store, media_storage=storage
    )
    with TestClient(app) as client:
        recipe_id = _create_recipe(client)
        response = _upload(client, recipe_id, content=JPEG + b"\x00" * MIB)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert store.media == {}


def test_oversized_audio_is_413(
    store: FakeStore, verifier: FakeTokenVerifier, storage: FakeMediaStorage
) -> None:
    app = build_test_app(
        _settings(imagekit_max_audio_upload_mb=1), verifier, store, media_storage=storage
    )
    with TestClient(app) as client:
        recipe_id = _create_recipe(client)
        response = _upload(
            client,
            recipe_id,
            media_type="audio",
            filename="recording.webm",
            content=WEBM + b"\x00" * MIB,
            content_type="audio/webm",
        )
    assert response.status_code == 413
    assert store.media == {}


def test_original_filename_is_sanitised_and_storage_name_is_generated(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    response = _upload(client, recipe_id, filename="../../etc/My Photo!.JPEG")
    assert response.status_code == 201, response.text
    assert response.json()["original_filename"] == "My_Photo_.JPEG"

    upload = storage.uploads[0]
    assert upload["file_name"] != "My Photo!.JPEG"
    assert upload["file_name"].endswith(".jpg")
    assert len(upload["file_name"].split(".")[0]) == 32
    assert ".." not in upload["file_path"]


def test_upload_is_linked_to_the_current_version_uuid(client: TestClient, store: FakeStore) -> None:
    recipe_id = _create_recipe(client)
    updated = client.put(
        f"/api/recipes/{recipe_id}",
        headers=_auth(),
        json={"original_transcript": "version two", "draft": {"n": 2}},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    media_id = _upload(client, recipe_id).json()["id"]
    latest = max(store.versions[recipe_id], key=lambda version: version["version_number"])
    assert latest["version_number"] == 2
    assert store.media[media_id]["recipe_version_id"] == latest["id"]
    assert store.media[media_id]["recipe_version_id"] != "2"


def test_list_returns_signed_urls_with_the_configured_ttl(
    client: TestClient, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    _upload(client, recipe_id)
    _upload(
        client,
        recipe_id,
        media_type="audio",
        filename="recording.webm",
        content=WEBM,
        content_type="audio/webm",
    )

    response = client.get(f"/api/recipes/{recipe_id}/media", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    by_type = {item["media_type"]: item for item in body["items"]}
    assert set(by_type) == {"image", "audio"}
    for item in body["items"]:
        assert item["delivery_url"].startswith("https://ik.imagekit.io/test/users/user-a/")
        assert "ttl=900" in item["delivery_url"]
        assert item["url_expires_in"] == 900
    assert len(storage.signed) == 2
    assert all(ttl == 900 for _, ttl in storage.signed)


def test_user_cannot_list_another_users_media(client: TestClient) -> None:
    recipe_id = _create_recipe(client, "token-a")
    _upload(client, recipe_id)
    response = client.get(f"/api/recipes/{recipe_id}/media", headers=_auth("token-b"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_media_url_endpoint_returns_a_fresh_signed_url(client: TestClient) -> None:
    recipe_id = _create_recipe(client)
    media_id = _upload(client, recipe_id).json()["id"]

    response = client.get(f"/api/recipes/{recipe_id}/media/{media_id}/url", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == media_id
    assert body["url_expires_in"] == 900
    assert body["delivery_url"].startswith("https://ik.imagekit.io/test/")


def test_delete_removes_the_file_then_the_row(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    media_id = _upload(client, recipe_id).json()["id"]

    response = client.delete(f"/api/recipes/{recipe_id}/media/{media_id}", headers=_auth())
    assert response.status_code == 200
    assert response.json() == {"id": media_id, "deleted": True}
    assert storage.deleted == ["file_1"]
    assert media_id not in store.media


def test_user_cannot_delete_another_users_media(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    media_id = _upload(client, recipe_id).json()["id"]

    response = client.delete(f"/api/recipes/{recipe_id}/media/{media_id}", headers=_auth("token-b"))
    assert response.status_code == 404
    assert storage.deleted == []
    assert media_id in store.media


def test_media_cannot_be_reached_through_the_wrong_recipe(
    client: TestClient, store: FakeStore
) -> None:
    recipe_one = _create_recipe(client, title="One")
    media_id = _upload(client, recipe_one).json()["id"]
    recipe_two = _create_recipe(client, title="Two")

    assert (
        client.get(f"/api/recipes/{recipe_two}/media/{media_id}/url", headers=_auth()).status_code
        == 404
    )
    assert (
        client.delete(f"/api/recipes/{recipe_two}/media/{media_id}", headers=_auth()).status_code
        == 404
    )
    assert media_id in store.media


def test_imagekit_upload_failure_creates_no_record(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    storage.upload_error = MediaStorageUnavailable("Media storage is unavailable.")
    recipe_id = _create_recipe(client)
    response = _upload(client, recipe_id)
    assert response.status_code == 503
    assert store.media == {}


def test_database_insert_failure_triggers_imagekit_cleanup(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    store.media_insert_error = DatabaseFailure("insert failed")
    recipe_id = _create_recipe(client)
    response = _upload(client, recipe_id)
    assert response.status_code == 502
    assert store.media == {}
    assert storage.deleted == ["file_1"]


def test_imagekit_delete_failure_keeps_the_metadata_row(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    media_id = _upload(client, recipe_id).json()["id"]
    storage.delete_error = MediaStorageFailure("Media storage returned an error.")

    response = client.delete(f"/api/recipes/{recipe_id}/media/{media_id}", headers=_auth())
    assert response.status_code == 502
    assert media_id in store.media
    assert storage.deleted == []


def test_database_delete_failure_after_file_delete_is_recoverable(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    media_id = _upload(client, recipe_id).json()["id"]

    store.media_delete_error = DatabaseFailure("delete failed")
    response = client.delete(f"/api/recipes/{recipe_id}/media/{media_id}", headers=_auth())
    assert response.status_code == 502
    assert "retry" in response.json()["error"]["hint"].lower()
    assert storage.deleted == ["file_1"]
    assert media_id in store.media

    store.media_delete_error = None
    retry = client.delete(f"/api/recipes/{recipe_id}/media/{media_id}", headers=_auth())
    assert retry.status_code == 200
    assert media_id not in store.media
    assert storage.deleted == ["file_1", "file_1"]


def test_media_operations_require_imagekit_configuration(
    store: FakeStore, verifier: FakeTokenVerifier
) -> None:
    app = build_test_app(_settings(), verifier, store, media_storage=ImageKitMediaStorage())
    with TestClient(app) as client:
        recipe_id = _create_recipe(client)
        upload = _upload(client, recipe_id)
        listing = client.get(f"/api/recipes/{recipe_id}/media", headers=_auth())
        media_url = client.get(f"/api/recipes/{recipe_id}/media/{uuid4()}/url", headers=_auth())
        deletion = client.delete(f"/api/recipes/{recipe_id}/media/{uuid4()}", headers=_auth())
    assert upload.status_code == 503
    assert upload.json()["error"]["code"] == "UPSTREAM_BUSY"
    assert listing.status_code == 503
    assert media_url.status_code == 503
    assert deletion.status_code == 503


def test_unexpected_stored_path_is_not_signed(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    _seed_media(store, recipe_id, path="/users/someone-else/recipes/other/images/x.jpg")

    response = client.get(f"/api/recipes/{recipe_id}/media", headers=_auth())
    assert response.status_code == 200
    assert response.json()["items"][0]["delivery_url"] is None
    assert storage.signed == []


def test_delete_refuses_a_record_outside_the_expected_prefix(
    client: TestClient, store: FakeStore, storage: FakeMediaStorage
) -> None:
    recipe_id = _create_recipe(client)
    media_id = _seed_media(store, recipe_id, path="/users/someone-else/recipes/other/images/x.jpg")

    response = client.delete(f"/api/recipes/{recipe_id}/media/{media_id}", headers=_auth())
    assert response.status_code == 404
    assert storage.deleted == []
    assert media_id in store.media


def test_malformed_recipe_id_is_422(client: TestClient) -> None:
    response = client.post(
        "/api/recipes/not-a-uuid/media",
        headers=_auth(),
        data={"media_type": "image"},
        files={"file": ("photo.jpg", JPEG, "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_existing_missing_recipe_returns_404(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    response = _upload(client, missing)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
