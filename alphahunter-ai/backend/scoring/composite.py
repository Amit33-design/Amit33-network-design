"""Composite AI score + full StockRecommendation assembly.

Blends the five sub-scores with the spec weights (35/25/20/10/10) into a single
0-100 number, then builds the complete recommendation payload from the spec's
"Stock Recommendation Output" section: entry, stop, targets, R:R, options
ideas, confidence, and a plain-English explanation citing score contributions.
"""
from __future__ import annotations

from backend.config import settings
from backend.options.analyzer import summarize_options
from backend.scanners.base import ScanHit
from backend.scoring import engines
from backend.utils.market_data import MarketData, StockSnapshot


def _action_from_score(score: float) -> str:
    if score >= 75:
        return "Buy"
    if score >= 60:
        return "Accumulate"
    if score >= 45:
        return "Hold"
    if score >= 30:
        return "Reduce"
    return "Sell"


def _confidence(hit: ScanHit, score: float) -> str:
    passed = len(hit.passed_names)
    total = len(hit.criteria)
    if score >= 70 and passed == total:
        return "High"
    if score >= 55 and passed >= total - 1:
        return "Medium"
    return "Low"


def score_snapshot(snap: StockSnapshot, hit: ScanHit, md: MarketData | None = None) -> dict:
    ind = hit.metrics.get("indicators", {})
    last = snap.last_close

    # Options metrics (best-effort; safe if no chain).
    opt_metrics = None
    if md is not None:
        chain = md.options_chain(snap.ticker)
        opt_metrics = summarize_options(chain, last) if chain else None

    subs = [
        engines.technical_score(ind),
        engines.fundamental_score(snap.info),
        engines.options_score(opt_metrics),
        engines.momentum_score(ind),
        engines.sentiment_score(snap.info, last),
    ]
    by_name = {s.name: s for s in subs}
    weights = settings.score_weights
    composite = sum(by_name[n].score * w for n, w in weights.items())
    composite = round(composite, 1)

    # Trade plan from ATR (fallbacks keep it defined even with sparse data).
    atr = ind.get("atr")
    entry = round(last, 2) if last else None
    stop = round(last - 1.5 * atr, 2) if (last and atr) else None
    target1 = round(last + 2.0 * atr, 2) if (last and atr) else None
    target2 = snap.target_mean_price
    risk = (entry - stop) if (entry and stop) else None
    reward = (target1 - entry) if (entry and target1) else None
    rr = round(reward / risk, 2) if (risk and reward and risk > 0) else None

    explanation = _build_explanation(snap.ticker, composite, weights, by_name, hit)

    return {
        "ticker": snap.ticker,
        "company": snap.info.get("shortName") or snap.info.get("longName") or snap.ticker,
        "score": composite,
        "action": _action_from_score(composite),
        "subscores": {n: round(by_name[n].score, 1) for n in weights},
        "weights": weights,
        "entry": entry,
        "stop_loss": stop,
        "target1": target1,
        "target2": target2,
        "risk_reward": rr,
        "covered_call": (opt_metrics or {}).get("covered_call_idea"),
        "cash_secured_put": (opt_metrics or {}).get("csp_idea"),
        "confidence": _confidence(hit, composite),
        "criteria_passed": hit.passed_names,
        "criteria_failed": hit.failed_names,
        "metrics": {k: v for k, v in hit.metrics.items() if k != "indicators"},
        "reasoning": explanation,
    }


def _build_explanation(ticker, composite, weights, by_name, hit: ScanHit) -> str:
    contribs = []
    for n, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        s = by_name[n]
        contribs.append(f"{n} {s.score:.0f}/100 (x{w:.2f} = {s.score*w:.1f})")
    top_factors = []
    for n in ("technical", "fundamental", "sentiment", "options", "momentum"):
        top_factors += by_name[n].factors[:2]

    crash = ", ".join(c.detail for c in hit.criteria if c.name in
                      {"down_5pct_day", "down_20pct_month", "revenue_over_1b"})
    return (
        f"{ticker} scored {composite}/100. "
        f"Setup: {crash}. "
        f"Contributions — {'; '.join(contribs)}. "
        f"Key drivers: {'; '.join(top_factors) if top_factors else 'mixed signals'}."
    )
