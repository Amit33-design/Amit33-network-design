"""Paper portfolio — put $100 into every Buy and see what happened.

Rank correlations and alpha are the right tools for judging a *ranker*, but
they are a poor way to answer the question a person actually asks: "if I had
followed this thing, would I have money?"

So this does the obvious literal thing. Every time the system said Buy, put
$100 in at that day's price. Never add to a name it repeats — the first Buy
is the entry, later repeats are the same idea, not a new $100. Value every
open position at the latest price. The result is a plain P&L statement, with
the same money put into SPY on the same days as the control.

`simulate()` is pure — picks and a price function in, a dict out — so it is
fully testable offline.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Callable

from .performance import load_history

STAKE = 100.0
# Which verdicts count as "the system told me to buy this". Accumulate is a
# buy with a smaller size in the product's own language, so it counts; Hold,
# Reduce, Sell and Avoid do not.
BUY_ACTIONS = ("buy", "strong buy", "accumulate")


def _is_buy(action: str | None) -> bool:
    return bool(action) and action.strip().lower() in BUY_ACTIONS


def simulate(
    history: list[tuple[str, list[dict]]],
    price_now: Callable[[str], float | None],
    *,
    stake: float = STAKE,
    bench_price: Callable[[str, str], float | None] | None = None,
    benchmark: str = "SPY",
) -> dict:
    """One $100 position per distinct Buy, valued at today's price.

    ``bench_price(ticker, date)`` gives the benchmark's close on a past date,
    so the same $100 on the same day can be tracked into SPY as a control.
    """
    positions: dict[str, dict] = {}
    for date_str, results in sorted(history):
        for r in results:
            t, action = r.get("ticker"), r.get("action")
            entry = (r.get("metrics") or {}).get("price")
            if not t or not _is_buy(action) or not entry or entry <= 0:
                continue
            if t in positions:          # first Buy is the entry, not each repeat
                positions[t]["repeats"] += 1
                continue
            positions[t] = {
                "ticker": t, "company": r.get("company"),
                "first_buy": date_str, "action": action,
                "entry": round(float(entry), 2),
                "shares": stake / float(entry),
                "score": r.get("score"), "quality_grade": r.get("quality_grade"),
                "repeats": 0,
            }

    rows, invested, value = [], 0.0, 0.0
    bench_invested = bench_value = 0.0
    for p in positions.values():
        now = price_now(p["ticker"])
        invested += stake
        if now is None or now <= 0:
            rows.append({**p, "now": None, "value": None, "pnl": None,
                         "return_%": None, "priced": False})
            value += stake                      # unpriced: carried at cost
            continue
        val = p["shares"] * float(now)
        value += val
        rows.append({
            **p, "now": round(float(now), 2), "value": round(val, 2),
            "pnl": round(val - stake, 2),
            "return_%": round((val / stake - 1) * 100, 2),
            "priced": True,
        })

        # The control: the same $100, the same day, into the index instead.
        if bench_price:
            b_then = bench_price(benchmark, p["first_buy"])
            b_now = price_now(benchmark)
            if b_then and b_now:
                bench_invested += stake
                bench_value += stake * (float(b_now) / float(b_then))

    priced = [r for r in rows if r["priced"]]
    wins = [r for r in priced if r["return_%"] > 0]
    rows.sort(key=lambda r: (r["return_%"] is None, -(r["return_%"] or 0)))

    # Does the AI score actually separate winners from losers? If the bands
    # are flat or inverted, the score is decoration and the product should
    # say so rather than keep displaying it as conviction.
    def _band(h: dict) -> str:
        sc = h.get("score") or 0
        return "80+" if sc >= 80 else "70-79" if sc >= 70 else "60-69" if sc >= 60 else "<60"

    bands: dict[str, list[float]] = {}
    for h in priced:
        bands.setdefault(_band(h), []).append(h["return_%"])
    by_score = [
        {"band": b,
         "n": len(v),
         "avg_return_%": round(sum(v) / len(v), 2),
         "win_rate": round(sum(1 for x in v if x > 0) / len(v), 3)}
        for b, v in sorted(bands.items(), reverse=True)
    ]
    # "Higher score => better outcome" should mean the bands descend in order.
    ordered = [b["avg_return_%"] for b in by_score]
    score_separates = len(ordered) > 1 and all(
        a >= b for a, b in zip(ordered, ordered[1:])
    )

    out = {
        "stake": stake,
        "by_score_band": by_score,
        "score_separates": score_separates,
        "positions": len(rows),
        "priced": len(priced),
        "invested": round(invested, 2),
        "value": round(value, 2),
        "pnl": round(value - invested, 2),
        "return_%": round((value / invested - 1) * 100, 2) if invested else None,
        "win_rate": round(len(wins) / len(priced), 3) if priced else None,
        "winners": len(wins),
        "losers": len(priced) - len(wins),
        "best": rows[0] if rows and rows[0]["priced"] else None,
        "worst": next((r for r in reversed(rows) if r["priced"]), None),
        "holdings": rows,
    }
    if bench_invested:
        b_ret = (bench_value / bench_invested - 1) * 100
        out["benchmark"] = benchmark
        out["benchmark_return_%"] = round(b_ret, 2)
        out["benchmark_value"] = round(bench_value, 2)
        out["benchmark_invested"] = round(bench_invested, 2)
        out["alpha_%"] = round((out["return_%"] or 0) - b_ret, 2)
        out["beat_benchmark"] = (out["return_%"] or 0) > b_ret
    return out


def build(results_dir: str, out_path: str, *, stake: float = STAKE) -> dict:
    """Network wrapper: price every held name once, then simulate."""
    import yfinance as yf

    history = load_history(results_dir)
    if not history:
        return {"error": "no scan history", "holdings": []}

    # Historical benchmark closes, fetched once and shared by every position.
    bench_closes: dict[str, float] = {}
    try:
        first = min(d for d, _ in history)
        h = yf.Ticker("SPY").history(
            start=(dt.date.fromisoformat(first) - dt.timedelta(days=7)).isoformat(),
            auto_adjust=True)
        bench_closes = {d.strftime("%Y-%m-%d"): float(c) for d, c in h["Close"].items()}
    except Exception:
        pass

    def bench_price(_ticker: str, date_str: str) -> float | None:
        # The first session on or after the pick date.
        for d in sorted(bench_closes):
            if d >= date_str:
                return bench_closes[d]
        return None

    cache: dict[str, float | None] = {}
    if bench_closes:
        cache["SPY"] = bench_closes[max(bench_closes)]

    def price_now(ticker: str) -> float | None:
        if ticker in cache:
            return cache[ticker]
        try:
            h = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
            cache[ticker] = float(h["Close"].iloc[-1]) if h is not None and not h.empty else None
        except Exception:
            cache[ticker] = None
        return cache[ticker]

    result = simulate(history, price_now, stake=stake, bench_price=bench_price)
    result["generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":  # pragma: no cover - manual/CI entrypoint
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = build(os.path.join(here, "results"),
              os.path.join(here, "frontend", "public", "paper.json"))
    print(json.dumps({k: v for k, v in r.items() if k != "holdings"}, indent=2))
