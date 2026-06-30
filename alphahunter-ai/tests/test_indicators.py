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
