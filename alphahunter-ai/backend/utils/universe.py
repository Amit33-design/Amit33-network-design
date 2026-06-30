"""US-listed common-stock universe loader.

Reuses the proven approach from the existing ``screener/build_universe.py``:
pull NASDAQ Trader's pipe-delimited symbol directories (NASDAQ + NYSE/AMEX),
which need a browser-like User-Agent. Falls back to the cached
``universe_1b_revenue.csv`` produced by the existing pipeline when present, so
AlphaHunter and the legacy screener share one source of truth.
"""
from __future__ import annotations

import io
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
        if s and " " not in s and len(s) <= 6:
            cleaned.append(s)
    return sorted(set(cleaned))


def load_cached_1b_universe() -> list[str]:
    """The >$1B-revenue list maintained by the legacy pipeline, if it exists."""
    if os.path.exists(CACHED_1B_UNIVERSE):
        try:
            df = pd.read_csv(CACHED_1B_UNIVERSE)
            return df["ticker"].dropna().astype(str).tolist()
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
