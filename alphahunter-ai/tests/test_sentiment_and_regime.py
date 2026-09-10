"""Offline tests for the multi-source sentiment engine and the regime read."""
import pytest

from backend.market_regime import apply_to_position, assess, breadth, realized_vol
from backend.sentiment_sources import (
    composite_sentiment, consensus_signal, insider_signal, news_tone_signal,
    revision_signal, short_interest_signal, target_signal,
)


# --------------------------- consensus -------------------------------------
def test_thin_coverage_is_discounted_not_trusted():
    """A 1.5 from two analysts is not the evidence a 1.5 from thirty is."""
    many = consensus_signal({"recommendationMean": 1.5, "numberOfAnalystOpinions": 30})
    few = consensus_signal({"recommendationMean": 1.5, "numberOfAnalystOpinions": 2})

    assert many.score == pytest.approx(few.score)      # same opinion...
    assert many.confidence > few.confidence * 2        # ...much less weight
    assert "thin coverage" in " ".join(few.factors)


def test_bearish_consensus_scores_negative():
    s = consensus_signal({"recommendationMean": 4.2, "numberOfAnalystOpinions": 12})
    assert s.score < 0 and "sell" in " ".join(s.factors)


# --------------------------- revisions -------------------------------------
def test_upgrades_and_cuts_are_opposite_signals():
    up = revision_signal([
        {"period": "-3m", "strongBuy": 1, "buy": 2, "hold": 7, "sell": 0, "strongSell": 0},
        {"period": "0m", "strongBuy": 6, "buy": 3, "hold": 1, "sell": 0, "strongSell": 0},
    ])
    down = revision_signal([
        {"period": "-3m", "strongBuy": 6, "buy": 3, "hold": 1, "sell": 0, "strongSell": 0},
        {"period": "0m", "strongBuy": 1, "buy": 2, "hold": 7, "sell": 0, "strongSell": 0},
    ])

    assert up.score > 40 and "upgraded" in " ".join(up.factors)
    assert down.score < -40 and "cut" in " ".join(down.factors)


def test_steady_ratings_are_not_mistaken_for_a_signal():
    rows = [{"period": p, "strongBuy": 3, "buy": 4, "hold": 3, "sell": 0, "strongSell": 0}
            for p in ("-3m", "0m")]
    s = revision_signal(rows)
    assert s.score == 0.0 and "steady" in " ".join(s.factors)


def test_missing_history_returns_no_signal_rather_than_neutral_noise():
    s = revision_signal([{"period": "0m", "strongBuy": 5, "buy": 1, "hold": 0,
                          "sell": 0, "strongSell": 0}])
    assert not s.available


# --------------------------- targets ---------------------------------------
def test_trading_above_target_is_scored_as_the_bad_cohort_it_was():
    s = target_signal({"targetMeanPrice": 80.0}, 100.0)
    assert s.score < 0
    assert "worst cohort" in " ".join(s.factors)


def test_wildly_disagreeing_targets_lower_confidence():
    tight = target_signal({"targetMeanPrice": 130.0, "targetLowPrice": 120.0,
                           "targetHighPrice": 140.0}, 100.0)
    wide = target_signal({"targetMeanPrice": 130.0, "targetLowPrice": 40.0,
                          "targetHighPrice": 300.0}, 100.0)
    assert wide.confidence < tight.confidence
    assert "little agreement" in " ".join(wide.factors)


# --------------------------- insiders --------------------------------------
def test_insider_buying_counts_more_than_insider_selling():
    """Selling has tax and diversification reasons; buying has one reason."""
    buy = insider_signal({"bought_shares": 300_000, "sold_shares": 0})
    sell = insider_signal({"bought_shares": 0, "sold_shares": 300_000})
    assert buy.score > 0 and sell.score < 0
    assert abs(buy.score) > abs(sell.score) * 2
    assert "many innocent reasons" in " ".join(sell.factors)


# --------------------------- short interest --------------------------------
def test_short_interest_is_read_two_sided():
    heavy = short_interest_signal({"shortPercentOfFloat": 0.25})
    covering = short_interest_signal({"shortPercentOfFloat": 0.25,
                                      "sharesShort": 700_000,
                                      "sharesShortPriorMonth": 1_000_000})
    assert heavy.score < 0                      # crowded short = pressure
    assert covering.score > heavy.score         # ...but shorts covering helps
    assert "shrank" in " ".join(covering.factors)


# --------------------------- news tone -------------------------------------
def test_headline_tone_uses_a_finance_lexicon():
    good = news_tone_signal(["Acme beats estimates, raises guidance",
                             "Analysts upgrade Acme after record quarter",
                             "Acme wins $2B contract"])
    bad = news_tone_signal(["Acme misses badly, cuts outlook",
                            "SEC probe into Acme accounting",
                            "Acme announces layoffs and delays launch"])
    assert good.score > 50 and bad.score < -50
    assert good.confidence <= 0.7               # never allowed to dominate


def test_toneless_headlines_do_not_invent_a_signal():
    s = news_tone_signal(["Acme to present at a conference",
                          "Acme names new board member"])
    assert s.score == 0.0


