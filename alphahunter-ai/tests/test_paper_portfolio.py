"""Offline tests for the $100-per-Buy paper portfolio."""
from backend.paper_portfolio import simulate, _is_buy


def _rec(ticker, action, price, score=70):
    return {"ticker": ticker, "company": f"{ticker} Inc", "action": action,
            "score": score, "metrics": {"price": price}}


def test_one_hundred_dollars_goes_into_each_buy():
    history = [("2026-01-05", [_rec("AAA", "Buy", 50.0), _rec("BBB", "Buy", 200.0)])]
    r = simulate(history, lambda t: {"AAA": 75.0, "BBB": 150.0}[t])

    assert r["positions"] == 2
    assert r["invested"] == 200.0
    # AAA +50%, BBB -25% ⇒ $150 + $75 = $225
    assert r["value"] == 225.0
    assert r["pnl"] == 25.0
    assert r["return_%"] == 12.5
    assert r["win_rate"] == 0.5


def test_only_buy_verdicts_are_funded():
    history = [("2026-01-05", [
        _rec("BUY1", "Buy", 100.0), _rec("ACC1", "Accumulate", 100.0),
        _rec("HOLD", "Hold", 100.0), _rec("RED", "Reduce", 100.0),
        _rec("SELL", "Sell", 100.0),
    ])]
    r = simulate(history, lambda t: 100.0)

    assert {h["ticker"] for h in r["holdings"]} == {"BUY1", "ACC1"}
    assert _is_buy("Strong Buy") and not _is_buy("Hold") and not _is_buy(None)


def test_a_repeated_buy_is_the_same_idea_not_a_second_hundred():
    """The screen re-surfaces the same names daily. Funding each repeat would
    silently overweight whatever the screen is most obsessed with."""
    history = [
        ("2026-01-05", [_rec("AAA", "Buy", 50.0)]),
        ("2026-01-06", [_rec("AAA", "Buy", 60.0)]),
        ("2026-01-07", [_rec("AAA", "Buy", 70.0)]),
    ]
    r = simulate(history, lambda t: 100.0)

    assert r["positions"] == 1
    assert r["invested"] == 100.0
    assert r["holdings"][0]["entry"] == 50.0      # the FIRST buy is the entry
    assert r["holdings"][0]["repeats"] == 2


def test_unpriced_positions_are_carried_at_cost_not_dropped():
    """Dropping a name we can't price would quietly delete losers."""
    history = [("2026-01-05", [_rec("AAA", "Buy", 50.0), _rec("GONE", "Buy", 10.0)])]
    r = simulate(history, lambda t: 100.0 if t == "AAA" else None)

    assert r["positions"] == 2 and r["priced"] == 1
    assert r["invested"] == 200.0
    assert r["value"] == 300.0                   # $200 for AAA + $100 held at cost
    assert r["holdings"][-1]["priced"] is False


def test_benchmark_control_uses_the_same_money_on_the_same_days():
    history = [("2026-01-05", [_rec("AAA", "Buy", 100.0)])]
    prices = {"AAA": 120.0, "SPY": 550.0}
    r = simulate(history, lambda t: prices[t],
                 bench_price=lambda _t, _d: 500.0)

    assert r["return_%"] == 20.0
    assert r["benchmark_return_%"] == 10.0       # 500 → 550
    assert r["alpha_%"] == 10.0
    assert r["beat_benchmark"] is True


def test_a_losing_book_reports_losing():
    history = [("2026-01-05", [_rec("AAA", "Buy", 100.0), _rec("BBB", "Buy", 100.0)])]
    # Both picks fall 40% while the index rises 10% — the case the panel must
    # not be able to dress up.
    prices = {"AAA": 60.0, "BBB": 60.0, "SPY": 550.0}
    r = simulate(history, lambda t: prices[t], bench_price=lambda _t, _d: 500.0)

    assert r["return_%"] == -40.0
    assert r["win_rate"] == 0.0
    assert r["winners"] == 0 and r["losers"] == 2
    assert r["beat_benchmark"] is False


def _band_history(returns_by_band):
    """5 names per band — enough to clear the small-band guard, which exists so
    a 2-name band can't decide whether the score works."""
    recs, prices = [], {}
    for band_score, ret in returns_by_band.items():
        for i in range(5):
            t = f"S{band_score}{i}"
            recs.append(_rec(t, "Buy", 100.0, score=band_score))
            prices[t] = 100.0 * (1 + ret / 100)
    return [("2026-01-05", recs)], prices


def test_score_bands_are_reported_and_an_inverted_score_is_called_out():
    """If a higher score doesn't mean a better outcome, the product must not
    keep presenting the score as conviction."""
    history, prices = _band_history({85: -20.0, 75: 0.0, 62: 30.0})
    r = simulate(history, lambda t: prices[t])

    bands = {b["band"]: b["avg_return_%"] for b in r["by_score_band"]}
    assert bands == {"80+": -20.0, "70-79": 0.0, "60-69": 30.0}
    assert r["score_separates"] is False        # inverted, and said so


def test_a_score_that_does_separate_is_recognised():
    history, prices = _band_history({85: 30.0, 75: 0.0, 62: -20.0})
    r = simulate(history, lambda t: prices[t])
    assert r["score_separates"] is True


def test_a_tiny_band_cannot_decide_whether_the_score_works():
    """One lucky name in the 80+ band must not flip the verdict."""
    history, prices = _band_history({75: 0.0, 62: 30.0})
    history[0][1].append(_rec("LUCKY", "Buy", 100.0, score=95))
    prices["LUCKY"] = 200.0                     # +100%, n=1

    r = simulate(history, lambda t: prices[t])
    assert any(b["band"] == "80+" and b["n"] == 1 for b in r["by_score_band"])
    assert r["score_separates"] is False        # still inverted where n is real


def test_quality_grade_is_held_to_the_same_standard_as_the_score():
    recs, prices = [], {}
    # Grade A does worst, D does best — an inverted grade must be reported.
    for grade, ret in (("A", -10.0), ("B", 0.0), ("C", 5.0), ("D", 15.0)):
        for i in range(5):
            t = f"{grade}{i}"
            rec = _rec(t, "Buy", 100.0)
            rec["quality_grade"] = grade
            recs.append(rec)
            prices[t] = 100.0 * (1 + ret / 100)
    r = simulate([("2026-01-05", recs)], lambda t: prices[t])

    grades = {b["band"]: b["avg_return_%"] for b in r["by_quality_grade"]}
    assert grades == {"A": -10.0, "B": 0.0, "C": 5.0, "D": 15.0}
    assert r["grade_separates"] is False
