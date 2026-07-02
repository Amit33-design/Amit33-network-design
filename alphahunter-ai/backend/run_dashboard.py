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

    for domain, tickers in DOMAINS.items():
        rows = []
        for t in tickers:
            snap = md.snapshot(t)
            if snap is None or snap.last_close is None:
                print(f"  {t}: no data")
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

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({
            "generated_at": now.isoformat(),
            "as_of": now.strftime("%Y-%m-%d %H:%M %Z"),
            "count": total,
            "domains": out_domains,
        }, f, indent=2, default=str)
    print(f"\nWrote {total} scored tickers across {len(out_domains)} domains -> {OUT}")


if __name__ == "__main__":
    main()
