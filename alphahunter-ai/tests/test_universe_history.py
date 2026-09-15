"""Offline tests for point-in-time universe reconstruction."""
from backend.universe_history import (
    Coverage, _parse_tickers, as_of, coverage, dropped_between, survivorship_gap,
)


def _snaps():
    return {
        "2026-01-05": {"AAA", "BBB", "CCC", "DDD"},
        "2026-06-05": {"AAA", "BBB", "CCC"},          # DDD gone
        "2026-12-05": {"AAA", "BBB", "EEE"},          # CCC gone, EEE new
    }


def test_parsing_skips_the_header_and_junk():
    csv = "ticker,revenue,checked_at\nAAPL,1.0,x\nBRK-B,2.0,y\n\n,,\n"
    assert _parse_tickers(csv) == {"AAPL", "BRK-B"}


def test_as_of_returns_the_universe_at_that_time_not_today():
    s = _snaps()
    assert "DDD" in as_of(s, "2026-03-01")       # still listed back then
    assert "DDD" not in as_of(s, "2026-07-01")
    assert as_of(s, "2020-01-01") == set()       # before any history


def test_dropped_between_finds_names_that_vanished():
    s = _snaps()
    assert dropped_between(s, "2026-01-05", "2026-12-05") == {"CCC", "DDD"}
    assert "EEE" not in dropped_between(s, "2026-01-05", "2026-12-05")


def test_survivorship_gap_sizes_what_a_study_would_be_missing():
    g = survivorship_gap(_snaps(), "2026-01-05", "2026-12-05")
    assert g["universe_at_start"] == 4 and g["dropped"] == 2
    assert g["drop_rate_%"] == 50.0
    assert "not proof of failure" in g["caveat"]


def test_coverage_refuses_a_horizon_it_cannot_support():
    """Thirteen days of history cannot correct a one-year study, and saying so
    is the entire point — otherwise the correction is theatre."""
    shallow = {"2026-09-02": {"AAA"}, "2026-09-15": {"AAA"}}
    c = coverage(shallow, horizon_days=252)
    assert c.usable_for_horizon is False
    assert "NOT enough" in c.note and c.days == 13


def test_coverage_accepts_a_deep_enough_history():
    c = coverage({"2024-01-01": {"AAA"}, "2026-09-01": {"AAA"}}, horizon_days=252)
    assert c.usable_for_horizon is True
    assert "Enough to build" in c.note


def test_no_history_is_handled():
    c = coverage({}, horizon_days=252)
    assert isinstance(c, Coverage) and c.usable_for_horizon is False
    assert as_of({}, "2026-01-01") == set()
