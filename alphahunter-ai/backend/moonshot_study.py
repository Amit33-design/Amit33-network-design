"""What did stocks that doubled actually look like BEFORE they doubled?

"Find me a stock that returns 100-200%" is usually answered with intuition.
It is an empirical question and the data can answer it: take a universe, find
every name that doubled over some window, and measure what those names looked
like at the START of that window versus everything that did not.

The output is deliberately two-sided, because the interesting number is not
"what did winners have" — it is "how often did that characteristic ALSO show
up in names that went nowhere". A trait present in 90% of doublers but also in
85% of everything else is not a signal, it is a description of the market.

The headline metric is LIFT: the share of names with a trait that doubled,
divided by the base rate. Lift of 1.0 means the trait told you nothing.

Pure functions over price/fundamental snapshots. No network.
"""
from __future__ import annotations

import math

TRADING_DAYS = 252


def _ret(px: list[float], a: int, b: int) -> float | None:
    if a < 0 or b >= len(px) or px[a] <= 0:
        return None
    return (px[b] / px[a] - 1) * 100


def _vol(px: list[float], end: int, window: int = 120) -> float | None:
    lo = max(1, end - window + 1)
    rets = [math.log(px[j] / px[j - 1]) for j in range(lo, end + 1)
            if px[j - 1] > 0 and px[j] > 0]
    if len(rets) < 20:
        return None
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / max(1, len(rets) - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS) * 100


def observe(px: list[float], t: int, horizon: int) -> dict | None:
    """Everything knowable at time t, plus what happened over the horizon.

    Every feature uses only data at or before t. Getting this wrong is how
    studies like this accidentally discover that stocks which went up, went up.
    """
    if t < 252 or t + horizon >= len(px):
        return None
    fwd = _ret(px, t, t + horizon)
    if fwd is None:
        return None
    hi = max(px[max(0, t - 252):t + 1])
    lo = min(px[max(0, t - 252):t + 1])
    return {
        "forward_%": fwd,
        "doubled": fwd >= 100.0,
        "price": px[t],
        "vol_%": _vol(px, t),
        "ret_6m_%": _ret(px, t - 126, t),
        "ret_12m_%": _ret(px, t - 252, t),
        "ret_1m_%": _ret(px, t - 21, t),
        "from_52w_high_%": (px[t] / hi - 1) * 100 if hi > 0 else None,
        "from_52w_low_%": (px[t] / lo - 1) * 100 if lo > 0 else None,
        "above_200d": px[t] > sum(px[t - 199:t + 1]) / 200 if t >= 200 else None,
    }


def build_observations(series: dict[str, list[float]], *, horizon: int = 252,
                       stride: int = 21) -> list[dict]:
    """Sample every ticker every `stride` days. Stride avoids counting the
    same setup 252 times and pretending they are independent."""
    out = []
    for ticker, px in series.items():
        clean = [float(p) for p in px if p and p > 0]
        for t in range(252, len(clean) - horizon, stride):
            o = observe(clean, t, horizon)
            if o:
                out.append({"ticker": ticker, "t": t, **o})
    return out


def trait_lift(obs: list[dict], name: str, predicate) -> dict | None:
    """How much more often did names with this trait double?"""
    usable = [o for o in obs if predicate(o) is not None]
    if len(usable) < 50:
        return None
    base = sum(1 for o in usable if o["doubled"]) / len(usable)
    have = [o for o in usable if predicate(o)]
    if len(have) < 25 or base <= 0:
        return None
    hit = sum(1 for o in have if o["doubled"]) / len(have)
    without = [o for o in usable if not predicate(o)]
    hit_wo = (sum(1 for o in without if o["doubled"]) / len(without)) if without else 0.0
    return {
        "trait": name,
        "n_with": len(have),
        "double_rate_with_%": round(hit * 100, 1),
        "double_rate_without_%": round(hit_wo * 100, 1),
        "base_rate_%": round(base * 100, 1),
        "lift": round(hit / base, 2),
        "median_forward_%": round(
            sorted(o["forward_%"] for o in have)[len(have) // 2], 1),
    }


# Traits worth testing, framed so each is a yes/no a screener could apply.
TRAITS = {
    "very high volatility (>80%)": lambda o: (o["vol_%"] or 0) > 80,
    "high volatility (50-80%)": lambda o: 50 < (o["vol_%"] or 0) <= 80,
    "low volatility (<30%)": lambda o: 0 < (o["vol_%"] or 0) < 30,
    "already up >50% in 12m": lambda o: (o["ret_12m_%"] or 0) > 50,
    "down >50% in 12m": lambda o: (o["ret_12m_%"] or 0) < -50,
    "within 10% of 52w high": lambda o: (o["from_52w_high_%"] or -99) > -10,
    "more than 50% off the high": lambda o: (o["from_52w_high_%"] or 0) < -50,
    "near the 52w low (<20% above)": lambda o: 0 <= (o["from_52w_low_%"] or 99) < 20,
    "above the 200-day": lambda o: bool(o["above_200d"]),
    "below the 200-day": lambda o: o["above_200d"] is False,
    "cheap (<$10)": lambda o: (o["price"] or 0) < 10,
    "6m momentum >30%": lambda o: (o["ret_6m_%"] or 0) > 30,
}


def study(series: dict[str, list[float]], *, horizon: int = 252) -> dict:
    obs = build_observations(series, horizon=horizon)
    if len(obs) < 200:
        return {"error": f"only {len(obs)} observations, need 200+"}

    results = [r for r in (trait_lift(obs, n, p) for n, p in TRAITS.items()) if r]
    results.sort(key=lambda r: -r["lift"])
    base = sum(1 for o in obs if o["doubled"]) / len(obs) * 100

    # Combining the two best traits — does stacking them help or just shrink n?
    best_two = results[:2]
    combo = None
    if len(best_two) == 2:
        p1, p2 = TRAITS[best_two[0]["trait"]], TRAITS[best_two[1]["trait"]]
        combo = trait_lift(obs, f"{best_two[0]['trait']} AND {best_two[1]['trait']}",
                           lambda o: p1(o) and p2(o))

    return {
        "observations": len(obs),
        "tickers": len({o["ticker"] for o in obs}),
        "horizon_days": horizon,
        "base_double_rate_%": round(base, 1),
        "traits": results,
        "best_two_combined": combo,
    }
