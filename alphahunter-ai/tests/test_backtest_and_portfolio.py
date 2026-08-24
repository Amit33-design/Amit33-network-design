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


def test_performance_summary_offline():
    from backend.performance import summarize_picks
    history = [
        ("2026-07-01", [
            {"ticker": "AAA", "entry": 100.0, "score": 80, "action": "Buy"},
            {"ticker": "BBB", "entry": 50.0, "score": 70, "action": "Accumulate"},
        ]),
        ("2026-07-15", [  # too fresh vs today=2026-07-16 -> excluded
            {"ticker": "CCC", "entry": 10.0, "score": 60, "action": "Hold"},
        ]),
    ]
    prices = {"AAA": 110.0, "BBB": 45.0, "CCC": 20.0}
    out = summarize_picks(history, lambda t: prices.get(t), today="2026-07-16")
    tickers = {p["ticker"] for p in out["picks"]}
    assert tickers == {"AAA", "BBB"}          # CCC too fresh
    s = out["summary"]
    assert s["picks"] == 2
    assert s["win_rate"] == 0.5               # AAA +10%, BBB -10%
    assert s["avg_return_%"] == 0.0
    assert s["best"]["ticker"] == "AAA" and s["worst"]["ticker"] == "BBB"


def test_performance_empty_history():
    from backend.performance import summarize_picks
    out = summarize_picks([], lambda t: None, today="2026-07-16")
    assert out == {"picks": [], "summary": None}


def test_performance_segments_by_quality_and_setup():
    from backend.performance import summarize_picks
    def rec(t, entry, grade, profile, score):
        return {"ticker": t, "entry": entry, "score": score, "action": "Buy",
                "quality_grade": grade, "confidence": "High",
                "metrics": {"profile": profile}}
    history = [("2026-07-01", [
        # Three A-grade winners, three C-grade losers.
        rec("AA1", 100, "A", None, 80), rec("AA2", 100, "A", None, 78),
        rec("AA3", 100, "A", None, 76),
        rec("CC1", 100, "C", "opportunity", 55), rec("CC2", 100, "C", "opportunity", 54),
        rec("CC3", 100, "C", "opportunity", 53),
        # A 2-pick cohort that must be dropped as too small to be meaningful.
        rec("BB1", 100, "B", None, 65), rec("BB2", 100, "B", None, 64),
    ])]
    prices = {"AA1": 120, "AA2": 110, "AA3": 115,
              "CC1": 80, "CC2": 90, "CC3": 85,
              "BB1": 200, "BB2": 200}
    out = summarize_picks(history, lambda t: prices.get(t), today="2026-07-20")
    segs = out["segments"]
    by_grade = {r["key"]: r for r in segs["quality_grade"]}
    assert by_grade["A"]["win_rate"] == 1.0 and by_grade["A"]["avg_return_%"] == 15.0
    assert by_grade["C"]["win_rate"] == 0.0 and by_grade["C"]["avg_return_%"] == -15.0
    # B had only 2 picks -> excluded despite a spectacular (noisy) return.
    assert "B" not in by_grade
    # Best cohort is listed first.
    assert segs["quality_grade"][0]["key"] == "A"
    # Setup buckets group ALL picks (the B pair counts here even though it is
    # too small for its own grade row), so assert the ordering invariant.
    by_setup = {r["key"]: r for r in segs["setup"]}
    assert by_setup["pullback"]["avg_return_%"] == -15.0   # the three C names
    assert by_setup["crash dip"]["picks"] == 5             # three A + two B
    assert by_setup["crash dip"]["avg_return_%"] > by_setup["pullback"]["avg_return_%"]
    # Score bands: 80/78/76 split across the "80+" and "70+" bands (1 and 2
    # picks), so both fall under the 3-pick minimum; only the C band survives.
    assert {r["key"] for r in segs["score_band"]} == {"50+"}
