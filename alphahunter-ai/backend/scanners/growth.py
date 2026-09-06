"""Growth leadership scanner — buy strength, not wreckage.

Every existing screen in this repo looks for the same thing: a stock that has
just fallen a long way. That is a mean-reversion bet, and the paper portfolio
says what it has been worth — roughly flat, slightly behind SPY, with the
deepest, cheapest names doing the most damage.

This scanner is the structural opposite, and exists because "find me growth
stocks" is a different question from "find me things that crashed":

  * the business is actually growing (revenue and earnings, not just price),
  * the stock is in an uptrend and near its highs rather than near its lows,
  * it is beating the index rather than lagging it,
  * and it is not so extended that we are buying the last buyer's exit.

That last criterion is the one that separates this from naive momentum chasing.
Growth investing loses money the same way every time: buying a vertical chart
after the move. So a blow-off RSI disqualifies a name here rather than
flattering it.

`growth_score` is pure — indicators and info dicts in, a score and reasons out
— so the whole engine is testable without touching the network.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from ..indicators import technical as ta
from ..utils.market_data import StockSnapshot
from .alphahunter import tradability_reason
from .base import Criterion, ScanHit


# --- thresholds ------------------------------------------------------------
# Deliberately conservative: a screen that returns 400 names has found nothing.
MIN_REVENUE_GROWTH = 0.15      # +15% YoY — real growth, not GDP drift
MIN_EARNINGS_GROWTH = 0.10     # +10% YoY, when reported
MIN_GROSS_MARGIN = 0.25        # below this, growth rarely turns into profit
MAX_DIST_FROM_HIGH = 25.0      # within 25% of the 52-week high = still working
MIN_RS_VS_SPY = 0.0            # must beat the index over 3 months
RSI_OVERHEATED = 80.0          # above this we are buying the blow-off
MIN_TREND_RETURN = 0.0         # 6-month return must be positive


def _f(info: dict, key: str) -> float | None:
    v = info.get(key)
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class GrowthRead:
    score: float
    reasons: list[str]
    warnings: list[str]
    factors: dict


def growth_score(ind: dict, info: dict, spy_ret_60d: float | None = None) -> GrowthRead:
    """0-100 growth-leadership score, with the arithmetic exposed.

    Five components, weighted by how directly each one bears on "is this a
    growing business whose stock is working":

      business growth 35 | trend quality 25 | relative strength 20
      | profitability 15 | valuation sanity 5

    Valuation gets only 5 points on purpose. Growth names are chronically
    expensive and refusing to pay up is the classic way to miss every winner;
    but an infinite multiple with decelerating growth still deserves a nudge.
    """
    reasons: list[str] = []
    warnings: list[str] = []
    f: dict = {}

    # --- business growth (35) ---
    rev_g = _f(info, "revenueGrowth")
    earn_g = _f(info, "earningsGrowth") or _f(info, "earningsQuarterlyGrowth")
    f["revenue_growth"] = rev_g
    f["earnings_growth"] = earn_g
    biz = 0.0
    if rev_g is not None:
        # 15% -> half marks, 50%+ -> full marks.
        biz += max(0.0, min(1.0, (rev_g - 0.05) / 0.45)) * 22
        if rev_g >= MIN_REVENUE_GROWTH:
            reasons.append(f"revenue growing {rev_g*100:.0f}% year over year")
        else:
            warnings.append(f"revenue growth only {rev_g*100:.0f}%")
    if earn_g is not None:
        biz += max(0.0, min(1.0, (earn_g - 0.0) / 0.50)) * 13
        if earn_g >= MIN_EARNINGS_GROWTH:
            reasons.append(f"earnings growing {earn_g*100:.0f}%")
        elif earn_g < 0:
            warnings.append(f"earnings shrinking {earn_g*100:.0f}%")
    f["business_score"] = round(biz, 1)

    # --- trend quality (25) ---
    ret_120 = ind.get("ret_120d")
    dist_high = ind.get("dist_52w_high")
    above200 = ind.get("above_ema200")
    ema50, ema200 = ind.get("ema50"), ind.get("ema200")
    trend = 0.0
    if above200:
        trend += 8
        reasons.append("trading above its 200-day average")
    else:
        warnings.append("below the 200-day average — the trend is not up")
    if ema50 is not None and ema200 is not None and ema50 > ema200:
        trend += 6
        reasons.append("50-day above 200-day (uptrend intact)")
    if dist_high is not None:
        # 0% from the high -> full marks; 25% below -> zero.
        trend += max(0.0, min(1.0, 1 - abs(dist_high) / MAX_DIST_FROM_HIGH)) * 11
        if abs(dist_high) <= 10:
            reasons.append(f"within {abs(dist_high):.0f}% of its 52-week high")
        elif abs(dist_high) > MAX_DIST_FROM_HIGH:
            warnings.append(f"{abs(dist_high):.0f}% below its 52-week high")
    f["dist_52w_high"] = dist_high
    f["trend_score"] = round(trend, 1)

    # --- relative strength vs the index (20) ---
    ret_60 = ind.get("ret_60d")
    rs = None
    if ret_60 is not None and spy_ret_60d is not None:
        rs = ret_60 - spy_ret_60d
        # +20pp over 3 months is exceptional leadership.
        strength = max(0.0, min(1.0, (rs - MIN_RS_VS_SPY) / 20.0)) * 20
        if rs > 0:
            reasons.append(f"beating the market by {rs:.0f} points over 3 months")
        else:
            warnings.append(f"lagging the market by {abs(rs):.0f} points over 3 months")
    else:
        strength = 10.0 if (ret_60 or 0) > 0 else 0.0   # no benchmark: partial credit
    f["rs_vs_spy_60d"] = None if rs is None else round(rs, 1)
    f["strength_score"] = round(strength, 1)

    # --- profitability (15) ---
    gm = _f(info, "grossMargins")
    om = _f(info, "operatingMargins")
    fcf = _f(info, "freeCashflow")
    prof = 0.0
    if gm is not None:
        prof += max(0.0, min(1.0, (gm - 0.15) / 0.55)) * 8
        if gm >= 0.50:
            reasons.append(f"{gm*100:.0f}% gross margin")
        elif gm < MIN_GROSS_MARGIN:
            warnings.append(f"thin {gm*100:.0f}% gross margin")
    if om is not None and om > 0:
        prof += 4
    elif om is not None:
        warnings.append("not yet operating-profitable")
    if fcf is not None and fcf > 0:
        prof += 3
        reasons.append("free cash flow positive")
    f["gross_margin"] = gm
    f["profit_score"] = round(prof, 1)

    # --- valuation sanity (5) ---
    peg = _f(info, "pegRatio")
    fwd_pe = _f(info, "forwardPE")
    val = 2.5
    if peg is not None and 0 < peg <= 2.0:
        val = 5.0
        reasons.append(f"PEG {peg:.1f} — growth not absurdly priced")
    elif peg is not None and peg > 3.5:
        val = 0.0
        warnings.append(f"PEG {peg:.1f} — paying a lot for the growth")
    elif fwd_pe is not None and fwd_pe > 80:
        val = 0.0
        warnings.append(f"forward P/E {fwd_pe:.0f}")
    f["peg"] = peg
    f["value_score"] = round(val, 1)

    # --- the discipline check: are we late? ---
    rsi = ind.get("rsi")
    f["rsi"] = rsi
    if rsi is not None and rsi >= RSI_OVERHEATED:
        warnings.append(f"RSI {rsi:.0f} — extended, wait for a pause")

    total = biz + trend + strength + prof + val
    f["ret_60d"], f["ret_120d"] = ret_60, ret_120
    return GrowthRead(round(min(100.0, max(0.0, total)), 1), reasons, warnings, f)


class GrowthScanner:
    """Finds growing businesses whose stock is already working."""

    name = "growth"

    def __init__(self, spy_ret_60d: float | None = None, loose: bool = False) -> None:
        self.spy_ret_60d = spy_ret_60d
        # `loose` keeps names that fail the soft filters so a calm market still
        # returns a ranked list instead of an empty page.
        self.loose = loose

    def evaluate(self, snap: StockSnapshot) -> ScanHit | None:
        ind = ta.indicator_bundle(snap.history)
        last = snap.last_close
        if last is None or tradability_reason(snap, ind):
            return None

        info = snap.info or {}
        read = growth_score(ind, info, self.spy_ret_60d)

        rev_g = _f(info, "revenueGrowth")
        dist_high = ind.get("dist_52w_high")
        ret_120 = ind.get("ret_120d")
        rsi = ind.get("rsi")

        criteria: list[Criterion] = [
            Criterion("revenue_growth_15pct",
                      rev_g is not None and rev_g >= MIN_REVENUE_GROWTH,
                      f"revenue growth {rev_g*100:.0f}%" if rev_g is not None else "growth n/a"),
            Criterion("uptrend_above_ema200",
                      bool(ind.get("above_ema200")),
                      "above 200-day" if ind.get("above_ema200") else "below 200-day"),
            Criterion("near_52w_high",
                      dist_high is not None and abs(dist_high) <= MAX_DIST_FROM_HIGH,
                      f"{abs(dist_high):.0f}% off high" if dist_high is not None else "n/a"),
            Criterion("six_month_uptrend",
                      ret_120 is not None and ret_120 > MIN_TREND_RETURN,
                      f"6-month {ret_120:.0f}%" if ret_120 is not None else "n/a"),
            # Not overheated is a REQUIREMENT, not a bonus: buying a vertical
            # chart is how growth screens lose money.
            Criterion("not_overheated",
                      rsi is None or rsi < RSI_OVERHEATED,
                      f"RSI {rsi:.0f}" if rsi is not None else "RSI n/a"),
        ]
        if self.spy_ret_60d is not None:
            rs = (ind.get("ret_60d") or 0) - self.spy_ret_60d
            criteria.append(Criterion("beating_the_market", rs > MIN_RS_VS_SPY,
                                      f"{rs:+.0f}pp vs SPY (3mo)"))

        hard = {"uptrend_above_ema200", "not_overheated"}
        must_pass = [c for c in criteria if c.name in hard]
        if not all(c.passed for c in must_pass):
            return None
        if not self.loose and not all(c.passed for c in criteria):
            return None

        return ScanHit(
            ticker=snap.ticker,
            metrics={
                # score_snapshot reads its indicators from here. Omitting this
                # silently produced growth picks with NO stop, target or R:R —
                # every exit plan fell back to the flat 12%/-7% default, which
                # is exactly the kind of failure that looks fine on screen.
                "indicators": ind,
                "profile": "growth",
                "price": round(last, 2),
                "growth_score": read.score,
                "reasons": read.reasons,
                "warnings": read.warnings,
                **read.factors,
            },
            criteria=criteria,
        )
