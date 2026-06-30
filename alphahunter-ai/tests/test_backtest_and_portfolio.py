from backend.backtesting.engine import backtest_oversold
from backend.portfolio.analyzer import Position, analyze_portfolio


def test_backtest_runs_offline(crash_snapshot):
    res = backtest_oversold(crash_snapshot.history, hold_days=10).as_dict()
    # Synthetic series may produce few/zero trades; just assert shape + sanity.
    for key in ("trades", "win_rate", "avg_return_%", "sharpe", "profit_factor"):
        assert key in res
    assert res["trades"] >= 0
    assert 0 <= res["win_rate"] <= 1


def test_backtest_short_series_safe():
    import pandas as pd
    res = backtest_oversold(pd.DataFrame({"Close": [1.0, 2.0, 3.0]})).as_dict()
    assert res["trades"] == 0


def test_portfolio_position_dataclass():
    p = Position("AAPL", 10, 150.0)
    assert p.ticker == "AAPL" and p.quantity == 10
