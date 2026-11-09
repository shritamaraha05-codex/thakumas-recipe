"""ImageKit configuration: optional startup, env resolution, safe defaults."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def _settings(**overrides) -> Settings:
    base = {
        "supabase_url": "",
        "supabase_publishable_key": "",
        "supabase_anon_key": "",
        "imagekit_private_key": "",
        "imagekit_url_endpoint": "",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_app_starts_without_imagekit_credentials() -> None:
    app = create_app(_settings())
    assert app.state.media_storage.enabled is False
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_imagekit_settings_come_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("IMAGEKIT_PRIVATE_KEY", "env-private-key")
    monkeypatch.setenv("IMAGEKIT_URL_ENDPOINT", "https://ik.imagekit.io/env")
    monkeypatch.setenv("IMAGEKIT_SIGNED_URL_TTL_SECONDS", "60")
    monkeypatch.setenv("IMAGEKIT_MAX_AUDIO_UPLOAD_MB", "40")

    settings = Settings(_env_file=None)

    assert settings.imagekit_configured is True
    assert settings.imagekit_private_key == "env-private-key"
    assert settings.imagekit_signed_url_ttl_seconds == 60
    assert settings.imagekit_max_audio_upload_mb == 40


def test_imagekit_defaults_are_safe_when_absent(monkeypatch) -> None:
    for name in (
        "IMAGEKIT_PRIVATE_KEY",
        "IMAGEKIT_URL_ENDPOINT",
        "IMAGEKIT_SIGNED_URL_TTL_SECONDS",
        "IMAGEKIT_MAX_IMAGE_UPLOAD_MB",
        "IMAGEKIT_MAX_AUDIO_UPLOAD_MB",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.imagekit_configured is False
    assert settings.imagekit_signed_url_ttl_seconds == 900
    assert settings.imagekit_max_image_upload_mb == 8
    assert settings.imagekit_max_audio_upload_mb == 25
