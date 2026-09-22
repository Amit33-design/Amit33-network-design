"""Validate every price series before it is computed on or displayed.

One obviously-wrong number destroys trust in every number on the page, so bad
bars are caught at the boundary rather than after they have propagated through
five indicators and a recommendation.

WHAT THIS CATCHES
  * null, zero or negative closes and volumes — impossible, always dropped;
  * single-day moves beyond a threshold, which are usually an unadjusted
    corporate action or a bad tick;
  * closes far outside the series' own recent range;
  * a bad LATEST bar, which is the dangerous case: it is the number shown on
    the dashboard. That bar is quarantined and the last good one shown
    instead, flagged `stale`, because a slightly old price beats a wrong one.

WHAT THIS DOES NOT CATCH, and it matters
  A series that is internally consistent but wrong in LEVEL. If a provider
  returns a whole series on the wrong split basis, every bar agrees with its
  neighbours, no daily move is unusual, and nothing here fires. MU showing
  $1,042 was reported as an impossible price, but its 30-day series moves
  smoothly from $861 with a largest daily change of 7% — so this layer would
  pass it, correctly, because there is no internal evidence of an error.
  Detecting that needs a second independent source, not a consistency check,
  and claiming otherwise would be false comfort.

Pure functions. No network.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# 40%, not 50%: a 2:1 split is exactly -50%, and adjacent-price drift puts the
# observed ratio just under any 50% threshold, so the most common corporate
# action slipped through the net entirely.
MAX_DAILY_MOVE = 0.40
SANITY_BAND = 3.0            # 3x outside the recent range
# Ratios near a common split factor are treated as a corporate action rather
# than corrupt data — the distinction changes what you do about it.
SPLIT_RATIOS = (2.0, 3.0, 4.0, 5.0, 7.0, 10.0, 20.0)
SPLIT_TOLERANCE = 0.06


@dataclass
class QualityReport:
    clean_dates: list[str] = field(default_factory=list)
    clean_closes: list[float] = field(default_factory=list)
    clean_volumes: list[float] = field(default_factory=list)
    dropped: int = 0
    flags: list[dict] = field(default_factory=list)
    quality: str = "ok"           # ok | stale | unusable
    display_close: float | None = None
    display_date: str | None = None

    @property
    def is_stale(self) -> bool:
        return self.quality == "stale"

    def to_dict(self) -> dict:
        return {
            "data_quality": self.quality,
            "bars": len(self.clean_closes),
            "dropped": self.dropped,
            "flags": self.flags[:10],
            "display_close": self.display_close,
            "display_date": self.display_date,
        }


def _looks_like_split(ratio: float) -> float | None:
    """The SPLIT FACTOR this price ratio resembles, or None.

    Returns the factor, not the ratio: a 2:1 split halves the price, giving a
    ratio of 0.5, and it should be reported as "2:1" rather than "0.5:1".
    """
    for r in SPLIT_RATIOS:
        if abs(ratio - r) / r <= SPLIT_TOLERANCE:          # reverse split
            return r
        inv = 1 / r
        if abs(ratio - inv) / inv <= SPLIT_TOLERANCE:      # forward split
            return r
    return None


def validate_bars(
    dates: list[str],
    closes: list[float],
    volumes: list[float] | None = None,
    *,
    ticker: str = "?",
    max_daily_move: float = MAX_DAILY_MOVE,
) -> QualityReport:
    """Clean a series and decide what price is safe to display."""
    rep = QualityReport()
    vols = volumes or [0.0] * len(closes)

    # --- impossible values ---
    for i, (d, c) in enumerate(zip(dates, closes)):
        v = vols[i] if i < len(vols) else 0.0
        try:
            c = float(c)
            v = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            rep.dropped += 1
            continue
        if c is None or c <= 0 or v < 0:
            rep.dropped += 1
            continue
        rep.clean_dates.append(d)
        rep.clean_closes.append(c)
        rep.clean_volumes.append(v)

    if len(rep.clean_closes) < 2:
        rep.quality = "unusable"
        log.warning("[data_quality] %s: only %d usable bars",
                    ticker, len(rep.clean_closes))
        return rep

    # --- suspicious jumps ---
    for i in range(1, len(rep.clean_closes)):
        prev, cur = rep.clean_closes[i - 1], rep.clean_closes[i]
        move = cur / prev - 1
        if abs(move) <= max_daily_move:
            continue
        split = _looks_like_split(cur / prev)
        flag = {
            "date": rep.clean_dates[i],
            "kind": "possible_split" if split else "suspicious_jump",
            "move_%": round(move * 100, 1),
            "detail": (f"{cur / prev:.2f}x move resembles a {split:g}:1 split — "
                       f"likely an unadjusted corporate action"
                       if split else
                       f"{move * 100:+.1f}% in one day with no matching split ratio"),
        }
        rep.flags.append(flag)
        log.warning("[data_quality] %s %s: %s", ticker, flag["date"], flag["detail"])

    # --- level sanity against the series' own range ---
    # The reference window EXCLUDES the latest bar. Including it meant the bar
    # under suspicion set the range it was being compared against, so a 10x
    # spike became the new high and was, by construction, never out of band.
    prior = rep.clean_closes[:-1]
    window = prior[-252:] if len(prior) > 252 else prior
    last, last_date = rep.clean_closes[-1], rep.clean_dates[-1]
    lo, hi = (min(window), max(window)) if window else (last, last)
    out_of_band = bool(window) and hi > 0 and (
        last > hi * SANITY_BAND or last < lo / SANITY_BAND)
    if out_of_band:
        rep.flags.append({
            "date": last_date, "kind": "out_of_band",
            "detail": (f"${last:,.2f} sits outside {SANITY_BAND:g}x the recent "
                       f"${lo:,.2f}-${hi:,.2f} range"),
        })
        log.warning("[data_quality] %s: latest bar out of band (%.2f)", ticker, last)

    # --- quarantine the latest bar if IT is the problem ---
    #
    # Deliberately NOT "any large move". Stocks really do fall 45% in a day,
    # and replacing that with yesterday's price during a genuine crash would
    # be the most damaging thing this layer could do. Only two things get
    # quarantined: a level outside the series' own range, and a jump that
    # matches a split ratio — an unadjusted corporate action, where the price
    # is wrong rather than merely dramatic.
    latest_bad = out_of_band or any(
        f["date"] == last_date and f["kind"] == "possible_split" for f in rep.flags)
    if latest_bad and len(rep.clean_closes) >= 2:
        rep.quality = "stale"
        rep.display_close = rep.clean_closes[-2]
        rep.display_date = rep.clean_dates[-2]
        log.warning("[data_quality] %s: quarantined %s, showing %s instead",
                    ticker, last_date, rep.display_date)
    else:
        rep.display_close = last
        rep.display_date = last_date
    return rep
