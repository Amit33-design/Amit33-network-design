from backend.indicators import technical as ta


def test_rsi_in_range(crash_snapshot):
    rsi = ta.rsi(crash_snapshot.history)
    assert rsi is not None
    assert 0 <= rsi <= 100


def test_ema_ordering_on_uptrend(healthy_snapshot):
    ema50 = ta.ema(healthy_snapshot.history, 50)
    ema200 = ta.ema(healthy_snapshot.history, 200)
    assert ema50 is not None and ema200 is not None
    # In a steady uptrend the faster EMA sits above the slower one.
    assert ema50 > ema200


def test_volume_ratio_detects_spike(crash_snapshot):
    vr = ta.volume_ratio(crash_snapshot.history)
    assert vr is not None and vr > 1.5


def test_bundle_keys(crash_snapshot):
    bundle = ta.indicator_bundle(crash_snapshot.history)
    for key in ("rsi", "ema200", "above_ema200", "atr", "ret_20d", "volume_ratio"):
        assert key in bundle


def test_short_history_is_none():
    import pandas as pd
    empty = pd.DataFrame({"Close": [1.0, 2.0]})
    assert ta.ema(empty, 200) is None
    assert ta.rsi(empty) is None


def test_weekly_trend_up_and_down():
    import numpy as np, pandas as pd
    from backend.indicators.technical import weekly_trend
    idx = pd.date_range("2024-01-01", periods=200, freq="D")
    up = pd.DataFrame({"Close": np.linspace(50, 150, 200)}, index=idx)
    down = pd.DataFrame({"Close": np.linspace(150, 50, 200)}, index=idx)
    assert weekly_trend(up)["weekly_trend"] == "up"
    assert weekly_trend(down)["weekly_trend"] == "down"
    # Short series degrades safely.
    short = pd.DataFrame({"Close": [1, 2, 3]})
    assert weekly_trend(short)["weekly_trend"] == "flat"


def test_mtf_in_recommendation(crash_snapshot):
    from backend.scanners.alphahunter import AlphaHunterScanner
    from backend.scoring.composite import score_snapshot
    hit = AlphaHunterScanner(require_all=False).evaluate(crash_snapshot)
    rec = score_snapshot(crash_snapshot, hit, md=None)
    assert "mtf" in rec
    assert set(rec["mtf"]) == {"weekly_trend", "weekly_return_%", "confirms"}
    assert rec["mtf"]["weekly_trend"] in {"up", "down", "flat"}


def test_with_retries_recovers_from_transient_errors():
    from backend.utils.market_data import with_retries
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("429 rate limited")
        return "ok"
    assert with_retries(flaky, attempts=3, backoff=0.0) == "ok"
    assert calls["n"] == 3


def test_with_retries_gives_up_and_does_not_retry_empty():
    from backend.utils.market_data import with_retries
    # Always raising -> None after the attempt budget.
    def always_fails():
        raise TimeoutError("nope")
    assert with_retries(always_fails, attempts=2, backoff=0.0) is None
    # A clean None (delisted ticker) is FINAL - must not burn retries.
    calls = {"n": 0}
    def empty():
        calls["n"] += 1
        return None
    assert with_retries(empty, attempts=3, backoff=0.0) is None
    assert calls["n"] == 1
