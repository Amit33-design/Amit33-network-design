#!/usr/bin/env python3
"""
Oversold-with-Upside Stock Screener
====================================

Scans a universe of tickers and returns up to 50 that match ALL of:

  1. Fell >= 5% in a single day (latest session vs prior close)
  2. Fell >= 20% over the past week (~5 trading days)
  3. Trailing-twelve-month revenue > $1 billion
  4. Analyst consensus is a Buy / Strong Buy
  5. Has "growth" signals: meaningful analyst upside to target price
     and/or elevated options activity (volume vs open interest)

Results are ranked by analyst upside (target vs current price).

This is a screening TOOL, not financial advice. It fetches live market
data when YOU run it; the output reflects the moment you run it.

-------------------------------------------------------------------------
SETUP (run on your own machine, not a restricted sandbox):

    pip install yfinance pandas

    python oversold_growth_screener.py

Optional: edit UNIVERSE below, or pass your own list of tickers.
-------------------------------------------------------------------------
"""

import io
import time
import math
import pandas as pd
import requests
import yfinance as yf

# Wikipedia returns 403 Forbidden to requests without a browser-like User-Agent.
WIKI_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; oversold-growth-screener/1.0)"}

# ---------------------------------------------------------------------------
# CRITERIA — tweak these thresholds to loosen or tighten the screen
# ---------------------------------------------------------------------------
MAX_RESULTS       = 50
SLEEP_BETWEEN     = 0.4      # politeness delay between tickers (seconds)

# Two profiles run together. A ticker is a MATCH if it passes EITHER one.
# Each result is tagged with the profile name(s) it satisfied.
PROFILES = {
    # Realistic large-cap dip: looser weekly bar, keep the $1B revenue floor.
    "LARGE_CAP_DIP": {
        "day_drop_pct":   -5.0,
        "week_drop_pct":  -12.0,        # loosened from -20
        "min_revenue":    1_000_000_000,
        "max_rec_mean":   2.5,
        "min_upside_pct": 5.0,          # loosened from 10.0 to surface more matches
    },
    # Deep small-cap selloff: keep the -20% weekly crash, drop the revenue floor.
    "SMALL_CAP_CRASH": {
        "day_drop_pct":   -5.0,
        "week_drop_pct":  -20.0,        # original strict weekly bar
        "min_revenue":    0,            # revenue floor removed (HIGHER RISK)
        "max_rec_mean":   2.5,
        "min_upside_pct": 5.0,          # loosened from 10.0 to surface more matches
    },
}

# ---------------------------------------------------------------------------
# UNIVERSE — the list of tickers to scan.
# Default pulls the S&P 500 from Wikipedia; falls back to a small sample.
# Replace with your own list for a broader / different universe.
# ---------------------------------------------------------------------------
def load_universe():
    try:
        resp = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                            headers=WIKI_HEADERS, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        tickers = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        print(f"Loaded {len(tickers)} tickers from S&P 500.")
        return tickers
    except Exception as e:
        print(f"Could not load S&P 500 list ({e}); using fallback sample.")
        return ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL",
                "TSLA", "AMD", "NFLX", "CRM", "INTC", "PYPL"]


def pct(a, b):
    """Percent change from b to a."""
    if b in (None, 0) or a is None:
        return None
    return (a - b) / b * 100.0


