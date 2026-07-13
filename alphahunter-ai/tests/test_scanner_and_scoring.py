from backend.scanners.alphahunter import AlphaHunterScanner
from backend.scoring.composite import score_snapshot
from backend.scoring import engines


def test_crash_setup_triggers(crash_snapshot):
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    assert hit is not None
    # Core crash criteria must all pass.
    for name in ("revenue_over_1b", "down_5pct_day", "down_20pct_month"):
        assert name in hit.passed_names


def test_healthy_name_does_not_trigger(healthy_snapshot):
    hit = AlphaHunterScanner(require_all=True).evaluate(healthy_snapshot)
    assert hit is None  # no crash, so core criteria fail


def test_composite_score_bounds_and_shape(crash_snapshot):
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    assert 0 <= rec["score"] <= 100
    assert rec["action"] in {"Buy", "Accumulate", "Hold", "Reduce", "Sell"}
    assert set(rec["subscores"]) == {
        "technical", "fundamental", "options", "momentum", "sentiment"
    }
    assert rec["reasoning"]
    assert rec["confidence"] in {"High", "Medium", "Low"}


def test_quality_grade_and_expected_gain(crash_snapshot):
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    assert rec["quality_grade"] in {"A", "B", "C", "D", "F"}
    # The crash fixture has $150 target vs ~$95 price -> positive analyst upside,
    # and expected_gain should be a positive fraction of it (tempered down).
    assert rec["analyst_upside_%"] is not None and rec["analyst_upside_%"] > 0
    assert rec["expected_gain_%"] is not None
    assert 0 < rec["expected_gain_%"] <= rec["analyst_upside_%"]


def test_quality_grade_monotonic():
    from backend.scoring.engines import quality_grade
    grades = [quality_grade(s) for s in (90, 70, 60, 45, 20)]
    assert grades == ["A", "B", "C", "D", "F"]


def test_backtest_calibrated_fields_present(crash_snapshot):
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    # New backtest-calibration fields exist and are sane types.
    assert "hist_win_rate" in rec and 0 <= rec["hist_win_rate"] <= 1
    assert "hist_avg_return_%" in rec
    assert "hist_trades" in rec and rec["hist_trades"] >= 0
    assert rec["confidence"] in {"High", "Medium", "Low"}


def test_confidence_bump_helper():
    from backend.scoring.composite import _bump
    assert _bump("Low", +1) == "Medium"
    assert _bump("High", +1) == "High"      # clamps at top
    assert _bump("Low", -1) == "Low"        # clamps at bottom
    assert _bump("Medium", -1) == "Low"


def test_risk_flags_shape(crash_snapshot):
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    assert isinstance(rec["risk_flags"], list)
    for f in rec["risk_flags"]:
        assert set(f) == {"level", "text"}
        assert f["level"] in {"warn", "info", "good"}


def test_rel_strength_offline_is_none(crash_snapshot):
    # With no market-data provider, rel strength degrades to None and the
    # payload still carries the field.
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    assert "rel_strength" in rec
    assert rec["rel_strength"] is None


def test_rel_strength_with_fake_benchmarks(crash_snapshot):
    import numpy as np
    import pandas as pd
    from backend.indicators import technical as ta
    from backend.scoring.relative_strength import compute_rel_strength, apply_rel_strength
    from backend.scoring.engines import SubScore

    # Flat benchmark: 0% over the lookback -> spread == the stock's own return.
    flat = pd.DataFrame({"Close": [100.0] * 130})

    class FakeMD:
        def history(self, symbol, period="6mo"):
            return flat

    crash_snapshot.info["sector"] = "Technology"
    ind = ta.indicator_bundle(crash_snapshot.history)
    rs = compute_rel_strength(crash_snapshot, ind, FakeMD())
    assert rs is not None
    assert rs["sector_etf"] == "XLK"
    assert rs["vs_spy"] == round(ind["ret_60d"] - 0.0, 1)

    # A big positive spread should boost momentum; a big negative one cut it.
    up = SubScore("momentum", 50.0)
    apply_rel_strength(up, {"vs_spy": 20.0, "vs_sector": None, "sector_etf": "XLK"})
    assert up.score > 50 and any("outperforming" in f for f in up.factors)
    down = SubScore("momentum", 50.0)
    apply_rel_strength(down, {"vs_spy": -30.0, "vs_sector": None, "sector_etf": "XLK"})
    assert down.score < 50 and any("lagging" in f for f in down.factors)


