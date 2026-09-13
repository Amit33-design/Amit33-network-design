"""Offline tests for two-stock volatility harvesting."""
import math

import pytest

from backend.pair_rebalance import (
    capital_for_goal, correlation, expected_bonus, rank_pairs, realized_vol, simulate,
)


def _alternating(n, start=100.0, up=2.0, down=0.5):
    """A stock that doubles, halves, doubles... — net flat, wildly volatile."""
    out, px = [start], start
    for i in range(n - 1):
        px *= up if i % 2 == 0 else down
        out.append(px)
    return out


def _trend(n, start=100.0, daily=0.002):
    return [start * (1 + daily) ** i for i in range(n)]


def _flat(n, start=100.0):
    return [start] * n


# --------------------------- the core effect -------------------------------
def test_rebalancing_extracts_gain_from_two_stocks_that_go_nowhere():
    """Shannon's Demon: a violently volatile stock that ends where it started,
    paired with a flat one, still compounds when rebalanced."""
    a = _alternating(101)           # ends exactly where it began
    b = _flat(101)
    assert a[-1] == pytest.approx(a[0])

    r = simulate(a, b, capital=100_000)

    assert r["static_5050_value"] == pytest.approx(100_000, rel=1e-6)  # holding earns nothing
    assert r["final_value"] > 200_000                                  # rebalancing does
    assert r["rebalancing_bonus_%"] > 0


def test_the_bonus_needs_volatility_not_mean_reversion():
    """Two calm stocks harvest nothing however long you run it."""
    r = simulate(_trend(300, daily=0.0004), _trend(300, daily=0.0003))
    assert abs(r["rebalancing_bonus_%"]) < 0.5


def test_correlated_stocks_harvest_almost_nothing():
    """The bonus scales with (1 - rho). Two names that move together are not
    a pair, they are one position held twice."""
    base = _alternating(201)
    same = [p * 1.01 for p in base]            # essentially identical path
    r = simulate(base, same)

    assert r["correlation"] > 0.99
    assert r["expected_bonus_%"] < 0.5


# --------------------------- where it LOSES --------------------------------
def test_rebalancing_loses_to_simply_holding_the_winner():
    """The honest cost: rebalancing systematically sells the stock that is
    working to buy the one that isn't."""
    winner = _trend(400, daily=0.004)          # compounds hard
    laggard = _flat(400)
    r = simulate(winner, laggard)

    assert r["beat_best_single_stock"] is False
    assert r["final_value"] < r["hold_a_value"]


def test_trading_costs_eat_the_bonus_on_a_daily_schedule():
    a, b = _alternating(201), _flat(201)
    free = simulate(a, b, cost_bps=0.0)
    costly = simulate(a, b, cost_bps=10.0)     # 10bps per rebalance leg

    assert costly["final_value"] < free["final_value"]
    assert costly["trading_costs"] > 0
    assert costly["turnover_x_capital"] > 10   # daily rebalancing churns hard


def test_a_no_trade_band_cuts_the_number_of_rebalances():
    # A gentle random walk, because a stock that doubles and halves every day
    # blows through any band and would not exercise this at all.
    import random
    random.seed(9)
    a = [100.0]
    for _ in range(400):
        a.append(a[-1] * math.exp(random.gauss(0, 0.015)))
    b = _flat(401)

    daily = simulate(a, b, band=0.0)
    banded = simulate(a, b, band=0.03)
    assert daily["rebalances"] > banded["rebalances"] > 0
    assert daily["turnover_x_capital"] > banded["turnover_x_capital"]


def test_tax_drag_is_applied_to_gains_not_ignored():
    a, b = _alternating(201), _flat(201)
    r = simulate(a, b, tax_rate=0.35)
    assert r["after_tax_value"] < r["final_value"]
    assert r["after_tax_value"] > r["capital"]


# --------------------------- the analytics ---------------------------------
def test_the_formula_and_the_simulation_broadly_agree():
    """If the closed form and the path simulation disagree wildly, one of them
    is wrong and the whole exercise is worthless."""
    import random
    random.seed(5)
    n = 1500
    a, b = [100.0], [100.0]
    for _ in range(n):
        a.append(a[-1] * math.exp(random.gauss(0, 0.03)))
        b.append(b[-1] * math.exp(random.gauss(0, 0.03)))

    r = simulate(a, b)
    assert r["correlation"] < 0.2
    # The formula is defined against the weighted average of the two stocks'
    # own compound returns, NOT against a static blend (which drifts toward
    # the winner and so earns part of the gap by itself).
    assert r["bonus_vs_weighted_avg_%"] == pytest.approx(r["expected_bonus_%"], abs=1.5)
    assert r["bonus_vs_weighted_avg_%"] > r["rebalancing_bonus_%"]


def test_expected_bonus_rewards_vol_and_punishes_correlation():
    assert expected_bonus(0.6, 0.6, 0.0) > expected_bonus(0.3, 0.3, 0.0)
    assert expected_bonus(0.6, 0.6, 0.9) < expected_bonus(0.6, 0.6, 0.0)
    assert expected_bonus(0.6, 0.6, 1.0) == pytest.approx(0.0)


def test_pair_ranking_prefers_volatile_and_uncorrelated():
    import random
    random.seed(1)
    def walk(vol, n=400):
        out = [100.0]
        for _ in range(n):
            out.append(out[-1] * math.exp(random.gauss(0, vol)))
        return out

    ranked = rank_pairs({"WILD1": walk(0.04), "WILD2": walk(0.04),
                         "CALM1": walk(0.004), "CALM2": walk(0.004)})
    assert ranked[0]["pair"] == "WILD1/WILD2"
    assert ranked[-1]["pair"] == "CALM1/CALM2"


# --------------------------- the money question ----------------------------
def test_capital_required_for_an_income_goal():
    assert capital_for_goal(100_000, 5.0) == pytest.approx(2_000_000)
    assert capital_for_goal(100_000, 10.0) == pytest.approx(1_000_000)
    assert capital_for_goal(100_000, 0.0) is None      # no bonus, no amount works


# --------------------------- guards ----------------------------------------
def test_too_little_data_is_refused():
    assert "error" in simulate([100.0] * 5, [100.0] * 5)


def test_helpers_handle_degenerate_input():
    assert realized_vol([100.0]) is None
    assert correlation([1.0], [1.0]) is None
    assert realized_vol(_flat(50)) == pytest.approx(0.0)
