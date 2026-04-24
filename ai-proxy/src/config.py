"""Configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service
    ai_proxy_port: int = 8080

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    anthropic_model_haiku: str = "claude-haiku-4-5-20251001"

    # Database — the proxy writes ai_usage_logs directly.
    database_url: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "axon"
    postgres_user: str = "axon"
    postgres_password: str = "axon_dev_password"

    # Cost cap per audit (USD).
    ai_proxy_per_audit_cost_cap_usd: float = Field(default=0.50)

    # v1 default tenant (pre-auth).
    default_org_id: str = "00000000-0000-0000-0000-000000000001"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def stub_mode(self) -> bool:
        """True when we should NOT call Anthropic (no key, or key is a placeholder)."""
        key = (self.anthropic_api_key or "").strip()
        return not key or key.startswith("sk-ant-replace-me") or key == "stub"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
