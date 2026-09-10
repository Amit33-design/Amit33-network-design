"""Market regime — the context every single-stock score was missing.

Every score in this product is computed for one ticker in isolation, as if the
market around it did not exist. That is a real omission: the same setup is
worth very different things depending on whether the index is trending up with
broad participation or falling with everything correlating to one.

Four inputs, all computable from data the scan already fetches:

  TREND       where the index sits against its own 50/200-day structure.
  BREADTH     what fraction of the watchlist is above its 200-day. Breadth
              deteriorating while the index holds up is the classic warning —
              an index carried by a handful of names.
  VOLATILITY  realized volatility of the index, as a stand-in for VIX. Rising
              realized vol means wider stops and smaller positions, not just
              a gloomier mood.
  LEADERSHIP  are offensive sectors leading defensive ones?

The output is a regime label plus a `position_scale` — an explicit multiplier
on position size. That is the honest way to use a regime read: it changes how
much you commit, not whether the individual analysis was right.

Pure functions over price series. No network.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegimeRead:
    regime: str                # risk-on | neutral | risk-off
    score: float               # 0..100
    position_scale: float      # multiplier on position size
    factors: list[str]
    detail: dict


def _sma(xs: list[float], n: int) -> float | None:
    return sum(xs[-n:]) / n if len(xs) >= n else None


def _ret(xs: list[float], n: int) -> float | None:
    if len(xs) <= n or xs[-1 - n] == 0:
        return None
    return (xs[-1] / xs[-1 - n] - 1) * 100.0


def realized_vol(closes: list[float], window: int = 20) -> float | None:
    """Annualised realized volatility, in percent."""
    if len(closes) < window + 1:
        return None
    rets = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - window, len(closes))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
    return (var ** 0.5) * (252 ** 0.5) * 100.0


def breadth(above_200_flags: list[bool]) -> float | None:
    """Share of a universe trading above its own 200-day, 0..1."""
    flags = [f for f in above_200_flags if f is not None]
    return (sum(1 for f in flags if f) / len(flags)) if flags else None


def assess(
    index_closes: list[float],
    *,
    above_200_flags: list[bool] | None = None,
    offensive_ret: float | None = None,
    defensive_ret: float | None = None,
) -> RegimeRead:
    """Read the market's posture.

    ``offensive_ret`` / ``defensive_ret`` are recent returns for a growth-ish
    and a defensive sector proxy (e.g. XLK vs XLU). Leadership is skipped
    rather than guessed when they are absent.
    """
    factors: list[str] = []
    detail: dict = {}
    score = 50.0

    if len(index_closes) < 60:
        return RegimeRead("unknown", 50.0, 1.0,
                          ["not enough index history to read a regime"], {})

    last = index_closes[-1]
    s50, s200 = _sma(index_closes, 50), _sma(index_closes, 200)
    detail["index_last"] = round(last, 2)

    # --- trend (up to ±25) ---
    if s200:
        above200 = last > s200
        score += 15 if above200 else -20
        factors.append("index above its 200-day" if above200
                       else "index BELOW its 200-day — the tape is not on your side")
        detail["above_200"] = above200
    if s50 and s200:
        golden = s50 > s200
        score += 10 if golden else -10
        factors.append("50-day above 200-day" if golden else "50-day below 200-day")
        detail["golden_cross"] = golden

    r20 = _ret(index_closes, 20)
    if r20 is not None:
        detail["index_1m_%"] = round(r20, 2)
        if r20 < -5:
            score -= 10
            factors.append(f"index down {abs(r20):.1f}% in a month")

    # --- breadth (up to ±20) ---
    b = breadth(above_200_flags or [])
    if b is not None:
        detail["breadth"] = round(b, 2)
        score += (b - 0.5) * 40.0
        pct = b * 100
        if b >= 0.6:
            factors.append(f"broad participation — {pct:.0f}% of the board above its 200-day")
        elif b <= 0.35:
            factors.append(f"narrow market — only {pct:.0f}% of the board above its 200-day")
        else:
            factors.append(f"mixed participation ({pct:.0f}% above the 200-day)")

    # --- volatility (up to -20) ---
    vol = realized_vol(index_closes)
    if vol is not None:
        detail["realized_vol_%"] = round(vol, 1)
        if vol > 30:
            score -= 20
            factors.append(f"realized volatility {vol:.0f}% — size down, stops need room")
        elif vol > 20:
            score -= 8
            factors.append(f"elevated volatility ({vol:.0f}%)")
        else:
            score += 5
            factors.append(f"calm tape ({vol:.0f}% realized vol)")

    # --- leadership (up to ±10) ---
    if offensive_ret is not None and defensive_ret is not None:
        spread = offensive_ret - defensive_ret
        detail["offense_minus_defense_pp"] = round(spread, 1)
        score += max(-10.0, min(10.0, spread / 5.0 * 10.0))
        factors.append(
            f"offensive sectors {'leading' if spread > 0 else 'lagging'} defensives by {abs(spread):.1f}pp")

    score = max(0.0, min(100.0, score))
    if score >= 62:
        regime, scale = "risk-on", 1.0
    elif score >= 40:
        regime, scale = "neutral", 0.75
    else:
        regime, scale = "risk-off", 0.5

    return RegimeRead(regime, round(score, 1), scale, factors, detail)


def apply_to_position(shares: int, read: RegimeRead) -> dict:
    """Scale a position by the regime, and say so.

    Explicit rather than silent: a regime read that quietly halves your size
    without telling you is worse than no regime read at all.
    """
    scaled = int(shares * read.position_scale)
    return {
        "shares": scaled,
        "original_shares": shares,
        "scale": read.position_scale,
        "reason": (f"{read.regime} market ({read.score}/100) — "
                   + ("full size" if read.position_scale >= 1.0
                      else f"sized to {int(read.position_scale * 100)}% of normal")),
    }
