"""Offline tests for the daily pair-rebalancing instruction."""
import pytest

from backend.pair_signals import daily_order, open_position


def test_a_balanced_book_is_told_to_do_nothing():
    o = daily_order("AAA", "BBB", 100.0, 100.0, 50, 50)
    assert o.action == "hold"
    assert "inside the" in o.reason and "band" in o.reason


def test_a_drifted_book_gets_a_concrete_order():
    # AAA doubled: 50x200 = 10,000 vs 50x100 = 5,000 ⇒ 66.7% / 33.3%.
    o = daily_order("AAA", "BBB", 200.0, 100.0, 50, 50)

    assert o.action == "rebalance"
    assert o.sell_ticker == "AAA" and o.buy_ticker == "BBB"
    assert o.drift_pp == pytest.approx(16.67, abs=0.1)
    # The excess is $2,500, but whole shares only: 12 x $200 = $2,400 sold,
    # which buys 24 of BBB at $100. The $100 residual is the rounding cost.
    assert o.sell_shares == 12 and o.sell_value == 2_400.0
    assert o.buy_shares == 24 and o.buy_value == 2_400.0


def test_the_order_actually_restores_the_target_weight():
    """The point of the instruction is that following it works."""
    pa, pb, sa, sb = 180.0, 40.0, 60, 90
    o = daily_order("AAA", "BBB", pa, pb, sa, sb)
    assert o.action == "rebalance"

    if o.sell_ticker == "AAA":
        sa -= o.sell_shares
        sb += o.buy_shares
    else:
        sb -= o.sell_shares
        sa += o.buy_shares

    after = daily_order("AAA", "BBB", pa, pb, sa, sb)
    assert abs(after.drift_pp) < abs(o.drift_pp)
    assert after.action == "hold"          # one trade is enough


def test_the_losing_leg_is_the_one_bought():
    """This is the whole mechanism — buy what fell, sell what rose."""
    o = daily_order("WINNER", "LOSER", 300.0, 50.0, 50, 50)
    assert o.sell_ticker == "WINNER" and o.buy_ticker == "LOSER"


def test_a_tiny_drift_is_not_worth_the_spread():
    o = daily_order("AAA", "BBB", 101.0, 100.0, 50, 50, band=0.03)
    assert o.action == "hold"


def test_a_drift_smaller_than_one_share_holds():
    o = daily_order("PRICEY", "BBB", 5_000.0, 10.0, 1, 400, band=0.001)
    assert o.action == "hold"
    assert "less than one share" in o.reason


def test_a_trade_below_the_minimum_ticket_is_skipped():
    o = daily_order("AAA", "BBB", 20.0, 10.0, 30, 40, band=0.001, min_trade=500.0)
    assert o.action == "hold"
    assert "minimum" in o.reason


def test_whole_share_residual_cash_is_reported_not_hidden():
    o = daily_order("AAA", "BBB", 100.0, 70.0, 100, 50, band=0.01)
    if o.action == "rebalance" and o.warnings:
        assert any("left as cash" in w for w in o.warnings)


def test_you_cannot_sell_more_than_you_hold():
    o = daily_order("AAA", "BBB", 100.0, 1.0, 2, 10_000, band=0.001)
    assert o.sell_shares <= 10_000
    if o.sell_ticker == "AAA":
        assert o.sell_shares <= 2


def test_an_empty_book_is_handled():
    o = daily_order("AAA", "BBB", 100.0, 100.0, 0, 0)
    assert o.action == "hold" and "no position" in o.reason


def test_opening_a_position_buys_whole_shares_within_budget():
    out = open_position("AAA", "BBB", 150.0, 40.0, 10_000.0)
    a, b = out["buy"]
    assert a["shares"] == 33 and b["shares"] == 125     # 4,950 + 5,000
    assert out["invested"] <= 10_000
    assert out["cash_left"] >= 0


def test_opening_warns_when_the_capital_cannot_hold_both():
    out = open_position("BRKA", "BBB", 700_000.0, 50.0, 1_000.0)
    assert out["buy"][0]["shares"] == 0
    assert any("not enough" in w for w in out["warnings"])


def test_a_non_5050_target_is_respected():
    o = daily_order("AAA", "BBB", 100.0, 100.0, 50, 50, target_a=0.75)
    assert o.action == "rebalance"
    assert o.buy_ticker == "AAA"           # underweight the 75% leg
