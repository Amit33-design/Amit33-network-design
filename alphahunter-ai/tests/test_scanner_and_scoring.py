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
