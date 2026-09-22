"""Is this stock trending, or has it gone sideways — and where in the range?

A verdict of "Buy" is close to useless without a price attached. A stock that
has oscillated between $80 and $120 all year is a buy at $85 and a bad trade
at $118, and the same technicals can be true at both. The usual fix — buy when
RSI is low — fails here because a range-bound stock spends most of its time
with unremarkable RSI.

So this classifies the last year into one of three regimes and, when the
answer is "sideways", says what to wait for:

  TRENDING UP    price is going somewhere, and a pullback is an entry rather
                 than a warning.
  TRENDING DOWN  the range low is not support, it is a waypoint.
  LATERAL        the range is the whole story. Position within it decides
                 everything, and buying the top half is how people lose money
                 in a stock that "did nothing".

Classification uses three things together, because any one alone is fooled:
a small net move (a stock can round-trip 40% and end flat), a low R-squared on
the trend line (drift with noise looks like a range over short windows), and
repeated crossings of the midline (what actually distinguishes an oscillation
from a slow drift).

Pure functions over price lists. No network. Keep in parity with
`api/_regime.js`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

WINDOW = 252                 # ~1 trading year
LATERAL_NET_MOVE = 18.0      # |net move| under this is "went nowhere"
LATERAL_R2 = 0.35            # trend explains little of the variance
TREND_R2 = 0.55              # ...versus a convincing trend
MIN_CROSSINGS = 3            # a range oscillates; a drift does not
BUY_ZONE = 0.35              # bottom third of the range
WAIT_ZONE = 0.65             # above this, wait rather than chase


@dataclass
class RangeRead:
    regime: str                      # trending_up | trending_down | lateral | unclear
    position: float | None           # 0 = at the low, 1 = at the high
    low: float | None = None
    high: float | None = None
    net_move_pct: float | None = None
    range_width_pct: float | None = None
    r2: float | None = None
    crossings: int = 0
    # Entry guidance, only meaningful when lateral.
    action: str = "none"             # buy_zone | wait | none
    entry_target: float | None = None
    upside_to_range_high_pct: float | None = None
    typical_wait_sessions: int | None = None
    reason: str = ""
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "position_in_range": round(self.position, 3) if self.position is not None else None,
            "range_low": self.low, "range_high": self.high,
            "net_move_%": self.net_move_pct,
            "range_width_%": self.range_width_pct,
            "trend_r2": self.r2,
            "midline_crossings": self.crossings,
            "action": self.action,
            "entry_target": self.entry_target,
            "upside_to_range_high_%": self.upside_to_range_high_pct,
            "typical_wait_sessions": self.typical_wait_sessions,
            "reason": self.reason,
            "factors": self.factors,
        }


def _r2_of_log_trend(closes: list[float]) -> float | None:
    """How much of the price path a straight line explains.

    On log price, so a constant percentage growth rate is a straight line —
    otherwise every compounder looks curved and scores as non-trending.
    """
    pts = [(i, math.log(c)) for i, c in enumerate(closes) if c and c > 0]
    n = len(pts)
    if n < 20:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    syy = sum((y - my) ** 2 for _, y in pts)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return max(0.0, min(1.0, (sxy * sxy) / (sxx * syy)))


def _midline_crossings(closes: list[float], low: float, high: float) -> int:
    """How many times price crossed the middle of the range.

    This is what separates a genuine oscillation from a slow drift that merely
    happens to end near where it started.
    """
    mid = (low + high) / 2
    crossings, above = 0, None
    for c in closes:
        now = c > mid
        if above is not None and now != above:
            crossings += 1
        above = now
    return crossings


def _typical_wait(closes: list[float], low: float, high: float,
                  target: float) -> int | None:
    """Median sessions between visits to the lower part of the range.

    Answers the question a "wait" recommendation immediately raises — wait how
    long? — with history rather than a shrug.
    """
    visits = [i for i, c in enumerate(closes) if c <= target]
    if len(visits) < 2:
        return None
    # Collapse consecutive sessions into one visit.
    gaps, last = [], visits[0]
    for v in visits[1:]:
        if v - last > 5:
            gaps.append(v - last)
        last = v
    if not gaps:
        return None
    gaps.sort()
    return int(gaps[len(gaps) // 2])


def analyse(closes: list[float], window: int = WINDOW) -> RangeRead:
    """Classify the regime and, if lateral, give entry guidance."""
    px = [float(c) for c in closes if c and float(c) > 0]
    if len(px) < 60:
        return RangeRead("unclear", None, reason="not enough history to judge a range")

    w = px[-window:] if len(px) > window else px
    last = w[-1]
    low, high = min(w), max(w)
    if high <= low:
        return RangeRead("unclear", None, reason="degenerate price range")

    position = (last - low) / (high - low)
    # Net move from the MEDIAN of the first and last fifth, not from single
    # endpoint bars. A single first bar makes the answer depend on where the
    # window happens to start: a stock oscillating around $100 that closes at
    # its $82 low reads as -18% and gets called a downtrend, when nothing
    # about the stock changed — only the window did.
    seg = max(3, len(w) // 5)
    head = sorted(w[:seg])[seg // 2]
    tail = sorted(w[-seg:])[seg // 2]
    net_move = (tail / head - 1) * 100 if head > 0 else 0.0
    width = (high - low) / low * 100
    r2 = _r2_of_log_trend(w) or 0.0
    crossings = _midline_crossings(w, low, high)

    read = RangeRead("unclear", position, round(low, 2), round(high, 2),
                     round(net_move, 1), round(width, 1), round(r2, 3), crossings)

    # "Lateral" requires all three: it went nowhere, a line does not explain
    # it, and it actually oscillated. Dropping the last condition is how a
    # stock that rose 40% and gave it all back gets called range-bound — it
    # ends flat but never traded a range, and buying its "range low" would
    # mean buying a downtrend at the worst moment.
    lateral = (abs(net_move) < LATERAL_NET_MOVE and r2 < LATERAL_R2
               and crossings >= MIN_CROSSINGS)
    if lateral:
        read.regime = "lateral"
    elif r2 >= TREND_R2:
        read.regime = "trending_up" if net_move > 0 else "trending_down"
    elif net_move > LATERAL_NET_MOVE:
        read.regime = "trending_up"
    elif net_move < -LATERAL_NET_MOVE:
        read.regime = "trending_down"
    else:
        # Went nowhere, but without the oscillation that makes a range
        # tradeable. Saying so beats inventing an entry target from a range
        # the stock never respected.
        read.regime = "unclear"

    read.factors = [
        f"{net_move:+.0f}% over the window against a {width:.0f}%-wide range",
        f"trend line explains {r2 * 100:.0f}% of the move",
        f"crossed the midline {crossings} times",
        f"sitting {position * 100:.0f}% of the way up the range",
    ]

    if read.regime == "unclear":
        read.action = "none"
        read.reason = (
            "Roughly flat over the window, but it never oscillated between two "
            "levels — so there is no range to buy the bottom of. Position "
            "within the high-low band is not meaningful here.")
        return read

    if read.regime != "lateral":
        direction = "up" if read.regime == "trending_up" else "down"
        read.action = "none"
        read.reason = (
            f"Trending {direction}, not range-bound — the range low is not a "
            f"reliable entry and position within it says little.")
        return read

    # --- lateral: the position in the range IS the decision ---
    target = low + BUY_ZONE * (high - low)
    read.entry_target = round(target, 2)
    read.upside_to_range_high_pct = round((high / last - 1) * 100, 1)
    read.typical_wait_sessions = _typical_wait(w, low, high, target)

    if position <= BUY_ZONE:
        read.action = "buy_zone"
        read.reason = (
            f"Sideways for the window and trading in the bottom "
            f"{position * 100:.0f}% of its ${low:,.2f}-${high:,.2f} range. This is "
            f"where a range-bound name is worth buying — about "
            f"{read.upside_to_range_high_pct:.0f}% back to the top of the range.")
    elif position >= WAIT_ZONE:
        read.action = "wait"
        wait_txt = (f" It has revisited that area roughly every "
                    f"{read.typical_wait_sessions} sessions."
                    if read.typical_wait_sessions else "")
        read.reason = (
            f"Sideways for the window and already {position * 100:.0f}% of the way "
            f"up its ${low:,.2f}-${high:,.2f} range. Buying here pays near the top "
            f"of a range that has gone nowhere — wait for roughly "
            f"${target:,.2f}.{wait_txt}")
    else:
        read.action = "wait"
        read.reason = (
            f"Sideways for the window, mid-range at {position * 100:.0f}%. "
            f"Neither cheap nor extended — a patient entry near ${target:,.2f} "
            f"is worth more than the {read.upside_to_range_high_pct:.0f}% left to "
            f"the top of the range.")
    return read
