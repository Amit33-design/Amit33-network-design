"""Exit rules — when to take the money.

The product has always said Buy and never said Sell. That is not a small gap:
the portfolio backtest in this repo found that holding the picks for 10 trading
days returned +21% while holding them indefinitely (the paper portfolio) came
out roughly flat and behind SPY. Same picks. The entire difference is the exit.

So every recommendation now carries a plan with four ways out, checked in the
order a real trader checks them:

  1. STOP   — the thesis is wrong. Cut it. Checked first, always: if a gap
              takes price through both the stop and the target, the loss is
              what actually happened to you.
  2. TARGET — the move played out. Book it.
  3. TIME   — the edge measured here is a multi-week bounce, not a multi-year
              hold. If nothing has happened by the horizon, the reason for
              owning it has expired.
  4. TRAIL  — once a position is up enough to matter, protect it. A winner
              that round-trips to breakeven is the most demoralising outcome
              in the book and the easiest to prevent.

Pure functions: prices and a plan in, a decision out. No network, no state.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import ROUND_HALF_UP, Decimal


def money(x: float) -> float:
    """Round a price to cents, half UP — the same rule as the TypeScript port.

    Python's round() is banker's rounding (half to even) and JavaScript's
    Math.round is half up, so a level landing on exactly half a cent came out
    a cent apart depending on which page you were looking at: $12.50 x 0.93 =
    11.625 was $11.62 here and $11.63 in the browser. The shared parity
    fixture caught it on its first run. Going through str() uses the shortest
    repr, so 11.625 is treated as the half it looks like rather than as its
    binary neighbour.
    """
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# Defaults come from this repo's own measurements, not from convention.
DEFAULT_HORIZON_DAYS = 10       # the holding period the backtest actually paid
DEFAULT_TARGET_PCT = 12.0       # take-profit, ~2x the typical 10-day move
DEFAULT_STOP_PCT = -7.0         # cut, sized so target:stop is better than 1.5:1
TRAIL_ARMS_AT_PCT = 8.0         # only start trailing once there is a gain worth keeping
TRAIL_GIVEBACK_PCT = 5.0        # ...then give back at most this much from the peak


@dataclass
class ExitPlan:
    entry: float
    target: float
    stop: float
    horizon_days: int
    target_pct: float
    stop_pct: float
    trail_arms_at_pct: float
    trail_giveback_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


# Moonshots are a different strategy, not a riskier version of the same one.
# Their evidence is "doubled within a year" (19% vs a 4.8% base rate, with a
# MEDIAN outcome of only +6.7%) — a fat right tail you only collect by holding.
# The generic 10-day plan put a -15% stop on stocks that move 5% a day: every
# one of the first 20 moonshot picks was stopped out within days, so the
# product was telling people to trade the profile in the one way the study
# says loses. Position size is the risk control here, not a stop.
MOONSHOT_TARGET_PCT = 100.0      # sell (at least half) at the double
MOONSHOT_HORIZON_DAYS = 252      # the study's window: one year of sessions


def build_moonshot_plan(entry: float) -> ExitPlan:
    if entry <= 0:
        raise ValueError("entry must be positive")
    return ExitPlan(
        entry=money(entry),
        target=money(entry * (1 + MOONSHOT_TARGET_PCT / 100)),
        stop=0.0,                       # no price stop: size it as a possible total loss
        horizon_days=MOONSHOT_HORIZON_DAYS,
        target_pct=MOONSHOT_TARGET_PCT,
        stop_pct=-100.0,
        trail_arms_at_pct=MOONSHOT_TARGET_PCT,   # never trails before the double
        trail_giveback_pct=TRAIL_GIVEBACK_PCT,
    )


def plan_for(entry: float, *, atr: float | None = None, profile: str | None = None) -> ExitPlan:
    """The exit plan that matches how a screen's evidence was measured."""
    if profile == "moonshot":
        return build_moonshot_plan(entry)
    return build_plan(entry, atr=atr)


