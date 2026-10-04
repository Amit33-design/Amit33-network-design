"""Data for the factor lab (backend/factor_study.py), fetched in CI.

~600 stocks: every theme-basket member (so group momentum has peers) plus a
seeded draw from the scan universe; 3 years of daily closes (validated — a
split-shaped series is left out), and each stock's past earnings reports with
EPS surprise. Only reports that HAVE a reported EPS are kept: get_earnings_dates
also lists upcoming dates, which carry an estimate but no result yet.

    python -m backend.factor_data OUT.json [--sample 600]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time

from backend.theme_pulse import load_defs, members, resolve
from backend.utils.universe import load_universe
from backend.verdict_data import sample_tickers, usable

PUBLIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "frontend", "public")


def earnings_rows(df) -> list[dict]:
    """Past reports with a reported EPS, as {date, surprise_pct}. Pure on a
    DataFrame-like (index of timestamps; 'Reported EPS', 'Surprise(%)')."""
    out = []
    if df is None or len(df) == 0:
        return out
    for ts, row in df.iterrows():
        rep = row.get("Reported EPS")
        if rep is None or (isinstance(rep, float) and math.isnan(rep)):
            continue
        sp = row.get("Surprise(%)")
        sp = None if sp is None or (isinstance(sp, float) and math.isnan(sp)) else float(sp)
        out.append({"date": ts.strftime("%Y-%m-%d"), "surprise_pct": sp})
    return sorted(out, key=lambda e: e["date"])


def main() -> None:  # pragma: no cover - network
    import yfinance as yf

    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--sample", type=int, default=600)
    a = ap.parse_args()

    defs = load_defs()
    try:
        with open(os.path.join(PUBLIC, "profiles.json")) as f:
            profiles = json.load(f).get("profiles", {})
    except Exception:
        profiles = {}
    theme_members = sorted({t for v in members(defs, profiles).values() for t in v})
    tickers = sample_tickers(load_universe(), theme_members, max(0, a.sample - len(theme_members)))

    prices: dict[str, dict] = {}
    for i in range(0, len(tickers) + 1, 100):
        chunk = (["SPY"] if i == 0 else []) + tickers[i:i + 100]
        if not chunk:
            continue
        df = yf.download(chunk, period="3y", auto_adjust=True, progress=False,
                         threads=True, group_by="ticker")
        for t in chunk:
            try:
                col = (df[t]["Close"] if len(chunk) > 1 else df["Close"]).dropna()
            except Exception:
                continue
            dates = [d.strftime("%Y-%m-%d") for d in col.index]
            closes = [float(x) for x in col.values]
            if t != "SPY" and not usable(dates, closes, t):
                continue
            prices[t] = {"dates": dates, "c": closes}

    earnings: dict[str, list] = {}
    for t in prices:
        if t == "SPY":
            continue
        try:
            earnings[t] = earnings_rows(yf.Ticker(t).get_earnings_dates(limit=16))
        except Exception:
            earnings[t] = []
        time.sleep(0.2)

    themes = {}
    for t in prices:
        k = resolve(t, (profiles.get(t) or {}).get("industry"), defs)
        if k:
            themes[t] = k
    with open(a.out, "w") as f:
        json.dump({"prices": prices, "earnings": earnings, "themes": themes}, f)
    with_e = sum(1 for v in earnings.values() if v)
    print(f"factor data: {len(prices) - 1} stocks, {len(themes)} themed, {with_e} with earnings history")


if __name__ == "__main__":  # pragma: no cover
    main()
