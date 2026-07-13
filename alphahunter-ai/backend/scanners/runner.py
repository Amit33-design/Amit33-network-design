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
