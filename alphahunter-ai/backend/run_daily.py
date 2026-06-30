#!/usr/bin/env python3
"""Daily AlphaHunter scan — CI entrypoint.

Runs the AlphaHunter scan once and writes BOTH a rich JSON and a flat CSV to
alphahunter-ai/results/, dated by Pacific date. Mirrors the legacy
screener/run_ci.py so it drops cleanly into GitHub Actions.

    python -m backend.run_daily            # full universe
    python -m backend.run_daily --limit 300 --loose
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

import pandas as pd

from backend.scanners.runner import run_scan

PACIFIC = ZoneInfo("America/Los_Angeles")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(_ROOT, "results")
# The deployed static site reads this file; refreshing it auto-deploys via Vercel.
FRONTEND_SNAPSHOT = os.path.join(_ROOT, "frontend", "public", "snapshot.json")

CSV_COLUMNS = [
    "ticker", "company", "score", "quality_grade", "expected_gain_%",
    "analyst_upside_%", "action", "confidence",
    "rsi", "day_%", "month_%", "revenue_$B", "institutional_%",
    "entry", "stop_loss", "target1", "target2", "risk_reward",
    "covered_call", "cash_secured_put",
]


def _flatten(rec: dict) -> dict:
    m = rec.get("metrics", {})
    return {
        "ticker": rec["ticker"],
        "company": rec["company"],
        "score": rec["score"],
        "quality_grade": rec.get("quality_grade"),
        "expected_gain_%": rec.get("expected_gain_%"),
        "analyst_upside_%": rec.get("analyst_upside_%"),
        "action": rec["action"],
        "confidence": rec["confidence"],
        "rsi": m.get("rsi"),
        "day_%": m.get("day_%"),
        "month_%": m.get("month_%"),
        "revenue_$B": m.get("revenue_$B"),
        "institutional_%": m.get("institutional_%"),
        "entry": rec.get("entry"),
        "stop_loss": rec.get("stop_loss"),
        "target1": rec.get("target1"),
        "target2": rec.get("target2"),
        "risk_reward": rec.get("risk_reward"),
        "covered_call": rec.get("covered_call"),
        "cash_secured_put": rec.get("cash_secured_put"),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="AlphaHunter daily scan")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--loose", action="store_true",
                   help="surface near-misses (core crash filter only)")
    args = p.parse_args()

    today = dt.datetime.now(PACIFIC).strftime("%Y-%m-%d")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"AlphaHunter daily scan for {today} (Pacific). "
          f"require_all={not args.loose} limit={args.limit}")
    results = run_scan(
        require_all=not args.loose,
        limit=args.limit,
        progress=lambda i, t, n: print(f"  ...{i}/{t} scanned, {n} hits"),
    )

    json_path = os.path.join(RESULTS_DIR, f"alphahunter_{today}.json")
    csv_path = os.path.join(RESULTS_DIR, f"alphahunter_{today}.csv")

    with open(json_path, "w") as f:
        json.dump({"date": today, "count": len(results), "results": results},
                  f, indent=2, default=str)

    rows = [_flatten(r) for r in results]
    df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    df.to_csv(csv_path, index=False)

    # Refresh the snapshot the deployed frontend serves (same Recommendation
    # shape as the live API), so committing it auto-deploys fresh data to Vercel.
    os.makedirs(os.path.dirname(FRONTEND_SNAPSHOT), exist_ok=True)
    with open(FRONTEND_SNAPSHOT, "w") as f:
        json.dump({"date": today, "snapshot": True, "live": True,
                   "count": len(results), "results": results}, f, indent=2, default=str)

    print(f"\nWrote {len(results)} ranked recommendations:")
    print(f"  {json_path}")
    print(f"  {csv_path}")
    print(f"  {FRONTEND_SNAPSHOT}  (deployed site refreshes on commit)")
    if results:
        top = results[0]
        print(f"Top pick: {top['ticker']} score {top['score']} ({top['action']})")


if __name__ == "__main__":
    main()
