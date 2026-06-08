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
daily screener if it scans the same universe twice in a short window from
the same IP. So this script processes the full listing in small CHUNK_SIZE
batches — oldest / never-checked tickers first — and persists progress to
screener/universe_scan_state.csv between runs.

To bootstrap faster, the work can be SHARDED across several parallel jobs
(each GitHub Actions runner gets its own IP, so parallel shards don't share
a rate-limit bucket the way sequential same-day re-runs do):

    scan mode  (one process per shard, runs in parallel):
        python build_universe.py scan --shard-index I --shard-count N
        -> writes its slice of results to universe_partial_I.csv

    merge mode (one process, after all shards finish):
        python build_universe.py merge --shard-count N
        -> combines universe_partial_*.csv into universe_scan_state.csv,
           recomputes universe_1b_revenue.csv, and removes the partials

See .github/workflows/build-universe.yml for the orchestration: N parallel
"scan" jobs feed a single "merge" job that commits the results. Running
with N shards checks roughly N * CHUNK_SIZE tickers per day, so the
universe bootstraps in days rather than weeks.

-------------------------------------------------------------------------
SETUP (run on your own machine, not a restricted sandbox):

    pip install -r requirements.txt
    python screener/build_universe.py            # single-shard scan + merge
-------------------------------------------------------------------------
"""

import argparse
import glob
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
CHUNK_SIZE = 800          # tickers checked per shard per run (~10-15 min at SLEEP_BETWEEN)
REFRESH_DAYS = 30         # re-check entries older than this many days
SLEEP_BETWEEN = 0.4       # politeness delay between tickers (seconds)

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "universe_scan_state.csv")
OUTPUT_PATH = os.path.join(HERE, "universe_1b_revenue.csv")
PARTIAL_PATTERN = os.path.join(HERE, "universe_partial_*.csv")


def partial_path(shard_index):
    return os.path.join(HERE, f"universe_partial_{shard_index}.csv")


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


def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path, parse_dates=["checked_at"])
    return pd.DataFrame(columns=["ticker", "revenue", "checked_at"])


def pick_chunk(full_list, state, size):
    """Oldest / never-checked tickers first, capped at `size`."""
    checked_at = dict(zip(state["ticker"], state["checked_at"]))
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=REFRESH_DAYS)

    never_checked = [t for t in full_list if t not in checked_at]
    stale = sorted(
        (t for t in full_list if t in checked_at and checked_at[t] < cutoff),
        key=lambda t: checked_at[t],
    )
    return (never_checked + stale)[:size]


def fetch_revenue(ticker):
    """Trailing revenue in USD, or None if unavailable / not USD-denominated.

    yfinance reports `totalRevenue` in the company's reporting currency, not
    USD -- e.g. Honda (HMC) reports in JPY and Argentine ADRs (GGAL, BMA, ...)
    report in ARS, both of which dwarf $1B in nominal local-currency terms
    without representing $1B+ of actual USD revenue. Restricting to
    `financialCurrency == "USD"` keeps the $1B floor meaningful and, as a
    side effect, keeps the universe to companies that report in USD.
    """
    try:
        info = yf.Ticker(ticker).info or {}
        if (info.get("financialCurrency") or "").upper() != "USD":
            return None
        return info.get("totalRevenue")
    except Exception:
        return None


def write_qualifying(state):
    qualifying = (state[state["revenue"].fillna(0) >= REVENUE_FLOOR]
                  .sort_values("revenue", ascending=False)
                  .reset_index(drop=True))
    qualifying.to_csv(OUTPUT_PATH, index=False)
    return qualifying


def scan(shard_index, shard_count):
    """Check revenue for this shard's slice of the next chunk; write a partial file."""
    full_list = load_full_listing()
    if not full_list:
        print("Could not load any ticker listings; aborting.")
        sys.exit(1)
    print(f"Full US-listed common-stock universe: {len(full_list)} symbols")

    state = load_csv(STATE_PATH)
    chunk = pick_chunk(full_list, state, CHUNK_SIZE * shard_count)
    my_slice = chunk[shard_index * CHUNK_SIZE:(shard_index + 1) * CHUNK_SIZE]

    print(f"Shard {shard_index}/{shard_count}: checking {len(my_slice)} tickers "
          f"(of {len(chunk)} selected this cycle, {len(state)}/{len(full_list)} "
          f"checked so far)\n")

    now = pd.Timestamp.utcnow().tz_localize(None)
    rows = []
    for i, ticker in enumerate(my_slice, 1):
        revenue = fetch_revenue(ticker)
        rows.append({"ticker": ticker, "revenue": revenue, "checked_at": now})
        if revenue and revenue >= REVENUE_FLOOR:
            print(f"  ${revenue / 1e9:6.1f}B  {ticker}")
        if i % 100 == 0:
            print(f"  ...{i}/{len(my_slice)} checked")
        time.sleep(SLEEP_BETWEEN)

    out = pd.DataFrame(rows, columns=["ticker", "revenue", "checked_at"])
    out.to_csv(partial_path(shard_index), index=False)
    print(f"\nShard {shard_index}: wrote {len(out)} results -> {partial_path(shard_index)}")


def merge(shard_count):
    """Combine every shard's partial results into the persisted state + output."""
    state = load_csv(STATE_PATH)
    partials = sorted(glob.glob(PARTIAL_PATTERN))
    if not partials:
        print("No partial files found; nothing to merge.")
    else:
        updates = [load_csv(p) for p in partials]
        combined_updates = pd.concat(updates, ignore_index=True)
        state = (pd.concat([state, combined_updates], ignore_index=True)
                 .drop_duplicates(subset="ticker", keep="last")
                 .sort_values("ticker")
                 .reset_index(drop=True))
        state.to_csv(STATE_PATH, index=False)
        print(f"Merged {len(combined_updates)} results from {len(partials)} "
              f"shard(s) into {STATE_PATH}")
        for p in partials:
            os.remove(p)

    qualifying = write_qualifying(state)

    full_list = load_full_listing()
    total = len(full_list) if full_list else max(len(state), 1)

    print(f"\n{'=' * 70}")
    print(f"Universe state: {len(state)}/{total} symbols checked, "
          f"{len(qualifying)} qualify with revenue > ${REVENUE_FLOOR / 1e9:.0f}B")
    print(f"Saved qualifying list -> {OUTPUT_PATH}")
    print(f"Saved scan progress   -> {STATE_PATH}")
    print(f"{'=' * 70}")
    if len(state) < total:
        print(f"Bootstrap in progress: {total - len(state)} symbols left to "
              f"check for the first time. With {shard_count} shard(s) checking "
              f"~{CHUNK_SIZE * shard_count} tickers/day, the universe will be "
              f"fully built in roughly {-(-(total - len(state)) // (CHUNK_SIZE * shard_count))} "
              f"more day(s) of runs.")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", nargs="?", default="scan", choices=["scan", "merge"],
                   help="'scan' checks revenue for one shard's slice; "
                        "'merge' combines all shards' results (default: scan)")
    p.add_argument("--shard-index", type=int,
                   default=int(os.environ.get("SHARD_INDEX", "0")),
                   help="this worker's shard number, 0-based (env SHARD_INDEX)")
    p.add_argument("--shard-count", type=int,
                   default=int(os.environ.get("SHARD_COUNT", "1")),
                   help="total number of parallel shards (env SHARD_COUNT)")
    return p.parse_args()


def main():
    args = parse_args()
    if args.mode == "scan":
        scan(args.shard_index, args.shard_count)
    else:
        merge(args.shard_count)


if __name__ == "__main__":
    main()
