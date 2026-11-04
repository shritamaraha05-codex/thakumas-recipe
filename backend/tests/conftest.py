"""Shared test fixtures.

Every test builds an app with explicit, credential-free settings, so the suite
is deterministic and never reads a developer's real environment.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Credential-free settings; explicit init values override any local .env."""
    return Settings(
        api_prefix="/api",
        gnani_api_key="",
        gnani_mock=True,
        llm_chain="rules",
        gemini_api_key="",
        gemini_model="",
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client
