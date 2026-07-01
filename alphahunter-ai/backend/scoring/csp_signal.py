"""CSP-on-dip signal.

Flags the classic income entry: the stock is DOWN today, but the chart says the
larger trend is intact (above EMA200 / analyst upside) and the historical data
says this kind of dip has tended to bounce — so selling a cash-secured put into
the weakness gets paid elevated premium for a strike you'd be happy owning.

Output shape (always present, explainable either way):
    {"active": bool, "strength": "strong"|"moderate"|None,
     "suggested_strike": float|None, "idea": str|None, "reason": str}
"""
from __future__ import annotations

from backend.config import settings


def compute_csp_signal(
    day_change: float | None,
    above_ema200: bool | None,
    analyst_upside: float | None,
    bt: dict,
    opt_metrics: dict | None,
    last: float | None,
    atr: float | None,
) -> dict:
    out = {"active": False, "strength": None, "suggested_strike": None,
           "idea": None, "reason": ""}

    if day_change is None or day_change > settings.csp_dip_day_pct:
        out["reason"] = "no meaningful dip today"
        return out

    # Upside potential per the chart / street.
    chart_up = bool(above_ema200)
    street_up = analyst_upside is not None and analyst_upside >= settings.csp_min_upside
    if not (chart_up or street_up):
        out["reason"] = f"down {day_change:.1f}% but no upside signal (below EMA200, <{settings.csp_min_upside:.0f}% target upside)"
        return out

    # Historical bounce evidence (from the setup backtest already computed).
    trades = bt.get("hist_trades", 0)
    win = bt.get("hist_win_rate", 0.0)
    avg = bt.get("hist_avg_return_%", 0.0)
    if trades >= 3 and (win < 0.45 or avg < 0):
        out["reason"] = (f"down {day_change:.1f}% with upside signals, but history is against it "
                         f"(bounced only {win*100:.0f}% of {trades} dips)")
        return out

    strong = trades >= 3 and win >= settings.csp_min_hist_win and avg > 0
    out["active"] = True
    out["strength"] = "strong" if strong else "moderate"

    # Strike: prefer the live chain's OTM put; else ~1.5 ATR below spot.
    if opt_metrics and opt_metrics.get("csp_idea"):
        out["idea"] = opt_metrics["csp_idea"]
    if last is not None and atr:
        out["suggested_strike"] = round(last - 1.5 * atr, 2)

    why = [f"down {day_change:.1f}% today"]
    if chart_up:
        why.append("uptrend intact (above EMA200)")
    if street_up:
        why.append(f"{analyst_upside:.0f}% upside to target")
    if strong:
        why.append(f"historically bounced {win*100:.0f}% of {trades} similar dips (avg {avg:+.1f}%)")
    elif trades >= 3:
        why.append(f"bounce history mixed ({win*100:.0f}% of {trades})")
    else:
        why.append("limited dip history")
    out["reason"] = "; ".join(why)
    return out
