"""Market-data provider.

Thin, cached wrapper around yfinance so the rest of the backend never talks
to the network directly. Everything returns plain dataclasses / DataFrames so
the scoring and scanning code stays testable (you can construct a
``StockSnapshot`` by hand in a unit test without any network).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover - yfinance optional at import time
    yf = None

from backend.config import settings
from backend.utils.cache import TTLCache

_cache = TTLCache(ttl_seconds=settings.cache_ttl_seconds)


@dataclass
class StockSnapshot:
    """Everything the engines need about a single ticker at a point in time."""

    ticker: str
    history: pd.DataFrame                  # OHLCV, daily
    info: dict[str, Any] = field(default_factory=dict)

    # ---- convenience accessors (None-safe) ----
    @property
    def last_close(self) -> float | None:
        closes = self.history["Close"].dropna() if not self.history.empty else pd.Series(dtype=float)
        return float(closes.iloc[-1]) if len(closes) else None

    @property
    def revenue(self) -> float:
        return float(self.info.get("totalRevenue") or 0)

    @property
    def financial_currency(self) -> str:
        return (self.info.get("financialCurrency") or "").upper()

    @property
    def free_cash_flow(self) -> float | None:
        fcf = self.info.get("freeCashflow")
        return float(fcf) if fcf is not None else None

    @property
    def institutional_ownership(self) -> float | None:
        held = self.info.get("heldPercentInstitutions")
        return float(held) if held is not None else None

    @property
    def recommendation_mean(self) -> float | None:
        rm = self.info.get("recommendationMean")
        return float(rm) if rm is not None else None

    @property
    def target_mean_price(self) -> float | None:
        t = self.info.get("targetMeanPrice")
        return float(t) if t is not None else None


class MarketData:
    """Fetches snapshots and options chains, with TTL caching."""

    def __init__(self, period: str = "260d") -> None:
        # 260d ≈ one trading year, enough for EMA200 / 252-day momentum.
        self.period = period

    def snapshot(self, ticker: str) -> StockSnapshot | None:
        if yf is None:
            raise RuntimeError("yfinance is not installed; cannot fetch live data")

        def _produce() -> StockSnapshot | None:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period=self.period, interval="1d")
                if hist is None or hist.empty:
                    return None
                info = t.info or {}
                return StockSnapshot(ticker=ticker, history=hist, info=info)
            except Exception:
                return None

        return _cache.get_or_set(f"snap:{ticker}:{self.period}", _produce)

    def options_chain(self, ticker: str) -> dict[str, Any] | None:
        if yf is None:
            return None

        def _produce() -> dict[str, Any] | None:
            try:
                t = yf.Ticker(ticker)
                expiries = t.options
                if not expiries:
                    return None
                near = t.option_chain(expiries[0])
                return {
                    "expiry": expiries[0],
                    "expiries": list(expiries),
                    "calls": near.calls,
                    "puts": near.puts,
                }
            except Exception:
                return None

        return _cache.get_or_set(f"opt:{ticker}", _produce)
