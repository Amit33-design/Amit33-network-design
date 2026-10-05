"""Strategy lab: whole strategies, tested the way a skeptical analyst would.

The factor lab asks "does this ingredient rank stocks?". This asks the next
question — "would trading it have made money after costs, how rough was the
ride, and does it survive out of sample, across regimes, and with a different
parameter?" — for several fundamentally different strategies, each a rule
stated BEFORE looking at results (textbook anomalies, not fitted):

  momentum_12_1   top 10% by 12-month return skipping the last month
  pead            top 20% by last EPS surprise, report within 63 sessions
  high52          top 10% closest to their 52-week high
  low_vol         bottom 20% by 60-day volatility
  reversal_1w     bottom 10% by last week's return (buy the losers)
  group_momentum  members of the 3 strongest themes over 6 months
  mom_pead_combo  momentum + earnings surprise, averaged ranks — CHOSEN AFTER
                  the factor lab showed both as leads, so it is in-sample by
                  construction and labelled as such

Same engine for all: equal weight, rebalanced every HOLD sessions (non-
overlapping periods, so no overlap correction is needed), names below
MIN_PRICE or MIN_DOLLAR_VOL (20-day average, as of the rebalance) excluded as
untradeable, and COST_BPS charged on every dollar traded. Benchmarks: SPY and
an equal-weight basket of the same tradeable universe — beating SPY because
small caps rallied is not a strategy.

Quality checklist (from the research brief): beats SPY after costs with
t >= 2; Sharpe > 1; max drawdown better than -30%; positive alpha in BOTH
halves of the period; positive in BOTH market regimes (S&P above/below its
EMA200 at entry); and positive with the selection fraction halved AND
doubled (not dependent on one parameter).

Caveat stated in the output: the universe is today's listed stocks, so
delisted losers are missing — absolute returns are flattered; comparisons
between strategies on the same universe are the trustworthy part.

Pure: takes the factor-lab data (backend/factor_data.py) and returns a dict.
"""
from __future__ import annotations

import math
from statistics import mean

from backend.factor_study import align, earnings_factors, group_factors, price_factors

HOLD = 20                    # sessions per period; rebalance every period
COST_BPS = 20                # one-way: ~10 bps fees/spread + ~10 bps slippage
MIN_PRICE = 3.0
MIN_DOLLAR_VOL = 5_000_000   # 20-day average dollar volume
PERIODS_PER_YEAR = 252 / HOLD


# ------------------------------------------------------------- selections
def _top(rows, key, frac, reverse=True, cond=None):
    pool = [r for r in rows if r["f"].get(key) is not None and (cond is None or cond(r))]
    if len(pool) < 10:
        return []
    pool.sort(key=lambda r: r["f"][key], reverse=reverse)
    n = max(3, int(len(pool) * frac))
    return [r["t"] for r in pool[:n]]


def _group_mom(rows, frac):
    by: dict[str, list[float]] = {}
    for r in rows:
        if r.get("theme") and r["f"].get("group_mom_6m") is not None:
            by.setdefault(r["theme"], []).append(r["f"]["group_mom_6m"])
    ranked = sorted(by, key=lambda th: mean(by[th]), reverse=True)
    top = set(ranked[:max(1, round(30 * frac))])     # 3 themes at the base 10%
    return [r["t"] for r in rows if r.get("theme") in top]


def _combo(rows, frac):
    pool = [r for r in rows if r["f"].get("mom_12_1") is not None and r["f"].get("eps_surprise") is not None]
    if len(pool) < 10:
        return []
    def ranks(key):
        order = sorted(pool, key=lambda r: r["f"][key])
        return {r["t"]: i / (len(order) - 1) for i, r in enumerate(order)}
    a, b = ranks("mom_12_1"), ranks("eps_surprise")
    pool.sort(key=lambda r: a[r["t"]] + b[r["t"]], reverse=True)
    return [r["t"] for r in pool[:max(3, int(len(pool) * frac))]]


