"""Analyst price targets for the Analysis page (QA 2026-09-29, P2-6).

Informational display only: mean / high / low target, number of analysts and
an "as of" date, with the source named. Never turned into a buy/sell call —
the factor lab has not tested targets as a signal. Yahoo serves these only
through crumb-protected endpoints, so they are fetched weekly in CI with
yfinance and committed as public/analysts.json.

    python -m backend.analyst_targets
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time

PUBLIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "frontend", "public")


def _num(x):
    try:
        x = float(x)
        return None if math.isnan(x) or x <= 0 else round(x, 2)
    except (TypeError, ValueError):
        return None


def targets_from_info(info: dict | None) -> dict | None:
    """The target block, or None when there is no real coverage. Pure."""
    if not info:
        return None
    mean = _num(info.get("targetMeanPrice"))
    n = info.get("numberOfAnalystOpinions")
    try:
        n = int(n) if n is not None else None
    except (TypeError, ValueError):
        n = None
    if mean is None or not n:
        return None
    return {
        "mean": mean, "high": _num(info.get("targetHighPrice")), "low": _num(info.get("targetLowPrice")),
        "median": _num(info.get("targetMedianPrice")), "analysts": n,
        "currency": info.get("financialCurrency") or info.get("currency") or "USD",
    }


def main() -> None:  # pragma: no cover - network
    import yfinance as yf

    from backend.utils.universe import load_universe
    from backend.watchlist import all_tickers

    tickers = list(dict.fromkeys(all_tickers() + load_universe()))
    today = dt.date.today().isoformat()
    out = {}
    for t in tickers:
        try:
            tg = targets_from_info(yf.Ticker(t).info)
            if tg:
                out[t] = tg
        except Exception:
            pass
        time.sleep(0.15)
    with open(os.path.join(PUBLIC, "analysts.json"), "w") as f:
        json.dump({"as_of": today, "source": "Yahoo Finance (consensus via yfinance)",
                   "count": len(out), "targets": out}, f)
    print(f"analyst targets: {len(out)}/{len(tickers)} covered")


if __name__ == "__main__":  # pragma: no cover
    main()
