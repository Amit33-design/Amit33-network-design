"""Offline tests for the growth scanner, exit rules and income planner."""
import numpy as np
import pandas as pd
import pytest

from backend.exit_rules import build_plan, check_exit
from backend.income_plan import assess, capital_required, edge_from_history, project
from backend.scanners.growth import GrowthScanner, growth_score
from backend.utils.market_data import StockSnapshot


# --------------------------- fixtures --------------------------------------
def _hist(n=300, start=50.0, daily=0.004, noise=0.012):
    """A synthetic price series with a controllable drift.

    Noise is on by default and matters: a perfectly monotonic rise gives RSI
    100, which the scanner correctly rejects as overheated. Real uptrends
    pull back, so the fixture has to as well or it tests nothing.
    """
    rng = np.random.default_rng(0)
    px, out = start, []
    for _ in range(n):
        px *= 1 + daily + (rng.normal(0, noise) if noise else 0)
        out.append(px)
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame(
        {"Open": out, "High": [p * 1.01 for p in out], "Low": [p * 0.99 for p in out],
         "Close": out, "Volume": [5_000_000] * n},
        index=idx)


GROWTH_INFO = {
    "revenueGrowth": 0.35, "earningsGrowth": 0.40, "grossMargins": 0.62,
    "operatingMargins": 0.22, "freeCashflow": 5e8, "pegRatio": 1.4,
    "totalRevenue": 5e9, "financialCurrency": "USD",
}


# --------------------------- growth score ----------------------------------
def test_a_growing_leader_scores_far_above_a_shrinking_laggard():
    up = _hist(daily=0.004)
    down = _hist(daily=-0.003)
    from backend.indicators import technical as ta

    good = growth_score(ta.indicator_bundle(up), GROWTH_INFO, spy_ret_60d=5.0)
    bad = growth_score(
        ta.indicator_bundle(down),
        {"revenueGrowth": -0.10, "earningsGrowth": -0.30, "grossMargins": 0.12,
         "operatingMargins": -0.05, "pegRatio": 9.0},
        spy_ret_60d=5.0)

    assert good.score > bad.score + 30
    assert any("revenue growing" in r for r in good.reasons)
    assert any("shrinking" in w or "thin" in w for w in bad.warnings)


def test_being_extended_is_flagged_rather_than_rewarded():
    """Buying a vertical chart is how growth screens lose money."""
    from backend.indicators import technical as ta
    ind = ta.indicator_bundle(_hist(daily=0.02, noise=0.001))     # relentless vertical move
    read = growth_score(ind, GROWTH_INFO, spy_ret_60d=2.0)
    assert ind["rsi"] >= 80
    assert any("extended" in w for w in read.warnings)


def test_scanner_rejects_a_downtrend_even_with_great_fundamentals():
    snap = StockSnapshot(ticker="FALLING", history=_hist(daily=-0.004),
                         info=GROWTH_INFO)
    assert GrowthScanner(spy_ret_60d=0.0).evaluate(snap) is None


def test_scanner_accepts_a_growing_leader_and_explains_why():
    snap = StockSnapshot(ticker="LEADER", history=_hist(daily=0.004),
                         info=GROWTH_INFO)
    hit = GrowthScanner(spy_ret_60d=1.0).evaluate(snap)

    assert hit is not None
    assert hit.metrics["profile"] == "growth"
    assert hit.metrics["growth_score"] > 60
    assert "revenue_growth_15pct" in hit.passed_names
    assert hit.metrics["reasons"]                 # never an unexplained pick


def test_penny_stocks_never_reach_the_growth_screen():
    snap = StockSnapshot(ticker="CHEAP", history=_hist(start=0.5, daily=0.004),
                         info=GROWTH_INFO)
    assert GrowthScanner().evaluate(snap) is None


# --------------------------- exit rules ------------------------------------
def test_target_hit_says_book_it():
    plan = build_plan(100.0, target_pct=12.0, stop_pct=-7.0)
    out = check_exit(plan, 113.0, days_held=4)
    assert out["action"] == "take_profit" and "Book it" in out["reason"]


