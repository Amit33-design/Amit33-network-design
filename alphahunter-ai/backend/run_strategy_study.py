#!/usr/bin/env python3
"""Backtest the wheel on real names, and study what past doublers looked like.

    python -m backend.run_strategy_study

Needs network; runs in CI. Writes results/strategy_study.json.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from backend.moonshot_study import study as moonshot
from backend.wheel_strategy import simulate_wheel

# Names people actually run the wheel on: liquid, optionable, volatile enough
# to pay a premium worth collecting.
WHEEL_NAMES = [
    "NVDA", "AMD", "PLTR", "SOFI", "F", "INTC", "AAPL", "MSFT", "TSLA",
    "COIN", "MARA", "SMCI", "MU", "AMZN", "GOOGL", "META", "UBER", "BAC",
    "SPY", "QQQ", "XLF", "GLD",
]
CAPITAL = 25_000.0


def main() -> None:  # pragma: no cover - CI entrypoint
    import yfinance as yf

    series: dict[str, list[float]] = {}
    for t in WHEEL_NAMES:
        try:
            h = yf.Ticker(t).history(period="5y", auto_adjust=True)
            if h is not None and not h.empty and len(h) > 400:
                series[t] = [float(x) for x in h["Close"].dropna()]
        except Exception as e:
            print(f"  {t}: {e}")
    print(f"fetched {len(series)}/{len(WHEEL_NAMES)}")

    wheel = []
    for t, px in series.items():
        r = simulate_wheel(px, capital=CAPITAL)
        if "error" not in r:
            wheel.append({"ticker": t, **r})
    wheel.sort(key=lambda r: -(r["cagr_%"] or -999))

    print(f"\nTHE WHEEL on ${CAPITAL:,.0f}, 5 years, 30 DTE, 5% OTM, close at 70%")
    print(f"{'ticker':<8}{'CAGR':>8}{'buy&hold':>10}{'beat?':>7}{'maxDD':>8}"
          f"{'premium':>10}{'assign':>8}")
    for r in wheel:
        print(f"{r['ticker']:<8}{(r['cagr_%'] or 0):>7.1f}%{(r['buy_hold_cagr_%'] or 0):>9.1f}%"
              f"{str(r['beat_buy_hold']):>7}{r['max_drawdown_%']:>7.0f}%"
              f"{r['premium_collected']:>10,.0f}{r['assignments']:>8}")

    beat = [r for r in wheel if r["beat_buy_hold"]]
    pos = [r for r in wheel if (r["cagr_%"] or 0) > 0]
    med = sorted(r["cagr_%"] or 0 for r in wheel)[len(wheel) // 2] if wheel else 0
    print(f"\n  {len(pos)}/{len(wheel)} profitable · {len(beat)}/{len(wheel)} beat "
          f"buy-and-hold · median {med:.1f}%/yr")

    # What did names that doubled look like a year earlier?
    ms = moonshot(series, horizon=252)
    print(f"\nWHAT DOUBLERS LOOKED LIKE A YEAR EARLIER "
          f"({ms.get('observations')} observations, base rate "
          f"{ms.get('base_double_rate_%')}%)")
    print(f"{'trait':<34}{'n':>6}{'doubled':>9}{'without':>9}{'lift':>7}")
    for t in ms.get("traits", []):
        print(f"{t['trait']:<34}{t['n_with']:>6}{t['double_rate_with_%']:>8.1f}%"
              f"{t['double_rate_without_%']:>8.1f}%{t['lift']:>7.2f}")
    if ms.get("best_two_combined"):
        c = ms["best_two_combined"]
        print(f"\n  combined: {c['trait']}")
        print(f"    n={c['n_with']} doubled {c['double_rate_with_%']}% lift {c['lift']}")

    out = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "wheel_capital": CAPITAL, "wheel": wheel, "moonshot": ms}
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "results", "strategy_study.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":  # pragma: no cover
    main()
