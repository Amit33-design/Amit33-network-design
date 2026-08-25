#!/usr/bin/env python3
"""Which signals actually predict returns? (offline, from committed history)

Reconstructs forward returns from the dated ``results/alphahunter_*.json``
scans — a ticker priced on one scan date and again on a later one gives a
realized holding return — then correlates every sub-score, the composite and
expected_gain_% against it. Also scores candidate score-weightings, reporting
both full-sample and held-out-later-half correlations.

    python -m backend.analyze_signals

No network: it reads only what the daily scan already committed. Use it to
justify weight changes with evidence instead of intuition.
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict

SUB_KEYS = ("technical", "fundamental", "options", "momentum", "sentiment")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(_ROOT, "results")


def load_samples(results_dir: str = RESULTS_DIR) -> list[dict]:
    """(sub-scores, realized forward return, pick date) for every reappearing pick."""
    prices: dict[str, dict[str, float]] = defaultdict(dict)
    recs: list[tuple[str, dict]] = []
    for path in sorted(glob.glob(os.path.join(results_dir, "alphahunter_*.json"))):
        try:
            data = json.load(open(path))
        except Exception:
            continue
        date = data.get("date")
        for r in data.get("results", []):
            price = (r.get("metrics") or {}).get("price")
            if price:
                prices[r["ticker"]][date] = price
            recs.append((date, r))

    samples = []
    for date, r in recs:
        entry = (r.get("metrics") or {}).get("price")
        if not entry:
            continue
        later = {d: p for d, p in prices[r["ticker"]].items() if d > date}
        if not later:
            continue
        last = max(later)
        samples.append({
            "ticker": r["ticker"], "date": date,
            "forward_%": (later[last] - entry) / entry * 100,
            "score": r.get("score"), "subscores": r.get("subscores") or {},
            "expected_gain_%": r.get("expected_gain_%"),
        })
    return samples


def correlation(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def weighted(subscores: dict, weights: dict[str, float]) -> float:
    return sum(subscores.get(k, 50.0) * w for k, w in weights.items())


def main() -> None:
    samples = load_samples()
    if not samples:
        print("No samples — need at least two dated scans sharing a ticker.")
        return
    fwd = [s["forward_%"] for s in samples]
    print(f"samples: {len(samples)}\n")
    print("=== signal vs forward return (Pearson r) ===")
    print(f"  {'composite score':20} {correlation([s['score'] or 0 for s in samples], fwd):+.3f}")
    for k in SUB_KEYS:
        pair = [(s["subscores"].get(k), s["forward_%"]) for s in samples
                if s["subscores"].get(k) is not None]
        if len(pair) >= 3:
            r = correlation([p[0] for p in pair], [p[1] for p in pair])
            print(f"  {k:20} {r:+.3f}  (n={len(pair)})")

    from backend.config import settings
    dates = sorted({s["date"] for s in samples})
    cut = dates[len(dates) // 2]
    held = [s for s in samples if s["date"] >= cut]
    fwd_held = [s["forward_%"] for s in held]
    print(f"\n=== weightings: full sample | held-out (dates >= {cut}) ===")
    for name, w in (("current", settings.score_weights),):
        full = correlation([weighted(s["subscores"], w) for s in samples], fwd)
        out = correlation([weighted(s["subscores"], w) for s in held], fwd_held)
        print(f"  {name:12} r={full:+.4f} | held-out r={out:+.4f}")


if __name__ == "__main__":
    main()
