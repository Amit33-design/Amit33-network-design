#!/usr/bin/env python3
"""Screen real candidates for two-stock volatility harvesting, then backtest.

Ranks pairs by the analytic bonus (high volatility, low correlation) rather
than by realized profit, because picking the pair that made the most money
over the sample just selects the two stocks that went up — which says nothing
about whether rebalancing contributed anything.

    python -m backend.run_pair_study

Writes results/pair_study.json. Needs network, so it runs in CI.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from backend.pair_rebalance import capital_for_goal, rank_pairs, simulate

# Deliberately spread across things that do NOT share a driver. Two AI
# semiconductor names would be one position held twice and harvest nothing.
CANDIDATES = [
    # high-beta tech / AI
    "PLTR", "SMCI", "MSTR", "COIN", "MARA", "RIOT", "AFRM", "SOFI",
    # biotech
    "MRNA", "CRSP", "NVAX",
    # energy / commodities
    "OXY", "FCX", "AA", "UNG", "USO",
    # gold & miners (classically low correlation to equities)
    "GLD", "NEM", "AEM",
    # bonds / defensives (negative correlation is worth more than volatility)
    "TLT", "GDX", "VXX",
    # EV / speculative
    "TSLA", "RIVN", "RKLB", "ASTS",
]
GOAL = 100_000.0
LOOKBACK = "3y"


def walk_forward(series: dict[str, list[float]]) -> dict:
    """Choose a pair on the first half, then measure it on the second.

    Picking the best of ~200 pairs on the same data that reports the result is
    hindsight, not a strategy, and the numbers it produces are indefensible.
    So the pair is selected on the EARLIER half and re-run untouched on the
    LATER half it has never seen. The gap between the two is the measure of
    how much of the backtest was selection.

    Two selection rules are compared on purpose: by the analytic bonus (which
    never looks at returns) and by realized profit (which looks at nothing
    else). If the second holds up far worse out of sample, that is the
    overfitting showing.
    """
    halves = {}
    for t, px in series.items():
        if len(px) >= 400:
            mid = len(px) // 2
            halves[t] = (px[:mid], px[mid:])
    if len(halves) < 4:
        return {"error": "not enough history to split"}

    train = {t: v[0] for t, v in halves.items()}
    test = {t: v[1] for t, v in halves.items()}

    def run(a_name, b_name, book):
        a, b = book[a_name], book[b_name]
        n = min(len(a), len(b))
        return simulate(a[-n:], b[-n:], capital=100_000, cost_bps=5.0,
                        band=0.02, tax_rate=0.35)

    # Rule 1: rank by the formula, which never sees a return.
    by_formula = rank_pairs(train, top=1)
    # Rule 2: rank by what actually made the most money in the training half.
    scored = []
    for cand in rank_pairs(train, top=25):
        r = run(cand["a"], cand["b"], train)
        if "error" not in r:
            scored.append((r["cagr_%"], cand))
    by_profit = [max(scored, key=lambda x: x[0])[1]] if scored else []

    out = {"train_days": len(next(iter(train.values()))),
           "test_days": len(next(iter(test.values())))}
    for label, picks in (("by_formula", by_formula), ("by_past_profit", by_profit)):
        if not picks:
            continue
        c = picks[0]
        tr, te = run(c["a"], c["b"], train), run(c["a"], c["b"], test)
        out[label] = {
            "pair": c["pair"],
            "in_sample_cagr_%": tr.get("cagr_%"),
            "out_of_sample_cagr_%": te.get("cagr_%"),
            "out_of_sample_bonus_%": te.get("rebalancing_bonus_%"),
            "out_of_sample_maxdd_%": te.get("max_drawdown_%"),
            "beat_both_legs_out_of_sample": (
                te.get("final_value", 0) > max(te.get("hold_a_value", 0),
                                               te.get("hold_b_value", 0))),
            "decay_pp": (None if tr.get("cagr_%") is None or te.get("cagr_%") is None
                         else round(te["cagr_%"] - tr["cagr_%"], 1)),
        }
    return out


def main() -> None:  # pragma: no cover - CI entrypoint
    import yfinance as yf

    series: dict[str, list[float]] = {}
    for t in CANDIDATES:
        try:
            h = yf.Ticker(t).history(period=LOOKBACK, auto_adjust=True)
            if h is not None and not h.empty and len(h) > 200:
                series[t] = [float(x) for x in h["Close"].dropna()]
        except Exception as e:
            print(f"  {t}: {e}")
    print(f"fetched {len(series)} of {len(CANDIDATES)} candidates")

    ranked = rank_pairs(series, top=15)
    results = []
    for cand in ranked:
        a, b = series[cand["a"]], series[cand["b"]]
        n = min(len(a), len(b))
        # Backtest both frictionless and with realistic costs + a no-trade
        # band, because the gap between those two IS the finding.
        ideal = simulate(a[-n:], b[-n:], capital=100_000)
        real = simulate(a[-n:], b[-n:], capital=100_000, cost_bps=5.0,
                        band=0.02, tax_rate=0.35)
        if "error" in ideal:
            continue
        results.append({
            **cand,
            "ideal": {k: v for k, v in ideal.items() if k != "curve"},
            "realistic": {k: v for k, v in real.items() if k != "curve"},
            "capital_for_goal": capital_for_goal(GOAL, real["rebalancing_bonus_%"]),
        })

    results.sort(key=lambda r: -(r["realistic"]["rebalancing_bonus_%"]))
    wf = walk_forward(series)
    out = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "lookback": LOOKBACK, "goal": GOAL,
        "assumptions": {"cost_bps": 5.0, "band": 0.02, "tax_rate": 0.35},
        "walk_forward": wf,
        "pairs": results,
    }

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "results", "pair_study.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)

    # The bonus column alone is misleading and the first run proved it: ranking
    # on bonus put VXX pairs on top, and VXX bleeds structurally, so a big
    # harvest sat on top of a large loss. TOTAL RETURN is what you keep.
    print(f"\n{'pair':<13}{'vols':>12}{'corr':>7}{'bonus':>8}{'CAGR':>9}"
          f"{'vs hold A':>11}{'vs hold B':>11}{'maxDD':>9}")
    for r in results[:12]:
        real = r["realistic"]
        print(f"{r['pair']:<13}"
              + f"{r['vol_a_%']:.0f}/{r['vol_b_%']:.0f}%".rjust(12)
              + f"{r['correlation']:>7.2f}"
              + f"{real['rebalancing_bonus_%']:>7.1f}%"
              + f"{real['cagr_%']:>8.1f}%"
              + f"{(real['final_value'] / real['hold_a_value'] - 1) * 100:>10.0f}%"
              + f"{(real['final_value'] / real['hold_b_value'] - 1) * 100:>10.0f}%"
              + f"{real['max_drawdown_%']:>8.0f}%")

    profitable = [r for r in results if r["realistic"]["cagr_%"] > 0]
    print(f"\n{len(profitable)} of {len(results)} pairs actually made money after "
          f"costs and tax.")
    if profitable:
        best = max(profitable, key=lambda r: r["realistic"]["cagr_%"])
        need = capital_for_goal(GOAL, best["realistic"]["cagr_%"])
    print("\n--- WALK-FORWARD: chosen on the first half, measured on the second ---")
    for rule in ("by_formula", "by_past_profit"):
        w = wf.get(rule)
        if not w:
            continue
        print(f"  {rule:<15} {w['pair']:<12} in-sample {w['in_sample_cagr_%']:>7.1f}%/yr"
              f"  ->  OUT OF SAMPLE {w['out_of_sample_cagr_%']:>7.1f}%/yr"
              f"  (decay {w['decay_pp']:+.1f}pp, maxDD {w['out_of_sample_maxdd_%']:.0f}%,"
              f" beat both legs: {w['beat_both_legs_out_of_sample']})")

        print(f"Best by total return: {best['pair']} at "
              f"{best['realistic']['cagr_%']:.1f}%/yr -> "
              f"${need:,.0f} needed for ${GOAL:,.0f}/yr")
    print(f"\nwrote {path}")


if __name__ == "__main__":  # pragma: no cover
    main()
