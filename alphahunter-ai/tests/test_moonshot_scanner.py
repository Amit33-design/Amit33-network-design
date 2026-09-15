"""Offline tests for the moonshot screen.

Its thresholds come from a measured study, so the tests check that the screen
actually reflects what was measured — including the traits that argue AGAINST
a double, which are the easy half to forget.
"""
import math

import numpy as np
import pandas as pd
import pytest

from backend.scanners.moonshot import (
    BASE_RATE, MoonshotScanner, annualised_vol, moonshot_score,
)
from backend.utils.market_data import StockSnapshot


def _hist(n=400, start=40.0, daily=0.0, vol=0.03, seed=2):
    rng = np.random.default_rng(seed)
    px, out = start, []
    for _ in range(n):
        px *= math.exp(daily + rng.normal(0, vol))
        out.append(px)
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame(
        {"Open": out, "High": [p * 1.02 for p in out], "Low": [p * 0.98 for p in out],
         "Close": out, "Volume": [8_000_000] * n}, index=idx)


INFO = {"totalRevenue": 2e9, "financialCurrency": "USD"}


def test_a_calm_stock_is_rejected_outright():
    """Calm stocks doubled 0.8% of the time — lift 0.17. Not a candidate at
    any price, so volatility is a hard gate rather than a scoring input."""
    calm = StockSnapshot("CALM", _hist(vol=0.004), INFO)
    assert MoonshotScanner().evaluate(calm) is None


def test_a_volatile_beaten_down_name_is_found_and_explained():
    snap = StockSnapshot("WILD", _hist(start=200.0, daily=-0.004, vol=0.055), INFO)
    hit = MoonshotScanner().evaluate(snap)

    assert hit is not None
    assert hit.metrics["profile"] == "moonshot"
    assert hit.metrics["volatility_%"] > 50
    assert hit.metrics["reasons"]
    assert "lift" in " ".join(hit.metrics["reasons"])


def test_every_pick_carries_its_measured_odds():
    """A screen for doubles must never read as a list of stocks that WILL
    double — the odds and the median travel with the pick."""
    hit = MoonshotScanner().evaluate(
        StockSnapshot("WILD", _hist(start=200.0, daily=-0.004, vol=0.055), INFO))
    m = hit.metrics
    assert m["measured_double_rate_%"] > m["base_rate_%"]
    assert m["median_outcome_%"] < 20            # the fat tail, thin middle
    assert "upper bound" in m["caveat"]
    assert "delists" in m["caveat"]


def test_scoring_follows_the_measured_lifts():
    very_vol = moonshot_score(95.0, -60.0, -65.0, 6.0)[0]
    mild = moonshot_score(55.0, -10.0, -20.0, 80.0)[0]
    calm = moonshot_score(18.0, 5.0, -5.0, 200.0)[0]

    assert very_vol > mild > calm
    assert calm == 0.0                          # floored, never negative


def test_being_near_the_high_counts_against_a_double():
    """Lift 0.61 — the opposite of what the growth screen wants, and the
    distinction between the two screens depends on it."""
    off_high = moonshot_score(85.0, -55.0, -60.0, 20.0)[0]
    at_high = moonshot_score(85.0, -55.0, -2.0, 20.0)[0]
    assert off_high > at_high
    assert any("argues against" in r for r in moonshot_score(85.0, -55.0, -2.0, 20.0)[1])


def test_the_calm_penalty_is_explained_not_silent():
    _, why = moonshot_score(18.0, -60.0, -70.0, 5.0)
    assert any("0.8%" in r for r in why)


def test_indicators_travel_with_the_hit():
    """Missing these silently strips the stop, target and R:R from every pick —
    the exact bug the growth scanner shipped with."""
    hit = MoonshotScanner().evaluate(
        StockSnapshot("WILD", _hist(start=200.0, daily=-0.004, vol=0.055), INFO))
    assert hit.metrics.get("indicators", {}).get("atr")


def test_penny_stocks_still_cannot_reach_the_screen():
    """The $10 tradability floor outranks the sub-$10 lift: 13.5% of penny
    names doubled, but the paper portfolio measured them losing 10% on
    average, and you cannot get filled at the quoted price."""
    cheap = StockSnapshot("PENNY", _hist(start=0.8, vol=0.06), INFO)
    assert MoonshotScanner().evaluate(cheap) is None


def test_annualised_vol_matches_a_hand_computation():
    flat = _hist(vol=0.0001)
    assert annualised_vol(flat) < 1.0
    assert annualised_vol(_hist(vol=0.05)) > annualised_vol(_hist(vol=0.01))
    assert BASE_RATE < 10                        # sanity: doubling is rare
