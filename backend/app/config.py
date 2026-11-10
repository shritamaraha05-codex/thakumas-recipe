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
# The backend's own .env lives next to this package (``backend/.env``). It is
# resolved from this source file, not the current working directory, so the
# settings load identically whether Uvicorn is started from the repository root
# or anywhere else. Real environment variables still override file values.
BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKEND_ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_MOCK_FIXTURE = REPO_ROOT / "docs" / "fixtures" / "parse_result.sample.json"


class Settings(BaseSettings):
    """All runtime configuration, resolved from the environment."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Thakuma's Recipe"
    api_prefix: str = "/api"

    # Gnani speech services. An empty key (or GNANI_MOCK=1) keeps the app offline.
    gnani_api_key: str = ""
    gnani_mock: bool = True
    gnani_stt_model: str = "prisma-v3.0"
    gnani_stt_url: str = "https://api.vachana.ai/stt/v3"
    gnani_stt_timeout: float = 5.0
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

    # Supabase project. The publishable key is public (it identifies the project
    # to the Data API/Auth), never a password or a service-role secret. The
    # backend uses the user's access token for data access, so no database
    # password or service-role key is configured here.
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    # Legacy name retained only as a fallback for existing local .env files.
    supabase_anon_key: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_cache_seconds: int = 300
    supabase_request_timeout: float = 10.0

    # Browser origins allowed to call this API (comma-separated). The default
    # covers the Vite dev server under both host spellings; production origins
    # must be set through FRONTEND_ORIGINS.
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

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

    @property
    def supabase_key(self) -> str:
        """The publishable key, with the legacy anon-key name as a fallback."""
        return self.supabase_publishable_key or self.supabase_anon_key

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip().rstrip('/') for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings, cached so repeated reads are cheap."""
    return Settings()