def test_position_sizing_and_rr_gate(crash_snapshot):
    from backend.config import settings
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    # Sizing math: shares = floor(account*risk% / stop distance), risk_$ <= budget.
    pos = rec["position"]
    assert pos is not None and pos["shares"] >= 1
    budget = settings.account_size * settings.max_risk_pct / 100.0
    assert pos["risk_$"] <= budget + 1e-6
    risk_per_share = rec["entry"] - rec["stop_loss"]
    assert pos["shares"] == int(budget // risk_per_share)
    # R:R gate consistent with the flag list.
    assert isinstance(rec["rr_pass"], bool)
    if rec["risk_reward"] is not None and not rec["rr_pass"]:
        assert any("R:R" in f["text"] for f in rec["risk_flags"])


def test_csp_signal_fires_on_dip_with_upside_and_history():
    from backend.scoring.csp_signal import compute_csp_signal
    bt_good = {"hist_trades": 8, "hist_win_rate": 0.7, "hist_avg_return_%": 4.2}
    sig = compute_csp_signal(-3.5, True, 25.0, bt_good, None, 100.0, 4.0)
    assert sig["active"] is True and sig["strength"] == "strong"
    assert sig["suggested_strike"] == 94.0        # 100 - 1.5*ATR
    assert "bounced 70%" in sig["reason"]


def test_csp_signal_blocked_without_dip_or_upside_or_history():
    from backend.scoring.csp_signal import compute_csp_signal
    bt = {"hist_trades": 0, "hist_win_rate": 0.0, "hist_avg_return_%": 0.0}
    # No dip today -> inactive.
    assert compute_csp_signal(-0.5, True, 30.0, bt, None, 100.0, 4.0)["active"] is False
    # Dip but below EMA200 and no analyst upside -> inactive.
    assert compute_csp_signal(-4.0, False, 2.0, bt, None, 100.0, 4.0)["active"] is False
    # Dip with upside but history says dips don't bounce -> inactive.
    bt_bad = {"hist_trades": 6, "hist_win_rate": 0.2, "hist_avg_return_%": -3.0}
    blocked = compute_csp_signal(-4.0, True, 30.0, bt_bad, None, 100.0, 4.0)
    assert blocked["active"] is False and "history is against it" in blocked["reason"]


def test_csp_signal_in_payload(crash_snapshot):
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    sig = rec["csp_signal"]
    assert set(sig) == {"active", "strength", "suggested_strike", "idea", "reason"}
    # The crash fixture drops ~6% on the last day with an uptrend + upside, so
    # the dip gate and upside gate both pass.
    assert sig["active"] is True


def test_risk_flags_detects_leverage_and_earnings():
    from backend.scoring.risk import compute_risk_flags
    import datetime as dt
    soon = int((dt.datetime.utcnow() + dt.timedelta(days=3)).timestamp())
    info = {"debtToEquity": 450, "freeCashflow": -1e8, "earningsTimestamp": soon,
            "recommendationKey": "strong_buy"}
    flags = compute_risk_flags(info, {"dist_52w_low": 50, "golden_cross": False}, 100.0)
    texts = " ".join(f["text"] for f in flags)
    assert "high leverage" in texts
    assert "negative free cash flow" in texts
    assert "earnings in" in texts
    assert any(f["level"] == "good" for f in flags)  # strong-buy consensus


def test_weights_sum_to_one():
    from backend.config import settings
    assert abs(sum(settings.score_weights.values()) - 1.0) < 1e-9


def test_subscores_bounded(crash_snapshot):
    ind = __import__("backend.indicators.technical", fromlist=["indicator_bundle"]).indicator_bundle(crash_snapshot.history)
    for sub in (engines.technical_score(ind),
                engines.fundamental_score(crash_snapshot.info),
                engines.momentum_score(ind),
                engines.sentiment_score(crash_snapshot.info, crash_snapshot.last_close)):
        assert 0 <= sub.score <= 100


def test_opportunity_scanner_flags_pullback(crash_snapshot):
    from backend.scanners.alphahunter import OpportunityScanner
    hit = OpportunityScanner().evaluate(crash_snapshot)
    # The crash fixture is a >$1B name deep in a pullback -> should qualify.
    assert hit is not None
    assert hit.metrics["profile"] == "opportunity"
    assert "revenue_over_1b" in hit.metrics["passed"]


def test_opportunity_scanner_skips_calm_large_cap():
    from backend.scanners.alphahunter import OpportunityScanner
    from backend.utils.market_data import StockSnapshot
    import numpy as np, pandas as pd
    # A steadily-rising >$1B name with no pullback and healthy RSI -> not a hit.
    idx = pd.date_range("2024-01-01", periods=260, freq="D")
    close = np.linspace(100, 160, 260)
    hist = pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99,
                         "Close": close, "Volume": [1_000_000] * 260}, index=idx)
    snap = StockSnapshot(ticker="CALM", history=hist,
                         info={"totalRevenue": 5e9, "financialCurrency": "USD"})
    assert OpportunityScanner().evaluate(snap) is None
