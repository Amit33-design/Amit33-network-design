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
BENCHMARK = "SPY"       # what every pick is measured against


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
    bench_return: Callable[[str], float | None] | None = None,
) -> dict:
    """Score past picks, optionally against a benchmark.

    ``bench_return(pick_date)`` returns the benchmark's % return from that date
    to today. Raw returns alone are misleading — a -2% average is good in a
    market that fell 6% and bad in one that rose 10% — so when a benchmark is
    supplied every pick also carries its alpha over the same holding window.
    """
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
                # Attributes we segment performance by, so we learn which
                # signals actually predict returns (see _segment below).
                "quality_grade": r.get("quality_grade"),
                "confidence": r.get("confidence"),
                "setup": ("pullback" if (r.get("metrics") or {}).get("profile") == "opportunity"
                          else "crash dip"),
                "entry": round(float(entry), 2),
                "price": round(float(cur), 2),
                "return_%": round((cur - entry) / entry * 100, 1),
                "days": age,
                **_bench_fields(bench_return, date_str,
                                (cur - entry) / entry * 100),
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
    alphas = [p["alpha_%"] for p in picks if p.get("alpha_%") is not None]
    if alphas:
        summary["avg_alpha_%"] = round(sum(alphas) / len(alphas), 1)
        summary["beat_benchmark_rate"] = round(
            sum(1 for a in alphas if a > 0) / len(alphas), 2)
        summary["benchmark"] = BENCHMARK

    segments = {
        "quality_grade": _segment(picks, lambda p: p.get("quality_grade")),
        "setup": _segment(picks, lambda p: p.get("setup")),
        "confidence": _segment(picks, lambda p: p.get("confidence")),
        "score_band": _segment(picks, _score_band),
    }
    picks.sort(key=lambda p: (p["date"], -(p["score"] or 0)), reverse=True)
    return {"picks": picks[:60], "summary": summary, "segments": segments}


def _bench_fields(bench_return, date_str: str, pick_ret: float) -> dict:
    """Benchmark return over the same window plus the pick's alpha."""
    if bench_return is None:
        return {}
    b = bench_return(date_str)
    if b is None:
        return {}
    return {"benchmark_%": round(b, 1), "alpha_%": round(pick_ret - b, 1)}


def _score_band(pick: dict) -> str | None:
    s = pick.get("score")
    if s is None:
        return None
    for lo in (80, 70, 60, 50):
        if s >= lo:
            return f"{lo}+"
    return "<50"


def _segment(picks: list[dict], key: Callable[[dict], str | None],
             min_n: int = 3) -> list[dict]:
    """Win rate / avg return grouped by an attribute, best cohort first.

    Groups with fewer than ``min_n`` picks are dropped — a 100% win rate on
    one pick is noise, and showing it would invite exactly the wrong lesson.
    """
    buckets: dict[str, list[dict]] = {}
    for p in picks:
        k = key(p)
        if k:
            buckets.setdefault(str(k), []).append(p)
    rows = []
    for k, v in buckets.items():
        if len(v) < min_n:
            continue
        rets = [x["return_%"] for x in v]
        row = {
            "key": k,
            "picks": len(v),
            "win_rate": round(sum(1 for x in rets if x > 0) / len(rets), 2),
            "avg_return_%": round(sum(rets) / len(rets), 1),
        }
        alphas = [x["alpha_%"] for x in v if x.get("alpha_%") is not None]
        if alphas:
            row["avg_alpha_%"] = round(sum(alphas) / len(alphas), 1)
        rows.append(row)
    # Rank by alpha when we have it — beating the market is the real test.
    rows.sort(key=lambda r: r.get("avg_alpha_%", r["avg_return_%"]), reverse=True)
    return rows


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

    # Benchmark: SPY closes indexed by date, so each pick can be measured
    # against what simply holding the market would have returned since.
    bench_return = None
    bench_hist = md.history(BENCHMARK, period="1y")
    if bench_hist is None or getattr(bench_hist, "empty", True):
        # A single rate-limited fetch shouldn't silently drop alpha for the
        # whole report, so fall back to the (separately cached) snapshot.
        snap = md.snapshot(BENCHMARK)
        bench_hist = snap.history if snap is not None else None
    if bench_hist is not None and not bench_hist.empty:
        closes = bench_hist["Close"].dropna()
        by_date = {str(idx.date()): float(v) for idx, v in closes.items()}
        latest = float(closes.iloc[-1])
        dates_sorted = sorted(by_date)

        def bench_return(date_str: str) -> float | None:
            # Pick dates can be weekends/holidays; use the next session on or
            # after the pick date so the window matches the pick's holding.
            base = by_date.get(date_str)
            if base is None:
                nxt = [d for d in dates_sorted if d >= date_str]
                if not nxt:
                    return None
                base = by_date[nxt[0]]
            return (latest - base) / base * 100 if base else None

    if bench_return is None:
        print(f"Track record: {BENCHMARK} benchmark unavailable — "
              f"reporting raw returns without alpha.")

    out = summarize_picks(history, price_of, today, bench_return=bench_return)
    out["generated"] = today
    return out


def write_performance_json(results_dir: str, today: str, out_path: str) -> dict:
    perf = build_performance(results_dir, today)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(perf, f, indent=2, default=str)
    return perf
