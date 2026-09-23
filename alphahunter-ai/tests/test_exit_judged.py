"""Offline tests: judging picks at their exit plan, not held forever."""
import pytest

from backend.exit_judged import judge_history, judge_pick, recover_atr, summarise


def test_atr_is_recovered_from_the_published_levels():
    # target1 = entry + 2·ATR in every historical pick.
    assert recover_atr({"entry": 46.34, "target1": 50.77}) == pytest.approx(2.215)
    # stop-only fallback: stop = entry − 1.5·ATR.
    assert recover_atr({"entry": 100.0, "stop_loss": 97.0}) == pytest.approx(2.0)
    assert recover_atr({"entry": 100.0}) is None


def test_a_pick_that_runs_to_target_books_the_target_not_the_later_price():
    """Held forever, this pick would be judged at wherever it ended up. The
    product told the user to take profit — so that is the result."""
    path = [101, 103, 106, 109, 113, 118, 90, 80]   # hits target, then collapses
    r = judge_pick(100.0, path, atr=None)            # default plan: +12% / -7%
    assert r["exit"] == "take_profit"
    assert r["return_%"] == pytest.approx(13.0)
    assert r["days_held"] == 5                       # not the -20% at the end


def test_a_stop_caps_the_loss():
    r = judge_pick(100.0, [99, 97, 92, 70, 50])
    assert r["exit"] == "sell"
    assert r["return_%"] == -8.0                     # stopped, not -50%


def test_nothing_happening_closes_at_the_review_date():
    r = judge_pick(100.0, [100.5, 101, 100.2, 99.8, 100.4, 101, 100.9, 100.1, 100.6, 101.2, 150])
    assert r["exit"] == "close_stale" and r["days_held"] == 10


def test_an_unfinished_trade_is_not_a_result():
    """The old record mixed open and closed trades. An open trade is excluded."""
    assert judge_pick(100.0, [101, 100.5, 101.5]) is None


def test_alpha_is_measured_over_the_same_holding_window():
    history = [("2026-01-05", [{"ticker": "AAA", "score": 80, "entry": 100.0}])]
    dates = [f"2026-01-{d:02d}" for d in range(6, 20)]
    closes = {
        "AAA": dict(zip(dates, [101, 103, 106, 109, 113, 118, 120, 120, 120, 120, 120, 120, 120, 120])),
        "SPY": {"2026-01-05": 500.0, **dict(zip(dates, [500 + i for i in range(1, 15)]))},
    }
    out = judge_history(history, closes)
    t = out["recent"][0]
    assert t["exit"] == "take_profit" and t["exit_date"] == "2026-01-10"
    # SPY from the pick date to THAT exit date — not to today.
    assert t["spy_%"] == pytest.approx((505 / 500 - 1) * 100, abs=0.01)
    assert out["summary"]["avg_alpha_%"] == pytest.approx(13.0 - 1.0, abs=0.05)


def test_screens_are_reported_separately():
    history = [("2026-01-05", [
        {"ticker": "G", "score": 80, "entry": 100.0, "metrics": {"profile": "growth"}},
        {"ticker": "C", "score": 70, "entry": 100.0},
    ])]
    dates = [f"2026-01-{d:02d}" for d in range(6, 20)]
    closes = {"G": dict(zip(dates, [101, 104, 108, 113] + [113] * 10)),
              "C": dict(zip(dates, [99, 96, 92] + [92] * 11)),
              "SPY": {"2026-01-05": 500.0, **{d: 500.0 for d in dates}}}
    out = judge_history(history, closes)
    assert out["by_screen"]["growth"]["avg_return_%"] > 0
    assert out["by_screen"]["crash"]["avg_return_%"] < 0


def test_summary_reports_how_each_trade_ended():
    s = summarise([
        {"exit": "take_profit", "return_%": 12.0, "spy_%": 1.0, "days_held": 4},
        {"exit": "sell", "return_%": -7.0, "spy_%": 0.0, "days_held": 2},
        {"exit": "close_stale", "return_%": 0.5, "spy_%": 0.5, "days_held": 10},
    ])
    assert s["exits"] == {"take_profit": 1, "sell": 1, "close_stale": 1}
    assert s["win_rate"] == pytest.approx(0.667, abs=0.001)
    assert s["avg_loss_%"] == -7.0              # the stop caps it
    assert summarise([]) is None


def test_a_trailing_stop_that_gaps_below_entry_is_not_called_take_profit():
    """Up 10%, then a gap down to -2% on the next close. The trail fires (the
    holder's instruction is still "take profit"), but a record that files a
    loss under take-profit flatters itself. TRMD did exactly this."""
    r = judge_pick(100.0, [104, 110, 98])            # default plan: +12% target
    assert r["exit"] == "trail"
    assert r["return_%"] == -2.0


def _spy(dates, start="2026-01-05"):
    return {start: 500.0, **{d: 500.0 for d in dates}}


def test_days_are_counted_on_the_market_calendar_not_the_tickers_own_bars():
    """A series with a three-week hole must not turn week four into "day 1"."""
    cal = [f"2026-02-{d:02d}" for d in range(2, 28)]
    history = [("2026-01-30", [{"ticker": "THIN", "score": 60, "entry": 10.0}])]
    closes = {"THIN": {"2026-02-25": 5.0},          # first bar weeks later
              "SPY": _spy(cal, "2026-01-30")}
    out = judge_history(history, closes)
    assert out["summary"] is None                   # not tradable as recommended
    assert out["unpriced"] == 1


def test_warrants_units_and_rights_are_left_out_of_the_record_visibly():
    cal = [f"2026-01-{d:02d}" for d in range(6, 20)]
    history = [("2026-01-05", [
        {"ticker": "GRABW", "score": 90, "entry": 0.02},
        {"ticker": "AAA", "score": 80, "entry": 100.0},
    ])]
    closes = {"GRABW": {d: 0.04 for d in cal},       # +100% "win"
              "AAA": dict(zip(cal, [99, 96, 92] + [92] * 11)),
              "SPY": _spy(cal)}
    out = judge_history(history, closes)
    assert out["summary"]["trades"] == 1 and out["summary"]["avg_return_%"] < 0
    assert out["excluded_non_common"] == {"picks": 1, "tickers": ["GRABW"]}


def test_the_summary_counts_distinct_pick_dates():
    s = summarise([
        {"exit": "sell", "return_%": -7.0, "days_held": 2, "picked": "2026-01-05"},
        {"exit": "sell", "return_%": -6.0, "days_held": 2, "picked": "2026-01-05"},
        {"exit": "sell", "return_%": -5.0, "days_held": 2, "picked": "2026-01-06"},
    ])
    assert s["trades"] == 3 and s["dates"] == 2


def test_share_classes_are_common_stock_and_warrants_are_not():
    from backend.utils.universe import is_common_share
    for t in ("AAPL", "BRK-B", "GOOGL", "SNOW", "F"):
        assert is_common_share(t), t
    for t in ("GRABW", "HTZWW", "BTSGU", "GENVR", "X-WS", "ABC-RT"):
        assert not is_common_share(t), t
