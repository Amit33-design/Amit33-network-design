"""Portfolio-level backtest — what would actually holding the picks have done?

The Dashboard's track record answers "how did individual picks do?". That is
not the same question as "would running this system have made money?", because
a list of picks is not a portfolio: it ignores position count, holding period,
overlap between days, and the market you were holding into.

This module simulates the obvious mechanical strategy a user would run:

    every scan day, buy the top N picks equal-weight and hold them H trading
    days, letting positions from different days overlap.

The portfolio's return on any day is the average daily return of the positions
open that day; the equity curve compounds those. SPY is compounded over the
exact same days, so the comparison is apples-to-apples: the benchmark is out of
the market on days the strategy holds nothing.

`simulate()` is pure — history and a price table go in, a result dict comes out
— so it is fully testable offline. `build()` is the thin network wrapper that
fetches closes and writes frontend/public/backtest.json.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from .performance import load_history

TOP_N = 5            # positions opened per scan day
HOLD_DAYS = 10       # trading days held before exit
BENCHMARK = "SPY"
MAX_TICKERS = 120    # bound the price-history fetch


def _pick_universe(history: list[tuple[str, list[dict]]], top_n: int) -> list[str]:
    """Every ticker the strategy would ever have opened, most-used first."""
    counts: dict[str, int] = {}
    for _date, results in history:
        for r in sorted(results, key=lambda x: x.get("score") or 0, reverse=True)[:top_n]:
            t = r.get("ticker")
            if t:
                counts[t] = counts.get(t, 0) + 1
    return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def _max_drawdown(curve: list[float]) -> float:
    peak, mdd = curve[0] if curve else 1.0, 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v / peak - 1.0)
    return round(mdd * 100, 2)


def simulate(
    history: list[tuple[str, list[dict]]],
    closes: dict[str, dict[str, float]],
    *,
    top_n: int = TOP_N,
    hold_days: int = HOLD_DAYS,
    benchmark: str = BENCHMARK,
) -> dict:
    """Run the top-N / hold-H simulation.

    ``closes`` maps ticker -> {ISO date: close}. The trading calendar is taken
    from the benchmark's own series, so weekends and holidays are handled by
    the data rather than by a hand-rolled calendar.
    """
    bench_series = closes.get(benchmark) or {}
    calendar = sorted(bench_series)
    if len(calendar) < 2:
        return {"error": "no benchmark price history", "points": []}
    index_of = {d: i for i, d in enumerate(calendar)}

    def next_trading_day(date_str: str) -> int | None:
        """Index of the first trading day on or after date_str."""
        i = index_of.get(date_str)
        if i is not None:
            return i
        for j, d in enumerate(calendar):
            if d >= date_str:
                return j
        return None

    # Build the position book: (entry index, exit index, ticker).
    positions: list[tuple[int, int, str]] = []
    trades: list[dict] = []
    for date_str, results in history:
        entry = next_trading_day(date_str)
        if entry is None or entry + 1 >= len(calendar):
            continue
        ranked = sorted(results, key=lambda x: x.get("score") or 0, reverse=True)[:top_n]
        for r in ranked:
            t = r.get("ticker")
            series = closes.get(t or "")
            if not t or not series:
                continue
            exit_i = min(entry + hold_days, len(calendar) - 1)
            if calendar[entry] not in series or calendar[exit_i] not in series:
                continue
            positions.append((entry, exit_i, t))
            e, x = series[calendar[entry]], series[calendar[exit_i]]
            if e:
                trades.append({
                    "ticker": t, "entry_date": calendar[entry], "exit_date": calendar[exit_i],
                    "return_%": round((x / e - 1) * 100, 2),
                    "score": r.get("score"),
                })

    if not positions:
        return {"error": "no tradable positions", "points": []}

    first, last = min(p[0] for p in positions), max(p[1] for p in positions)

    # Daily equal-weight return of whatever is open that day.
    equity, bench_equity = 1.0, 1.0
    points: list[dict] = []
    days_invested = 0
    for i in range(first, last + 1):
        open_now = [p for p in positions if p[0] < i <= p[1]]
        rets = []
        for _entry, _exit, t in open_now:
            s = closes[t]
            prev, cur = s.get(calendar[i - 1]), s.get(calendar[i])
            if prev and cur:
                rets.append(cur / prev - 1)
        day_ret = sum(rets) / len(rets) if rets else 0.0
        if rets:
            days_invested += 1
        equity *= 1 + day_ret

        bprev, bcur = bench_series.get(calendar[i - 1]), bench_series.get(calendar[i])
        if bprev and bcur:
            bench_equity *= bcur / bprev

        points.append({
            "date": calendar[i],
            "strategy": round(equity, 5),
            "benchmark": round(bench_equity, 5),
            "positions": len(open_now),
        })

    strat_ret = (equity - 1) * 100
    bench_ret = (bench_equity - 1) * 100
    wins = [t for t in trades if t["return_%"] > 0]
    return {
        "params": {"top_n": top_n, "hold_days": hold_days, "benchmark": benchmark},
        "start": points[0]["date"] if points else None,
        "end": points[-1]["date"] if points else None,
        "trading_days": len(points),
        "days_invested": days_invested,
        "trades": len(trades),
        "strategy_return_%": round(strat_ret, 2),
        "benchmark_return_%": round(bench_ret, 2),
        "alpha_%": round(strat_ret - bench_ret, 2),
        "max_drawdown_%": _max_drawdown([p["strategy"] for p in points]),
        "benchmark_max_drawdown_%": _max_drawdown([p["benchmark"] for p in points]),
        "trade_win_rate": round(len(wins) / len(trades), 3) if trades else None,
        "avg_trade_%": round(sum(t["return_%"] for t in trades) / len(trades), 2) if trades else None,
        "best_trade": max(trades, key=lambda t: t["return_%"]) if trades else None,
        "worst_trade": min(trades, key=lambda t: t["return_%"]) if trades else None,
        "points": points,
    }


def _fetch_closes(tickers: list[str], start: str, end: str) -> dict[str, dict[str, float]]:
    """Daily closes per ticker. Network-only; kept out of `simulate` on purpose."""
    import yfinance as yf

    out: dict[str, dict[str, float]] = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(start=start, end=end, auto_adjust=True)
            if h is None or h.empty:
                continue
            out[t] = {d.strftime("%Y-%m-%d"): float(c) for d, c in h["Close"].items()}
        except Exception:
            continue
    return out


def build(results_dir: str, out_path: str, *, top_n: int = TOP_N,
          hold_days: int = HOLD_DAYS) -> dict:
    history = load_history(results_dir)
    if not history:
        return {"error": "no scan history", "points": []}

    dates = [d for d, _ in history]
    start = (dt.date.fromisoformat(min(dates)) - dt.timedelta(days=5)).isoformat()
    end = (dt.date.fromisoformat(max(dates)) + dt.timedelta(days=hold_days * 2 + 5)).isoformat()
    end = min(end, (dt.date.today() + dt.timedelta(days=1)).isoformat())

    tickers = _pick_universe(history, top_n)[:MAX_TICKERS]
    closes = _fetch_closes([BENCHMARK] + tickers, start, end)
    result = simulate(history, closes, top_n=top_n, hold_days=hold_days)
    result["generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":  # pragma: no cover - manual/CI entrypoint
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = build(os.path.join(here, "results"),
              os.path.join(here, "frontend", "public", "backtest.json"))
    print(json.dumps({k: v for k, v in r.items() if k != "points"}, indent=2))
