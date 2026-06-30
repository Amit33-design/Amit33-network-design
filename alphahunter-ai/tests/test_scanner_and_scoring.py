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