def test_stop_wins_when_a_gap_breaches_both_levels():
    """If price gapped through the stop, the loss is what happened to you."""
    plan = build_plan(100.0, target_pct=12.0, stop_pct=-7.0)
    plan.target = 90.0                       # contrived: both levels below price
    out = check_exit(plan, 85.0, days_held=1)
    assert out["action"] == "sell" and "stop hit" in out["reason"]


def test_time_stop_frees_capital_when_nothing_happened():
    plan = build_plan(100.0)
    out = check_exit(plan, 101.0, days_held=plan.horizon_days)
    assert out["action"] == "close_stale" and "window has passed" in out["reason"]


def test_trailing_stop_protects_a_winner_from_round_tripping():
    plan = build_plan(100.0, target_pct=25.0, stop_pct=-10.0)
    # Ran to +15%, now back to +9% — a 5.2% giveback from the peak.
    out = check_exit(plan, 109.0, days_held=3, peak_price=115.0)
    assert out["action"] == "take_profit" and "given back" in out["reason"]


def test_a_small_winner_is_left_alone_to_work():
    plan = build_plan(100.0)
    out = check_exit(plan, 103.0, days_held=2, peak_price=104.0)
    assert out["action"] == "hold" and "left in the window" in out["reason"]


def test_atr_sizes_the_plan_to_the_stock_not_a_fixed_percent():
    calm = build_plan(100.0, atr=0.5)
    wild = build_plan(100.0, atr=6.0)
    assert wild.target_pct > calm.target_pct
    assert abs(wild.stop_pct) > abs(calm.stop_pct)
    assert 3.0 <= abs(wild.stop_pct) <= 15.0          # clamped, never absurd


def test_a_zero_entry_is_rejected_rather_than_producing_nonsense():
    with pytest.raises(ValueError):
        build_plan(0.0)


# --------------------------- income planning -------------------------------
def test_projection_reflects_the_edge_and_shows_a_range():
    p = project(100_000, win_rate=0.55, avg_win_pct=10.0, avg_loss_pct=6.0,
                trades_per_year=50, concurrent_positions=5)
    assert p["profitable_edge"] is True
    assert p["expected_annual_profit"] > 0
    assert p["range_low"] < p["expected_annual_profit"] < p["range_high"]


def test_a_negative_edge_makes_any_goal_unreachable():
    """More capital on a losing system just loses faster — say so."""
    a = assess(50_000, 25_000, win_rate=0.40, avg_win_pct=5.0, avg_loss_pct=9.0,
               trades_per_year=50, concurrent_positions=5)
    assert a["feasible"] is False
    assert a["capital_required"] is None
    assert "negative" in a["verdict"] and "lose faster" in a["verdict"]


def test_an_out_of_reach_goal_names_the_required_return_and_capital():
    a = assess(50_000, 25_000, win_rate=0.55, avg_win_pct=10.0, avg_loss_pct=6.0,
               trades_per_year=50, concurrent_positions=5)
    assert a["feasible"] is False
    assert a["required_return_%"] == 200.0        # $50k on $25k
    assert a["capital_required"] > 25_000
    assert "how accounts get ruined" in a["verdict"]


def test_a_reachable_goal_is_confirmed():
    a = assess(20_000, 400_000, win_rate=0.55, avg_win_pct=10.0, avg_loss_pct=6.0,
               trades_per_year=50, concurrent_positions=5)
    assert a["feasible"] is True and "Reachable" in a["verdict"]


def test_capital_required_scales_with_the_goal():
    kw = dict(win_rate=0.55, avg_win_pct=10.0, avg_loss_pct=6.0,
              trades_per_year=50, concurrent_positions=5)
    assert capital_required(100_000, **kw) == pytest.approx(
        2 * capital_required(50_000, **kw))


def test_edge_is_measured_from_real_holdings_not_assumed():
    holdings = ([{"priced": True, "return_%": 10.0}] * 12
                + [{"priced": True, "return_%": -5.0}] * 8)
    e = edge_from_history(holdings)
    assert e["sample"] == 20 and e["win_rate"] == 0.6
    assert e["avg_win_pct"] == 10.0 and e["avg_loss_pct"] == 5.0


def test_too_little_history_refuses_to_guess_an_edge():
    assert edge_from_history([{"priced": True, "return_%": 5.0}] * 5) is None