# --------------------------- composite -------------------------------------
def test_missing_sources_do_not_drag_the_score_toward_neutral():
    """Re-normalising over what's available is the difference between a real
    score and mush."""
    bullish = consensus_signal({"recommendationMean": 1.4, "numberOfAnalystOpinions": 25})
    absent = [insider_signal(None), news_tone_signal([]), short_interest_signal({})]

    alone = composite_sentiment([bullish])
    with_gaps = composite_sentiment([bullish] + absent)
    assert alone["score"] == with_gaps["score"]     # gaps change nothing
    assert with_gaps["score"] > 70                  # and the bull case survives


def test_coverage_reports_how_much_evidence_there_actually_was():
    thin = composite_sentiment([consensus_signal(
        {"recommendationMean": 2.0, "numberOfAnalystOpinions": 20})])
    rich = composite_sentiment([
        consensus_signal({"recommendationMean": 2.0, "numberOfAnalystOpinions": 20}),
        target_signal({"targetMeanPrice": 130.0}, 100.0),
        insider_signal({"bought_shares": 100_000, "sold_shares": 10_000}),
        short_interest_signal({"shortPercentOfFloat": 0.03}),
    ])
    assert rich["coverage"] > thin["coverage"]


def test_no_data_at_all_is_neutral_and_says_so():
    out = composite_sentiment([insider_signal(None), news_tone_signal([])])
    assert out["score"] == 50.0 and "no sentiment data" in out["factors"][0]


# --------------------------- market regime ---------------------------------
def _series(n, start=400.0, daily=0.0005, shock=None):
    px, out = start, []
    for i in range(n):
        d = daily if shock is None or i < n - shock[0] else shock[1]
        px *= 1 + d
        out.append(px)
    return out


def test_a_healthy_tape_reads_risk_on_at_full_size():
    r = assess(_series(300), above_200_flags=[True] * 18 + [False] * 2,
               offensive_ret=8.0, defensive_ret=2.0)
    assert r.regime == "risk-on" and r.position_scale == 1.0
    assert any("above its 200-day" in f for f in r.factors)


def test_a_broken_tape_reads_risk_off_and_halves_size():
    r = assess(_series(300, daily=-0.0015), above_200_flags=[False] * 17 + [True] * 3,
               offensive_ret=-9.0, defensive_ret=1.0)
    assert r.regime == "risk-off" and r.position_scale == 0.5
    assert any("BELOW its 200-day" in f for f in r.factors)


def test_narrow_breadth_is_flagged_even_when_the_index_holds_up():
    """An index carried by a handful of names is the classic warning."""
    r = assess(_series(300), above_200_flags=[True] * 5 + [False] * 15)
    assert r.detail["above_200"] is True            # index still fine...
    assert any("narrow market" in f for f in r.factors)   # ...but breadth is not
    assert r.score < assess(_series(300), above_200_flags=[True] * 20).score


def test_position_scaling_is_explicit_rather_than_silent():
    r = assess(_series(300, daily=-0.0015), above_200_flags=[False] * 20)
    out = apply_to_position(100, r)
    assert out["shares"] == 50 and out["original_shares"] == 100
    assert "50% of normal" in out["reason"]


def test_volatility_and_breadth_helpers():
    assert realized_vol([100.0] * 30) == pytest.approx(0.0)
    assert realized_vol([100.0]) is None
    assert breadth([True, True, False, False]) == 0.5
    assert breadth([]) is None


def test_too_little_history_refuses_to_call_a_regime():
    r = assess([100.0] * 10)
    assert r.regime == "unknown" and r.position_scale == 1.0


# --------------------------- wiring ----------------------------------------
def test_both_scoring_paths_actually_use_the_extra_sentiment_sources():
    """Regression: score_ticker_general (the dashboard path) was calling the
    sentiment engine without the bundle, so the board silently kept scoring on
    the two original analyst fields while appearing to use six sources."""
    import inspect
    from backend.scoring import composite

    for fn in (composite.score_snapshot, composite.score_ticker_general):
        src = inspect.getsource(fn)
        assert "sentiment_bundle" in src, (
            f"{fn.__name__} does not pass the sentiment bundle — the extra "
            f"sources will silently do nothing on that path")


def test_the_engine_reports_which_sources_it_actually_had():
    from backend.scoring import engines

    info = {"recommendationMean": 1.6, "numberOfAnalystOpinions": 20,
            "targetMeanPrice": 140.0}
    thin = engines.sentiment_score(info, 100.0)
    rich = engines.sentiment_score(info, 100.0, {
        "recommendation_periods": [
            {"period": "-3m", "strongBuy": 1, "buy": 2, "hold": 7},
            {"period": "0m", "strongBuy": 6, "buy": 3, "hold": 1},
        ],
        "insider_purchases": {"bought_shares": 250_000, "sold_shares": 5_000},
        "headlines": ["Acme beats estimates and raises guidance"],
    })

    assert rich.detail["coverage"] > thin.detail["coverage"]
    assert rich.detail["sources"]["revisions"]["confidence"] > 0
    assert thin.detail["sources"]["revisions"]["confidence"] == 0
    assert rich.score > thin.score          # upgrades + insider buying help
