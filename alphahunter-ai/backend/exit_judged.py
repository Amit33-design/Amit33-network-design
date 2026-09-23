"""Judge every pick the way the product tells people to trade it.

Every recommendation ships with an exit plan — a take-profit, a stop, and a
review after 10 trading days — and the Portfolio page tells users to follow
it. But the track record and the $100 paper portfolio scored picks HELD TO
TODAY, a buy-and-forget strategy the product explicitly advises against. That
is where the headline -2.4% alpha came from, and it made the tool look worse
than its own advice while hiding which advice actually works.

This walks each pick's real price path from the day it was recommended and
applies its exit plan day by day: whichever of stop, target, trailing stop or
the 10-day review comes first ends the trade. SPY is measured over EXACTLY the
same holding window, so every trade carries its own alpha.

Older picks predate the exit_plan field, but every one carries entry, stop and
target1, and target1 = entry + 2·ATR, so ATR is recoverable. Every historical
pick is therefore judged with the same build_plan() the product uses today —
one rule, applied uniformly, rather than a different rule for old picks.

`judge_pick` and `summarise` are pure. Only `build` touches the network.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from statistics import median

from .exit_rules import build_plan, check_exit

MAX_GAP_SESSIONS = 5


def recover_atr(rec: dict) -> float | None:
    """ATR at the moment of the pick, from the levels it was published with."""
    entry, t1, stop = rec.get("entry"), rec.get("target1"), rec.get("stop_loss")
    try:
        if entry and t1 and float(t1) > float(entry):
            return (float(t1) - float(entry)) / 2.0
        if entry and stop and float(stop) < float(entry):
            return (float(entry) - float(stop)) / 1.5
    except (TypeError, ValueError):
        pass
    return None


def judge_pick(entry: float, path: list[float], *, atr: float | None = None,
               horizon_days: int = 10) -> dict | None:
    """Apply the exit plan to the closes AFTER the pick, day by day.

    ``path`` is the sequence of daily closes starting with the first session
    after the pick. Returns None when there is not yet enough history to reach
    any exit — an open trade is not a result, and counting it as one is how
    the old track record mixed finished and unfinished trades.
    """
    if not entry or entry <= 0 or not path:
        return None
    plan = build_plan(float(entry), atr=atr, horizon_days=horizon_days)
    peak = float(entry)
    for day, px in enumerate(path, 1):
        if px is None or px <= 0:
            continue
        peak = max(peak, px)
        out = check_exit(plan, float(px), days_held=day, peak_price=peak)
        if out["action"] != "hold":
            action = out["action"]
            # check_exit calls the trailing stop "take_profit" because that is
            # the instruction to the holder. For a RECORD it is a different
            # event: judged on closes, a stock that was up 8% and gapped down
            # overnight exits below entry, and TRMD's -2% was being counted as
            # profit-taking. Only a close at or above the target is a target hit.
            if action == "take_profit" and px < plan.target:
                action = "trail"
            return {
                "exit": action,                 # take_profit | trail | sell | close_stale
                "days_held": day,
                "exit_price": round(float(px), 2),
                "return_%": round((px / entry - 1) * 100, 2),
                "target_pct": plan.target_pct,
                "stop_pct": plan.stop_pct,
            }
    return None   # still open


def summarise(trades: list[dict]) -> dict | None:
    """Aggregate closed trades. Trades carry `return_%` and optionally `spy_%`."""
    if not trades:
        return None
    rets = [t["return_%"] for t in trades]
    alphas = [t["return_%"] - t["spy_%"] for t in trades if t.get("spy_%") is not None]
    exits: dict[str, int] = {}
    for t in trades:
        exits[t["exit"]] = exits.get(t["exit"], 0) + 1
    wins = [r for r in rets if r > 0]
    # Picks made on the same day share one market; 36 trades from three scan
    # dates are closer to three observations than to 36.
    dates = len({t["picked"] for t in trades if t.get("picked")})
    losses = [r for r in rets if r <= 0]
    return {
        "trades": len(trades),
        "dates": dates,
        "win_rate": round(len(wins) / len(rets), 3),
        "avg_return_%": round(sum(rets) / len(rets), 2),
        "median_return_%": round(median(rets), 2),
        "avg_win_%": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss_%": round(sum(losses) / len(losses), 2) if losses else None,
        "avg_alpha_%": round(sum(alphas) / len(alphas), 2) if alphas else None,
        "beat_spy_rate": (round(sum(1 for a in alphas if a > 0) / len(alphas), 3)
                          if alphas else None),
        "avg_days_held": round(sum(t["days_held"] for t in trades) / len(trades), 1),
        "exits": exits,
    }


def judge_history(history: list[tuple[str, list[dict]]],
                  closes: dict[str, dict[str, float]],
                  *, benchmark: str = "SPY", top_n: int | None = None) -> dict:
    """Judge every pick in the history against its real subsequent path.

    ``closes`` maps ticker -> {ISO date: close}. Each ticker is judged from the
    first session AFTER its pick date, so the entry day's own move is never
    counted as part of the trade.
    """
    from .screens import name_for

    from .utils.universe import is_common_share

    bench = closes.get(benchmark) or {}
    # Days are counted on the benchmark's trading calendar, not on the ticker's
    # own bars. A thinly traded series with a months-long gap otherwise turns
    # "day 1" into twelve weeks later: PGYWW was picked on 30 Jun and "exited
    # after 1 day" on 23 Sep.
    calendar = sorted(bench)
    trades, still_open, unpriced, excluded = [], 0, 0, []
    for date_str, results in history:
        picks = sorted(results, key=lambda r: -(r.get("score") or 0))
        if top_n:
            picks = picks[:top_n]
        for rec in picks:
            t = rec.get("ticker")
            series = closes.get(t or "")
            entry = rec.get("entry") or (rec.get("metrics") or {}).get("price")
            if not t or not series or not entry:
                unpriced += 1
                continue
            if not is_common_share(t):
                excluded.append(t)
                continue
            days = ([d for d in calendar if d > date_str] if calendar
                    else sorted(d for d in series if d > date_str))
            path = [series.get(d) for d in days]
            # No close in the first week after the pick: it could not have
            # been traded as recommended, so it is not a result either way.
            if days and not any(px for px in path[:MAX_GAP_SESSIONS]):
                unpriced += 1
                continue
            res = judge_pick(float(entry), path, atr=recover_atr(rec))
            if res is None:
                still_open += 1
                continue
            exit_date = days[res["days_held"] - 1]
            b0 = next((bench[d] for d in sorted(bench) if d >= date_str), None)
            b1 = bench.get(exit_date)
            spy = ((b1 / b0 - 1) * 100) if (b0 and b1) else None
            trades.append({
                **res, "ticker": t, "picked": date_str, "exit_date": exit_date,
                "score": rec.get("score"),
                "screen": name_for((rec.get("metrics") or {}).get("profile")),
                "spy_%": round(spy, 2) if spy is not None else None,
            })

    by_screen = {}
    for s in sorted({t["screen"] for t in trades}):
        by_screen[s] = summarise([t for t in trades if t["screen"] == s])

    return {
        "method": ("each pick judged at its own exit plan — take-profit, stop, "
                   "trailing stop or 10-trading-day review, whichever came first"),
        "summary": summarise(trades),
        "by_screen": by_screen,
        "still_open": still_open,
        "unpriced": unpriced,
        # Warrants, units and rights reached the pick lists because yfinance
        # gives them the parent's revenue. They are left out of the record
        # rather than silently dropped: the count stays visible.
        "excluded_non_common": {"picks": len(excluded),
                                "tickers": sorted(set(excluded))},
        "recent": sorted(trades, key=lambda x: x["exit_date"], reverse=True)[:25],
    }


def build(results_dir: str, out_path: str) -> dict:  # pragma: no cover - network
    import yfinance as yf

    from .performance import load_history
    from .screens import globs

    history: list[tuple[str, list[dict]]] = []
    for pattern in globs():
        history += load_history(results_dir, pattern)
    if not history:
        return {"error": "no scan history"}

    tickers = sorted({r.get("ticker") for _, rs in history for r in rs if r.get("ticker")})
    start = (dt.date.fromisoformat(min(d for d, _ in history)) - dt.timedelta(days=5)).isoformat()
    closes: dict[str, dict[str, float]] = {}
    for i in range(0, len(tickers) + 1, 100):
        chunk = (["SPY"] if i == 0 else []) + tickers[i:i + 100]
        if not chunk:
            continue
        try:
            df = yf.download(chunk, start=start, auto_adjust=True, progress=False,
                             threads=True, group_by="ticker")
        except Exception:
            continue
        for t in chunk:
            try:
                col = df[t]["Close"] if len(chunk) > 1 else df["Close"]
                closes[t] = {d.strftime("%Y-%m-%d"): float(v)
                             for d, v in col.dropna().items()}
            except Exception:
                continue

    out = judge_history(history, closes)
    out["generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":  # pragma: no cover - CI/manual entrypoint
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = build(os.path.join(here, "results"),
                os.path.join(here, "frontend", "public", "exit_judged.json"))
    s = out.get("summary") or {}
    print(json.dumps({"summary": s, "by_screen": out.get("by_screen"),
                      "still_open": out.get("still_open")}, indent=2))
