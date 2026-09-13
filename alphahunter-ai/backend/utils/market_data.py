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


# Yahoo's insider_purchases table mixes per-action rows with AGGREGATE rows:
# "Purchases", "Sales", "Net Shares Purchased (Sold)", "Total Insider Shares
# Held", "% Net Shares Purchased (Sold)". A substring match on "purchase"/"buy"
# hits four of those, so the first version summed the net and percentage rows
# into the buy total — which is how NVDA came back as 117 million insider
# shares bought and MU as NEGATIVE 335,845 bought. Only the two plain action
# rows count.
_INSIDER_BUY_ROWS = {"purchases", "purchase"}
_INSIDER_SELL_ROWS = {"sales", "sale"}


# Words that mark a row as something other than a decision to buy or sell at
# market. Option exercises, vesting, grants and gifts move shares without
# expressing any view, and lumping them in is why NVIDIA still showed 61
# million shares "bought" after the aggregate rows were excluded.
_NON_MARKET = (
    "conversion", "exercise", "exercisable", "award", "grant", "vest",
    "gift", "inherit", "tax", "withhold", "option", "deferred", "plan",
)
_BUY_WORDS = ("purchase", "buy", "bought", "acquisition")
_SELL_WORDS = ("sale", "sell", "sold", "disposition")


def parse_insider_transactions(rows: list[dict]) -> dict | None:
    """Open-market insider buying and selling, from the per-transaction table.

    Yahoo's `insider_purchases` summary counts option exercises and share
    grants as "Purchases", which carry no information about what an insider
    thinks — they are compensation mechanics. This reads the itemised
    transaction list instead and keeps only rows whose description is an
    actual market purchase or sale.
    """
    bought = sold = 0.0
    buys = sells = 0
    for r in rows or []:
        text = " ".join(
            str(r.get(k, "")) for k in ("Text", "text", "Transaction", "transaction")
        ).lower()
        if not text or any(w in text for w in _NON_MARKET):
            continue
        shares = r.get("Shares", r.get("shares"))
        try:
            shares = abs(float(shares))
        except (TypeError, ValueError):
            continue
        if shares <= 0:
            continue
        if any(w in text for w in _BUY_WORDS):
            bought += shares
            buys += 1
        elif any(w in text for w in _SELL_WORDS):
            sold += shares
            sells += 1

    if bought <= 0 and sold <= 0:
        return None
    return {"bought_shares": bought, "sold_shares": sold,
            "buy_count": buys, "sell_count": sells, "source": "transactions"}


def parse_insider_purchases(rows: list[dict], label_column: str) -> dict | None:
    """Net insider buying from Yahoo's SUMMARY table, ignoring aggregate rows.

    Fallback only. The summary cannot separate open-market buying from option
    exercises, so `parse_insider_transactions` is preferred whenever the
    itemised list is available.
    """
    bought = sold = 0.0
    for r in rows:
        label = str(r.get(label_column, "")).strip().lower()
        # Anything summarising other rows is not itself a transaction.
        if not label or "%" in label or "net" in label or "total" in label:
            continue
        val = r.get("Shares", r.get("shares"))
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        # A share count is never negative; a negative here means an aggregate
        # row slipped through, so drop it rather than corrupt the total.
        if val < 0:
            continue
        if label in _INSIDER_BUY_ROWS:
            bought += val
        elif label in _INSIDER_SELL_ROWS:
            sold += val

    if bought <= 0 and sold <= 0:
        return None
    return {"bought_shares": bought, "sold_shares": sold, "source": "summary"}


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

    def sentiment_bundle(self, ticker: str) -> dict[str, Any]:
        """Extra sentiment sources: ratings history, insider flow, headlines.

        Fetched separately from the main snapshot and only for names that
        already passed a screen — these are three more network round-trips per
        ticker, which is fine for the dozens of hits and absurd for a
        1,900-name universe. Every piece degrades to absent rather than
        raising, so a missing source costs a signal and never the scan.
        """
        if yf is None:
            return {}

        def _fetch() -> dict[str, Any]:
            t = yf.Ticker(ticker)
            out: dict[str, Any] = {}

            try:                       # ratings breakdown by period
                rec = t.recommendations
                if rec is not None and not rec.empty:
                    out["recommendation_periods"] = rec.to_dict("records")
            except Exception:
                pass

            # Itemised transactions first — only they distinguish an open-market
            # purchase from an option exercise. The summary table is the
            # fallback when the itemised list is unavailable.
            parsed = None
            try:
                it = t.insider_transactions
                if it is not None and not it.empty:
                    parsed = parse_insider_transactions(it.to_dict("records"))
            except Exception:
                pass
            if parsed is None:
                try:
                    ip = t.insider_purchases
                    if ip is not None and not ip.empty:
                        parsed = parse_insider_purchases(
                            ip.to_dict("records"), str(ip.columns[0]))
                except Exception:
                    pass
            if parsed:
                out["insider_purchases"] = parsed

            try:                       # recent headlines
                news = t.news or []
                titles = []
                for n in news[:12]:
                    title = (n.get("title")
                             or (n.get("content") or {}).get("title"))
                    if title:
                        titles.append(str(title))
                if titles:
                    out["headlines"] = titles
            except Exception:
                pass

            return out

        return _cache.get_or_set(f"sent:{ticker}", lambda: with_retries(_fetch)) or {}

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
