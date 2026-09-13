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
    out = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "lookback": LOOKBACK, "goal": GOAL,
        "assumptions": {"cost_bps": 5.0, "band": 0.02, "tax_rate": 0.35},
        "pairs": results,
    }

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "results", "pair_study.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\n{'pair':<14}{'vols':<14}{'corr':>7}{'bonus(ideal)':>14}{'bonus(real)':>13}{'beat best?':>12}")
    for r in results[:10]:
        print(f"{r['pair']:<14}{r['vol_a_%']:.0f}%/{r['vol_b_%']:.0f}%".ljust(28)
              + f"{r['correlation']:>7.2f}"
              + f"{r['ideal']['rebalancing_bonus_%']:>13.2f}%"
              + f"{r['realistic']['rebalancing_bonus_%']:>12.2f}%"
              + f"{str(r['realistic']['beat_best_single_stock']):>12}")
    print(f"\nwrote {path}")


if __name__ == "__main__":  # pragma: no cover
    main()
