"""Environment-based application configuration.

Secrets are read from environment variables (or a local ``.env`` file that must
never be committed) and are never hard-coded. Every external integration is
optional: with no keys, ``GNANI_MOCK=1`` and ``LLM_CHAIN=rules`` the application
still starts and serves fixture data, as required by the project golden rules.

The settings object is deliberately small. New providers or storage fields are
added only when the task that needs them is implemented.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MOCK_FIXTURE = REPO_ROOT / "docs" / "fixtures" / "parse_result.sample.json"


class Settings(BaseSettings):
    """All runtime configuration, resolved from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Thakuma's Recipe"
    api_prefix: str = "/api"

    # Gnani speech services. An empty key (or GNANI_MOCK=1) keeps the app offline.
    gnani_api_key: str = ""
    gnani_mock: bool = True
    gnani_stt_model: str = "prisma-v3.0"
    gnani_tts_model: str = "timbre-v3.0"
    gnani_voice: str = "Shivani"

    # LLM provider chain. "rules" is the deterministic floor and must remain last.
    # Auto mode walks this chain; an explicit mode="llm" uses Gemini (M-10).
    llm_chain: str = "rules"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = ""
    llm_replay_only: bool = False

    # Deprecated placeholder. SQLite is no longer the store: persistence moves
    # to Supabase PostgreSQL under M-18A (docs/02, docs/03). No database is
    # opened by the app yet; this field stays only so the current health
    # response is unchanged until M-18A replaces it.
    db_path: str = "thakuma.db"

    # Deterministic fixture served by POST /api/parse until the parser exists.
    mock_fixture_path: Path = DEFAULT_MOCK_FIXTURE

    @property
    def llm_chain_list(self) -> list[str]:
        """The configured chain as an ordered, de-duplicated list."""
        seen: dict[str, None] = {}
        for part in self.llm_chain.split(","):
            name = part.strip()
            if name:
                seen.setdefault(name, None)
        return list(seen)


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings, cached so repeated reads are cheap."""
    return Settings()
