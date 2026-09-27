"""Offline: the profile builder covers the universe over successive runs."""
import datetime as dt

from backend.build_profiles import MAX_AGE_DAYS, plan_fetch

TODAY = dt.date(2026, 9, 27)


def _p(days_ago):
    return {"summary": "x", "fetched": (TODAY - dt.timedelta(days=days_ago)).isoformat()}


def test_missing_names_are_fetched_before_refreshing_known_ones():
    existing = {"AAA": _p(1), "BBB": _p(1)}
    todo = plan_fetch(existing, [], ["AAA", "BBB", "CCC", "DDD"], limit=10, today=TODAY)
    assert todo == ["CCC", "DDD"]          # fresh ones are left alone


def test_priority_names_come_first_and_the_budget_is_respected():
    existing = {"WL": _p(MAX_AGE_DAYS + 5)}  # a stale watchlist name
    todo = plan_fetch(existing, ["WL", "PICK"], ["A", "B", "C"], limit=3, today=TODAY)
    assert todo == ["WL", "PICK", "A"]


def test_repeated_runs_reach_the_whole_universe():
    """The old builder fetched the same first 400 every day: most tickers
    never got a description. Simulate runs with a small budget."""
    universe = [f"T{i}" for i in range(25)]
    existing: dict = {}
    for day in range(3):
        for t in plan_fetch(existing, [], universe, limit=10, today=TODAY):
            existing[t] = _p(0)
    assert set(existing) == set(universe)


def test_stale_profiles_refresh_oldest_first_and_unstamped_count_as_oldest():
    existing = {"OLD": _p(90), "OLDER": _p(200), "UNSTAMPED": {"summary": "x"}, "NEW": _p(2)}
    todo = plan_fetch(existing, [], list(existing), limit=None, today=TODAY)
    assert todo == ["UNSTAMPED", "OLDER", "OLD"]