def screen_ticker(ticker):
    """Return a dict of metrics if the ticker passes EITHER profile, else None.

    The returned dict includes a 'profiles' field listing which profile name(s)
    the ticker satisfied (e.g. 'LARGE_CAP_DIP', 'SMALL_CAP_CRASH', or both).
    """
    try:
        t = yf.Ticker(ticker)

        # --- price history for day & week drops ---
        hist = t.history(period="10d", interval="1d")
        if len(hist) < 6:
            return None
        closes = hist["Close"].dropna()
        last = closes.iloc[-1]
        prev_day = closes.iloc[-2]
        week_ago = closes.iloc[-6]   # ~5 sessions back

        day_change = pct(last, prev_day)
        week_change = pct(last, week_ago)
        if day_change is None or week_change is None:
            return None

        info = t.info or {}
        revenue = info.get("totalRevenue") or 0
        rec_mean = info.get("recommendationMean")
        rec_key = (info.get("recommendationKey") or "").lower()
        is_buy = (rec_mean is not None and rec_mean <= 2.5) or \
                 rec_key in ("buy", "strong_buy")
        target = info.get("targetMeanPrice")
        upside = pct(target, last) if target else None

        # Evaluate against every profile; collect the ones that pass.
        passed = []
        for name, p in PROFILES.items():
            if (day_change <= p["day_drop_pct"]
                    and week_change <= p["week_drop_pct"]
                    and revenue >= p["min_revenue"]
                    and ((rec_mean is not None and rec_mean <= p["max_rec_mean"])
                         or rec_key in ("buy", "strong_buy"))
                    and upside is not None and upside >= p["min_upside_pct"]):
                passed.append(name)
        if not passed:
            return None

        # CRITERION 5b: options activity signal (best-effort, optional)
        opt_signal = ""
        try:
            expiries = t.options
            if expiries:
                chain = t.option_chain(expiries[0])
                call_vol = chain.calls["volume"].fillna(0).sum()
                put_vol = chain.puts["volume"].fillna(0).sum()
                call_oi = chain.calls["openInterest"].fillna(0).sum()
                put_oi = chain.puts["openInterest"].fillna(0).sum()
                pc_ratio = (put_vol / call_vol) if call_vol else None
                vol_oi = ((call_vol + put_vol) / (call_oi + put_oi)
                          if (call_oi + put_oi) else None)
                if vol_oi and vol_oi > 0.5:
                    opt_signal = "elevated volume"
                if pc_ratio is not None:
                    opt_signal += f" (P/C {pc_ratio:.2f})"
        except Exception:
            pass

        return {
            "ticker": ticker,
            "profiles": "+".join(passed),
            "price": round(last, 2),
            "day_%": round(day_change, 1),
            "week_%": round(week_change, 1),
            "revenue_$B": round(revenue / 1e9, 2),
            "rec_mean": rec_mean,
            "rec": rec_key,
            "target": target,
            "upside_%": round(upside, 1),
            "options": opt_signal.strip(),
        }
    except Exception:
        return None


def main():
    universe = load_universe()
    matches = []

    print(f"\nScanning {len(universe)} tickers against profiles: "
          f"{', '.join(PROFILES)}\n")
    for i, ticker in enumerate(universe, 1):
        result = screen_ticker(ticker)
        if result:
            matches.append(result)
            print(f"  MATCH [{result['profiles']:<28}] {ticker:6} "
                  f"day {result['day_%']}%  week {result['week_%']}%  "
                  f"upside {result['upside_%']}%")
        if i % 25 == 0:
            print(f"  ...{i}/{len(universe)} scanned, {len(matches)} matches so far")
        time.sleep(SLEEP_BETWEEN)

    if not matches:
        print("\nNo tickers matched either profile right now. "
              "This is common — these are contrarian filters. "
              "Try loosening week_drop_pct or min_upside_pct in PROFILES.")
        return

    df = pd.DataFrame(matches).sort_values("upside_%", ascending=False)
    df = df.head(MAX_RESULTS).reset_index(drop=True)

    out_path = "screen_results.csv"
    df.to_csv(out_path, index=False)

    print(f"\n{'='*70}")
    print(f"{len(df)} stocks matched (up to {MAX_RESULTS}, ranked by upside):")
    print(f"{'='*70}")
    print(df.to_string(index=False))
    print(f"\nSaved to {out_path}")
    print("\nNote: a screen is a starting point for research, not a buy list. "
          "SMALL_CAP_CRASH names in particular are down hard for real reasons.")


if __name__ == "__main__":
    main()
