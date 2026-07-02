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
from backend.scoring.csp_signal import compute_csp_signal
from backend.scoring.relative_strength import apply_rel_strength, compute_rel_strength
from backend.scoring.risk import compute_risk_flags
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

    # Sector relative strength: leaders vs SPY/sector get a momentum boost,
    # laggards a haircut — folded in BEFORE the weighted blend so it moves the
    # composite, and recorded as factors so it stays explainable.
    rs = compute_rel_strength(snap, ind, md)
    apply_rel_strength(by_name["momentum"], rs)

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

    # Position sizing: risk a fixed % of the account per trade against the
    # ATR stop distance — bigger stops mean fewer shares, automatically.
    position = None
    if risk and risk > 0 and entry:
        budget = settings.account_size * settings.max_risk_pct / 100.0
        shares = int(budget // risk)
        if shares > 0:
            position = {
                "shares": shares,
                "value": round(shares * entry, 2),
                "risk_$": round(shares * risk, 2),
                "basis": f"{settings.max_risk_pct:.1f}% of ${settings.account_size:,.0f} "
                         f"at ${risk:.2f}/share stop distance",
            }
    rr_pass = rr is not None and rr >= settings.min_risk_reward

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

    risk_flags = compute_risk_flags(snap.info, ind, last)
    if rr is not None and not rr_pass:
        risk_flags.append({
            "level": "warn",
            "text": f"R:R {rr:.2f} below {settings.min_risk_reward:.1f} floor",
        })

    explanation = _build_explanation(snap.ticker, composite, weights, by_name, hit)
    if bt["hist_trades"] >= 3:
        explanation += (
            f" Backtest: this setup fired {bt['hist_trades']}x historically, "
            f"bounced {bt['hist_win_rate']*100:.0f}% of the time "
            f"(avg {bt['hist_avg_return_%']:+.1f}% over the hold)."
        )
    # Sector thesis: is the weakness group-driven (whole sector down together,
    # the way memory names fall when DRAM pricing turns) or stock-specific?
    if rs and rs.get("vs_sector") is not None:
        vs = rs["vs_sector"]
        sect = rs.get("sector") or "its sector"
        if abs(vs) <= 5:
            explanation += (f" Sector thesis: moving WITH {sect} "
                            f"({vs:+.0f}pp vs {rs.get('sector_etf')}) — the decline is "
                            f"group-driven, so a sector turn should lift it too.")
        elif vs < -5:
            explanation += (f" Sector thesis: lagging {sect} by {abs(vs):.0f}pp — the "
                            f"weakness is stock-specific, not just the group; check for "
                            f"company news before assuming a sector bounce fixes it.")
        else:
            explanation += (f" Sector thesis: outperforming {sect} by {vs:.0f}pp — a "
                            f"relative leader in its group.")

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
        "risk_flags": risk_flags,
        "rel_strength": rs,
        "position": position,
        "rr_pass": rr_pass,
        "csp_signal": compute_csp_signal(
            ind.get("ret_1d"), ind.get("above_ema200"), analyst_upside,
            bt, opt_metrics, last, atr,
        ),
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


def score_ticker_general(snap: StockSnapshot, md: MarketData | None = None) -> dict:
    """Score ANY ticker (no oversold gate) for the dashboard watchlist.

    Reuses the same five engines + relative strength, so a mega-cap in a calm
    uptrend gets a fair read. Returns a compact, dashboard-friendly record.
    """
    from backend.indicators import technical as ta

    ind = ta.indicator_bundle(snap.history)
    last = snap.last_close
    subs = {
        "technical": engines.technical_score(ind),
        "fundamental": engines.fundamental_score(snap.info),
        "options": engines.options_score(None),   # skip chain fetch for speed
        "momentum": engines.momentum_score(ind),
        "sentiment": engines.sentiment_score(snap.info, last),
    }
    rs = compute_rel_strength(snap, ind, md)
    apply_rel_strength(subs["momentum"], rs)

    weights = settings.score_weights
    composite = round(sum(subs[n].score * w for n, w in weights.items()), 1)
    analyst_upside = ((snap.target_mean_price - last) / last * 100.0
                      if (snap.target_mean_price and last) else None)
    return {
        "ticker": snap.ticker,
        "company": snap.info.get("shortName") or snap.info.get("longName") or snap.ticker,
        "price": round(last, 2) if last else None,
        "day_%": ind.get("ret_1d"),
        "score": composite,
        "action": _action_from_score(composite),
        "quality_grade": engines.quality_grade(subs["fundamental"].score),
        "rsi": round(ind["rsi"], 1) if ind.get("rsi") is not None else None,
        "above_ema200": ind.get("above_ema200"),
        "cycle": "bull" if ind.get("golden_cross") else "bear",
        "analyst_upside_%": round(analyst_upside, 1) if analyst_upside is not None else None,
        "rel_strength": rs,
        "subscores": {n: round(subs[n].score, 1) for n in weights},
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
