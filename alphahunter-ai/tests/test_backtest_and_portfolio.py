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


def test_alert_selection_uses_score_and_grade_a():
    """Gates calibrated from realized ALPHA: score >= 80 AND grade A.

    The old filter (A/B grade + High/Medium confidence) selected on attributes
    the track record showed were not predictive — grade B was the worst cohort
    and Low confidence outperformed High — so those must NOT gate anymore.
    """
    from backend.alerts.engine import select_alert_worthy, format_digest, send_scan_digest
    recs = [
        {"ticker": "AAA", "quality_grade": "A", "confidence": "High",
         "rr_pass": True, "expected_gain_%": 12, "score": 82, "action": "Buy"},
        # Grade A, above the gate, but LOW confidence -> still included,
        # because confidence proved non-predictive.
        {"ticker": "LOWC", "quality_grade": "A", "confidence": "Low",
         "rr_pass": True, "expected_gain_%": 30, "score": 85, "action": "Buy"},
        # Grade A but in the 70s — that band realized NEGATIVE alpha vs SPY,
        # so it must no longer qualify for an alert.
        {"ticker": "MID", "quality_grade": "A", "confidence": "High",
         "rr_pass": True, "expected_gain_%": 45, "score": 75, "action": "Buy"},
        # Grade B was the worst realized cohort -> excluded even at a high score.
        {"ticker": "BBB", "quality_grade": "B", "confidence": "High",
         "rr_pass": True, "expected_gain_%": 40, "score": 88, "action": "Buy"},
        # Grade A but below the score gate -> excluded.
        {"ticker": "LOWS", "quality_grade": "A", "confidence": "High",
         "rr_pass": True, "expected_gain_%": 50, "score": 64, "action": "Buy"},
        # Fails risk/reward -> excluded.
        {"ticker": "RRX", "quality_grade": "A", "confidence": "High",
         "rr_pass": False, "expected_gain_%": 50, "score": 90, "action": "Buy"},
    ]
    picks = select_alert_worthy(recs, limit=5)
    # Ranked by SCORE (the predictive variable), not expected gain.
    assert [p["ticker"] for p in picks] == ["LOWC", "AAA"]   # 85 then 82
    digest = format_digest("2026-08-24", picks)
    assert "AAA" in digest and "BBB" not in digest and "LOWS" not in digest
    assert "MID" not in digest          # 70s band lags the market -> no alert
    out = send_scan_digest("2026-08-24", recs)
    assert out["delivered_to"] == ["log"]
    assert out["tickers"] == ["LOWC", "AAA"]


def test_alert_digest_empty():
    from backend.alerts.engine import format_digest
    assert "no A-grade setups" in format_digest("2026-07-08", [])


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


def test_performance_alpha_vs_benchmark():
    from backend.performance import summarize_picks
    history = [("2026-07-01", [
        {"ticker": "WIN", "entry": 100.0, "score": 70, "quality_grade": "A"},
        {"ticker": "LAG", "entry": 100.0, "score": 60, "quality_grade": "A"},
        {"ticker": "DWN", "entry": 100.0, "score": 55, "quality_grade": "C"},
    ])]
    prices = {"WIN": 112.0, "LAG": 103.0, "DWN": 96.0}   # +12%, +3%, -4%
    # The market rose 5% over the same window.
    out = summarize_picks(history, lambda t: prices.get(t), today="2026-07-20",
                          bench_return=lambda d: 5.0)
    by_ticker = {p["ticker"]: p for p in out["picks"]}
    assert by_ticker["WIN"]["alpha_%"] == 7.0     # +12 vs +5
    assert by_ticker["LAG"]["alpha_%"] == -2.0    # a "winner" that LOST to SPY
    assert by_ticker["DWN"]["alpha_%"] == -9.0
    s = out["summary"]
    assert s["benchmark"] == "SPY"
    # Two of three picks were up, but only one actually beat the market.
    assert s["win_rate"] == 0.67
    assert s["beat_benchmark_rate"] == round(1 / 3, 2)
    assert s["avg_alpha_%"] == round((7.0 - 2.0 - 9.0) / 3, 1)


def test_performance_without_benchmark_omits_alpha():
    from backend.performance import summarize_picks
    history = [("2026-07-01", [{"ticker": "AAA", "entry": 100.0, "score": 70}])]
    out = summarize_picks(history, lambda t: 110.0, today="2026-07-20")
    assert "alpha_%" not in out["picks"][0]
    assert "avg_alpha_%" not in out["summary"]


def test_build_performance_prefers_warm_6mo_benchmark(tmp_path, monkeypatch):
    """The SPY fetch must reuse the cache key the scan already warmed.

    Regression guard: asking for period="1y" was a different TTL-cache key
    than relative_strength's "6mo", so it triggered a fresh fetch at the end
    of a long run and got rate-limited — alpha came back silently empty.
    """
    import json as _json
    import pandas as pd
    import backend.utils.market_data as md_mod
    from backend.performance import build_performance

    results = tmp_path / "results"
    results.mkdir()
    (results / "alphahunter_2026-07-01.json").write_text(_json.dumps({
        "date": "2026-07-01",
        "results": [{"ticker": "AAA", "entry": 100.0, "score": 75,
                     "quality_grade": "A", "action": "Buy"}],
    }))

    idx = pd.date_range("2026-06-25", periods=40, freq="D")
    spy = pd.DataFrame({"Close": [100.0 + i for i in range(40)]}, index=idx)
    asked: list[str] = []

    class FakeMD:
        def history(self, ticker, period="3y"):
            asked.append(period)
            return spy if period == "6mo" else None   # only "6mo" is warm
        def snapshot(self, ticker):
            class S:  # priced well above entry
                last_close = 130.0
            return S()

    monkeypatch.setattr(md_mod, "MarketData", FakeMD)
    out = build_performance(str(results), "2026-07-20")

    assert asked[0] == "6mo"          # warm key tried FIRST
    assert "1y" not in asked          # and it succeeded, so no extra fetch
    s = out["summary"]
    assert s["benchmark"] == "SPY"
    assert s["avg_alpha_%"] is not None
    # AAA returned +30%; SPY rose from 106 (2026-07-01) to 139 (~+31%),
    # so this "winner" actually trailed the market — exactly what alpha is for.
    assert s["avg_alpha_%"] < 0
