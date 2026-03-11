"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for Research Forge."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.2, alias="OPENAI_TEMPERATURE")

    arxiv_api_url: str = Field(default="https://export.arxiv.org/api/query", alias="ARXIV_API_URL")
    arxiv_timeout_seconds: int = Field(default=20, alias="ARXIV_TIMEOUT_SECONDS")
    arxiv_max_retries: int = Field(default=2, alias="ARXIV_MAX_RETRIES")
    arxiv_backoff_seconds: float = Field(default=2.0, alias="ARXIV_BACKOFF_SECONDS")
    arxiv_max_results_per_query: int = Field(default=16, alias="ARXIV_MAX_RESULTS_PER_QUERY")

    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(default=None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    experiment_timeout_seconds: int = Field(default=20, alias="EXPERIMENT_TIMEOUT_SECONDS")
    max_extraction_retries: int = Field(default=2, alias="MAX_EXTRACTION_RETRIES")

    artifacts_dir: Path = Field(default=Path("artifacts"), alias="ARTIFACTS_DIR")
    local_strategy_cache_path: Path = Field(
        default=Path("artifacts/local_strategy_cache.json"),
        alias="LOCAL_STRATEGY_CACHE_PATH",
    )

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_user and self.neo4j_password)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
