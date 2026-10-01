"""Regression: several result files on the same date must not crash the
paper portfolio (it was frozen from 13 Sep by "'<' not supported between
instances of 'dict' and 'dict'")."""
from backend.paper_portfolio import simulate


def test_two_screens_on_the_same_date_do_not_crash():
    history = [
        ("2026-09-13", [{"ticker": "AAA", "action": "Buy", "score": 70, "metrics": {"price": 10.0}}]),
        ("2026-09-13", [{"ticker": "BBB", "action": "Buy", "score": 60, "metrics": {"price": 20.0}}]),
        ("2026-09-12", [{"ticker": "CCC", "action": "Buy", "score": 65, "metrics": {"price": 5.0}}]),
    ]
    out = simulate(history, lambda t: {"AAA": 11.0, "BBB": 18.0, "CCC": 5.5}[t])
    assert out["positions"] == 3
