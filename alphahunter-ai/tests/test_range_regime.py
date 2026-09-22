"""Offline tests for lateral-range detection and entry timing."""
import math

import pytest

from backend.indicators.range_regime import analyse


def _oscillate(n=252, low=80.0, high=120.0, cycles=4):
    """A genuine range: repeated round trips between two levels."""
    mid, amp = (low + high) / 2, (high - low) / 2
    return [mid + amp * math.sin(2 * math.pi * cycles * i / n) for i in range(n)]


def _trend(n=252, start=100.0, daily=0.0035):
    return [start * (1 + daily) ** i for i in range(n)]


def _drift_ending_flat(n=252):
    """Rises then falls back — ends flat WITHOUT being range-bound. The case
    that fools a net-move-only test."""
    half = n // 2
    up = [100 * (1 + 0.006) ** i for i in range(half)]
    down = [up[-1] * (1 - 0.006) ** i for i in range(n - half)]
    return up + down


# --------------------------- classification --------------------------------
def test_an_oscillating_stock_is_called_lateral():
    r = analyse(_oscillate())
    assert r.regime == "lateral"
    assert r.crossings >= 3
    assert r.r2 < 0.35


def test_a_compounding_stock_is_called_trending_up():
    r = analyse(_trend())
    assert r.regime == "trending_up"
    assert r.action == "none"
    assert "not range-bound" in r.reason


def test_a_falling_stock_is_called_trending_down():
    r = analyse(_trend(daily=-0.003))
    assert r.regime == "trending_down"
    assert r.action == "none"


def test_a_round_trip_that_ends_flat_is_not_mistaken_for_a_range():
    """It goes nowhere on net, but it never oscillated — buying its 'range low'
    would mean buying a downtrend."""
    r = analyse(_drift_ending_flat())
    assert abs(r.net_move_pct) < 20          # ends near where it started...
    assert r.crossings < 3                   # ...but crossed the midline once
    assert r.regime != "lateral"


# --------------------------- entry guidance --------------------------------
def test_the_bottom_of_a_range_is_a_buy_zone():
    px = _oscillate()
    px.append(82.0)                          # drop to near the low
    r = analyse(px)
    assert r.regime == "lateral" and r.action == "buy_zone"
    assert r.position < 0.35
    assert "worth buying" in r.reason
    assert r.upside_to_range_high_pct > 30


def test_the_top_of_a_range_says_wait_with_a_price():
    px = _oscillate()
    px.append(118.0)                         # near the high
    r = analyse(px)
    assert r.action == "wait"
    assert r.entry_target is not None and r.entry_target < 118.0
    assert "wait for roughly" in r.reason
    assert f"${r.entry_target:,.2f}" in r.reason


def test_mid_range_also_waits_rather_than_shrugging():
    px = _oscillate()
    px.append(100.0)
    r = analyse(px)
    assert r.action == "wait"
    assert "mid-range" in r.reason


def test_a_wait_says_how_long_the_wait_has_historically_been():
    """'Wait' immediately raises 'how long?' — answer it from history."""
    px = _oscillate()
    px.append(118.0)
    r = analyse(px)
    assert r.typical_wait_sessions is not None
    assert 5 < r.typical_wait_sessions < 252
    assert "every" in r.reason


def test_a_trending_stock_gets_no_entry_target():
    """Position in range is meaningless when the range keeps moving."""
    r = analyse(_trend())
    assert r.entry_target is None
    assert r.action == "none"


# --------------------------- guards ----------------------------------------
def test_too_little_history_is_refused():
    r = analyse([100.0] * 20)
    assert r.regime == "unclear" and "not enough history" in r.reason


def test_a_flat_line_is_not_a_tradeable_range():
    r = analyse([100.0] * 300)
    assert r.regime == "unclear"


def test_the_read_serialises_for_the_api():
    d = analyse(_oscillate() + [118.0]).to_dict()
    for k in ("regime", "position_in_range", "action", "entry_target", "reason"):
        assert k in d
    assert d["action"] == "wait"
