"""Market-data provider.

Thin, cached wrapper around yfinance so the rest of the backend never talks
to the network directly. Everything returns plain dataclasses / DataFrames so
the scoring and scanning code stays testable (you can construct a
``StockSnapshot`` by hand in a unit test without any network).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover - yfinance optional at import time
    yf = None

from backend.config import settings
from backend.utils.cache import TTLCache

_cache = TTLCache(ttl_seconds=settings.cache_ttl_seconds)

T = TypeVar("T")


def with_retries(
    fn: Callable[[], T | None],
    attempts: int | None = None,
    backoff: float | None = None,
) -> T | None:
    """Run ``fn`` with bounded exponential backoff on EXCEPTIONS only.

    Yahoo rate-limits (429s) surface as raised errors and deserve a retry;
    a clean None/empty result means "no such data" (delisted ticker) and
    retrying would just triple the scan time — so it's returned as-is.
    """
    attempts = attempts if attempts is not None else settings.fetch_retries
    backoff = backoff if backoff is not None else settings.fetch_backoff_seconds
    for i in range(max(1, attempts)):
        try:
            return fn()
        except Exception:
            if i >= attempts - 1:
                return None
            time.sleep(backoff * (2 ** i))
    return None


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

        def _fetch() -> StockSnapshot | None:
            t = yf.Ticker(ticker)
            hist = t.history(period=self.period, interval="1d")
            if hist is None or hist.empty:
                return None                      # no data ≠ transient failure
            info = t.info or {}
            return StockSnapshot(ticker=ticker, history=hist, info=info)

        return _cache.get_or_set(
            f"snap:{ticker}:{self.period}", lambda: with_retries(_fetch)
        )

    def history(self, ticker: str, period: str = "3y") -> pd.DataFrame | None:
        """Longer daily history for backtesting a ticker's own setup (cached)."""
        if yf is None:
            return None

        def _fetch():
            h = yf.Ticker(ticker).history(period=period, interval="1d")
            return h if (h is not None and not h.empty) else None

        return _cache.get_or_set(
            f"hist:{ticker}:{period}", lambda: with_retries(_fetch)
        )

    def options_chain(self, ticker: str) -> dict[str, Any] | None:
        if yf is None:
            return None

        def _fetch() -> dict[str, Any] | None:
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

        return _cache.get_or_set(f"opt:{ticker}", lambda: with_retries(_fetch))
