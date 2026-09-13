"""Offline tests for the wheel backtester and the doubler study."""
import math

import pytest

from backend.moonshot_study import build_observations, observe, study, trait_lift
from backend.wheel_strategy import bs_call, bs_put, simulate_wheel, trailing_vol


def _walk(n, start=100.0, drift=0.0, vol=0.02, seed=3):
    import random
    r = random.Random(seed)
    out = [start]
    for _ in range(n):
        out.append(out[-1] * math.exp(drift + r.gauss(0, vol)))
    return out


def _ramp(n, start=100.0, daily=0.004):
    """A DETERMINISTIC trend — zero volatility. Useful only for checking the
    look-ahead arithmetic; useless for the wheel, because an option on a
    riskless path is worth nothing and no trade ever opens."""
    return [start * (1 + daily) ** i for i in range(n)]


# --------------------------- option pricing --------------------------------
def test_black_scholes_behaves_like_an_option():
    # Deeper out-of-the-money puts are cheaper; more time and vol cost more.
    assert bs_put(100, 90, 0.08, 0.4) < bs_put(100, 100, 0.08, 0.4)
    assert bs_put(100, 95, 0.25, 0.4) > bs_put(100, 95, 0.08, 0.4)
    assert bs_put(100, 95, 0.08, 0.8) > bs_put(100, 95, 0.08, 0.2)
    # At expiry an option is worth exactly its intrinsic value.
    assert bs_put(90, 100, 0.0, 0.4) == pytest.approx(10.0)
    assert bs_call(110, 100, 0.0, 0.4) == pytest.approx(10.0)


def test_put_call_parity_holds():
    S, K, T, sig, r = 100.0, 95.0, 0.25, 0.45, 0.04
    lhs = bs_call(S, K, T, sig, r) - bs_put(S, K, T, sig, r)
    assert lhs == pytest.approx(S - K * math.exp(-r * T), abs=1e-6)


def test_trailing_vol_never_looks_forward():
    """A series that is calm then explodes must read calm at the calm point."""
    px = [100.0] * 200 + [100.0 * (1.15 ** i) for i in range(1, 60)]
    assert trailing_vol(px, 150) < 0.2
    assert trailing_vol(px, 250) > trailing_vol(px, 150)


# --------------------------- the wheel -------------------------------------
def test_the_wheel_earns_premium_on_a_stock_going_nowhere():
    """The case the strategy is built for: chop, no trend."""
    r = simulate_wheel(_walk(600, drift=0.0, vol=0.02), capital=25_000)
    assert r["premium_collected"] > 0
    assert r["trades"] > 5
    assert r["cagr_%"] is not None


def test_the_wheel_gives_up_the_upside_on_a_stock_that_runs():
    """Covered calls cap you at the strike. On a name that compounds, the
    wheel must lose to simply owning it — this is the trade you are making."""
    r = simulate_wheel(_walk(600, drift=0.0035, vol=0.02, seed=7), capital=25_000)
    assert r["trades"] > 5, "fixture must actually trade or this proves nothing"
    assert r["beat_buy_hold"] is False
    assert r["buy_hold_cagr_%"] > r["cagr_%"]


def test_the_wheel_keeps_the_full_downside():
    """Assignment happens exactly when the stock is falling. Premium softens
    the loss; it does not prevent it."""
    r = simulate_wheel(_walk(600, drift=-0.003, vol=0.022, seed=5), capital=25_000)
    assert r["trades"] > 5, "fixture must actually trade or this proves nothing"
    assert r["profit"] < 0
    assert r["assignments"] >= 1
    assert r["max_drawdown_%"] < -5


def test_taking_profit_early_frees_capital_and_trades_more():
    px = _walk(600, vol=0.025, seed=11)
    eager = simulate_wheel(px, take_profit=0.5)
    patient = simulate_wheel(px, take_profit=0.95)
    assert eager["trades"] >= patient["trades"]


def test_cash_secured_means_no_leverage():
    """Contracts are sized to the cash on hand, so premium scales with it —
    and below one contract's collateral the strategy is unavailable, not just
    small."""
    px = _walk(400, start=50.0, vol=0.02)
    small = simulate_wheel(px, capital=10_000)
    big = simulate_wheel(px, capital=100_000)
    assert big["premium_collected"] > small["premium_collected"] * 3

    too_small = simulate_wheel(px, capital=1_000)
    assert too_small.get("error") == "no trades possible"


def test_a_short_series_is_refused():
    assert "error" in simulate_wheel([100.0] * 50)


# --------------------------- the doubler study -----------------------------
def test_observations_never_use_future_information():
    px = _ramp(800)
    o = observe(px, 400, horizon=252)
    # Every backward-looking feature must match a hand computation at t=400.
    assert o["ret_12m_%"] == pytest.approx((px[400] / px[148] - 1) * 100)
    assert o["forward_%"] == pytest.approx((px[652] / px[400] - 1) * 100)
    assert observe(px, 100, 252) is None      # not enough lookback
    assert observe(px, 700, 252) is None      # not enough forward data


def test_lift_reports_a_useless_trait_as_useless():
    """A trait that splits the population at random must come out near 1.0 —
    this is the check that stops the study inventing findings."""
    import random
    rnd = random.Random(4)
    obs = [{"doubled": rnd.random() < 0.2, "flag": rnd.random() < 0.5,
            "forward_%": rnd.gauss(10, 50)} for _ in range(4000)]
    out = trait_lift(obs, "coin flip", lambda o: o["flag"])
    assert 0.85 < out["lift"] < 1.15


def test_lift_detects_a_trait_that_genuinely_predicts():
    obs = ([{"doubled": True, "flag": True, "forward_%": 150.0}] * 300
           + [{"doubled": False, "flag": False, "forward_%": 5.0}] * 700)
    out = trait_lift(obs, "real", lambda o: o["flag"])
    assert out["lift"] > 2.5
    assert out["double_rate_with_%"] > out["double_rate_without_%"]


def test_tiny_samples_are_refused_rather_than_reported():
    obs = [{"doubled": True, "flag": True}] * 10
    assert trait_lift(obs, "thin", lambda o: o["flag"]) is None


def test_the_study_runs_end_to_end_and_reports_a_base_rate():
    series = {f"T{i}": _walk(900, drift=0.0004, vol=0.03, seed=i) for i in range(12)}
    out = study(series)
    assert out["observations"] > 200
    assert "base_double_rate_%" in out
    assert out["traits"]
    # Every trait must be reported with the counterfactual, not just its own rate.
    assert all("double_rate_without_%" in t for t in out["traits"])


def test_build_observations_strides_rather_than_double_counting():
    series = {"A": _walk(1000)}
    dense = build_observations(series, stride=1)
    sparse = build_observations(series, stride=21)
    assert len(dense) > len(sparse) * 15


def test_a_stock_too_expensive_to_collateralise_says_so():
    """On $25k, SPY at ~$550 needs ~$55k per contract. That is impossible,
    not unprofitable, and reporting 0.0% CAGR conflates the two."""
    expensive = _walk(400, start=600.0, vol=0.015)
    r = simulate_wheel(expensive, capital=25_000)

    assert "error" in r and r["error"] == "no trades possible"
    assert r["min_capital_needed"] > 25_000
    assert "collateral" in r["reason"]

    # With enough capital the same series trades normally.
    ok = simulate_wheel(expensive, capital=200_000)
    assert "error" not in ok and ok["trades"] > 0
