"""Weekly log of analyst EPS estimates, to test estimate REVISIONS forward.

Revision momentum (stocks whose estimates are being raised outperform) is one
of the best-documented anomalies, but free data has no history of past
estimates — yfinance only knows today's, plus where they stood 7/30/60/90
days ago. That cannot be backtested honestly. It can be tested going
forward: snapshot the revision now, look at the price 20 and 60 sessions
later. This starts that clock. factor_study.revision_study() evaluates the
logs once enough have matured.

    python -m backend.estimate_log [--sample 600]
writes results/estimates_YYYY-MM-DD.json (deliberately not a screen name, so
the screen registry never reads it as picks).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import time

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def _num(x):
    try:
        x = float(x)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def revision_fields(trend, revisions) -> dict:
    """Current-fiscal-year ('0y') EPS revision over 30/90 days and the net
    count of analysts raising vs cutting in the last 30 days. Pure on
    DataFrame-likes indexed by period."""
    out = {"rev_30d_pct": None, "rev_90d_pct": None, "net_up_30d": None}
    try:
        row = trend.loc["0y"]
        cur, d30, d90 = _num(row.get("current")), _num(row.get("30daysAgo")), _num(row.get("90daysAgo"))
        if cur is not None and d30:
            out["rev_30d_pct"] = (cur - d30) / abs(d30) * 100
        if cur is not None and d90:
            out["rev_90d_pct"] = (cur - d90) / abs(d90) * 100
    except Exception:
        pass
    try:
        r = revisions.loc["0y"]
        up, down = _num(r.get("upLast30days")), _num(r.get("downLast30days"))
        if up is not None and down is not None:
            out["net_up_30d"] = up - down
    except Exception:
        pass
    return out


def main() -> None:  # pragma: no cover - network
    import yfinance as yf

    from backend.theme_pulse import load_defs, members
    from backend.utils.universe import load_universe
    from backend.verdict_data import sample_tickers

    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=600)
    a = ap.parse_args()
    public = os.path.join(os.path.dirname(RESULTS), "frontend", "public")
    try:
        with open(os.path.join(public, "profiles.json")) as f:
            profiles = json.load(f).get("profiles", {})
    except Exception:
        profiles = {}
    tm = sorted({t for v in members(load_defs(), profiles).values() for t in v})
    tickers = sample_tickers(load_universe(), tm, max(0, a.sample - len(tm)))

    today = dt.date.today().isoformat()
    rows = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            f = revision_fields(tk.eps_trend, tk.eps_revisions)
            if any(v is not None for v in f.values()):
                rows[t] = f
        except Exception:
            pass
        time.sleep(0.2)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, f"estimates_{today}.json"), "w") as fh:
        json.dump({"date": today, "count": len(rows), "estimates": rows}, fh)
    print(f"estimate log: {len(rows)}/{len(tickers)} stocks with estimates -> estimates_{today}.json")


if __name__ == "__main__":  # pragma: no cover
    main()
