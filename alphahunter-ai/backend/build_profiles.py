#!/usr/bin/env python3
"""Company profiles: what the business does, and which segment it sits in.

A verdict on a ticker is much less useful when the reader does not know what
the company sells. "TNK is a buy" means little; "Teekay Tankers, a crude-oil
shipping company" is a different sentence.

Generated in CI rather than fetched live, because Yahoo's profile endpoint
needs a crumb that the serverless functions cannot obtain (see AGENTS.md §5).
yfinance handles that in Actions, so the result is committed as a static file
the static deploy can read — the same pattern as snapshot.json.

    python -m backend.build_profiles [--limit N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os

from backend.utils.universe import load_universe
from backend.watchlist import all_tickers

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "frontend", "public", "profiles.json")
SUMMARY_CHARS = 600


def _clean_summary(text: str | None) -> str | None:
    """Trim to a readable length at a sentence boundary, not mid-word."""
    if not text:
        return None
    t = " ".join(str(text).split())
    if len(t) <= SUMMARY_CHARS:
        return t
    cut = t[:SUMMARY_CHARS]
    stop = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return (cut[:stop + 1] if stop > SUMMARY_CHARS * 0.5 else cut.rstrip()) + " …"


def build(tickers: list[str]) -> dict:  # pragma: no cover - network
    import yfinance as yf

    out: dict[str, dict] = {}
    for i, t in enumerate(tickers, 1):
        try:
            info = yf.Ticker(t).info or {}
        except Exception:
            continue
        summary = _clean_summary(info.get("longBusinessSummary"))
        sector, industry = info.get("sector"), info.get("industry")
        if not (summary or sector):
            continue
        out[t] = {
            "name": info.get("longName") or info.get("shortName") or t,
            "sector": sector,
            "industry": industry,
            "summary": summary,
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country"),
            "website": info.get("website"),
            "market_cap": info.get("marketCap"),
        }
        if i % 100 == 0:
            print(f"  {i}/{len(tickers)} requested, {len(out)} with profiles")
    return out


def main() -> None:  # pragma: no cover - CI entrypoint
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    # Watchlist names first: they are always on screen, so they matter most if
    # the run is cut short.
    seen, tickers = set(), []
    for t in all_tickers() + load_universe():
        if t not in seen:
            seen.add(t)
            tickers.append(t)
    if args.limit:
        tickers = tickers[:args.limit]

    profiles = build(tickers)
    payload = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "count": len(profiles), "profiles": profiles}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
    print(f"wrote {len(profiles)} profiles -> {OUT}")


if __name__ == "__main__":  # pragma: no cover
    main()