# (key, name, thesis, base fraction, selector(rows, frac), in_sample_flag)
STRATEGIES = [
    ("momentum_12_1", "12-1 momentum",
     "Winners of the last year (skipping the latest month) keep winning: investors under-react to news and trends persist.",
     0.10, lambda rows, f: _top(rows, "mom_12_1", f), False),
    ("pead", "Post-earnings drift",
     "After a big earnings beat, prices keep drifting up for weeks as the market slowly digests the surprise.",
     0.20, lambda rows, f: _top(rows, "eps_surprise", f, cond=lambda r: (r["f"]["eps_surprise"] or 0) > 0), False),
    ("high52", "Near 52-week high",
     "Stocks near their 52-week high outperform: traders anchor to the high and under-react to the good news behind it.",
     0.10, lambda rows, f: _top(rows, "high52_prox", f), False),
    ("low_vol", "Low volatility",
     "Calm stocks earn as much or more than volatile ones per unit of risk: investors overpay for lottery-like names.",
     0.20, lambda rows, f: _top(rows, "vol_60", f, reverse=False), False),
    ("reversal_1w", "1-week reversal",
     "Last week's biggest losers bounce as short-term liquidity pressure fades.",
     0.10, lambda rows, f: _top(rows, "rev_1w", f, reverse=False), False),
    ("group_momentum", "Group momentum",
     "Stocks in the strongest themes keep leading: money rotates into groups and stays.",
     0.10, lambda rows, f: _group_mom(rows, f), False),
    ("mom_pead_combo", "Momentum + earnings surprise",
     "Combines the two strongest factor-lab leads. Chosen AFTER seeing those results, so it is in-sample by construction.",
     0.10, lambda rows, f: _combo(rows, f), True),
]


# ------------------------------------------------------------- the engine
def _ema(c: list, k: int, n: int = 200) -> float | None:
    vals = [x for x in c[:k + 1] if x]
    if len(vals) < n:
        return None
    a, e = 2 / (n + 1), vals[0]
    for x in vals[1:]:
        e = x * a + e * (1 - a)
    return e


def periods(data: dict, hold: int = HOLD) -> list[dict]:
    """Non-overlapping rebalance periods: the tradeable universe with its
    factors at each rebalance, and each name's raw return over the period."""
    spy_s = data["prices"]["SPY"]
    cal, spy = spy_s["dates"], spy_s["c"]
    aligned = {t: align(s, cal) for t, s in data["prices"].items() if t != "SPY"}
    vols = {t: align({"dates": s["dates"], "c": s.get("v") or [0.0] * len(s["dates"])}, cal)
            for t, s in data["prices"].items() if t != "SPY"}
    themes = data.get("themes", {})
    groups: dict[str, list[str]] = {}
    for t, th in themes.items():
        if th and t in aligned:
            groups.setdefault(th, []).append(t)
    earnings = data.get("earnings", {})
    out = []
    for k in range(252, len(cal) - hold, hold):
        rows = []
        for t, c in aligned.items():
            px = c[k]
            if px is None or px < MIN_PRICE:
                continue
            v = [x for x in vols[t][k - 19:k + 1] if x is not None]
            pxs = [x for x in c[k - 19:k + 1] if x is not None]
            if len(v) < 15 or len(pxs) < 15:
                continue
            dollar_vol = mean(v) * mean(pxs)
            if dollar_vol < MIN_DOLLAR_VOL:
                continue
            end = c[k + hold]
            if end is None:      # stopped trading inside the period: last price seen
                seen = [x for x in c[k + 1:k + hold + 1] if x is not None]
                end = seen[-1] if seen else px
            f = price_factors(c, k)
            f.update(earnings_factors(earnings.get(t, []), cal, c, spy, k))
            th = themes.get(t)
            f.update(group_factors(t, groups.get(th, []), aligned, k) if th else {})
            rows.append({"t": t, "f": f, "theme": th, "ret": end / px - 1})
        spy_up = _ema(spy, k)
        out.append({
            "date": cal[k], "rows": rows,
            "spy_ret": spy[k + hold] / spy[k] - 1,
            "regime": None if spy_up is None else ("up" if spy[k] > spy_up else "down"),
        })
    return out


