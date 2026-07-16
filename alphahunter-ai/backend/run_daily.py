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

from backend.alerts.engine import send_scan_digest
from backend.config import settings
from backend.scanners.runner import run_opportunity_scan, run_scan

PACIFIC = ZoneInfo("America/Los_Angeles")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(_ROOT, "results")
# The deployed static site reads this file; refreshing it auto-deploys via Vercel.
FRONTEND_SNAPSHOT = os.path.join(_ROOT, "frontend", "public", "snapshot.json")

CSV_COLUMNS = [
    "ticker", "company", "score", "quality_grade", "expected_gain_%",
    "analyst_upside_%", "hist_win_rate", "hist_avg_return_%", "hist_trades",
    "rs_vs_spy", "rs_vs_sector", "sector",
    "csp_signal", "csp_reason",
    "risk_flags", "action", "confidence",
    "rsi", "day_%", "month_%", "revenue_$B", "institutional_%",
    "entry", "stop_loss", "target1", "target2", "risk_reward", "rr_pass",
    "suggested_shares", "position_value",
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
        "hist_win_rate": rec.get("hist_win_rate"),
        "hist_avg_return_%": rec.get("hist_avg_return_%"),
        "hist_trades": rec.get("hist_trades"),
        "rs_vs_spy": (rec.get("rel_strength") or {}).get("vs_spy"),
        "rs_vs_sector": (rec.get("rel_strength") or {}).get("vs_sector"),
        "sector": (rec.get("rel_strength") or {}).get("sector"),
        "csp_signal": (rec.get("csp_signal") or {}).get("strength")
                      if (rec.get("csp_signal") or {}).get("active") else None,
        "csp_reason": (rec.get("csp_signal") or {}).get("reason"),
        "risk_flags": "; ".join(f["text"] for f in rec.get("risk_flags", [])),
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
        "rr_pass": rec.get("rr_pass"),
        "suggested_shares": (rec.get("position") or {}).get("shares"),
        "position_value": (rec.get("position") or {}).get("value"),
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

    # The strict crash screen finds nothing in a calm market. So the daily
    # board is never empty, fall back to a broad "best pullback/dip" scan and
    # merge in the top-scored opportunities (deduped, strict hits kept first).
    if len(results) < settings.opp_min_results:
        print(f"Strict scan yielded {len(results)}; running broad opportunity scan...")
        opp = run_opportunity_scan(
            limit=args.limit,
            progress=lambda i, t, n: print(f"  ...opp {i}/{t} scanned, {n} candidates"),
        )
        seen = {r["ticker"] for r in results}
        results.extend(r for r in opp if r["ticker"] not in seen)
        results.sort(key=lambda r: r["score"], reverse=True)
        print(f"Opportunity scan added {len(results) - len(seen)} names; {len(results)} total.")

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

    # Track record: price past picks and publish the verifiable performance
    # summary the Dashboard shows. Best-effort — never fails the scan.
    perf_path = os.path.join(os.path.dirname(FRONTEND_SNAPSHOT), "performance.json")
    try:
        from backend.performance import write_performance_json
        perf = write_performance_json(RESULTS_DIR, today, perf_path)
        if perf.get("summary"):
            s = perf["summary"]
            print(f"Track record: {s['picks']} picks, {s['win_rate']*100:.0f}% winners, "
                  f"avg {s['avg_return_%']:+.1f}%")
        else:
            print("Track record: not enough aged history yet.")
    except Exception as e:  # pragma: no cover - CI only
        print(f"Track record skipped: {e}")
        if not os.path.exists(perf_path):  # keep the workflow's git add happy
            with open(perf_path, "w") as f:
                json.dump({"picks": [], "summary": None, "generated": today}, f)

    # Push the day's best high-conviction setups to configured channels
    # (Slack/Discord webhooks via env/secrets); logs and no-ops when unset.
    outcome = send_scan_digest(today, results)
    print(f"Alert digest delivered to: {', '.join(outcome['delivered_to'])} "
          f"({len(outcome['tickers'])} setups)")


if __name__ == "__main__":
    main()
