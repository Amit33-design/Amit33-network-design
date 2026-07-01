"""Composite AI score + full StockRecommendation assembly.

Blends the five sub-scores with the spec weights (35/25/20/10/10) into a single
0-100 number, then builds the complete recommendation payload from the spec's
"Stock Recommendation Output" section: entry, stop, targets, R:R, options
ideas, confidence, and a plain-English explanation citing score contributions.
"""
from __future__ import annotations

from backend.backtesting.engine import backtest_oversold
from backend.config import settings
from backend.options.analyzer import summarize_options
from backend.scanners.base import ScanHit
from backend.scoring import engines
from backend.utils.market_data import MarketData, StockSnapshot

_LEVELS = ["Low", "Medium", "High"]


def _bump(level: str, delta: int) -> str:
    i = max(0, min(len(_LEVELS) - 1, _LEVELS.index(level) + delta))
    return _LEVELS[i]


def _backtest_stats(snap: StockSnapshot, md: MarketData | None) -> dict:
    """Historical bounce rate + avg forward return of this ticker's own setup.

    Prefers a longer history (via md) for meaningful sample size; falls back to
    the snapshot's own history. Returns zeros when there isn't enough data.
    """
    hist = None
    if md is not None:
        hist = md.history(snap.ticker)
    if hist is None or getattr(hist, "empty", True):
        hist = snap.history
    try:
        res = backtest_oversold(hist).as_dict()
        return {
            "hist_trades": res["trades"],
            "hist_win_rate": res["win_rate"],
            "hist_avg_return_%": res["avg_return_%"],
        }
    except Exception:
        return {"hist_trades": 0, "hist_win_rate": 0.0, "hist_avg_return_%": 0.0}


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

    # Quality grade (A–F) from the fundamental sub-score, and an expected-gain
    # estimate: analyst upside tempered by how confident/high-quality the setup
    # is — so the list can be ranked by realistic gain, not raw target upside.
    grade = engines.quality_grade(by_name["fundamental"].score)
    analyst_upside = (
        (snap.target_mean_price - last) / last * 100.0
        if (snap.target_mean_price and last) else None
    )

    # Calibrate confidence against how this ticker's oversold setup has actually
    # played out historically (bounce rate + avg forward return).
    bt = _backtest_stats(snap, md)
    conf = _confidence(hit, composite)
    if bt["hist_trades"] >= 3:
        if bt["hist_win_rate"] >= 0.6 and bt["hist_avg_return_%"] > 0:
            conf = _bump(conf, +1)
        elif bt["hist_win_rate"] < 0.4 or bt["hist_avg_return_%"] < 0:
            conf = _bump(conf, -1)
    conf_mult = {"High": 0.85, "Medium": 0.6, "Low": 0.4}[conf]
    quality_mult = 0.7 + 0.6 * (by_name["fundamental"].score / 100.0)  # 0.7–1.3
    expected_gain = (round(analyst_upside * conf_mult * min(quality_mult, 1.0), 1)
                     if analyst_upside is not None else None)

    explanation = _build_explanation(snap.ticker, composite, weights, by_name, hit)
    if bt["hist_trades"] >= 3:
        explanation += (
            f" Backtest: this setup fired {bt['hist_trades']}x historically, "
            f"bounced {bt['hist_win_rate']*100:.0f}% of the time "
            f"(avg {bt['hist_avg_return_%']:+.1f}% over the hold)."
        )

    return {
        "ticker": snap.ticker,
        "company": snap.info.get("shortName") or snap.info.get("longName") or snap.ticker,
        "score": composite,
        "action": _action_from_score(composite),
        "quality_grade": grade,
        "analyst_upside_%": round(analyst_upside, 1) if analyst_upside is not None else None,
        "expected_gain_%": expected_gain,
        "hist_win_rate": bt["hist_win_rate"],
        "hist_avg_return_%": bt["hist_avg_return_%"],
        "hist_trades": bt["hist_trades"],
        "subscores": {n: round(by_name[n].score, 1) for n in weights},
        "weights": weights,
        "entry": entry,
        "stop_loss": stop,
        "target1": target1,
        "target2": target2,
        "risk_reward": rr,
        "covered_call": (opt_metrics or {}).get("covered_call_idea"),
        "cash_secured_put": (opt_metrics or {}).get("csp_idea"),
        "confidence": conf,
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
