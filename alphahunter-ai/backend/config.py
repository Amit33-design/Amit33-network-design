"""Central configuration for AlphaHunter AI.

All tunables come from environment variables (loaded from a .env file in
development) — there are no hardcoded secrets. Import the singleton
``settings`` anywhere in the backend.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    alphahunter_env: str = "development"
    log_level: str = "INFO"

    # Screener thresholds (defaults mirror AlphaHunter_AI_CODE_SPEC "Existing Screener")
    revenue_floor: float = 1_000_000_000
    day_drop_pct: float = -5.0
    month_drop_pct: float = -20.0
    rsi_max: float = 35.0
    volume_spike_ratio: float = 1.5
    institutional_ownership_min: float = 0.50

    # Composite AI score weights (spec: 35/25/20/10/10)
    weight_technical: float = 0.35
    weight_fundamental: float = 0.25
    weight_options: float = 0.20
    weight_momentum: float = 0.10
    weight_sentiment: float = 0.10

    # Data / caching
    cache_ttl_seconds: int = 900
    max_universe: int = 0          # 0 = uncapped
    request_sleep: float = 0.3

    # Infrastructure (optional)
    database_url: str | None = None
    redis_url: str | None = None

    # Optional LLM
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Alerts (optional)
    slack_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    alert_email_to: str | None = None

    @property
    def score_weights(self) -> dict[str, float]:
        return {
            "technical": self.weight_technical,
            "fundamental": self.weight_fundamental,
            "options": self.weight_options,
            "momentum": self.weight_momentum,
            "sentiment": self.weight_sentiment,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
