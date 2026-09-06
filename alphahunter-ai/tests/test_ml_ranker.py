"""Offline tests for the learned ranker's ship/no-ship gate.

The gate is the whole point of the module: it decides whether a fitted model
is allowed to influence what the product recommends. These tests pin the two
ways it could fail — shipping noise, and refusing a real edge.
"""
import datetime as dt

from backend.ml_ranker import build_matrix, evaluate, explain


def _sample(i: int, sentiment: float, forward: float, score: float) -> dict:
    day = (dt.date(2026, 1, 5) + dt.timedelta(days=i // 12)).isoformat()
    return {
        "ticker": f"T{i:04d}", "date": day, "forward_%": forward, "score": score,
        "expected_gain_%": 20.0,
        "subscores": {"technical": 60.0, "fundamental": 55.0, "options": 65.0,
                      "momentum": 50.0, "sentiment": sentiment},
    }


def test_gate_ships_a_model_with_a_real_out_of_sample_edge():
    # Forward return is a clean function of sentiment, so the model should
    # learn it and keep ranking correctly on unseen dates.
    # The incumbent score varies but is only weakly related, so the gate has a
    # real baseline to beat rather than a degenerate constant.
    samples = [_sample(i, sentiment=40 + (i % 60), forward=(i % 60) - 30.0,
                       score=50.0 + (i % 7)) for i in range(600)]
    r = evaluate(samples)

    assert r["ships"] is True
    assert r["ridge_rank_ic"] > r["noise_floor"]
    assert "worth blending" in r["verdict"]


def test_gate_refuses_a_model_that_merely_beats_a_backwards_baseline():
    """The bug this gate exists for: a model whose own IC is negative must not
    ship just because the incumbent score is even more negative."""
    # Forward return is pure noise w.r.t. the features; the baseline score is
    # deliberately ranked backwards against it.
    import random
    random.seed(11)
    samples = []
    for i in range(600):
        fwd = random.gauss(0, 10)
        samples.append(_sample(i, sentiment=random.gauss(60, 12),
                               forward=fwd, score=-fwd))  # perfectly backwards
    r = evaluate(samples)

    assert r["baseline_rank_ic"] < 0        # the incumbent really is backwards
    assert r["ships"] is False              # ...and that is not a reason to ship
    assert "nothing ships" in r["verdict"]


def test_noise_is_never_reported_as_a_finding():
    import random
    random.seed(3)
    samples = [_sample(i, sentiment=random.gauss(60, 12),
                       forward=random.gauss(0, 10), score=random.gauss(60, 10))
               for i in range(600)]
    r = evaluate(samples)

    assert r["ships"] is False
    assert abs(r["ridge_rank_ic"]) < r["noise_floor"] or r["ridge_rank_ic"] <= 0


def test_build_matrix_keeps_row_indices_aligned():
    """Rows with a missing feature are dropped; `keep` must let the caller
    gather the baseline through the same filter."""
    good = _sample(0, 60.0, 1.0, 70.0)
    bad = _sample(1, 60.0, 1.0, 70.0)
    bad["subscores"]["sentiment"] = None
    X, y, dates, keep = build_matrix([good, bad, good])

    assert len(X) == 2
    assert keep == [0, 2]                   # the broken row is skipped, not shifted


def test_evaluate_refuses_to_guess_from_a_tiny_sample():
    r = evaluate([_sample(i, 60.0, 1.0, 70.0) for i in range(10)])
    assert "error" in r and "samples" in r["error"]


def test_explain_returns_signed_plain_english_reasons():
    model = {
        "ridge_coefficients": {"sentiment": 2.0, "momentum": -1.0, "technical": 0.1},
        "feature_means": {"sentiment": 60.0, "momentum": 50.0, "technical": 60.0},
        "feature_scales": {"sentiment": 10.0, "momentum": 10.0, "technical": 10.0},
    }
    lines = explain(model, {"sentiment": 80.0, "momentum": 70.0, "technical": 61.0},
                    expected_gain=None, top=2)

    assert len(lines) == 2
    assert lines[0].startswith("+") and "sentiment" in lines[0]   # biggest driver
    assert lines[1].startswith("−") and "momentum" in lines[1]    # biggest drag
