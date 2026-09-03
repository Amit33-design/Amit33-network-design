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
            "risk_flags": r.get("risk_flags") or [],
            "csp_signal": r.get("csp_signal") or {},
            "rr_pass": r.get("rr_pass"),
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


def flag_spreads(samples: list[dict], min_n: int = 10) -> list[dict]:
    """Mean forward return WITH vs WITHOUT each boolean signal.

    Covers the parts of the payload that aren't numeric sub-scores — risk
    flags, the CSP signal, the R:R gate — so every claim the product makes can
    be checked against realized returns rather than assumed.
    """
    def prefix(text: str) -> str:
        return text.split("(")[0].strip()

    names: set[str] = set()
    for s in samples:
        for f in s.get("risk_flags") or []:
            names.add(prefix(f.get("text", "")))

    tests: list[tuple[str, Callable[[dict], bool]]] = [
        (n, (lambda s, n=n: any(prefix(f.get("text", "")) == n
                                for f in (s.get("risk_flags") or []))))
        for n in sorted(names) if n and not n.startswith("R:R")
    ]
    tests += [
        ("csp_signal active", lambda s: (s.get("csp_signal") or {}).get("active") is True),
        ("csp_signal strong", lambda s: (s.get("csp_signal") or {}).get("strength") == "strong"),
        ("rr_pass", lambda s: s.get("rr_pass") is True),
    ]

    rows = []
    for name, pred in tests:
        with_ = [s["forward_%"] for s in samples if pred(s)]
        without = [s["forward_%"] for s in samples if not pred(s)]
        if len(with_) < min_n or not without:
            continue
        mw, mo = sum(with_) / len(with_), sum(without) / len(without)
        rows.append({"signal": name, "n": len(with_),
                     "with_%": round(mw, 2), "without_%": round(mo, 2),
                     "spread_pp": round(mw - mo, 2)})
    rows.sort(key=lambda r: r["spread_pp"], reverse=True)
    return rows


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

    rows = flag_spreads(samples)
    if rows:
        print("\n=== boolean signals: forward return WITH vs WITHOUT (n>=10) ===")
        for r in rows:
            print(f"  {r['signal']:32} n={r['n']:4}  with={r['with_%']:+6.2f}%  "
                  f"without={r['without_%']:+6.2f}%  spread={r['spread_pp']:+6.2f}pp")


if __name__ == "__main__":
    main()
