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

from backend.utils.universe import is_common_share, load_universe
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


MAX_AGE_DAYS = 30   # business descriptions change slowly; refresh monthly


def plan_fetch(existing: dict, priority: list[str], universe: list[str],
               limit: int | None, today: dt.date) -> list[str]:
    """Which tickers to fetch this run. Pure, so it is tested.

    The old run fetched the SAME first 400 tickers every day and rewrote the
    file, so the other ~1,500 never got a description — the Analysis page
    showed a sector badge and nothing about what most companies do. Now each
    run spends its budget on: priority names that are missing or stale, then
    universe names never fetched, then the stalest. Coverage grows every day
    until the whole universe is in, and then stays fresh.
    """
    def age(t: str) -> int:
        f = (existing.get(t) or {}).get("fetched")
        try:
            return (today - dt.date.fromisoformat(f)).days
        except (TypeError, ValueError):
            return 10_000          # fetched before dates were stamped
    seen: set[str] = set()
    ordered: list[str] = []
    def add(ts):
        for t in ts:
            if t not in seen:
                seen.add(t)
                ordered.append(t)
    add(t for t in priority if t not in existing or age(t) > MAX_AGE_DAYS)
    add(t for t in universe if t not in existing)
    add(sorted((t for t in universe if age(t) > MAX_AGE_DAYS), key=age, reverse=True))
    return ordered[:limit] if limit else ordered


def _scan_tickers() -> list[str]:
    """Tickers on today's pick lists: the names people open next."""
    base = os.path.dirname(OUT)
    out: list[str] = []
    for name in ("snapshot.json", "growth.json", "moonshot.json"):
        try:
            with open(os.path.join(base, name)) as f:
                j = json.load(f)
            rows = j.get("results") or j.get("picks") or j.get("recommendations") or []
            out += [r.get("ticker") for r in rows if isinstance(r, dict) and r.get("ticker")]
        except Exception:
            continue
    return out


def main() -> None:  # pragma: no cover - CI entrypoint
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="max profiles to FETCH this run (existing ones are kept)")
    args = ap.parse_args()

    existing: dict = {}
    try:
        with open(OUT) as f:
            existing = json.load(f).get("profiles", {})
    except Exception:
        pass
    today = dt.datetime.now(dt.timezone.utc).date()
    universe = [t for t in load_universe() if is_common_share(t)]
    todo = plan_fetch(existing, all_tickers() + _scan_tickers(), universe, args.limit, today)

    fresh = build(todo)
    for p in fresh.values():
        p["fetched"] = today.isoformat()
    profiles = {**existing, **fresh}
    payload = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "count": len(profiles), "profiles": profiles}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
    print(f"fetched {len(fresh)}/{len(todo)}; {len(profiles)} profiles total -> {OUT}")


if __name__ == "__main__":  # pragma: no cover
    main()
