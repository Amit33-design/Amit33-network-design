"""Options analytics from a yfinance option chain.

Computes the income-strategy metrics the spec's Options Engine calls for —
covered-call and cash-secured-put yields, bid/ask spread, open interest — and
emits concrete strategy ideas. Best-effort: any missing field degrades to None
rather than raising.
"""
from __future__ import annotations

import datetime as dt
from typing import Any


def _annualize(premium: float, strike: float, days: int) -> float | None:
    if strike <= 0 or days <= 0:
        return None
    period_yield = premium / strike
    return period_yield * (365.0 / days)


def summarize_options(chain: dict[str, Any] | None, last_price: float | None) -> dict | None:
    if not chain or last_price is None:
        return None
    calls = chain.get("calls")
    puts = chain.get("puts")
    expiry = chain.get("expiry")
    if calls is None or puts is None or expiry is None:
        return None

    try:
        exp_date = dt.date.fromisoformat(expiry)
        days = max((exp_date - dt.date.today()).days, 1)
    except Exception:
        days = 30

    out: dict[str, Any] = {"expiry": expiry, "days_to_expiry": days}

    # --- Covered call: nearest OTM call above spot ---
    try:
        otm_calls = calls[calls["strike"] >= last_price].sort_values("strike")
        if not otm_calls.empty:
            row = otm_calls.iloc[0]
            strike = float(row["strike"])
            bid = float(row.get("bid") or 0)
            ask = float(row.get("ask") or 0)
            mid = (bid + ask) / 2 if (bid or ask) else float(row.get("lastPrice") or 0)
            cc_yield = _annualize(mid, last_price, days)
            out["covered_call_yield"] = cc_yield
            out["covered_call_idea"] = (
                f"Sell {expiry} ${strike:.0f} call ~${mid:.2f} "
                f"({(cc_yield or 0)*100:.0f}% ann.)"
            )
            if ask > 0:
                out["bid_ask_spread_pct"] = (ask - bid) / ask if ask else None
            out["open_interest"] = float(row.get("openInterest") or 0)
    except Exception:
        pass

    # --- Cash-secured put: nearest OTM put below spot ---
    try:
        otm_puts = puts[puts["strike"] <= last_price].sort_values("strike", ascending=False)
        if not otm_puts.empty:
            row = otm_puts.iloc[0]
            strike = float(row["strike"])
            bid = float(row.get("bid") or 0)
            ask = float(row.get("ask") or 0)
            mid = (bid + ask) / 2 if (bid or ask) else float(row.get("lastPrice") or 0)
            csp_yield = _annualize(mid, strike, days)
            out["csp_annualized_yield"] = csp_yield
            out["csp_idea"] = (
                f"Sell {expiry} ${strike:.0f} put ~${mid:.2f} "
                f"({(csp_yield or 0)*100:.0f}% ann.)"
            )
    except Exception:
        pass

    return out
