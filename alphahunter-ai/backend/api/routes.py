"""REST API routers implementing the spec's endpoint list.

    GET  /market/top              ranked AlphaHunter picks
    GET  /market/oversold         RSI<35 subset
    GET  /market/breakouts        above-EMA200 subset
    GET  /scanner/results         raw scan (configurable strictness)
    POST /scanner/run             scan a custom ticker list / params
    GET  /portfolio               (stub: returns persisted, else empty)
    POST /portfolio/import        import + analyze holdings
    GET  /portfolio/recommendations
    GET  /options/coveredcalls    top covered-call ideas
    GET  /options/csp             top cash-secured-put ideas
    GET  /backtest/{ticker}       single-name oversold backtest
    GET  /report/morning          full morning report
    POST /ai/ask                  natural-language query over results
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api.schemas import PortfolioIn, QueryIn, ScanQuery
from backend.ai.explainer import answer_query
from backend.backtesting.engine import backtest_oversold
from backend.portfolio.analyzer import Position, analyze_portfolio
from backend.reports.morning import generate_morning_report
from backend.scanners.runner import run_scan
from backend.utils.market_data import MarketData

router = APIRouter()


# ---------------------------------------------------------------- market
@router.get("/market/top")
def market_top(limit: int = Query(50, ge=1, le=500)):
    results = run_scan(require_all=False, limit=limit)
    return {"count": len(results), "results": results}


@router.get("/market/oversold")
def market_oversold(limit: int = Query(50, ge=1, le=500)):
    results = run_scan(require_all=False, limit=limit)
    subset = [r for r in results if (r["metrics"].get("rsi") or 100) < 35]
    return {"count": len(subset), "results": subset}


@router.get("/market/breakouts")
def market_breakouts(limit: int = Query(50, ge=1, le=500)):
    results = run_scan(require_all=False, limit=limit)
    subset = [r for r in results if r["metrics"].get("above_ema200")]
    return {"count": len(subset), "results": subset}


# ---------------------------------------------------------------- scanner
@router.get("/scanner/results")
def scanner_results(strict: bool = True, limit: int = Query(100, ge=1, le=2000)):
    results = run_scan(require_all=strict, limit=limit)
    return {"count": len(results), "strict": strict, "results": results}


@router.post("/scanner/run")
def scanner_run(body: ScanQuery):
    results = run_scan(require_all=body.require_all, tickers=body.tickers, limit=body.limit)
    return {"count": len(results), "results": results}


# ---------------------------------------------------------------- options
@router.get("/options/coveredcalls")
def covered_calls(limit: int = Query(25, ge=1, le=200)):
    results = run_scan(require_all=False, limit=limit)
    picks = [r for r in results if r.get("covered_call")]
    return {"count": len(picks), "results": picks}


@router.get("/options/csp")
def cash_secured_puts(limit: int = Query(25, ge=1, le=200)):
    results = run_scan(require_all=False, limit=limit)
    picks = sorted(
        [r for r in results if r.get("cash_secured_put")],
        key=lambda r: r["subscores"].get("options", 0), reverse=True,
    )
    return {"count": len(picks), "results": picks}


# ---------------------------------------------------------------- portfolio
@router.get("/portfolio")
def portfolio():
    return {"positions": [], "note": "POST holdings to /portfolio/import"}


@router.post("/portfolio/import")
def portfolio_import(body: PortfolioIn):
    positions = [Position(p.ticker, p.quantity, p.cost_basis) for p in body.positions]
    return analyze_portfolio(positions)


@router.get("/portfolio/recommendations")
def portfolio_recommendations():
    return {"note": "POST holdings to /portfolio/import to get recommendations"}


# ---------------------------------------------------------------- backtest
@router.get("/backtest/{ticker}")
def backtest(ticker: str, hold_days: int = Query(10, ge=1, le=120)):
    md = MarketData(period="5y")
    snap = md.snapshot(ticker.upper())
    if snap is None:
        return {"ticker": ticker.upper(), "error": "no data"}
    result = backtest_oversold(snap.history, hold_days=hold_days)
    return {"ticker": ticker.upper(), "hold_days": hold_days, **result.as_dict()}


# ---------------------------------------------------------------- report / ai
@router.get("/report/morning")
def morning(limit: int | None = Query(None, ge=1, le=2000)):
    return generate_morning_report(limit=limit)


@router.post("/ai/ask")
def ai_ask(body: QueryIn):
    results = run_scan(require_all=False, limit=body.limit)
    return answer_query(body.query, results)
