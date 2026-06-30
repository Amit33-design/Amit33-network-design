"""The five sub-score engines, each returning a 0-100 score plus the factors
that produced it. Every engine is transparent: it appends human-readable
reasons so the composite explanation can cite exactly what moved the number.

Scores are deliberately rule-based and bounded. They are designed to be
sensible defaults that a later ML ranker (scikit-learn / XGBoost per the spec)
can be blended with or trained against.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class SubScore:
    name: str
    score: float
    factors: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Technical (35%) — oversold mean-reversion setup quality
# --------------------------------------------------------------------------
def technical_score(ind: dict) -> SubScore:
    score = 50.0
    factors: list[str] = []

    rsi = ind.get("rsi")
    if rsi is not None:
        if rsi < 25:
            score += 20; factors.append(f"deeply oversold (RSI {rsi:.0f})")
        elif rsi < 35:
            score += 12; factors.append(f"oversold (RSI {rsi:.0f})")
        elif rsi > 70:
            score -= 12; factors.append(f"overbought (RSI {rsi:.0f})")

    if ind.get("above_ema200"):
        score += 12; factors.append("above EMA200 (uptrend intact)")
    else:
        score -= 8; factors.append("below EMA200")

    if ind.get("golden_cross"):
        score += 6; factors.append("50/200 golden cross")

    macd_hist = ind.get("macd_hist")
    if macd_hist is not None and macd_hist > 0:
        score += 5; factors.append("MACD histogram turning up")

    vr = ind.get("volume_ratio")
    if vr is not None and vr >= 1.5:
        score += 6; factors.append(f"volume spike (x{vr:.1f})")

    return SubScore("technical", _clamp(score), factors)


# --------------------------------------------------------------------------
# Fundamental (25%) — quality / solvency / cash generation
# --------------------------------------------------------------------------
def fundamental_score(info: dict) -> SubScore:
    score = 50.0
    factors: list[str] = []

    fcf = info.get("freeCashflow")
    if fcf is not None:
        if fcf > 0:
            score += 12; factors.append("positive free cash flow")
        else:
            score -= 12; factors.append("negative free cash flow")

    margins = info.get("profitMargins")
    if margins is not None:
        if margins > 0.15:
            score += 10; factors.append(f"strong net margin ({margins*100:.0f}%)")
        elif margins < 0:
            score -= 10; factors.append("unprofitable")

    roe = info.get("returnOnEquity")
    if roe is not None and roe > 0.15:
        score += 8; factors.append(f"high ROE ({roe*100:.0f}%)")

    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        if rev_growth > 0.10:
            score += 8; factors.append(f"revenue growth ({rev_growth*100:.0f}%)")
        elif rev_growth < 0:
            score -= 6; factors.append("shrinking revenue")

    de = info.get("debtToEquity")
    if de is not None and de > 300:
        score -= 8; factors.append(f"high leverage (D/E {de:.0f}%)")

    return SubScore("fundamental", _clamp(score), factors)


# --------------------------------------------------------------------------
# Momentum (10%) — multi-horizon trend vs itself
# --------------------------------------------------------------------------
def momentum_score(ind: dict) -> SubScore:
    score = 50.0
    factors: list[str] = []

    r60 = ind.get("ret_60d")
    r120 = ind.get("ret_120d")
    r252 = ind.get("ret_252d")

    if r252 is not None:
        if r252 > 0:
            score += 10; factors.append(f"positive 1y trend ({r252:.0f}%)")
        else:
            score -= 6; factors.append(f"negative 1y trend ({r252:.0f}%)")
    if r120 is not None and r120 > 0:
        score += 6; factors.append("positive 6m trend")
    # For an oversold-bounce setup, a sharp short-term drop is the SETUP, so we
    # do not penalize negative 1-3 month returns here — that's the entry edge.
    if r60 is not None and r60 < -25:
        score += 6; factors.append("sharp recent pullback (bounce setup)")

    return SubScore("momentum", _clamp(score), factors)


# --------------------------------------------------------------------------
# Options (20%) — premium-selling attractiveness (best-effort from chain)
# --------------------------------------------------------------------------
def options_score(opt_metrics: dict | None) -> SubScore:
    if not opt_metrics:
        return SubScore("options", 50.0, ["no options data"])
    score = 50.0
    factors: list[str] = []

    csp_yield = opt_metrics.get("csp_annualized_yield")
    if csp_yield is not None:
        if csp_yield > 0.30:
            score += 20; factors.append(f"rich CSP yield ({csp_yield*100:.0f}% ann.)")
        elif csp_yield > 0.15:
            score += 10; factors.append(f"solid CSP yield ({csp_yield*100:.0f}% ann.)")

    spread = opt_metrics.get("bid_ask_spread_pct")
    if spread is not None and spread < 0.05:
        score += 6; factors.append("tight bid/ask")
    elif spread is not None and spread > 0.20:
        score -= 8; factors.append("wide bid/ask (illiquid)")

    oi = opt_metrics.get("open_interest")
    if oi is not None and oi > 1000:
        score += 6; factors.append("liquid open interest")

    return SubScore("options", _clamp(score), factors)


# --------------------------------------------------------------------------
# Sentiment (10%) — analyst posture + upside (yfinance proxy for now)
# --------------------------------------------------------------------------
def sentiment_score(info: dict, last_price: float | None) -> SubScore:
    score = 50.0
    factors: list[str] = []

    rec = info.get("recommendationMean")
    if rec is not None:
        if rec <= 1.8:
            score += 18; factors.append(f"strong-buy consensus ({rec:.2f})")
        elif rec <= 2.5:
            score += 10; factors.append(f"buy consensus ({rec:.2f})")
        elif rec >= 3.5:
            score -= 12; factors.append(f"bearish consensus ({rec:.2f})")

    target = info.get("targetMeanPrice")
    if target and last_price:
        upside = (target - last_price) / last_price * 100.0
        if upside > 50:
            score += 16; factors.append(f"{upside:.0f}% upside to target")
        elif upside > 20:
            score += 8; factors.append(f"{upside:.0f}% upside to target")
        elif upside < 0:
            score -= 8; factors.append("trading above target")

    return SubScore("sentiment", _clamp(score), factors)
