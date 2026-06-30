"""Shared test fixtures.

Builds synthetic OHLCV + info so the whole engine stack can be tested offline
with zero network calls.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.utils.market_data import StockSnapshot


def _make_history(prices: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    n = len(prices)
    idx = pd.date_range(end="2026-06-25", periods=n, freq="D")
    close = pd.Series(prices, index=idx)
    if volumes is None:
        volumes = [1_000_000.0] * (n - 1) + [3_000_000.0]
    return pd.DataFrame({
        "Open": close.values,
        "High": close.values * 1.01,
        "Low": close.values * 0.99,
        "Close": close.values,
        "Volume": volumes,
    }, index=idx)


@pytest.fixture
def crash_snapshot() -> StockSnapshot:
    """A name that fits the AlphaHunter crash setup: up trend, then a sharp drop."""
    # 230 days uptrending from 80 -> 130, then a 1-month slide to ~95 with a -6% last day.
    base = list(np.linspace(80, 130, 230))
    slide = list(np.linspace(129, 101, 21))
    last_day = [95.0]   # ~-6% vs prior close (101)
    prices = base + slide + last_day
    hist = _make_history(prices)
    info = {
        "totalRevenue": 5_000_000_000,
        "financialCurrency": "USD",
        "freeCashflow": 800_000_000,
        "heldPercentInstitutions": 0.72,
        "recommendationMean": 1.8,
        "targetMeanPrice": 150.0,
        "currentRatio": 1.6,
        "debtToEquity": 90.0,
        "ebitda": 1_200_000_000,
        "profitMargins": 0.18,
        "returnOnEquity": 0.22,
        "revenueGrowth": 0.14,
        "shortName": "CrashCo",
    }
    return StockSnapshot(ticker="CRSH", history=hist, info=info)


@pytest.fixture
def healthy_snapshot() -> StockSnapshot:
    """A calm uptrend that should NOT trigger the crash scanner."""
    prices = list(np.linspace(50, 90, 260))
    hist = _make_history(prices, volumes=[1_000_000.0] * 260)
    info = {
        "totalRevenue": 9_000_000_000,
        "financialCurrency": "USD",
        "freeCashflow": 1_000_000_000,
        "heldPercentInstitutions": 0.65,
        "recommendationMean": 2.0,
        "targetMeanPrice": 100.0,
        "currentRatio": 2.0,
        "ebitda": 2_000_000_000,
        "shortName": "SteadyCo",
    }
    return StockSnapshot(ticker="STDY", history=hist, info=info)
