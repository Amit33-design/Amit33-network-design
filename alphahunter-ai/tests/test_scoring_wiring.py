"""Guards against the recurring "built but never wired" failure.

Four times now a module has shipped, looked finished, and been used nowhere:
growth wrote no dated results, moonshot wrote results nothing read, the
sentiment bundle reached one scoring path but not the other, and range_regime
was written with full JS parity and then wired only into the JS half.

Each was invisible from the outside — the app rendered, tests passed, and the
feature simply did not exist on the surface that mattered. These tests make
that class of mistake fail loudly.
"""
import inspect
import pathlib

import numpy as np
import pandas as pd
import pytest

from backend.scoring import composite
from backend.utils.market_data import StockSnapshot


def _oscillating_snapshot(ticker="RANGE", n=300):
    """A genuinely range-bound stock — the case entry timing exists for."""
    import math
    mid, amp = 100.0, 20.0
    closes = [mid + amp * math.sin(2 * math.pi * 4 * i / n) for i in range(n)]
    closes.append(118.0)                       # near the top of the range
    idx = pd.bdate_range("2025-01-01", periods=len(closes))
    hist = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [5_000_000] * len(closes)}, index=idx)
    return StockSnapshot(ticker=ticker, history=hist, info={
        "totalRevenue": 3e9, "financialCurrency": "USD",
        "recommendationMean": 2.0, "numberOfAnalystOpinions": 12,
        "targetMeanPrice": 130.0})


# --------------------------- entry timing ----------------------------------
def test_both_scoring_paths_compute_entry_timing():
    """range_regime.py existed with full JS parity and was imported by nothing
    on the Python side, so every scan pick shipped without entry timing while
    the Analysis page had it."""
    for fn in (composite.score_snapshot, composite.score_ticker_general):
        src = inspect.getsource(fn)
        assert "_entry_timing_for" in src, (
            f"{fn.__name__} does not compute entry timing — scan picks will "
            f"ship without it while the Analysis page shows it")


def test_a_range_bound_stock_actually_gets_a_wait_from_the_dashboard_path():
    """Asserting the call exists is not enough; it has to produce something."""
    rec = composite.score_ticker_general(_oscillating_snapshot())
    t = rec.get("entry_timing")

    assert t is not None, "a stock at the top of a year-long range got no timing"
    assert t["action"] == "wait"
    assert t["entry_target"] is not None and t["entry_target"] < rec["price"]
    assert "range" in t["reason"].lower()


def test_a_trending_stock_gets_no_entry_timing():
    """Position in a range means nothing when the range keeps moving — a
    trending name must not be told to wait for a price it may never see."""
    closes = [50.0 * (1.004 ** i) for i in range(300)]
    idx = pd.bdate_range("2025-01-01", periods=len(closes))
    hist = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [5_000_000] * len(closes)}, index=idx)
    snap = StockSnapshot("TREND", hist, {"totalRevenue": 3e9,
                                         "financialCurrency": "USD"})
    assert composite.score_ticker_general(snap).get("entry_timing") is None


# --------------------------- the other paths -------------------------------
def test_both_scoring_paths_validate_their_price_series():
    for fn in (composite.score_snapshot, composite.score_ticker_general):
        src = inspect.getsource(fn)
        assert "_quality_for" in src or "quality" in src, (
            f"{fn.__name__} displays prices without validating them")


def test_js_and_python_regime_constants_agree():
    """The two implementations are a deliberate port. If one drifts, a stock
    reads WAIT on the Analysis page and BUY in the scan."""
    js = (pathlib.Path(__file__).parent.parent.parent / "api" / "_regime.js").read_text()
    from backend.indicators import range_regime as py

    for name, val in (("LATERAL_NET_MOVE", py.LATERAL_NET_MOVE),
                      ("LATERAL_R2", py.LATERAL_R2),
                      ("TREND_R2", py.TREND_R2),
                      ("MIN_CROSSINGS", py.MIN_CROSSINGS),
                      ("BUY_ZONE", py.BUY_ZONE),
                      ("WAIT_ZONE", py.WAIT_ZONE)):
        assert f"{name} = {val}" in js, (
            f"{name} is {val} in Python but differs in api/_regime.js — the "
            f"two verdicts will disagree for the same stock")
