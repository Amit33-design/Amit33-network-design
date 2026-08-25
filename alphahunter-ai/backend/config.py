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

    # Risk / catalyst awareness
    earnings_window_days: int = 7          # flag earnings within this many days
    high_short_interest: float = 0.10      # >10% of float = crowded short
    near_52w_low_pct: float = 8.0          # within 8% of the 52-week low

    # CSP-on-dip signal (sell a cash-secured put into weakness on strong names)
    csp_dip_day_pct: float = -2.0          # today's drop must be at least this
    csp_min_hist_win: float = 0.55         # historical bounce rate for "strong"
    csp_min_upside: float = 10.0           # analyst upside counts as potential

    # Position sizing & risk/reward gates
    account_size: float = 25_000           # notional account for sizing math
    max_risk_pct: float = 1.0              # risk per trade, % of account
    min_risk_reward: float = 1.5           # R:R floor; below it gets flagged

    # Tradability floors — keep penny stocks, warrants/units and illiquid
    # names out of every screen (a $0.05 warrant once scored 61 and lost 43%).
    min_price: float = 5.0                 # minimum share price
    min_dollar_volume: float = 5_000_000   # minimum avg daily $ volume (20d)
    exclude_derivative_tickers: bool = True  # warrants / units / rights

    # Alert digest — gates calibrated from realized ALPHA vs SPY, not raw
    # return. Measured 2026-08-25 over 414 aged picks:
    #   score 60+: alpha -2.8%   70+: alpha -1.7%   80+: alpha +19.0%
    #   grade A: +0.5%   B: -6.9%   C: -2.4%   D: -3.6%
    # Alpha rises monotonically with the score band and ONLY the 80+ cohort
    # actually beats the market, so a 70 gate was still pushing names that
    # lag SPY. Raised to 80: far fewer alerts, but only for the one cohort
    # with demonstrated edge. (Caveat: 80+ is 12 picks — thin. Revisit as the
    # sample grows; `grade_x_score` in performance.json tracks this cohort.)
    alert_min_score: float = 80.0

    # Opportunity scan — a broader "best pullback/dip" screen so the
    # Opportunities board is populated even in calm markets (the strict crash
    # screen finds nothing when nothing is down 5% day + 20% month).
    opp_month_drop: float = -8.0           # month return at/below this = pullback
    opp_week_drop: float = -6.0            # OR week return at/below this
    opp_rsi_max: float = 42.0              # OR RSI below this = oversold-ish
    opp_max_scored: int = 40               # cap fully-scored candidates (cost)
    opp_min_results: int = 15              # run the opp scan if strict yields < this

    # Composite AI score weights. Originally 35/25/20/10/10 by spec; retuned
    # from realized forward returns (1,489 samples reconstructed from the
    # committed scan history — see backend/analyze_signals.py):
    #   sentiment r=+0.216  technical r=+0.103  fundamental r=+0.064
    #   options   r=+0.057  momentum  r=-0.044
    # Sentiment was the strongest predictor at only 10% weight, while options
    # (20%) was near-useless and momentum was slightly NEGATIVE. Reweighting
    # lifts the composite's correlation with forward return from +0.101 to
    # +0.130 on a HELD-OUT later half, so it is not purely in-sample fitting.
    # Deliberately moderate: ~2 months in one market regime is thin evidence.
    weight_technical: float = 0.35
    weight_fundamental: float = 0.25
    weight_options: float = 0.10
    weight_momentum: float = 0.05
    weight_sentiment: float = 0.25

    # Data / caching
    cache_ttl_seconds: int = 900
    max_universe: int = 0          # 0 = uncapped
    request_sleep: float = 0.3
    fetch_retries: int = 3         # attempts per fetch (exceptions only)
    fetch_backoff_seconds: float = 1.5  # base backoff; doubles per attempt

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