def build_plan(
    entry: float,
    *,
    atr: float | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    target_pct: float = DEFAULT_TARGET_PCT,
    stop_pct: float = DEFAULT_STOP_PCT,
) -> ExitPlan:
    """Target and stop for one position.

    When ATR is known the levels widen or tighten to the stock's own volatility
    — a fixed 7% stop is noise on a name that moves 4% a day and a straitjacket
    on one that moves 0.5% — but they are clamped so a wild reading cannot
    produce an absurd plan.
    """
    if entry <= 0:
        raise ValueError("entry must be positive")

    tp, sp = target_pct, stop_pct
    if atr and atr > 0:
        atr_pct = atr / entry * 100
        # Scale to the HOLDING PERIOD, not to a single day. Volatility grows
        # with the square root of time, so a stock that moves 2% a day has a
        # ~6.5% expected range over 10 sessions — asking it for 2x its DAILY
        # ATR was both too tight and, once clamped at a 6% floor, identical
        # for almost every name. The first version handed a 2.2%-ATR stock and
        # a 2.8%-ATR stock exactly the same plan.
        horizon_move = atr_pct * (horizon_days ** 0.5)
        tp = max(5.0, min(30.0, horizon_move * 1.0))
        sp = -max(3.0, min(15.0, horizon_move * 0.6))   # ~1.67:1 reward:risk

    return ExitPlan(
        entry=money(entry),
        target=money(entry * (1 + tp / 100)),
        stop=money(entry * (1 + sp / 100)),
        horizon_days=horizon_days,
        target_pct=money(tp),
        stop_pct=money(sp),
        trail_arms_at_pct=TRAIL_ARMS_AT_PCT,
        trail_giveback_pct=TRAIL_GIVEBACK_PCT,
    )


def check_exit(
    plan: ExitPlan,
    price: float,
    *,
    days_held: int = 0,
    peak_price: float | None = None,
) -> dict:
    """Should this position be closed now, and why?

    ``peak_price`` is the highest price seen since entry; without it the trail
    cannot be evaluated and is simply skipped rather than guessed at.
    """
    gain_pct = (price / plan.entry - 1) * 100
    result = {
        "action": "hold",
        "reason": "",
        "gain_%": round(gain_pct, 2),
        "days_held": days_held,
    }

    # 1. Stop first — if both levels were breached, the loss is the real event.
    if price <= plan.stop:
        result.update(action="sell", reason=(
            f"stop hit at ${plan.stop:.2f} ({plan.stop_pct:.1f}%). The reason for "
            f"owning it is gone; take the small loss."))
        return result

    # 2. Target.
    if price >= plan.target:
        result.update(action="take_profit", reason=(
            f"target hit at ${plan.target:.2f} ({plan.target_pct:+.1f}%). "
            f"Book it — this is the move the setup was predicting."))
        return result

    # 3. Trailing stop, once there is a real gain to protect.
    if peak_price is not None and peak_price > plan.entry:
        peak_gain = (peak_price / plan.entry - 1) * 100
        giveback = (peak_price - price) / peak_price * 100
        if peak_gain >= plan.trail_arms_at_pct and giveback >= plan.trail_giveback_pct:
            result.update(action="take_profit", reason=(
                f"was up {peak_gain:.1f}% and has given back {giveback:.1f}% from "
                f"the high. Protect the gain rather than watch it round-trip."))
            return result

    # 4. Time. The measured edge is a multi-week move; past that the thesis
    #    has simply not worked, whatever the price is doing.
    if days_held >= plan.horizon_days:
        result.update(action="close_stale", reason=(
            f"{days_held} trading days held with no target or stop hit "
            f"({gain_pct:+.1f}%). The setup's window has passed — free the capital."))
        return result

    left = plan.horizon_days - days_held
    result["reason"] = (
        f"{gain_pct:+.1f}% · target ${plan.target:.2f} / stop ${plan.stop:.2f} · "
        f"{left} day{'s' if left != 1 else ''} left in the window")
    return result
