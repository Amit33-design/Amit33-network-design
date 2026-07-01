"""Catalyst & risk flags.

Surfaces the context that turns a good-looking setup into a landmine (or a
sweeter entry): imminent earnings, crowded shorts, a falling-knife 52-week-low
test, weak balance sheet, trading above analyst targets, etc. Every flag is a
short, explainable string with a level so the UI can colour it.

Levels: "warn" (caution), "info" (context), "good" (supportive).
"""
from __future__ import annotations

import datetime as dt

from backend.config import settings


def compute_risk_flags(info: dict, ind: dict, last_price: float | None) -> list[dict]:
    flags: list[dict] = []

    # --- imminent earnings (binary event risk) ---
    ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
    if ts:
        try:
            when = dt.datetime.utcfromtimestamp(int(ts))
            days = (when - dt.datetime.utcnow()).days
            if 0 <= days <= settings.earnings_window_days:
                flags.append({"level": "warn", "text": f"earnings in {days}d"})
        except Exception:
            pass

    # --- crowded short (squeeze fuel, but also a bearish tell) ---
    sp = info.get("shortPercentOfFloat")
    if sp is not None and sp >= settings.high_short_interest:
        flags.append({"level": "warn", "text": f"high short interest ({sp*100:.0f}%)"})

    # --- 52-week-low test: support or falling knife ---
    dlow = ind.get("dist_52w_low")
    if dlow is not None and dlow <= settings.near_52w_low_pct:
        flags.append({"level": "warn", "text": "near 52-week low (support test / falling knife)"})

    # --- trading above analyst target (limited upside left) ---
    target = info.get("targetMeanPrice")
    if target and last_price and last_price > target:
        flags.append({"level": "warn", "text": "trades above analyst target"})

    # --- balance-sheet fragility ---
    de = info.get("debtToEquity")
    if de is not None and de > 300:
        flags.append({"level": "warn", "text": f"high leverage (D/E {de:.0f}%)"})
    fcf = info.get("freeCashflow")
    if fcf is not None and fcf < 0:
        flags.append({"level": "warn", "text": "negative free cash flow"})

    # --- structural / volatility context ---
    mcap = info.get("marketCap")
    if mcap is not None and mcap < 2_000_000_000:
        flags.append({"level": "info", "text": "small cap (thinner liquidity)"})
    beta = info.get("beta")
    if beta is not None and beta > 1.8:
        flags.append({"level": "info", "text": f"high beta ({beta:.1f})"})

    # --- supportive catalysts ---
    rec_key = (info.get("recommendationKey") or "").lower()
    if rec_key == "strong_buy":
        flags.append({"level": "good", "text": "strong-buy consensus"})
    if ind.get("golden_cross"):
        flags.append({"level": "good", "text": "golden-cross regime"})

    return flags
