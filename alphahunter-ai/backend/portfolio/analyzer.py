"""Portfolio analyzer.

Imports holdings (ticker, quantity, cost basis), then for every position
computes gain/loss, scores it with the same engines used for discovery, and
emits a position-level recommendation (Hold / Buy More / Reduce / Sell /
Covered Call / Cash Secured Put / Protective Put).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.options.analyzer import summarize_options
from backend.scoring import engines
from backend.config import settings
from backend.indicators import technical as ta
from backend.utils.market_data import MarketData


@dataclass
class Position:
    ticker: str
    quantity: float
    cost_basis: float   # per-share


def _position_recommendation(score: float, gain_pct: float, opt: dict | None) -> str:
    if score >= 70:
        return "Buy More"
    if score >= 55:
        # Healthy but mature — harvest premium.
        if opt and opt.get("covered_call_idea"):
            return "Hold / Covered Call"
        return "Hold"
    if score >= 40:
        if gain_pct < -15 and opt and opt.get("csp_idea"):
            return "Hold / Protective Put"
        return "Reduce"
    return "Sell"


def analyze_portfolio(positions: list[Position]) -> dict:
    md = MarketData()
    rows = []
    total_value = 0.0
    total_cost = 0.0

    for pos in positions:
        snap = md.snapshot(pos.ticker)
        if snap is None or snap.last_close is None:
            rows.append({"ticker": pos.ticker, "error": "no data"})
            continue
        last = snap.last_close
        ind = ta.indicator_bundle(snap.history)

        subs = {
            "technical": engines.technical_score(ind).score,
            "fundamental": engines.fundamental_score(snap.info).score,
            "momentum": engines.momentum_score(ind).score,
            "sentiment": engines.sentiment_score(snap.info, last).score,
        }
        chain = md.options_chain(pos.ticker)
        opt = summarize_options(chain, last) if chain else None
        subs["options"] = engines.options_score(opt).score

        weights = settings.score_weights
        overall = round(sum(subs[n] * w for n, w in weights.items()), 1)

        value = last * pos.quantity
        cost = pos.cost_basis * pos.quantity
        gain = value - cost
        gain_pct = (gain / cost * 100.0) if cost else 0.0
        total_value += value
        total_cost += cost

        rows.append({
            "ticker": pos.ticker,
            "quantity": pos.quantity,
            "cost_basis": pos.cost_basis,
            "price": round(last, 2),
            "market_value": round(value, 2),
            "gain_loss": round(gain, 2),
            "gain_loss_%": round(gain_pct, 1),
            "scores": {k: round(v, 1) for k, v in subs.items()},
            "overall_score": overall,
            "recommendation": _position_recommendation(overall, gain_pct, opt),
            "covered_call": (opt or {}).get("covered_call_idea"),
            "cash_secured_put": (opt or {}).get("csp_idea"),
        })

    total_gain = total_value - total_cost
    return {
        "summary": {
            "market_value": round(total_value, 2),
            "cost_basis": round(total_cost, 2),
            "gain_loss": round(total_gain, 2),
            "gain_loss_%": round((total_gain / total_cost * 100.0), 1) if total_cost else 0.0,
            "positions": len([r for r in rows if "error" not in r]),
        },
        "positions": rows,
    }
