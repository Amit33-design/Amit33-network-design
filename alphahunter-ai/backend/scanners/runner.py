"""Drives a scanner across the universe and attaches composite scores.

This is the orchestration the REST API and the morning report call into. It
fetches snapshots (cached), runs the scanner, scores every hit, and returns a
ranked list of ``StockRecommendation`` dicts.
"""
from __future__ import annotations

import time
from typing import Callable

from backend.config import settings
from backend.scanners.alphahunter import AlphaHunterScanner, OpportunityScanner
from backend.scanners.base import ScanHit
from backend.scoring.composite import score_snapshot
from backend.utils.market_data import MarketData
from backend.utils.universe import load_universe


def run_scan(
    scanner=None,
    tickers: list[str] | None = None,
    require_all: bool = True,
    limit: int | None = None,
    progress: Callable[[int, int, int], None] | None = None,
) -> list[dict]:
    """Run ``scanner`` over ``tickers`` (or the default universe) and rank hits.

    Returns a list of recommendation dicts sorted by composite score desc.
    """
    scanner = scanner or AlphaHunterScanner(require_all=require_all)
    md = MarketData()

    if tickers is None:
        tickers = load_universe()
    if settings.max_universe and not limit:
        limit = settings.max_universe
    if limit:
        tickers = tickers[:limit]

    results: list[dict] = []
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        snap = md.snapshot(ticker)
        if snap is not None:
            hit: ScanHit | None = scanner.evaluate(snap)
            if hit is not None:
                scored = score_snapshot(snap, hit, md=md)
                results.append(scored)
        if progress and i % 25 == 0:
            progress(i, total, len(results))
        time.sleep(settings.request_sleep)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def run_moonshot_scan(
    limit: int | None = None,
    max_scored: int | None = 40,
) -> list[dict]:
    """Rank the lottery-ticket profile: volatile and beaten down.

    Ranked by moonshot score rather than the composite, for the same reason
    the growth scan is: the composite was tuned for oversold bounce setups and
    scores a different thing entirely.
    """
    from backend.scanners.moonshot import MoonshotScanner

    md = MarketData()
    scanner = MoonshotScanner()
    tickers = load_universe()
    if limit:
        tickers = tickers[:limit]

    hits = []
    for ticker in tickers:
        snap = md.snapshot(ticker)
        if snap is None:
            continue
        hit = scanner.evaluate(snap)
        if hit is not None:
            hits.append((hit.metrics.get("moonshot_score", 0), snap, hit))
        time.sleep(settings.request_sleep)

    hits.sort(key=lambda x: -x[0])
    results = []
    for _score, snap, hit in hits[: (max_scored or len(hits))]:
        try:
            results.append(score_snapshot(snap, hit, md=md))
        except Exception:
            continue
    results.sort(key=lambda r: ((r.get("metrics") or {}).get("moonshot_score") or 0,
                                r.get("score") or 0), reverse=True)
    return results


def run_growth_scan(
    limit: int | None = None,
    max_scored: int | None = 60,
    loose: bool = False,
) -> list[dict]:
    """Rank growing businesses whose stock is already working.

    Structurally the opposite of the oversold screens: it wants strength, not
    wreckage. SPY's own 3-month return is fetched once and passed in, so
    "beating the market" is measured rather than assumed.
    """
    from backend.indicators import technical as ta
    from backend.scanners.growth import GrowthScanner

    md = MarketData()
    spy_ret = None
    spy = md.snapshot("SPY")
    if spy is not None:
        spy_ret = ta.indicator_bundle(spy.history).get("ret_60d")

    scanner = GrowthScanner(spy_ret_60d=spy_ret, loose=loose)
    tickers = load_universe()
    if limit:
        tickers = tickers[:limit]

    hits: list[tuple[float, object, object]] = []
    for ticker in tickers:
        snap = md.snapshot(ticker)
        if snap is None:
            continue
        hit = scanner.evaluate(snap)
        if hit is not None:
            hits.append((hit.metrics.get("growth_score", 0), snap, hit))
        time.sleep(settings.request_sleep)

    # Score only the strongest candidates — the composite scoring step is the
    # expensive part and there is no value in pricing the tail.
    hits.sort(key=lambda x: -x[0])
    results = []
    for _score, snap, hit in hits[: (max_scored or len(hits))]:
        try:
            results.append(score_snapshot(snap, hit, md=md))
        except Exception:
            continue

    # Rank by the GROWTH score, not the composite. The composite was tuned for
    # oversold bounce setups, so it marks a healthy leader down for the crime
    # of not having crashed — on the first live run it put NVDA above FNV and
    # PLTR purely because they were less beaten up. The composite still rides
    # along on each row as a second opinion.
    results.sort(key=lambda r: ((r.get("metrics") or {}).get("growth_score") or 0,
                                r.get("score") or 0), reverse=True)
    return results


