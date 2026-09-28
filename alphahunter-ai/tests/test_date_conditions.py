"""Offline: does a condition known on the pick date separate good scan days?"""
import datetime as dt

from backend.date_conditions import MIN_SIDE_DATES, analyse


def _days(n, start=dt.date(2026, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


CAL = _days(200)


def _spy_alternating_trend():
    """SPY that spends stretches above and below its 50-day average."""
    import math
    return {d: 100 + 8 * math.sin(i / 12) for i, d in enumerate(CAL)}


def _trades_for(dates, alpha_fn):
    out = []
    for d in dates:
        for _ in range(3):
            out.append({"picked": d, "return_%": alpha_fn(d), "spy_%": 0.0, "exit": "sell", "days_held": 5})
    return out


def test_a_real_regime_effect_is_detected():
    spy = _spy_alternating_trend()
    pick_dates = CAL[60:180:2]

    def above50(d):
        ds = [x for x in CAL if x <= d][-50:]
        return spy[d] > sum(spy[x] for x in ds) / 50
    # Picks work in uptrends and fail in downtrends, with some noise.
    trades = _trades_for(pick_dates, lambda d: (3.0 if above50(d) else -3.0) + (int(d[-2:]) % 7 - 3) * 0.3)
    res = {c["key"]: c for c in analyse(trades, spy)["conditions"]}
    up = res["spy_uptrend"]
    assert up["yes"]["dates"] >= MIN_SIDE_DATES and up["no"]["dates"] >= MIN_SIDE_DATES
    assert up["notable"] and up["diff_t"] > 0
    assert "better when it holds" in up["verdict"]


def test_noise_is_not_called_a_pattern():
    spy = _spy_alternating_trend()
    pick_dates = CAL[60:180:2]
    trades = _trades_for(pick_dates, lambda d: (int(d[-2:]) % 11 - 5) * 0.5)
    res = analyse(trades, spy)["conditions"]
    assert not any(c["notable"] for c in res)


def test_only_data_up_to_the_pick_date_is_used():
    """A crash AFTER the pick date must not change that date's flags."""
    spy = _spy_alternating_trend()
    trades = _trades_for([CAL[100]], lambda d: 1.0)
    a = analyse(trades, spy)["conditions"]
    spy2 = {**spy, **{d: 1.0 for d in CAL[101:]}}
    b = analyse(trades, spy2)["conditions"]
    assert [c["yes"]["dates"] for c in a] == [c["yes"]["dates"] for c in b]


def test_too_few_dates_on_a_side_gives_no_verdict():
    spy = _spy_alternating_trend()
    trades = _trades_for(CAL[60:66], lambda d: 1.0)
    for c in analyse(trades, spy)["conditions"]:
        assert not c["notable"]
