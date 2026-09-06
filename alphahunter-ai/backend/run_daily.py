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
from backend.exit_rules import DEFAULT_STOP_PCT
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
    "csp_signal", "csp_reason", "profile",
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
        "profile": m.get("profile") or "crash",
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

    # Paper portfolio: $100 into every distinct Buy, valued today. The most
    # literal possible answer to "are these picks any good?".
    paper_path = os.path.join(os.path.dirname(FRONTEND_SNAPSHOT), "paper.json")
    try:
        from backend.paper_portfolio import build as build_paper
        pp = build_paper(RESULTS_DIR, paper_path)
        if pp.get("holdings"):
            print(f"Paper portfolio: {pp['positions']} x ${pp['stake']:.0f} = "
                  f"${pp['invested']:,.0f} -> ${pp['value']:,.0f} "
                  f"({pp['return_%']:+.1f}%, {pp['winners']}W/{pp['losers']}L)")
        else:
            print(f"Paper portfolio: {pp.get('error', 'no result')}")
    except Exception as e:  # pragma: no cover - CI only
        print(f"Paper portfolio skipped: {e}")
        if not os.path.exists(paper_path):
            with open(paper_path, "w") as f:
                json.dump({"error": "not generated yet", "holdings": []}, f)

    # Growth leaders: the other half of the product. The oversold screen finds
    # things that fell; this finds growing businesses whose stock is working.
    growth_path = os.path.join(os.path.dirname(FRONTEND_SNAPSHOT), "growth.json")
    try:
        from backend.scanners.runner import run_growth_scan
        growth = run_growth_scan(limit=args.limit or None, max_scored=40)
        with open(growth_path, "w") as f:
            json.dump({"date": today, "count": len(growth), "results": growth}, f, indent=2)
        if growth:
            top = growth[0]
            print(f"Growth leaders: {len(growth)} names, best {top['ticker']} "
                  f"(score {top['score']}, growth {top['metrics'].get('growth_score')})")
        else:
            print("Growth leaders: none passed the screen today.")
    except Exception as e:  # pragma: no cover - CI only
        print(f"Growth scan skipped: {e}")
        if not os.path.exists(growth_path):
            with open(growth_path, "w") as f:
                json.dump({"date": today, "count": 0, "results": []}, f)

    # Income plan: what the MEASURED edge implies for an annual profit goal.
    # Derived from the paper portfolio so it describes this system, not a
    # hypothetical good one.
    plan_path = os.path.join(os.path.dirname(FRONTEND_SNAPSHOT), "income_plan.json")
    try:
        from backend.income_plan import edge_from_history, project
        with open(os.path.join(os.path.dirname(FRONTEND_SNAPSHOT), "paper.json")) as f:
            holdings = json.load(f).get("holdings", [])
        edge = edge_from_history(holdings)
        if edge:
            base = project(settings.account_size, trades_per_year=25,
                           concurrent_positions=5,
                           win_rate=edge["win_rate"],
                           avg_win_pct=edge["avg_win_pct"],
                           avg_loss_pct=edge["avg_loss_pct"])
            # The same edge with losses actually cut at the stop. Arithmetic,
            # not a backtest — a stop also turns some dips that recovered into
            # realized losses — so it is published as a ceiling, not a promise.
            with_stop = project(settings.account_size, trades_per_year=25,
                                concurrent_positions=5,
                                win_rate=edge["win_rate"],
                                avg_win_pct=edge["avg_win_pct"],
                                avg_loss_pct=abs(DEFAULT_STOP_PCT))
            payload = {"edge": edge, "as_measured": base,
                       "with_stop_enforced": with_stop,
                       "stop_pct": DEFAULT_STOP_PCT,
                       "generated": today}
            with open(plan_path, "w") as f:
                json.dump(payload, f, indent=2)
            print(f"Income plan: edge {base['edge_per_trade_%']:+.2f}%/trade -> "
                  f"{base['expected_annual_return_%']:+.1f}%/yr; with a "
                  f"{DEFAULT_STOP_PCT:.0f}% stop {with_stop['expected_annual_return_%']:+.1f}%/yr")
        else:
            print("Income plan: not enough judged history yet.")
    except Exception as e:  # pragma: no cover - CI only
        print(f"Income plan skipped: {e}")
        if not os.path.exists(plan_path):
            with open(plan_path, "w") as f:
                json.dump({"error": "not generated yet"}, f)

    # Portfolio-level backtest: what a mechanical "buy the top N, hold H days"
    # book would actually have returned vs SPY. Best-effort — never fails the
    # scan. Costs a price-history fetch, so it runs after the scan is safe.
    bt_path = os.path.join(os.path.dirname(FRONTEND_SNAPSHOT), "backtest.json")
    try:
        from backend.portfolio_backtest import build as build_backtest
        bt = build_backtest(RESULTS_DIR, bt_path)
        if bt.get("points"):
            print(f"Backtest: {bt['trades']} trades, strategy {bt['strategy_return_%']:+.1f}% "
                  f"vs SPY {bt['benchmark_return_%']:+.1f}% (alpha {bt['alpha_%']:+.1f}pp)")
        else:
            print(f"Backtest: {bt.get('error', 'no result')}")
    except Exception as e:  # pragma: no cover - CI only
        print(f"Backtest skipped: {e}")
        if not os.path.exists(bt_path):  # keep the workflow's git add happy
            with open(bt_path, "w") as f:
                json.dump({"error": "not generated yet", "points": []}, f)

    # Push the day's best high-conviction setups to configured channels
    # (Slack/Discord webhooks via env/secrets); logs and no-ops when unset.
    outcome = send_scan_digest(today, results)
    print(f"Alert digest delivered to: {', '.join(outcome['delivered_to'])} "
          f"({len(outcome['tickers'])} setups)")


if __name__ == "__main__":
    main()
