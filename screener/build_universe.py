#!/usr/bin/env python3
"""
Universe Builder — PHASE 1 of the two-phase screener pipeline
==============================================================

Scrapes every NASDAQ- and NYSE/AMEX-listed US common stock and caches the
ones with trailing-twelve-month revenue > $1 billion to
screener/universe_1b_revenue.csv. The daily screener (PHASE 2,
oversold_growth_screener.py / run_ci.py) then loads THAT pre-qualified list
instead of the much smaller S&P 500 — so "any company with > $1B revenue
registered on US exchanges" is in scope, not just large-caps.

Why two phases? Checking revenue for thousands of tickers in one run would
trip Yahoo Finance's rate limiting — the same throttling that stalls the
daily screener if it scans the same universe twice in a short window. So
this script processes the full listing in small CHUNK_SIZE batches —
oldest / never-checked tickers first — and persists progress to
screener/universe_scan_state.csv between runs. Run it on a recurring
schedule (see .github/workflows/build-universe.yml): a couple of weeks of
daily runs fully bootstraps the universe, and it then keeps refreshing
stale entries indefinitely.

-------------------------------------------------------------------------
SETUP (run on your own machine, not a restricted sandbox):

    pip install -r requirements.txt
    python screener/build_universe.py
-------------------------------------------------------------------------
"""

import io
import os
import sys
import time

import pandas as pd
import requests
import yfinance as yf

# NASDAQ Trader publishes plain pipe-delimited symbol directories for every
# NASDAQ-listed and "other" (NYSE / NYSE American / ARCA / BATS) listed
# security — no fragile HTML scraping required. Like Wikipedia, it returns
# 403 Forbidden without a browser-like User-Agent.
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
LISTING_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; oversold-growth-screener/1.0)"}

REVENUE_FLOOR = 1_000_000_000
CHUNK_SIZE = 800          # tickers checked per run (~10-15 min at SLEEP_BETWEEN)
REFRESH_DAYS = 30         # re-check entries older than this many days
SLEEP_BETWEEN = 0.4       # politeness delay between tickers (seconds)

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "universe_scan_state.csv")
OUTPUT_PATH = os.path.join(HERE, "universe_1b_revenue.csv")


def _fetch_listing(url):
    resp = requests.get(url, headers=LISTING_HEADERS, timeout=30)
    resp.raise_for_status()
    # Pipe-delimited with a trailing "File Creation Time..." footer row.
    return pd.read_csv(io.StringIO(resp.text), sep="|")


def load_full_listing():
    """Every NASDAQ + NYSE/AMEX common-stock ticker (best effort, ETFs/test issues excluded)."""
    symbols = []
    try:
        nas = _fetch_listing(NASDAQ_LISTED_URL)
        nas = nas[(nas["Test Issue"] == "N") & (nas["ETF"] == "N")]
        symbols += nas["Symbol"].tolist()
    except Exception as e:
        print(f"Could not load nasdaqlisted.txt ({e})")

    try:
        oth = _fetch_listing(OTHER_LISTED_URL)
        oth = oth[(oth["Test Issue"] == "N") & (oth["ETF"] == "N")]
        symbols += oth["ACT Symbol"].tolist()
    except Exception as e:
        print(f"Could not load otherlisted.txt ({e})")

    cleaned = []
    for s in symbols:
        if not isinstance(s, str):
            continue
        s = s.strip().replace(".", "-")
        # Drop the trailing "File Creation Time..." footer row and anything
        # that obviously isn't a tradable symbol.
        if s and " " not in s and len(s) <= 6:
            cleaned.append(s)
    return sorted(set(cleaned))


def load_state():
    if os.path.exists(STATE_PATH):
        return pd.read_csv(STATE_PATH, parse_dates=["checked_at"])
    return pd.DataFrame(columns=["ticker", "revenue", "checked_at"])


def pick_chunk(full_list, state):
    """Oldest / never-checked tickers first, capped at CHUNK_SIZE."""
    checked_at = dict(zip(state["ticker"], state["checked_at"]))
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=REFRESH_DAYS)

    never_checked = [t for t in full_list if t not in checked_at]
    stale = sorted(
        (t for t in full_list if t in checked_at and checked_at[t] < cutoff),
        key=lambda t: checked_at[t],
    )
    return (never_checked + stale)[:CHUNK_SIZE]


def fetch_revenue(ticker):
    try:
        info = yf.Ticker(ticker).info or {}
        return info.get("totalRevenue")
    except Exception:
        return None


def main():
    full_list = load_full_listing()
    if not full_list:
        print("Could not load any ticker listings; aborting.")
        sys.exit(1)
    print(f"Full US-listed common-stock universe: {len(full_list)} symbols")

    state = load_state()
    chunk = pick_chunk(full_list, state)
    print(f"Checking revenue for {len(chunk)} tickers this run "
          f"({len(state)} previously checked, {len(full_list)} total)\n")

    now = pd.Timestamp.utcnow().tz_localize(None)
    rows = []
    for i, ticker in enumerate(chunk, 1):
        revenue = fetch_revenue(ticker)
        rows.append({"ticker": ticker, "revenue": revenue, "checked_at": now})
        if revenue and revenue >= REVENUE_FLOOR:
            print(f"  ${revenue / 1e9:6.1f}B  {ticker}")
        if i % 100 == 0:
            print(f"  ...{i}/{len(chunk)} checked")
        time.sleep(SLEEP_BETWEEN)

    if rows:
        update = pd.DataFrame(rows)
        state = (pd.concat([state, update], ignore_index=True)
                 .drop_duplicates(subset="ticker", keep="last")
                 .sort_values("ticker")
                 .reset_index(drop=True))
        state.to_csv(STATE_PATH, index=False)

    qualifying = (state[state["revenue"].fillna(0) >= REVENUE_FLOOR]
                  .sort_values("revenue", ascending=False)
                  .reset_index(drop=True))
    qualifying.to_csv(OUTPUT_PATH, index=False)

    print(f"\n{'=' * 70}")
    print(f"Universe state: {len(state)}/{len(full_list)} symbols checked, "
          f"{len(qualifying)} qualify with revenue > ${REVENUE_FLOOR / 1e9:.0f}B")
    print(f"Saved qualifying list -> {OUTPUT_PATH}")
    print(f"Saved scan progress   -> {STATE_PATH}")
    print(f"{'=' * 70}")
    if len(state) < len(full_list):
        print(f"Bootstrap in progress: {len(full_list) - len(state)} symbols "
              f"left to check for the first time. Run again (or wait for the "
              f"scheduled job) to keep going — each run picks up where the "
              f"last one left off.")


if __name__ == "__main__":
    main()
