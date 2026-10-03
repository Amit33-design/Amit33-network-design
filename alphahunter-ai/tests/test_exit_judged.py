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
    for t in ("AAPL", "BRK-B", "GOOGL", "SNOW", "F", "FWONK", "LBTYK", "RUSHA", "IMKTA"):
        assert is_common_share(t), t
    for t in ("GRABW", "HTZWW", "BTSGU", "GENVR", "X-WS", "ABC-RT",
              # preferreds: NASDAQ 5th letter P/O/N/M/I, Z = misc; NYSE -P
              "MCHPP", "FITBO", "BHFAN", "BHFAM", "FITBI", "AGNCZ", "BAC-PK"):
        assert not is_common_share(t), t


def test_one_company_counts_once_keeping_its_largest_listing():
    from backend.utils.universe import dedupe_by_company
    profiles = {
        "HBAN": {"name": "Huntington Bancshares Incorporated", "market_cap": 3e10},
        "HBANL": {"name": "Huntington Bancshares Incorporated", "market_cap": None},
        "RUSHA": {"name": "Rush Enterprises, Inc.", "market_cap": 5.6e9},
        "RUSHB": {"name": "Rush Enterprises, Inc.", "market_cap": 6.4e9},
        "AAPL": {"name": "Apple Inc.", "market_cap": 3e12},
    }
    out = dedupe_by_company(["HBANL", "HBAN", "RUSHA", "RUSHB", "AAPL", "UNPROFILED"], profiles)
    assert out == ["HBAN", "RUSHB", "AAPL", "UNPROFILED"]


def test_significance_is_measured_across_dates_not_trades():
    """Ten identical trades on one date are one observation."""
    def day(d, alphas):
        return [{"exit": "sell", "return_%": a, "spy_%": 0.0, "days_held": 3,
                 "picked": d} for a in alphas]
    # A consistent edge across dates → large t.
    steady = sum((day(f"2026-01-{i:02d}", [2.0 + (i % 3) * 0.1] * 5) for i in range(5, 15)), [])
    assert summarise(steady)["alpha_t_by_date"] > 10
    # One great date and nine flat-to-negative ones: the trade-weighted mean is
    # positive, but across dates it is noise.
    lumpy = day("2026-01-05", [40.0] * 30) + sum(
        (day(f"2026-01-{i:02d}", [-1.0, 0.5]) for i in range(6, 15)), [])
    s = summarise(lumpy)
    assert s["avg_alpha_%"] > 5 and abs(s["alpha_t_by_date"]) < 2
    assert s["dates_beating_spy"] == 0.1
    assert summarise(day("2026-01-05", [1.0, 2.0]))["alpha_t_by_date"] is None


def test_holding_instead_separates_bad_picks_from_bad_exits():
    """A pick that dips through its stop and then rallies: the plan books the
    stop, holding 10 sessions books the rally. compare_hold must show that
    the exits, not the selection, cost the screen."""
    cal = [f"2026-01-{d:02d}" for d in range(6, 31)]
    history = [(f"2026-01-0{k}", [{"ticker": f"T{k}", "score": 70, "entry": 100.0,
                                   "metrics": {"profile": "growth"}}]) for k in (2, 3, 5)]
    dip_then_rally = [97, 92, 95, 100, 104, 107, 109, 110, 111, 111.5] + [111.5] * 15
    closes = {f"T{k}": dict(zip(cal, dip_then_rally)) for k in (2, 3, 5)}
    closes["SPY"] = {"2026-01-02": 500.0, "2026-01-03": 500.0, "2026-01-05": 500.0,
                     **{d: 500.0 for d in cal}}
    g = judge_history(history, closes)["by_screen"]["growth"]
    assert g["avg_return_%"] < 0                     # stopped out on the dip
    h = g["held_instead"]
    assert h["avg_alpha_%"] > 10 and h["hold_minus_plan_pp"] > 15
    # 20-session hold: the path is flat at 111.5 after day 10, so it books
    # the same rally; it needs 20 sessions of history to exist at all.
    h20 = g["held_20"]
    assert h20["days"] == 20 and h20["avg_alpha_%"] == pytest.approx(11.5, abs=0.01)


def test_a_moonshot_is_not_stopped_out_by_noise():
    """The first 20 moonshot picks were all stopped out within days by a
    -15% stop on stocks that move 5% a day. Judged by its own plan, a -25%
    wobble on the way to a double is the strategy, not a failed trade."""
    from backend.exit_rules import build_moonshot_plan, plan_for
    plan = build_moonshot_plan(4.0)
    assert plan.target == 8.0 and plan.horizon_days == 252 and plan.stop == 0.0
    assert plan_for(4.0, profile="moonshot").target == 8.0
    assert plan_for(100.0, atr=2.0, profile="opportunity").horizon_days == 10

    wobble_then_double = [3.5, 3.0, 3.2, 4.4, 5.5, 6.9, 8.1]
    r = judge_pick(4.0, wobble_then_double, profile="moonshot")
    assert r["exit"] == "take_profit" and r["return_%"] > 100
    # The same path under the generic plan would have been stopped out.
    assert judge_pick(4.0, wobble_then_double, atr=0.25)["exit"] == "sell"
    # Not yet at the double and inside the year: still open, not a result.
    assert judge_pick(4.0, [3.5, 3.0, 4.2], profile="moonshot") is None


def test_moonshot_watch_tracks_the_studys_actual_claim():
    from backend.exit_judged import summarise_moonshots
    w = summarise_moonshots([
        {"sessions": 40, "doubled": True, "return_%": 85.0, "spy_%": 3.0},
        {"sessions": 30, "doubled": False, "return_%": -40.0, "spy_%": 2.0},
        {"sessions": 20, "doubled": False, "return_%": -10.0, "spy_%": 1.0},
        {"sessions": 0},
    ])
    assert w["picks"] == 3 and w["doubled_so_far"] == 1 and w["doubled_%"] == 33.3
    assert w["median_return_%"] == -10.0 and w["oldest_sessions"] == 40
    assert summarise_moonshots([]) is None
    # The same name re-listed on later dates counts once, from its first pick.
    w2 = summarise_moonshots([
        {"ticker": "AAA", "picked": "2026-01-02", "sessions": 9, "doubled": False, "return_%": -5.0, "spy_%": 0.0},
        {"ticker": "AAA", "picked": "2026-01-05", "sessions": 6, "doubled": False, "return_%": 2.0, "spy_%": 0.0},
        {"ticker": "BBB", "picked": "2026-01-05", "sessions": 6, "doubled": True, "return_%": 120.0, "spy_%": 0.0},
    ])
    assert w2["picks"] == 2 and w2["listings"] == 3 and w2["oldest_sessions"] == 9
    assert w2["median_return_%"] == pytest.approx(57.5)
