"""Morning report generator (spec: "Generate at 7AM").

Runs the AlphaHunter scan once and slices the ranked results into the report
buckets the spec lists: top stocks, oversold, breakouts, covered calls, CSPs,
LEAPS candidates, plus a coarse market-regime read.
"""
from __future__ import annotations

import datetime as dt

from backend.scanners.runner import run_scan
from backend.utils.market_data import MarketData


def _market_regime() -> dict:
    """Very coarse SPY-based regime read (trend + breadth proxy)."""
    md = MarketData()
    spy = md.snapshot("SPY")
    if spy is None or spy.last_close is None:
        return {"regime": "unknown", "risk_level": "medium"}
    from backend.indicators import technical as ta
    ind = ta.indicator_bundle(spy.history)
    above = ind.get("above_ema200")
    r20 = ind.get("ret_20d") or 0
    if above and r20 > 0:
        regime, risk = "risk-on (uptrend)", "low"
    elif above:
        regime, risk = "neutral (consolidating)", "medium"
    else:
        regime, risk = "risk-off (downtrend)", "high"
    return {"regime": regime, "risk_level": risk, "spy_20d_%": round(r20, 1)}


def generate_morning_report(limit: int | None = None) -> dict:
    results = run_scan(require_all=False, limit=limit)

    def top(pred, n=10):
        return [r for r in results if pred(r)][:n]

    report = {
        "date": dt.date.today().isoformat(),
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "market": _market_regime(),
        "counts": {"scanned_hits": len(results)},
        "top_stocks": results[:20],
        "top_oversold": top(lambda r: (r["metrics"].get("rsi") or 100) < 35),
        "top_breakouts": top(lambda r: r["metrics"].get("above_ema200") is True),
        "top_covered_calls": top(lambda r: r.get("covered_call")),
        "top_csp": top(lambda r: r.get("cash_secured_put")),
        "top_high_conviction": top(lambda r: r["confidence"] == "High"),
    }
    return report
