"""Worker configuration loaded from environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],  # project root first, worker-local overrides second
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service
    worker_port: int = 9090

    # Database
    database_url: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "axon"
    postgres_user: str = "axon"
    postgres_password: str = "axon_dev_password"

    # AI Proxy (all Claude calls go here — never direct to Anthropic)
    ai_proxy_url: str = "http://localhost:8080"
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    anthropic_model_haiku: str = "claude-haiku-4-5-20251001"

    # Amazon marketplace
    amazon_base_url: str = "https://www.amazon.com"

    # Playwright
    playwright_headless: bool = False
    playwright_navigation_timeout_ms: int = 30_000

    # Residential proxy (optional in dev; required in prod for real audits)
    proxy_provider: str = "oxylabs"
    proxy_endpoint: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None

    # Throttling — tuned for NO-PROXY mode (single residential IP).
    # Bump these down only if you add a residential proxy (set PROXY_* in .env).
    scrape_min_delay_ms: int = 6_000
    scrape_max_delay_ms: int = 14_000
    scrape_max_concurrency_per_audit: int = 2
    # Extra seconds to wait after a CAPTCHA/block before retrying (exponential).
    scrape_captcha_cooldown_s: int = 60

    # Safety caps — hard ceilings to protect proxy budget
    audit_soft_asin_warning: int = 500
    audit_hard_asin_ceiling: int = 2_000
    audit_soft_review_warning: int = 20_000
    audit_hard_review_ceiling: int = 50_000

    # Testing cap — set AUDIT_TEST_ASIN_LIMIT=30 in .env to process only the first N ASINs.
    # Leave unset (None) to process all discovered ASINs. Change to None for full production runs.
    audit_test_asin_limit: int | None = None

    # GCS
    gcs_reports_bucket: str = "axon-reports"

    # User-Agent pool for rotation
    user_agents: list[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        ]
    )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def has_proxy(self) -> bool:
        return bool(self.proxy_endpoint and self.proxy_username and self.proxy_password)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
