#!/usr/bin/env python3
"""Daily multi-domain dashboard builder.

Scores the curated watchlist (backend/watchlist.py) and writes
frontend/public/dashboard.json, which the Dashboard page renders grouped by
domain. Runs in GitHub Actions (live yfinance) — see
.github/workflows/dashboard.yml (9 AM ET).

    python -m backend.run_dashboard
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

from backend.config import settings
from backend.scoring.composite import score_ticker_general
from backend.utils.market_data import MarketData
from backend.watchlist import DOMAINS

ET = ZoneInfo("America/New_York")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(_ROOT, "frontend", "public", "dashboard.json")


def main() -> None:
    md = MarketData()
    now = dt.datetime.now(ET)
    out_domains: dict[str, list[dict]] = {}
    total = 0
    missing: list[str] = []   # delisted/renamed watchlist tickers to prune

    for domain, tickers in DOMAINS.items():
        rows = []
        for t in tickers:
            snap = md.snapshot(t)
            if snap is None or snap.last_close is None:
                print(f"  {t}: no data (delisted/renamed? consider pruning from watchlist.py)")
                missing.append(t)
                continue
            rec = score_ticker_general(snap, md)
            rec["domain"] = domain
            # 30-day closes for the card sparkline.
            closes = snap.history["Close"].dropna().tail(30)
            rec["spark"] = [round(float(x), 2) for x in closes]
            rows.append(rec)
            total += 1
            print(f"  {domain:20} {t:6} score {rec['score']:5} {rec['action']}")
            time.sleep(settings.request_sleep)
        rows.sort(key=lambda r: r["score"], reverse=True)
        out_domains[domain] = rows

    # Market regime, read from the market rather than from our own scores.
    # The dashboard used to label the regime by averaging the board's AI
    # scores, which is circular: it reported how bullish WE were, not what the
    # tape was doing. This reads SPY's own structure, the board's breadth, and
    # realized volatility, and produces an explicit position-size multiplier.
    regime_payload = None
    try:
        from backend.market_regime import assess as assess_regime

        spy = md.snapshot("SPY")
        if spy is not None and not spy.history.empty:
            closes = [float(c) for c in spy.history["Close"].dropna()]
            flags = [bool(r.get("above_ema200"))
                     for rows in out_domains.values() for r in rows]

            def sector_ret(sym: str) -> float | None:
                snap = md.snapshot(sym)
                if snap is None or snap.history.empty:
                    return None
                c = [float(x) for x in snap.history["Close"].dropna()]
                return (c[-1] / c[-64] - 1) * 100 if len(c) > 64 else None

            read = assess_regime(
                closes,
                above_200_flags=flags,
                offensive_ret=sector_ret("XLK"),      # tech = offense
                defensive_ret=sector_ret("XLU"),      # utilities = defense
            )
            regime_payload = {
                "regime": read.regime, "score": read.score,
                "position_scale": read.position_scale,
                "factors": read.factors, "detail": read.detail,
            }
            print(f"Market regime: {read.regime} ({read.score}/100) — "
                  f"size at {int(read.position_scale * 100)}% of normal")
            for f_ in read.factors:
                print(f"  · {f_}")
    except Exception as e:  # pragma: no cover - CI only
        print(f"Regime read skipped: {e}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({
            "generated_at": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "as_of": now.strftime("%Y-%m-%d %H:%M %Z"),
            "count": total,
            "missing": missing,
            "market_regime": regime_payload,
            "domains": out_domains,
        }, f, indent=2, default=str)
    print(f"\nWrote {total} scored tickers across {len(out_domains)} domains -> {OUT}")
    if missing:
        print(f"WATCHLIST WARNING: no data for {', '.join(missing)} — prune or fix in backend/watchlist.py")


if __name__ == "__main__":
    main()
