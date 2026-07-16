"""Track record — how did past scan picks actually perform?

Reads the dated results/alphahunter_*.json history the daily scan commits,
prices each historical pick today, and aggregates a verifiable performance
summary (win rate, avg return, best/worst). Written to
frontend/public/performance.json so the Dashboard can show the system's real
track record, not just today's opinions.

`summarize_picks` is pure (history + price function in, dict out) so it's
fully testable offline.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import time
from typing import Callable

TOP_PER_DAY = 10        # judge only each day's top-N picks (what a user acts on)
MIN_AGE_DAYS = 2        # too-fresh picks say nothing yet
MAX_TICKER_FETCHES = 80 # bound the pricing cost


def load_history(results_dir: str) -> list[tuple[str, list[dict]]]:
    hist = []
    for path in sorted(glob.glob(os.path.join(results_dir, "alphahunter_*.json"))):
        try:
            with open(path) as f:
                d = json.load(f)
            if d.get("date") and d.get("results"):
                hist.append((d["date"], d["results"]))
        except Exception:
            continue
    return hist


def summarize_picks(
    history: list[tuple[str, list[dict]]],
    price_of: Callable[[str], float | None],
    today: str,
    min_age_days: int = MIN_AGE_DAYS,
) -> dict:
    picks: list[dict] = []
    for date_str, results in history:
        try:
            age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(date_str)).days
        except ValueError:
            continue
        if age < min_age_days:
            continue
        for r in results[:TOP_PER_DAY]:
            entry = r.get("entry") or (r.get("metrics") or {}).get("price")
            if not entry:
                continue
            cur = price_of(r.get("ticker", ""))
            if not cur:
                continue
            picks.append({
                "date": date_str,
                "ticker": r["ticker"],
                "score": r.get("score"),
                "action": r.get("action"),
                "entry": round(float(entry), 2),
                "price": round(float(cur), 2),
                "return_%": round((cur - entry) / entry * 100, 1),
                "days": age,
            })

    if not picks:
        return {"picks": [], "summary": None}

    rets = [p["return_%"] for p in picks]
    wins = sum(1 for x in rets if x > 0)
    summary = {
        "picks": len(picks),
        "win_rate": round(wins / len(picks), 2),
        "avg_return_%": round(sum(rets) / len(rets), 1),
        "best": max(picks, key=lambda p: p["return_%"]),
        "worst": min(picks, key=lambda p: p["return_%"]),
    }
    picks.sort(key=lambda p: (p["date"], -(p["score"] or 0)), reverse=True)
    return {"picks": picks[:60], "summary": summary}


def build_performance(results_dir: str, today: str) -> dict:
    """CI helper: price history via MarketData (TTL-cached, so tickers already
    fetched by today's scan are free) and summarize."""
    from backend.config import settings
    from backend.utils.market_data import MarketData

    md = MarketData()
    history = load_history(results_dir)
    fetched: dict[str, float | None] = {}

    def price_of(ticker: str) -> float | None:
        if ticker in fetched:
            return fetched[ticker]
        if len(fetched) >= MAX_TICKER_FETCHES:
            return None
        snap = md.snapshot(ticker)
        fetched[ticker] = snap.last_close if snap else None
        time.sleep(settings.request_sleep)
        return fetched[ticker]

    out = summarize_picks(history, price_of, today)
    out["generated"] = today
    return out


def write_performance_json(results_dir: str, today: str, out_path: str) -> dict:
    perf = build_performance(results_dir, today)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(perf, f, indent=2, default=str)
    return perf
