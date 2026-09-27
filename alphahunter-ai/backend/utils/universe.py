"""US-listed common-stock universe loader.

Reuses the proven approach from the existing ``screener/build_universe.py``:
pull NASDAQ Trader's pipe-delimited symbol directories (NASDAQ + NYSE/AMEX),
which need a browser-like User-Agent. Falls back to the cached
``universe_1b_revenue.csv`` produced by the existing pipeline when present, so
AlphaHunter and the legacy screener share one source of truth.
"""
from __future__ import annotations

import io
import re
import os

import pandas as pd
import requests

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
LISTING_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; alphahunter-ai/1.0)"}

# Where the legacy pipeline writes its >$1B cache, relative to repo root.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CACHED_1B_UNIVERSE = os.path.join(_REPO_ROOT, "screener", "universe_1b_revenue.csv")


def _fetch_listing(url: str) -> pd.DataFrame:
    resp = requests.get(url, headers=LISTING_HEADERS, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text), sep="|")


def load_full_listing() -> list[str]:
    """Every NASDAQ + NYSE/AMEX common-stock ticker (ETFs/test issues excluded)."""
    symbols: list[str] = []
    try:
        nas = _fetch_listing(NASDAQ_LISTED_URL)
        nas = nas[(nas["Test Issue"] == "N") & (nas["ETF"] == "N")]
        symbols += nas["Symbol"].tolist()
    except Exception:
        pass
    try:
        oth = _fetch_listing(OTHER_LISTED_URL)
        oth = oth[(oth["Test Issue"] == "N") & (oth["ETF"] == "N")]
        symbols += oth["ACT Symbol"].tolist()
    except Exception:
        pass

    cleaned: list[str] = []
    for s in symbols:
        if not isinstance(s, str):
            continue
        s = s.strip().replace(".", "-")
        if s and " " not in s and len(s) <= 6 and is_common_share(s):
            cleaned.append(s)
    return sorted(set(cleaned))


# NASDAQ gives a 5-letter symbol's 5th character a meaning: W = warrant,
# U = unit, R = rights. NYSE writes them as suffixes (-WS, -U, -RT...). yfinance
# reports the PARENT's revenue for these, so they sail through the >$1B floor:
# GRABW, a two-cent warrant, was picked 32 times and a 60% one-day move in it
# counted in the track record as if it were a stock. Share classes (BRK-B,
# GOOGL) are ordinary equity and stay.
#
# The same convention marks preferred stock: P/O/N/M/I = a class of preferred,
# Z = miscellaneous (depositary shares, notes). HBANL, FITBO, AGNCZ and ~70
# others were in the universe; a preferred trades like a bond and has no
# business in a stock screen or a theme basket. L is left out on purpose —
# GOOGL is common stock — and share classes are deduped by company instead
# (dedupe_by_company).
_NON_COMMON = re.compile(
    r"^[A-Z]{4}[WURPONMIZ]$|^[A-Z]{4}WW$|-(W|WS|WT|U|UN|R|RT|P[A-Z]?)$")


def is_common_share(ticker: str) -> bool:
    """False for warrants, units and rights — instruments, not companies."""
    return bool(ticker) and not _NON_COMMON.search(ticker.strip().upper())


def _company_key(name: str | None) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    n = re.sub(r"\b(inc|incorporated|corp|corporation|co|ltd|plc|lp|l p|holdings?|group|the|class [a-z])\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def dedupe_by_company(tickers: list[str], profiles: dict) -> list[str]:
    """One ticker per company, keeping the order given and, within a company,
    the largest listing. RUSHA/RUSHB, GOOG/GOOGL, BRK-A/BRK-B and a common
    share next to its preferred (HBAN / HBANL, which has no market cap) are
    one business; counting both double-weights it. Unprofiled tickers pass."""
    best: dict[str, tuple[float, str]] = {}
    for t in tickers:
        p = profiles.get(t) or {}
        k = _company_key(p.get("name"))
        if not k:
            continue
        cap = p.get("market_cap") or -1
        if k not in best or cap > best[k][0]:
            best[k] = (cap, t)
    keep = {t for _, t in best.values()}
    return [t for t in tickers
            if t in keep or not _company_key((profiles.get(t) or {}).get("name"))]


def load_cached_1b_universe() -> list[str]:
    """The >$1B-revenue list maintained by the legacy pipeline, if it exists."""
    if os.path.exists(CACHED_1B_UNIVERSE):
        try:
            df = pd.read_csv(CACHED_1B_UNIVERSE)
            return [t for t in df["ticker"].dropna().astype(str) if is_common_share(t)]
        except Exception:
            return []
    return []


def load_universe(prefer_cached: bool = True) -> list[str]:
    """Best-available scan list: the >$1B cache first, else the full listing."""
    if prefer_cached:
        cached = load_cached_1b_universe()
        if cached:
            return cached
    return load_full_listing()
