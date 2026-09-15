"""Moonshot screen — the traits that actually preceded a double.

Every threshold here comes from `run_moonshot_full.py` measured over 62,202
observations across 1,775 tickers, not from intuition. Against a 4.8% base
rate of doubling within a year:

    very high volatility (>80%)      18.6% doubled    lift 3.84
    down >50% over 12 months         14.3% doubled    lift 2.96
    more than 50% off the high       14.3% doubled    lift 2.95
    under $10                        13.5% doubled    lift 2.79
    BOTH of the top two together     19.0% doubled    lift 3.93

And the traits that actively argue against a double:

    within 10% of the 52-week high    2.9% doubled    lift 0.61
    volatility under 30%              0.8% doubled    lift 0.17

That last one is the most useful line in the table: a calm stock essentially
never doubles. Whatever else this screen does, it must not return calm stocks.

TWO WARNINGS THAT BELONG ON EVERY RESULT.

The first is the median. Names down more than 50% double 14.3% of the time,
but their MEDIAN outcome is +6.7% — four in five do not double and plenty keep
falling. This is a lottery-ticket profile: a fat right tail bolted to a
mediocre middle. It is the opposite of the growth screen, which has a better
median and a thinner tail, and the two should be sized completely differently.

The second is survivorship. The universe only contains companies listed today,
and roughly 7% of it leaves every year — disproportionately the failures in
exactly these beaten-down buckets. So 19% is an upper bound.
"""
from __future__ import annotations

import math

from ..indicators import technical as ta
from ..utils.market_data import StockSnapshot
from .alphahunter import tradability_reason
from .base import Criterion, ScanHit

# Measured thresholds. Changing one means re-running the study, not guessing.
VERY_HIGH_VOL = 80.0        # lift 3.84 — the strongest single trait
HIGH_VOL = 50.0             # lift 2.62
CALM_VOL = 30.0             # lift 0.17 — near-disqualifying
DEEP_DRAWDOWN = -50.0       # lift 2.96
OFF_HIGH = -50.0            # lift 2.95
NEAR_HIGH = -10.0           # lift 0.61 — argues against

# Measured hit rates, attached to output so a pick is never shown without them.
BASE_RATE = 4.8
COMBO_RATE = 19.0
COMBO_MEDIAN = 6.7


def annualised_vol(hist, window: int = 120) -> float | None:
    closes = [float(c) for c in hist["Close"].dropna()][-window - 1:]
    if len(closes) < 40:
        return None
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
            if closes[i - 1] > 0 and closes[i] > 0]
    if len(rets) < 30:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / max(1, len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100


def moonshot_score(vol: float | None, ret_12m: float | None,
                   dist_high: float | None, price: float | None) -> tuple[float, list[str]]:
    """0-100, weighted by each trait's measured lift rather than by opinion."""
    score, why = 0.0, []
    if vol is not None:
        if vol >= VERY_HIGH_VOL:
            score += 38
            why.append(f"{vol:.0f}% volatility — the strongest measured trait (lift 3.8)")
        elif vol >= HIGH_VOL:
            score += 24
            why.append(f"{vol:.0f}% volatility (lift 2.6)")
        elif vol < CALM_VOL:
            score -= 40
            why.append(f"only {vol:.0f}% volatility — calm stocks doubled 0.8% of the time")
    if ret_12m is not None and ret_12m <= DEEP_DRAWDOWN:
        score += 28
        why.append(f"down {abs(ret_12m):.0f}% over 12 months (lift 3.0)")
    if dist_high is not None:
        if dist_high <= OFF_HIGH:
            score += 22
            why.append(f"{abs(dist_high):.0f}% below its 52-week high (lift 2.9)")
        elif dist_high >= NEAR_HIGH:
            score -= 25
            why.append("near its 52-week high — argues against doubling (lift 0.6)")
    if price is not None and price < 10:
        score += 12
        why.append(f"${price:.2f} — sub-$10 names doubled 13.5% of the time")
    return max(0.0, min(100.0, score)), why


class MoonshotScanner:
    """Finds the lottery-ticket profile. Deliberately not the growth screen."""

    name = "moonshot"

    def evaluate(self, snap: StockSnapshot) -> ScanHit | None:
        ind = ta.indicator_bundle(snap.history)
        last = snap.last_close
        if last is None or tradability_reason(snap, ind):
            return None

        vol = annualised_vol(snap.history)
        ret_12m = ind.get("ret_252d")
        dist_high = ind.get("dist_52w_high")
        score, why = moonshot_score(vol, ret_12m, dist_high, last)

        criteria = [
            Criterion("high_volatility", vol is not None and vol >= HIGH_VOL,
                      f"{vol:.0f}% annualised" if vol else "vol n/a"),
            Criterion("not_calm", vol is None or vol >= CALM_VOL,
                      "volatile enough" if (vol or 0) >= CALM_VOL else "too calm to double"),
            Criterion("beaten_down",
                      (ret_12m is not None and ret_12m <= DEEP_DRAWDOWN)
                      or (dist_high is not None and dist_high <= OFF_HIGH),
                      f"12m {ret_12m:.0f}%" if ret_12m is not None else "n/a"),
        ]
        # Volatility is the hard gate: a calm stock doubled 0.8% of the time,
        # which is not a candidate at any price.
        if not (vol is not None and vol >= HIGH_VOL):
            return None

        return ScanHit(
            ticker=snap.ticker,
            metrics={
                "indicators": ind,
                "profile": "moonshot",
                "price": round(last, 2),
                "moonshot_score": round(score, 1),
                "volatility_%": round(vol, 1) if vol else None,
                "ret_12m_%": round(ret_12m, 1) if ret_12m is not None else None,
                "dist_52w_high_%": round(dist_high, 1) if dist_high is not None else None,
                "reasons": why,
                # Measured odds travel with every pick, so no one reads this
                # screen as a list of stocks that WILL double.
                "measured_double_rate_%": COMBO_RATE,
                "base_rate_%": BASE_RATE,
                "median_outcome_%": COMBO_MEDIAN,
                "caveat": (
                    f"Measured on 62,202 samples: names like this doubled "
                    f"{COMBO_RATE}% of the time against a {BASE_RATE}% base rate — "
                    f"but the MEDIAN outcome was only +{COMBO_MEDIAN}%, and roughly "
                    f"7% of the universe delists each year, so this is an upper bound."),
            },
            criteria=criteria,
        )
