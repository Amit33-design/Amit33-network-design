"""Command-line entrypoint — run a scan without starting the API.

    python -m backend.cli scan --limit 200 --loose
    python -m backend.cli report
    python -m backend.cli backtest AAPL --hold 10

Designed to drop straight into a GitHub Actions step, mirroring the existing
screener/run_ci.py pattern.
"""
from __future__ import annotations

import argparse
import json


def _print_results(results: list[dict], top: int = 25) -> None:
    print(f"\n{len(results)} matches (showing top {min(top, len(results))}):\n")
    header = f"{'TICKER':<8}{'SCORE':>6}  {'ACTION':<11}{'RSI':>6}{'DAY%':>7}{'MON%':>7}  CONF"
    print(header)
    print("-" * len(header))
    for r in results[:top]:
        m = r["metrics"]
        print(f"{r['ticker']:<8}{r['score']:>6.1f}  {r['action']:<11}"
              f"{(m.get('rsi') or 0):>6.0f}{(m.get('day_%') or 0):>7.1f}"
              f"{(m.get('month_%') or 0):>7.1f}  {r['confidence']}")


def main() -> None:
    p = argparse.ArgumentParser(description="AlphaHunter AI CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scan", help="run the AlphaHunter scan")
    sc.add_argument("--limit", type=int, default=None)
    sc.add_argument("--loose", action="store_true",
                    help="surface near-misses (core crash filter only)")
    sc.add_argument("--json", action="store_true")

    rp = sub.add_parser("report", help="generate the morning report")
    rp.add_argument("--limit", type=int, default=None)

    bt = sub.add_parser("backtest", help="backtest the oversold setup on a ticker")
    bt.add_argument("ticker")
    bt.add_argument("--hold", type=int, default=10)

    args = p.parse_args()

    if args.cmd == "scan":
        from backend.scanners.runner import run_scan
        results = run_scan(require_all=not args.loose, limit=args.limit,
                           progress=lambda i, t, n: print(f"  ...{i}/{t} scanned, {n} hits"))
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            _print_results(results)
    elif args.cmd == "report":
        from backend.reports.morning import generate_morning_report
        print(json.dumps(generate_morning_report(limit=args.limit), indent=2, default=str))
    elif args.cmd == "backtest":
        from backend.utils.market_data import MarketData
        from backend.backtesting.engine import backtest_oversold
        snap = MarketData(period="5y").snapshot(args.ticker.upper())
        if snap is None:
            print("no data")
            return
        print(json.dumps(backtest_oversold(snap.history, hold_days=args.hold).as_dict(),
                         indent=2))


if __name__ == "__main__":
    main()
