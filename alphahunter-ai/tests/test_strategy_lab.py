"""Offline: the strategy lab finds a planted edge, charges costs, respects
liquidity, and computes standard metrics correctly."""
import datetime as dt
import random

import pytest

from backend.strategy_lab import (COST_BPS, MIN_DOLLAR_VOL, lab, metrics, periods, run)


def _cal(n):
    out, d = [], dt.date(2021, 1, 4)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def _data(persistent: bool, n=900, stocks=80, seed=5, volume=1e6):
    rnd = random.Random(seed)
    cal = _cal(n)
    prices = {"SPY": {"dates": cal, "c": [100 * 1.0003 ** i for i in range(n)], "v": [1e8] * n}}
    for j in range(stocks):
        # Persistent drift per stock = a real momentum effect when persistent.
        drift = (j / stocks - 0.5) * 0.003 if persistent else 0.0
        p, c = 50.0, []
        for _ in range(n):
            p *= 1 + drift + rnd.gauss(0, 0.018)
            c.append(p)
        prices[f"S{j}"] = {"dates": cal, "c": c, "v": [volume] * n}
    return {"prices": prices, "themes": {}, "earnings": {}}


def _get(out, key):
    return next(s for s in out["strategies"] if s["key"] == key)


def test_a_persistent_trend_is_found_by_momentum_after_costs():
    out = lab(_data(persistent=True))
    m = _get(out, "momentum_12_1")
    assert m["net"]["alpha_ann_%"] > 5
    assert m["checks"]["beats_spy_after_costs"] and m["checks"]["both_halves"]
    assert m["checks"]["not_parameter_dependent"]


def test_noise_does_not_beat_spy_after_costs():
    out = lab(_data(persistent=False, seed=9))
    for s in out["strategies"]:
        assert not s["checks"]["beats_spy_after_costs"], s["key"]


def test_costs_scale_with_turnover():
    pers = periods(_data(persistent=False, seed=2))
    churn = run(pers, lambda rows, f: [r["t"] for r in rows][(len(pers) % 3):][:10], 0.1)
    free = run(pers, lambda rows, f: [r["t"] for r in rows][(len(pers) % 3):][:10], 0.1, cost_bps=0)
    drag = sum(f["net"] - c["net"] for f, c in zip(free, churn))
    assert drag > 0                                  # costs always cost something
    assert churn[0]["turnover"] == pytest.approx(0.5)  # first period: buy everything (half of |Δw| sum)


def test_names_too_thin_to_trade_are_excluded():
    thin = _data(persistent=True, volume=MIN_DOLLAR_VOL / 50 / 100)    # ~$0.01M a day
    assert all(len(p["rows"]) == 0 for p in periods(thin))


def test_metrics_on_a_known_series():
    m = metrics([0.10, -0.20, 0.10], [0.0, 0.0, 0.0])
    assert m["total_return_%"] == pytest.approx(-3.2, abs=0.05)       # 1.1*0.8*1.1
    assert m["max_drawdown_%"] == pytest.approx(-20.0, abs=0.05)
    assert m["profit_factor"] == pytest.approx(1.0)
    assert m["win_rate_vs_spy"] == pytest.approx(0.667, abs=0.001)


def test_the_in_sample_combo_is_labelled():
    out = lab(_data(persistent=True))
    assert _get(out, "mom_pead_combo")["in_sample"] is True
    assert COST_BPS == out["assumptions"]["cost_bps_one_way"]
