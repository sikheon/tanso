"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in the project root (one level up from backend/), then backend/
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV, _BACKEND_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Routing APIs
    kakao_rest_api_key: str = Field(default="", description="Kakao Mobility REST API key")
    ors_api_key: str = Field(default="", description="OpenRouteService API key")

    # LLM
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.5-flash")

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://elo:elo_password@localhost:5432/elo"
    )

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Feature flags
    enable_llm_narrative: bool = True
    enable_ors: bool = True
    llm_fallback_to_template: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
