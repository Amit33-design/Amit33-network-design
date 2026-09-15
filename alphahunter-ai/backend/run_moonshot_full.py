#!/usr/bin/env python3
"""The doubler study, run on the whole universe instead of 22 famous names.

The first version of this study sampled 22 tickers — NVDA, TSLA, PLTR and
friends — and reported that names down more than 50% doubled 55% of the time.
That number was worthless, and the reason was my sample, not the method: I had
hand-picked companies that are famous TODAY, which is a filter for having
survived and recovered. Every stock that fell 50% and kept falling into
delisting was absent by construction.

This runs the same study across the full >$1B-revenue universe. That does not
eliminate survivorship — the universe still only contains companies that exist
now — but it removes the much larger bias of me choosing the winners, and it
takes the sample from hundreds of observations to tens of thousands.

The residual bias is reported rather than glossed: `survivorship_note` states
exactly what is still missing, because a reader who takes these lifts at face
value will overestimate the beaten-down buckets specifically.

    python -m backend.run_moonshot_full [--limit N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os

from backend.moonshot_study import study
from backend.utils.universe import load_universe

BATCH = 120
HORIZON = 252


def fetch_batches(tickers: list[str], period: str = "5y") -> dict[str, list[float]]:
    """Batch-download closes. One bad batch must not lose the whole run."""
    import yfinance as yf

    out: dict[str, list[float]] = {}
    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i:i + BATCH]
        try:
            df = yf.download(chunk, period=period, auto_adjust=True,
                             progress=False, threads=True, group_by="ticker")
        except Exception as e:
            print(f"  batch {i // BATCH}: {e}")
            continue
        for t in chunk:
            try:
                col = df[t]["Close"] if len(chunk) > 1 else df["Close"]
                s = [float(x) for x in col.dropna()]
                if len(s) > 400:
                    out[t] = s
            except Exception:
                continue
        print(f"  {i + len(chunk)}/{len(tickers)} requested, {len(out)} usable")
    return out


def main() -> None:  # pragma: no cover - CI entrypoint
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    tickers = load_universe()
    if args.limit:
        tickers = tickers[:args.limit]
    print(f"universe: {len(tickers)} tickers")

    series = fetch_batches(tickers)
    print(f"fetched {len(series)} usable series")

    out = study(series, horizon=HORIZON)
    out["generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    out["universe_size"] = len(tickers)
    # Size the residual bias from the universe's own git history rather than
    # hand-waving at it. The drop rate is how much of the universe vanishes
    # per year — those are disproportionately the failures the study cannot see.
    try:
        from backend.universe_history import coverage, snapshots, survivorship_gap
        repo = os.path.dirname(here) if (here := os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))) else "."
        snaps = snapshots(repo)
        cov = coverage(snaps, horizon_days=HORIZON)
        out["universe_history"] = {"note": cov.note, "days": cov.days,
                                   "usable_for_horizon": cov.usable_for_horizon}
        if len(snaps) >= 2:
            ds = sorted(snaps)
            gap = survivorship_gap(snaps, ds[0], ds[-1])
            span = max(1, cov.days)
            gap["annualised_drop_rate_%"] = round(
                gap["drop_rate_%"] * 365 / span, 1)
            out["universe_history"]["gap"] = gap
            print(f"\nuniverse turnover: {gap['drop_rate_%']}% over {span} days "
                  f"(~{gap['annualised_drop_rate_%']}%/yr leaves the universe)")
        print(f"survivorship: {cov.note}")
    except Exception as e:
        out["universe_history"] = {"error": str(e)}

    out["survivorship_note"] = (
        "The universe contains only companies listed with >$1B revenue TODAY. "
        "Names that fell and were delisted, acquired at a discount or dropped "
        "below the revenue floor are absent, so the beaten-down buckets "
        "(down >50%, far off the high, cheap) are overstated — those are "
        "exactly the cohorts whose failures disappear. Treat their lift as an "
        "upper bound."
    )

    if "error" in out:
        print(out["error"])
    else:
        print(f"\n{out['observations']:,} observations across {out['tickers']} tickers"
              f" · base double rate {out['base_double_rate_%']}%")
        print(f"{'trait':<34}{'n':>7}{'with':>8}{'without':>9}{'lift':>7}{'median fwd':>12}")
        for t in out["traits"]:
            print(f"{t['trait']:<34}{t['n_with']:>7}{t['double_rate_with_%']:>7.1f}%"
                  f"{t['double_rate_without_%']:>8.1f}%{t['lift']:>7.2f}"
                  f"{t['median_forward_%']:>11.1f}%")
        if out.get("best_two_combined"):
            c = out["best_two_combined"]
            print(f"\ncombined: {c['trait']}\n  n={c['n_with']} "
                  f"doubled {c['double_rate_with_%']}% lift {c['lift']}")

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "results", "moonshot_full.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":  # pragma: no cover
    main()
