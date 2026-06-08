#!/usr/bin/env python3
"""
CI entry point for the GitHub Actions cloud agent.

Runs ONE scan and writes results/screen_<YYYY-MM-DD>.csv (Pacific date).
Designed to be invoked by .github/workflows/daily-screener.yml.

It reuses the dual-profile logic in oversold_growth_screener.py:
  - LARGE_CAP_DIP   : -5% day, -12% week, >$1B revenue, Buy rating, upside
  - SMALL_CAP_CRASH : -5% day, -20% week, no revenue floor, Buy rating, upside
"""
import os
import sys
import time
import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd

# Make the screener module importable regardless of where CI runs from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oversold_growth_screener import (
    load_universe, screen_ticker, PROFILES, MAX_RESULTS, SLEEP_BETWEEN
)

PACIFIC = ZoneInfo("America/Los_Angeles")


def main():
    today = dt.datetime.now(PACIFIC).strftime("%Y-%m-%d")
    os.makedirs("results", exist_ok=True)
    out_path = os.path.join("results", f"screen_{today}.csv")

    print(f"Daily screen for {today} (Pacific). Profiles: {', '.join(PROFILES)}")
    universe = load_universe()

    matches = []
    for i, ticker in enumerate(universe, 1):
        result = screen_ticker(ticker)
        if result:
            matches.append(result)
            print(f"  MATCH [{result['profiles']}] {ticker} "
                  f"day {result['day_%']}% week {result['week_%']}% "
                  f"upside {result['upside_%']}%")
        if i % 50 == 0:
            print(f"  ...{i}/{len(universe)} scanned, {len(matches)} matches")
        time.sleep(SLEEP_BETWEEN)

    if matches:
        df = (pd.DataFrame(matches)
              .sort_values("upside_%", ascending=False)
              .head(MAX_RESULTS)
              .reset_index(drop=True))
    else:
        # Write an empty (header-only) file so the daily history is unbroken
        df = pd.DataFrame(columns=[
            "ticker", "profiles", "price", "day_%", "week_%", "revenue_$B",
            "rec_mean", "rec", "target", "upside_%", "options"
        ])

    df.to_csv(out_path, index=False)
    print(f"\nWrote {len(df)} matches to {out_path}")


if __name__ == "__main__":
    main()
