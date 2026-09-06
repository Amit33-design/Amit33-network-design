"""Offline tests for the portfolio-level backtest (no network)."""
from backend.portfolio_backtest import simulate, _max_drawdown, _pick_universe


def _calendar(n: int) -> list[str]:
    # Consecutive weekdays starting 2026-01-05 (a Monday).
    import datetime as dt
    out, d = [], dt.date(2026, 1, 5)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def _series(dates: list[str], start: float, daily: float) -> dict[str, float]:
    return {d: start * (1 + daily) ** i for i, d in enumerate(dates)}


def test_strategy_beating_benchmark_shows_positive_alpha():
    dates = _calendar(30)
    closes = {
        "SPY": _series(dates, 500.0, 0.001),   # +0.1%/day
        "AAA": _series(dates, 100.0, 0.010),   # +1.0%/day
    }
    history = [(dates[0], [{"ticker": "AAA", "score": 90}])]
    r = simulate(history, closes, top_n=1, hold_days=10)

    assert r["trades"] == 1
    assert r["strategy_return_%"] > r["benchmark_return_%"]
    assert r["alpha_%"] > 0
    # Held 10 trading days at +1%/day compounded ⇒ ~10.5%.
    assert 10.0 < r["strategy_return_%"] < 11.0
    assert r["trade_win_rate"] == 1.0


def test_losing_strategy_reports_negative_alpha_and_drawdown():
    dates = _calendar(30)
    closes = {
        "SPY": _series(dates, 500.0, 0.001),
        "BBB": _series(dates, 100.0, -0.010),
    }
    history = [(dates[0], [{"ticker": "BBB", "score": 80}])]
    r = simulate(history, closes, top_n=1, hold_days=10)

    assert r["strategy_return_%"] < 0
    assert r["alpha_%"] < 0
    assert r["max_drawdown_%"] < 0          # a falling book must show drawdown
    assert r["trade_win_rate"] == 0.0


def test_only_top_n_picks_are_traded():
    dates = _calendar(30)
    closes = {
        "SPY": _series(dates, 500.0, 0.0),
        "AAA": _series(dates, 100.0, 0.01),
        "ZZZ": _series(dates, 100.0, -0.01),
    }
    # ZZZ scores lower, so top_n=1 must ignore it entirely.
    history = [(dates[0], [{"ticker": "ZZZ", "score": 10}, {"ticker": "AAA", "score": 90}])]
    r = simulate(history, closes, top_n=1, hold_days=5)

    assert r["trades"] == 1
    assert r["best_trade"]["ticker"] == "AAA"
    assert _pick_universe(history, 1) == ["AAA"]


def test_positions_from_different_days_overlap():
    dates = _calendar(30)
    closes = {
        "SPY": _series(dates, 500.0, 0.0),
        "AAA": _series(dates, 100.0, 0.005),
        "BBB": _series(dates, 100.0, 0.005),
    }
    history = [
        (dates[0], [{"ticker": "AAA", "score": 90}]),
        (dates[2], [{"ticker": "BBB", "score": 90}]),
    ]
    r = simulate(history, closes, top_n=1, hold_days=10)

    assert r["trades"] == 2
    assert max(p["positions"] for p in r["points"]) == 2


def test_scan_dates_on_non_trading_days_snap_forward():
    dates = _calendar(30)
    closes = {"SPY": _series(dates, 500.0, 0.0), "AAA": _series(dates, 100.0, 0.01)}
    # 2026-01-10 is a Saturday; the entry must roll to the next trading day.
    history = [("2026-01-10", [{"ticker": "AAA", "score": 90}])]
    r = simulate(history, closes, top_n=1, hold_days=5)

    assert r["trades"] == 1
    assert r["points"][0]["date"] > "2026-01-10"


def test_missing_benchmark_history_degrades_gracefully():
    r = simulate([("2026-01-05", [{"ticker": "AAA", "score": 90}])], {}, top_n=1)
    assert r["points"] == []
    assert "error" in r


def test_max_drawdown_measures_peak_to_trough():
    assert _max_drawdown([1.0, 1.5, 0.75, 1.2]) == -50.0
    assert _max_drawdown([1.0, 1.1, 1.2]) == 0.0
