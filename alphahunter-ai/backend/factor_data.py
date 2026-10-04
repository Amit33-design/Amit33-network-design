"""Data for the factor lab (backend/factor_study.py), fetched in CI.

~600 stocks: every theme-basket member (so group momentum has peers) plus a
seeded draw from the scan universe; 5 years of daily closes (more dates =
more power: 3 years gave only 49 cutoffs) (validated — a
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


def next_earnings(df, today: str) -> str | None:
    """The earliest report on or after `today` that has no result yet — the
    upcoming date get_earnings_dates lists alongside the history. Pure."""
    if df is None or len(df) == 0:
        return None
    upcoming = []
    for ts, row in df.iterrows():
        d = ts.strftime("%Y-%m-%d")
        rep = row.get("Reported EPS")
        if d >= today and (rep is None or (isinstance(rep, float) and math.isnan(rep))):
            upcoming.append(d)
    return min(upcoming) if upcoming else None


LAST_REPORT_MAX_DAYS = 200     # older than ~2 quarters is not "the last result"


def calendar_entry(rows: list[dict], nxt: str | None, today: str | None = None) -> dict:
    """What the Analysis page and Today's plan need: the next report date and
    the last reported surprise. A "last" result older than ~2 quarters is
    dropped: GFI's latest listed report was from 2022 (an irregular foreign
    filer), and showing it as the latest result would mislead. Pure."""
    last = rows[-1] if rows else None
    if last and today:
        import datetime as _dt
        age = (_dt.date.fromisoformat(today) - _dt.date.fromisoformat(last["date"])).days
        if age > LAST_REPORT_MAX_DAYS:
            last = None
    return {"next": nxt, "last": last}


def main() -> None:  # pragma: no cover - network
    import yfinance as yf

    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    # The whole universe: the factor lab gets ~2.7x the stocks per date, and
    # the earnings calendar covers every name the scans can pick.
    ap.add_argument("--sample", type=int, default=2500)
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
        df = yf.download(chunk, period="5y", auto_adjust=True, progress=False,
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

    import datetime as dt
    today = dt.date.today().isoformat()
    earnings: dict[str, list] = {}
    calendar: dict[str, dict] = {}
    for t in prices:
        if t == "SPY":
            continue
        try:
            df = yf.Ticker(t).get_earnings_dates(limit=24)
            earnings[t] = earnings_rows(df)
            calendar[t] = calendar_entry(earnings[t], next_earnings(df, today), today)
        except Exception:
            earnings[t] = []
        time.sleep(0.2)
    # Earnings calendar for the site: a stop does not protect a position
    # through an earnings gap, so the next report date is risk information.
    with open(os.path.join(PUBLIC, "earnings.json"), "w") as f:
        json.dump({"generated": today, "count": len(calendar), "calendar": calendar}, f)

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
