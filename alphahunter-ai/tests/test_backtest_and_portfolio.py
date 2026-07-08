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


def test_alert_selection_and_digest():
    from backend.alerts.engine import select_alert_worthy, format_digest, send_scan_digest
    recs = [
        {"ticker": "AAA", "quality_grade": "A", "confidence": "High",
         "rr_pass": True, "expected_gain_%": 20, "score": 80, "action": "Buy"},
        {"ticker": "BBB", "quality_grade": "B", "confidence": "Medium",
         "rr_pass": True, "expected_gain_%": 12, "score": 66, "action": "Accumulate"},
        {"ticker": "CCC", "quality_grade": "C", "confidence": "High",   # C grade -> excluded
         "rr_pass": True, "expected_gain_%": 40, "score": 90, "action": "Buy"},
        {"ticker": "DDD", "quality_grade": "A", "confidence": "Low",    # low conf -> excluded
         "rr_pass": True, "expected_gain_%": 30, "score": 70, "action": "Buy"},
        {"ticker": "EEE", "quality_grade": "A", "confidence": "High",
         "rr_pass": False, "expected_gain_%": 50, "score": 88, "action": "Buy"},  # R:R fail -> excluded
    ]
    picks = select_alert_worthy(recs, limit=5)
    tickers = [p["ticker"] for p in picks]
    assert tickers == ["AAA", "BBB"]          # filtered + ranked by expected gain
    digest = format_digest("2026-07-08", picks)
    assert "AAA" in digest and "BBB" in digest and "CCC" not in digest
    # With no webhooks configured, it logs and reports the "log" channel.
    out = send_scan_digest("2026-07-08", recs)
    assert out["delivered_to"] == ["log"]
    assert out["tickers"] == ["AAA", "BBB"]


def test_alert_digest_empty():
    from backend.alerts.engine import format_digest
    assert "no high-conviction" in format_digest("2026-07-08", [])