def run_opportunity_scan(
    limit: int | None = None,
    max_scored: int | None = None,
    progress: Callable[[int, int, int], None] | None = None,
) -> list[dict]:
    """Broad pullback/dip scan, ranked by composite score.

    Two passes: cheaply collect candidates (the scanner only reads the cached
    snapshot's indicators), sort by most-oversold (month return), then fully
    score just the top ``max_scored`` to bound the expensive scoring, and return
    them ranked by score. Keeps the Opportunities board populated year-round.
    """
    md = MarketData()
    scanner = OpportunityScanner()
    tickers = tickers_ = load_universe()
    if limit:
        tickers = tickers_[:limit]
    max_scored = max_scored or settings.opp_max_scored

    candidates: list[tuple[float, str]] = []
    snaps = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        snap = md.snapshot(ticker)
        if snap is not None:
            hit = scanner.evaluate(snap)
            if hit is not None:
                snaps[ticker] = (snap, hit)
                candidates.append((hit.metrics.get("month_%") or 0.0, ticker))
        if progress and i % 50 == 0:
            progress(i, total, len(candidates))
        time.sleep(settings.request_sleep)

    candidates.sort(key=lambda x: x[0])  # most negative month first
    results: list[dict] = []
    for _, ticker in candidates[:max_scored]:
        snap, hit = snaps[ticker]
        results.append(score_snapshot(snap, hit, md=md))
    results.sort(key=lambda r: r["score"], reverse=True)
    return results

# ---------------------------------------------------------------------------
# One pass, every screen
# ---------------------------------------------------------------------------
def run_all_screens(
    limit: int | None = None,
    *,
    max_crash: int | None = None,
    max_opportunity: int | None = None,
    max_growth: int = 40,
    max_moonshot: int = 30,
    progress: Callable[[int, int, dict], None] | None = None,
) -> dict[str, list[dict]]:
    """Fetch each ticker ONCE and run every scanner against it.

    This replaces four separate passes over the universe (strict crash,
    pullback, growth, moonshot) that together killed the daily pipeline. Each
    pass slept 0.3 s per ticker unconditionally, and because the snapshot cache
    expires after 15 minutes, passes three and four were not even reading
    cache on a 38-minute scan — they re-fetched all ~1,900 tickers from the
    network. Four full scans against a 60-minute timeout: every run from 18 Sep
    onward was cancelled and nothing was committed for nine days.

    Fetching once is the fix; sleeping only on a real network fetch is the
    second half of it. Scoring (the expensive part) still runs only on each
    screen's top candidates.
    """
    from backend.indicators import technical as ta
    from backend.scanners.growth import GrowthScanner
    from backend.scanners.moonshot import MoonshotScanner

    md = MarketData()
    tickers = load_universe()
    if settings.max_universe and not limit:
        limit = settings.max_universe
    if limit:
        tickers = tickers[:limit]

    spy_ret = None
    spy = md.snapshot("SPY")
    if spy is not None:
        spy_ret = ta.indicator_bundle(spy.history).get("ret_60d")

    scanners = {
        "crash": AlphaHunterScanner(require_all=True),
        "opportunity": OpportunityScanner(),
        "growth": GrowthScanner(spy_ret_60d=spy_ret),
        "moonshot": MoonshotScanner(),
    }
    # (rank key, snapshot, hit) per screen. Each screen ranks candidates its
    # own way before the expensive scoring step.
    hits: dict[str, list[tuple[float, object, object]]] = {k: [] for k in scanners}

    total = len(tickers)
    fetched = 0
    for i, ticker in enumerate(tickers, 1):
        cached = md.is_cached(ticker)
        try:
            snap = md.snapshot(ticker)
        except Exception:
            snap = None
        if not cached:
            fetched += 1
            time.sleep(settings.request_sleep)   # courtesy only on a real fetch
        if snap is None:
            continue

        for name, scanner in scanners.items():
            try:
                hit = scanner.evaluate(snap)
            except Exception:
                continue
            if hit is None:
                continue
            m = hit.metrics or {}
            rank = {
                "crash": 0.0,                                  # scored in full
                "opportunity": -(m.get("month_%") or 0.0),     # most oversold first
                "growth": m.get("growth_score") or 0.0,
                "moonshot": m.get("moonshot_score") or 0.0,
            }[name]
            hits[name].append((rank, snap, hit))

        if progress and i % 100 == 0:
            progress(i, total, {k: len(v) for k, v in hits.items()})

    caps = {
        "crash": max_crash,
        "opportunity": max_opportunity or settings.opp_max_scored,
        "growth": max_growth,
        "moonshot": max_moonshot,
    }
    out: dict[str, list[dict]] = {}
    for name, rows in hits.items():
        rows.sort(key=lambda x: -x[0])
        cap = caps[name]
        scored = []
        for _rank, snap, hit in (rows[:cap] if cap else rows):
            try:
                scored.append(score_snapshot(snap, hit, md=md))
            except Exception:
                continue
        # Growth and moonshot rank by their own score; the composite was tuned
        # for oversold bounces and would reorder them by the wrong measure.
        key = {"growth": "growth_score", "moonshot": "moonshot_score"}.get(name)
        if key:
            scored.sort(key=lambda r: ((r.get("metrics") or {}).get(key) or 0,
                                       r.get("score") or 0), reverse=True)
        else:
            scored.sort(key=lambda r: r["score"], reverse=True)
        out[name] = scored

    out["_stats"] = [{"tickers": total, "network_fetches": fetched,
                      **{f"{k}_hits": len(v) for k, v in hits.items()}}]
    return out