def run(pers: list[dict], select, frac: float, cost_bps: float = COST_BPS) -> list[dict]:
    """Equal-weight portfolio per period; cost charged on every dollar traded."""
    prev: dict[str, float] = {}
    res = []
    for p in pers:
        rets = {r["t"]: r["ret"] for r in p["rows"]}
        picks = [t for t in select(p["rows"], frac) if t in rets]
        w = {t: 1 / len(picks) for t in picks} if picks else {}
        traded = sum(abs(w.get(t, 0) - prev.get(t, 0)) for t in set(w) | set(prev))
        gross = mean(rets[t] for t in picks) if picks else 0.0
        net = gross - traded * cost_bps / 10_000
        res.append({"date": p["date"], "gross": gross, "net": net, "spy": p["spy_ret"],
                    "turnover": traded / 2, "n": len(picks), "regime": p["regime"]})
        # Weights drift with returns before the next rebalance.
        if picks:
            grown = {t: w[t] * (1 + rets[t]) for t in picks}
            tot = sum(grown.values()) or 1
            prev = {t: x / tot for t, x in grown.items()}
        else:
            prev = {}
    return res


def _t(xs: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    m = mean(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return round(m / (sd / math.sqrt(len(xs))), 2) if sd > 0 else None


def metrics(rets: list[float], spy: list[float]) -> dict:
    """Standard performance metrics on per-period returns. Pure."""
    if not rets:
        return {}
    eq, peak, dd = 1.0, 1.0, 0.0
    curve = []
    for r in rets:
        eq *= 1 + r
        peak = max(peak, eq)
        dd = min(dd, eq / peak - 1)
        curve.append(eq)
    years = len(rets) / PERIODS_PER_YEAR
    m = mean(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1)) if len(rets) > 1 else 0
    down = [min(0.0, r) for r in rets]
    dsd = math.sqrt(sum(d * d for d in down) / len(down))
    alpha = [r - s for r, s in zip(rets, spy)]
    gains, losses = sum(r for r in rets if r > 0), -sum(r for r in rets if r < 0)
    return {
        "total_return_%": round((eq - 1) * 100, 1),
        "cagr_%": round((eq ** (1 / years) - 1) * 100, 1) if years > 0 and eq > 0 else None,
        "vol_%": round(sd * math.sqrt(PERIODS_PER_YEAR) * 100, 1),
        # rf ~ 0 for simplicity — stated in the method; compare strategies to each other and to SPY's.
        "sharpe": round(m / sd * math.sqrt(PERIODS_PER_YEAR), 2) if sd > 0 else None,
        "sortino": round(m / dsd * math.sqrt(PERIODS_PER_YEAR), 2) if dsd > 0 else None,
        "max_drawdown_%": round(dd * 100, 1),
        "win_rate_vs_spy": round(sum(a > 0 for a in alpha) / len(alpha), 3),
        "profit_factor": round(gains / losses, 2) if losses > 0 else None,
        "alpha_per_period_%": round(mean(alpha) * 100, 2),
        "alpha_ann_%": round(mean(alpha) * PERIODS_PER_YEAR * 100, 1),
        "alpha_t": _t(alpha),
        "periods": len(rets),
        "curve": [round(x, 4) for x in curve],
    }


def checklist(res: list[dict], variants: list[list[dict]]) -> dict:
    """The research brief's 'high quality' criteria, each pass/fail. Pure."""
    net = [r["net"] for r in res]
    spy = [r["spy"] for r in res]
    m = metrics(net, spy)
    half = len(res) // 2
    a1 = mean(r["net"] - r["spy"] for r in res[:half]) if half else 0
    a2 = mean(r["net"] - r["spy"] for r in res[half:]) if res[half:] else 0
    reg = {}
    for g in ("up", "down"):
        xs = [r["net"] - r["spy"] for r in res if r["regime"] == g]
        reg[g] = (mean(xs), len(xs)) if xs else (None, 0)
    var_alpha = [mean(r["net"] - r["spy"] for r in v) if v else None for v in variants]
    checks = {
        "beats_spy_after_costs": bool(m.get("alpha_t") is not None and m["alpha_t"] >= 2),
        "sharpe_above_1": bool(m.get("sharpe") is not None and m["sharpe"] > 1),
        "drawdown_under_30": bool(m.get("max_drawdown_%") is not None and m["max_drawdown_%"] > -30),
        "both_halves": a1 > 0 and a2 > 0,
        "both_regimes": all(v is not None and v > 0 for v, n in reg.values() if n >= 6)
                        and any(n >= 6 for _, n in reg.values()),
        "not_parameter_dependent": all(a is not None and a > 0 for a in var_alpha),
    }
    return {
        "checks": checks, "passed": sum(checks.values()), "of": len(checks),
        "first_half_alpha_%": round(a1 * 100, 2), "second_half_alpha_%": round(a2 * 100, 2),
        "regime_alpha_%": {g: (round(v * 100, 2) if v is not None else None) for g, (v, n) in reg.items()},
        "regime_periods": {g: n for g, (_, n) in reg.items()},
        "variant_alpha_%": [round(a * 100, 2) if a is not None else None for a in var_alpha],
    }


def lab(data: dict, cost_bps: float = COST_BPS) -> dict:
    pers = periods(data)
    if not pers:
        return {"strategies": [], "error": "not enough history"}
    spy = [p["spy_ret"] for p in pers]
    dates = [p["date"] for p in pers]
    ew = run(pers, lambda rows, f: [r["t"] for r in rows], 1.0, cost_bps)
    out = []
    for key, name, thesis, frac, sel, in_sample in STRATEGIES:
        res = run(pers, sel, frac, cost_bps)
        variants = [run(pers, sel, frac / 2, cost_bps), run(pers, sel, min(1.0, frac * 2), cost_bps)]
        net = metrics([r["net"] for r in res], spy)
        gross = metrics([r["gross"] for r in res], spy)
        chk = checklist(res, variants)
        out.append({
            "key": key, "name": name, "thesis": thesis, "in_sample": in_sample,
            "rule": f"equal weight, top {int(frac * 100)}% by its signal, rebalanced every {HOLD} sessions",
            "net": net, "gross": {k: gross.get(k) for k in ("total_return_%", "cagr_%", "sharpe", "alpha_ann_%")},
            "avg_holdings": round(mean(r["n"] for r in res), 1),
            "avg_turnover_%": round(mean(r["turnover"] for r in res) * 100, 1),
            "cost_drag_ann_%": round((mean(r["gross"] for r in res) - mean(r["net"] for r in res))
                                     * PERIODS_PER_YEAR * 100, 2),
            **chk,
        })
    # Rank: checklist first, then net Sharpe; in-sample constructions last on ties.
    out.sort(key=lambda s: (s["passed"], s["net"].get("sharpe") or -9, not s["in_sample"]), reverse=True)
    return {
        "strategies": out,
        "benchmarks": {
            "SPY": metrics(spy, spy),
            "equal_weight_universe": metrics([r["net"] for r in ew], spy),
        },
        "dates": dates,
        "periods": len(pers),
        "universe_avg": round(mean(len(p["rows"]) for p in pers)),
        "assumptions": {
            "hold_sessions": HOLD, "cost_bps_one_way": cost_bps, "min_price": MIN_PRICE,
            "min_dollar_volume": MIN_DOLLAR_VOL, "weighting": "equal", "risk_free": 0,
        },
        "caveats": [
            "Universe is today's listed stocks: delisted losers are missing, so absolute returns are flattered. "
            "Compare strategies with each other and with the equal-weight universe.",
            "Costs are a flat 20 bps per side; small, volatile names can cost more to trade.",
            "Sharpe uses a zero risk-free rate; compare it with SPY's Sharpe on the same basis.",
            "mom_pead_combo was chosen after seeing the factor lab, so its result is in-sample.",
        ],
    }


def main() -> None:  # pragma: no cover - CI entrypoint
    import datetime as dt
    import json
    import os
    import sys

    with open(sys.argv[1]) as f:
        data = json.load(f)
    out = lab(data)
    out["generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "frontend", "public", "strategy_lab.json"), "w") as f:
        json.dump(out, f, indent=1)
    b = out["benchmarks"]["SPY"]
    print(f"strategy lab: {out['periods']} periods, ~{out['universe_avg']} tradeable names. "
          f"SPY CAGR {b.get('cagr_%')}% Sharpe {b.get('sharpe')} DD {b.get('max_drawdown_%')}%")
    for s in out["strategies"]:
        n = s["net"]
        print(f"  {s['key']:16} {s['passed']}/{s['of']}  CAGR {n.get('cagr_%')}%  Sharpe {n.get('sharpe')}  "
              f"DD {n.get('max_drawdown_%')}%  alpha {n.get('alpha_ann_%')}%/yr t {n.get('alpha_t')}  "
              f"halves {s['first_half_alpha_%']}/{s['second_half_alpha_%']}  cost {s['cost_drag_ann_%']}%/yr")


if __name__ == "__main__":  # pragma: no cover
    main()
