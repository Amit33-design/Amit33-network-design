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
        # 2 ATR to the target, 1.2 ATR to the stop, then clamped to sane bounds.
        tp = max(6.0, min(30.0, atr_pct * 2.0))
        sp = -max(3.0, min(15.0, atr_pct * 1.2))

    return ExitPlan(
        entry=round(entry, 2),
        target=round(entry * (1 + tp / 100), 2),
        stop=round(entry * (1 + sp / 100), 2),
        horizon_days=horizon_days,
        target_pct=round(tp, 2),
        stop_pct=round(sp, 2),
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
