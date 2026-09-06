"""What annual profit is realistic — and what it would take.

A profit target is not an algorithm setting. It is arithmetic on three inputs:
how much capital is at work, what the strategy actually returns per trade, and
how many trades a year it produces. Getting this wrong in the optimistic
direction is how people size positions that blow up.

So this module refuses to be encouraging. It computes what the CURRENT measured
edge implies, and separately what capital or per-trade edge a stated income
goal would require — then names the gap. If the goal needs a 200% annual
return, it says so.

Pure functions throughout: numbers in, numbers out.
"""
from __future__ import annotations

import math

TRADING_DAYS = 252


def project(
    capital: float,
    *,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    trades_per_year: int,
    concurrent_positions: int,
    fraction_deployed: float = 1.0,
) -> dict:
    """Expected annual P&L from a measured edge.

    ``avg_loss_pct`` is given as a positive magnitude. Returns both the
    straight expectation and a volatility band, because a single expected
    value invites people to plan around a number they will not get.
    """
    if capital <= 0 or concurrent_positions <= 0:
        raise ValueError("capital and concurrent_positions must be positive")

    per_trade_pct = win_rate * avg_win_pct - (1 - win_rate) * abs(avg_loss_pct)
    position_size = capital * fraction_deployed / concurrent_positions
    expected = position_size * (per_trade_pct / 100) * trades_per_year

    # Spread of outcomes: per-trade standard deviation scaled by sqrt(n). This
    # is the honest part — the range is usually wider than the expectation.
    var = (win_rate * (avg_win_pct - per_trade_pct) ** 2
           + (1 - win_rate) * (-abs(avg_loss_pct) - per_trade_pct) ** 2)
    sd_trade = math.sqrt(max(var, 0.0))
    sd_annual = position_size * (sd_trade / 100) * math.sqrt(max(trades_per_year, 1))

    return {
        "capital": round(capital, 2),
        "position_size": round(position_size, 2),
        "concurrent_positions": concurrent_positions,
        "trades_per_year": trades_per_year,
        "edge_per_trade_%": round(per_trade_pct, 3),
        "expected_annual_profit": round(expected, 2),
        "expected_annual_return_%": round(expected / capital * 100, 2),
        # Roughly a 1-sigma band. Not a guarantee, and deliberately shown.
        "range_low": round(expected - sd_annual, 2),
        "range_high": round(expected + sd_annual, 2),
        "profitable_edge": per_trade_pct > 0,
    }


def capital_required(
    goal: float,
    *,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    trades_per_year: int,
    concurrent_positions: int,
) -> float | None:
    """Capital needed to expect ``goal`` per year. None if the edge is negative.

    With a negative edge no amount of capital reaches a positive goal — more
    money just loses faster — so this returns None rather than a large number.
    """
    per_trade_pct = win_rate * avg_win_pct - (1 - win_rate) * abs(avg_loss_pct)
    if per_trade_pct <= 0:
        return None
    per_position_annual = (per_trade_pct / 100) * trades_per_year
    return round(goal / per_position_annual * concurrent_positions, 2)


def assess(goal: float, capital: float, **edge) -> dict:
    """Compare a stated income goal against what the edge and capital support."""
    proj = project(capital, **edge)
    needed = capital_required(goal, **{k: v for k, v in edge.items()
                                       if k != "fraction_deployed"})
    required_return = goal / capital * 100 if capital > 0 else float("inf")

    if not proj["profitable_edge"]:
        verdict = (
            f"The measured edge is negative ({proj['edge_per_trade_%']}% per trade), "
            f"so no amount of capital reaches ${goal:,.0f} a year — more money "
            f"would only lose faster. The edge has to become positive first.")
        feasible = False
    elif needed is not None and needed <= capital:
        verdict = (
            f"Reachable: ${capital:,.0f} at this edge expects "
            f"${proj['expected_annual_profit']:,.0f} a year, which covers the "
            f"${goal:,.0f} goal.")
        feasible = True
    else:
        verdict = (
            f"${goal:,.0f} a year on ${capital:,.0f} means a "
            f"{required_return:.0f}% annual return. This edge expects "
            f"{proj['expected_annual_return_%']:.1f}%, so the goal needs about "
            f"${needed:,.0f} of capital — roughly {needed/capital:.1f}x what is "
            f"deployed. Sizing up to force the goal is how accounts get ruined; "
            f"the honest options are more capital, more time, or a better edge.")
        feasible = False

    return {
        "goal": goal,
        "required_return_%": round(required_return, 1),
        "capital_required": needed,
        "feasible": feasible,
        "verdict": verdict,
        **proj,
    }


def edge_from_history(holdings: list[dict]) -> dict | None:
    """Measure win rate and average win/loss from paper-portfolio holdings.

    The point of deriving these rather than assuming them: the projection is
    then a statement about THIS system, not about a hypothetical good one.
    """
    rets = [h["return_%"] for h in holdings
            if h.get("priced") and h.get("return_%") is not None]
    if len(rets) < 20:
        return None
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    return {
        "win_rate": round(len(wins) / len(rets), 4),
        "avg_win_pct": round(sum(wins) / len(wins), 3) if wins else 0.0,
        "avg_loss_pct": round(abs(sum(losses) / len(losses)), 3) if losses else 0.0,
        "sample": len(rets),
    }
