"""Sector relative strength.

Ranks a stock against its sector ETF and against SPY over a ~3-month window:
outperforming both = a leader in a strong group (the classic RS edge);
underperforming both = a laggard whose bounce is more suspect.

Benchmark histories come through MarketData (TTL-cached), so a full scan costs
at most ~12 extra fetches (11 SPDR sector ETFs + SPY), not one per ticker.
"""
from __future__ import annotations

from backend.indicators import technical as ta

# yfinance `info["sector"]` -> SPDR sector ETF
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

BENCH_LOOKBACK = 63  # ~3 trading months


def _bench_return(md, symbol: str) -> float | None:
    if md is None:
        return None
    hist = md.history(symbol, period="6mo")
    if hist is None or getattr(hist, "empty", True):
        return None
    return ta.pct_return(hist, BENCH_LOOKBACK)


def compute_rel_strength(snap, ind: dict, md) -> dict | None:
    """Relative 3-month performance vs SPY and the stock's sector ETF.

    Returns {"vs_spy", "vs_sector", "sector", "sector_etf"} (percentage-point
    spreads, positive = outperforming) or None when benchmarks are unavailable
    (offline runs degrade gracefully).
    """
    stock_ret = ind.get("ret_60d")
    if stock_ret is None:
        return None

    spy_ret = _bench_return(md, "SPY")
    sector = snap.info.get("sector")
    etf = SECTOR_ETFS.get(sector or "")
    sector_ret = _bench_return(md, etf) if etf else None

    if spy_ret is None and sector_ret is None:
        return None
    return {
        "vs_spy": round(stock_ret - spy_ret, 1) if spy_ret is not None else None,
        "vs_sector": round(stock_ret - sector_ret, 1) if sector_ret is not None else None,
        "sector": sector,
        "sector_etf": etf,
    }


def apply_rel_strength(momentum_sub, rs: dict | None) -> None:
    """Fold relative strength into the momentum sub-score (bounded, explainable)."""
    if not rs:
        return
    for key, label in (("vs_spy", "SPY"), ("vs_sector", rs.get("sector_etf") or "sector")):
        spread = rs.get(key)
        if spread is None:
            continue
        if spread > 5:
            momentum_sub.score = min(100.0, momentum_sub.score + 6)
            momentum_sub.factors.append(f"outperforming {label} by {spread:+.0f}pp (3mo)")
        elif spread < -15:
            momentum_sub.score = max(0.0, momentum_sub.score - 6)
            momentum_sub.factors.append(f"lagging {label} by {spread:+.0f}pp (3mo)")
