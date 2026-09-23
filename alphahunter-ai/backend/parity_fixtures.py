"""Golden cases shared by the Python and TypeScript test suites.

The exit rules exist twice — backend/exit_rules.py for the scan and
frontend/src/lib/exitRules.ts for the static site — and so does the pair
rebalancing order. Hand-verified parity is how three different stop levels
for one ticker shipped. So both suites now read ONE fixture: pytest asserts
Python reproduces it, vitest asserts TypeScript does. Drift on either side
fails a suite instead of reaching a user.

    python -m backend.parity_fixtures      # regenerate after an intended change
"""
from __future__ import annotations

import json
import os

from backend.exit_rules import build_plan, check_exit
from backend.pair_signals import daily_order

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "frontend", "src", "lib", "__fixtures__", "parity.json")

PLAN_CASES = [(price, atr) for price in (12.5, 46.12, 110.19, 524.14)
              for atr in (None, 0.2, 1.56, 2.86, 10.2, 40.0)]
EXIT_CASES = [
    # (entry, price, days_held, peak)
    (100.0, 113.0, 3, None), (100.0, 92.0, 2, None), (100.0, 101.0, 10, None),
    (100.0, 109.0, 3, 115.0), (100.0, 103.0, 2, 104.0), (100.0, 85.0, 1, None),
]
ORDER_CASES = [
    # (price_a, price_b, shares_a, shares_b, target_a)
    (200.0, 100.0, 50, 50, 0.5), (100.0, 100.0, 50, 50, 0.5),
    (180.0, 40.0, 60, 90, 0.5), (300.0, 50.0, 50, 50, 0.5),
    (100.0, 100.0, 50, 50, 0.75), (5000.0, 10.0, 1, 400, 0.5),
]


def generate() -> dict:
    plans = []
    for price, atr in PLAN_CASES:
        p = build_plan(price, atr=atr)
        plans.append({"price": price, "atr": atr, "target": p.target, "stop": p.stop,
                      "target_pct": p.target_pct, "stop_pct": p.stop_pct})
    exits = []
    for entry, price, days, peak in EXIT_CASES:
        out = check_exit(build_plan(entry), price, days_held=days, peak_price=peak)
        exits.append({"entry": entry, "price": price, "days_held": days,
                      "peak": peak, "action": out["action"]})
    orders = []
    for pa, pb, sa, sb, ta in ORDER_CASES:
        o = daily_order("A", "B", pa, pb, sa, sb, target_a=ta).to_dict()
        orders.append({"pa": pa, "pb": pb, "sa": sa, "sb": sb, "target_a": ta,
                       "action": o["action"],
                       "sell": o["sell"], "buy": o["buy"]})
    return {"plans": plans, "exits": exits, "orders": orders}


if __name__ == "__main__":  # pragma: no cover
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(generate(), f, indent=1)
    print(f"wrote {OUT}")
