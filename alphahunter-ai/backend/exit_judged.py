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

from .exit_rules import build_moonshot_plan, build_plan, check_exit

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
               horizon_days: int = 10, profile: str | None = None) -> dict | None:
    """Apply the exit plan to the closes AFTER the pick, day by day.

    ``path`` is the sequence of daily closes starting with the first session
    after the pick. Returns None when there is not yet enough history to reach
    any exit — an open trade is not a result, and counting it as one is how
    the old track record mixed finished and unfinished trades.
    """
    if not entry or entry <= 0 or not path:
        return None
    # Each screen is judged by the plan that matches its evidence: moonshots
    # by "hold a year, sell at the double", everything else by the 10-day plan.
    plan = (build_moonshot_plan(float(entry)) if profile == "moonshot"
            else build_plan(float(entry), atr=atr, horizon_days=horizon_days))
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
    # Is the edge distinguishable from zero? Same-day picks move together, so
    # the honest unit is the scan DATE: average each date's alpha, then take
    # the t-statistic across dates. Treating 2,000 correlated trades as
    # independent would make almost any average look significant.
    by_date: dict[str, list[float]] = {}
    for t in trades:
        if t.get("spy_%") is not None and t.get("picked"):
            by_date.setdefault(t["picked"], []).append(t["return_%"] - t["spy_%"])
    date_alphas = [sum(v) / len(v) for v in by_date.values()]
    alpha_t = None
    if len(date_alphas) >= 3:
        m = sum(date_alphas) / len(date_alphas)
        var = sum((a - m) ** 2 for a in date_alphas) / (len(date_alphas) - 1)
        if var > 0:
            alpha_t = round(m / (var / len(date_alphas)) ** 0.5, 2)
    return {
        "trades": len(trades),
        "dates": dates,
        "alpha_t_by_date": alpha_t,
        "dates_beating_spy": (round(sum(1 for a in date_alphas if a > 0) / len(date_alphas), 3)
                              if date_alphas else None),
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


def _moon_progress(entry: float, path: list, days: list[str], bench: dict,
                   b0: float | None) -> dict:
    """Where a moonshot pick stands so far: did it double at any close, and
    what is it worth now (vs SPY over the same sessions)."""
    priced = [(d, px) for d, px in zip(days, path) if px]
    if not priced:
        return {"sessions": 0}
    last_d, last_px = priced[-1]
    b1 = bench.get(last_d)
    return {
        "sessions": len(path),
        "doubled": max(px for _, px in priced) >= entry * 2,
        "return_%": (last_px / entry - 1) * 100,
        "spy_%": ((b1 / b0 - 1) * 100) if (b0 and b1) else None,
    }


def summarise_moonshots(watch: list[dict]) -> dict | None:
    """Progress against the moonshot study's actual claim — ~19% double within
    a year — rather than a 10-day verdict on a one-year bet. Pure."""
    w = [x for x in watch if x.get("sessions")]
    if not w:
        return None
    rets = sorted(x["return_%"] for x in w)
    alphas = [x["return_%"] - x["spy_%"] for x in w if x.get("spy_%") is not None]
    doubled = sum(1 for x in w if x["doubled"])
    return {
        "picks": len(w),
        "oldest_sessions": max(x["sessions"] for x in w),
        "doubled_so_far": doubled,
        "doubled_%": round(doubled / len(w) * 100, 1),
        "median_return_%": round(median(rets), 1),
        "avg_vs_spy_pp": round(sum(alphas) / len(alphas), 1) if alphas else None,
        "note": ("Measured against the study's claim of ~19% doubling within a year "
                 "(4.8% base rate). Early on, few picks have had time to double."),
    }


HOLD_DAYS = 10
# 20 as well: the walk-forward backtest found a 20-day hold best for the top
# picks. If that is real, the picks' own record should show it too.
HOLD_WINDOWS = (10, 20)


def _hold_keys(days: int) -> tuple[str, str]:
    return ("hold_%", "hold_spy_%") if days == HOLD_DAYS else (f"hold{days}_%", f"hold{days}_spy_%")


def compare_hold(trades: list[dict], days: int = HOLD_DAYS) -> dict | None:
    """The same picks held HOLD_DAYS sessions with no stop or target, summarised
    exactly like the plan (date-level alpha), plus which did better. Pure."""
    rk, sk = _hold_keys(days)
    held = [{"exit": "hold", "days_held": days, "picked": t["picked"],
             "return_%": t[rk], "spy_%": t.get(sk)}
            for t in trades if t.get(rk) is not None]
    if len(held) < 3:
        return None
    h = summarise(held)
    # The plan on the SAME picks (those old enough to have been held), so the
    # comparison is never between two different sets of trades.
    plan = summarise([t for t in trades if t.get(rk) is not None])
    diff = None
    if h and plan and h.get("avg_alpha_%") is not None and plan.get("avg_alpha_%") is not None:
        diff = round(h["avg_alpha_%"] - plan["avg_alpha_%"], 2)
    return {
        "days": days, "trades": h["trades"], "dates": h["dates"],
        "avg_alpha_%": h["avg_alpha_%"], "alpha_t_by_date": h["alpha_t_by_date"],
        "win_rate": h["win_rate"],
        "plan_avg_alpha_%": plan["avg_alpha_%"] if plan else None,
        # Positive: holding beat the exit plan on the same picks — the stops
        # or targets are costing this screen, not its stock selection.
        "hold_minus_plan_pp": diff,
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
    watch: list[dict] = []

    def b0_for(date_str: str) -> float | None:
        return next((bench[d] for d in sorted(bench) if d >= date_str), None)
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
            profile = (rec.get("metrics") or {}).get("profile")
            if profile == "moonshot":
                watch.append(_moon_progress(float(entry), path, days, bench, b0_for(date_str)))
            res = judge_pick(float(entry), path, atr=recover_atr(rec), profile=profile)
            if res is None:
                still_open += 1
                continue
            exit_date = days[res["days_held"] - 1]
            b0 = next((bench[d] for d in sorted(bench) if d >= date_str), None)
            b1 = bench.get(exit_date)
            spy = ((b1 / b0 - 1) * 100) if (b0 and b1) else None
            # Counterfactual: the same pick simply held HOLD_DAYS sessions, no
            # stop, no target. Comparing it with the plan says whether a weak
            # screen picks bad stocks or picks fine ones and exits them badly.
            held: dict[str, float | None] = {}
            for n in HOLD_WINDOWS:
                rk, sk = _hold_keys(n)
                h_px = path[n - 1] if len(path) >= n else None
                h_b1 = bench.get(days[n - 1]) if len(days) >= n else None
                held[rk] = round((h_px / entry - 1) * 100, 2) if h_px else None
                held[sk] = round((h_b1 / b0 - 1) * 100, 2) if (h_b1 and b0) else None
            trades.append({
                **res, "ticker": t, "picked": date_str, "exit_date": exit_date,
                "score": rec.get("score"),
                "screen": name_for((rec.get("metrics") or {}).get("profile")),
                "spy_%": round(spy, 2) if spy is not None else None,
                **held,
            })

    by_screen = {}
    for s in sorted({t["screen"] for t in trades}):
        mine = [t for t in trades if t["screen"] == s]
        by_screen[s] = summarise(mine)
        if by_screen[s]:
            by_screen[s]["held_instead"] = compare_hold(mine)
            by_screen[s]["held_20"] = compare_hold(mine, 20)

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
        "moonshot_watch": summarise_moonshots(watch),
        "recent": sorted(trades, key=lambda x: x["exit_date"], reverse=True)[:25],
        "_trades": trades,       # for build(); popped before writing
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

    # Longer SPY + VIX history for the pick-date conditions: a 50-day trend
    # on the first scan date needs bars from before it.
    try:
        early = (dt.date.fromisoformat(start) - dt.timedelta(days=120)).isoformat()
        ctx = yf.download(["SPY", "^VIX"], start=early, auto_adjust=True, progress=False,
                          group_by="ticker")
        spy_long = {d.strftime("%Y-%m-%d"): float(v) for d, v in ctx["SPY"]["Close"].dropna().items()}
        vix = {d.strftime("%Y-%m-%d"): float(v) for d, v in ctx["^VIX"]["Close"].dropna().items()}
    except Exception:
        spy_long, vix = closes.get("SPY", {}), {}

    out = judge_history(history, closes)
    from .date_conditions import analyse
    out["pick_date_conditions"] = analyse(out.pop("_trades", []), spy_long, vix)
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
