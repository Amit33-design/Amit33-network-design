"""Offline: theme baskets — membership, stats, and data hygiene."""
import pytest

from backend.theme_pulse import MIN_MEMBERS, basket, clean_series, load_defs, members, resolve

DEFS = load_defs()


def test_resolution_matches_the_js_theme_map():
    # Same cases as story.test.ts, so Python and JS agree on membership.
    assert resolve("NVDA", "Semiconductors", DEFS) == "ai_compute"
    assert resolve("XOM", "Oil & Gas Integrated", DEFS) == "oil_gas"
    assert resolve("VST", "Utilities - Independent Power Producers", DEFS) == "ai_power"
    assert resolve("DUK", "Utilities - Regulated Electric", DEFS) == "utilities"
    assert resolve("TXN", "Semiconductors", DEFS) == "semis"
    assert resolve("LLY", "Drug Manufacturers - General", DEFS) == "glp1"
    assert resolve("ZZZ", "Software—Infrastructure", DEFS) == "software"
    assert resolve("ZZZ", "Something New", DEFS) is None


def test_members_add_profiled_companies_by_industry_largest_first():
    profiles = {
        "SMALLIPP": {"industry": "Utilities - Independent Power Producers", "market_cap": 2e9},
        "BIGIPP": {"industry": "Utilities - Independent Power Producers", "market_cap": 40e9},
        "NVDA": {"industry": "Semiconductors", "market_cap": 5e12},   # explicit elsewhere
    }
    m = members(DEFS, profiles)
    power = m["ai_power"]
    assert power[0] == "VST"                        # explicit list keeps its order
    assert power.index("BIGIPP") < power.index("SMALLIPP")
    assert "NVDA" not in m["semis"]                 # a stock sits in one theme


def _line(n, pct, start=100.0):
    return [start * (1 + pct / 100 * i / (n - 1)) for i in range(n)]


def test_basket_is_equal_weight_and_measures_breadth_and_tone():
    spy = _line(130, 2)
    closes = {f"T{i}": _line(130, 30) for i in range(3)}
    closes["LAG"] = _line(130, -20)
    b = basket(closes, spy)
    assert b["n"] == 4
    assert b["breadth_50d"] == 0.75                 # 3 of 4 above their 50-day
    assert b["leaders"][0]["ticker"].startswith("T")
    assert b["laggards"][0]["ticker"] == "LAG"
    assert b["tone"] == 1 and b["vs_spy_3m"] > 5


def test_too_few_members_is_no_basket():
    closes = {f"T{i}": _line(130, 10) for i in range(MIN_MEMBERS - 1)}
    assert basket(closes, _line(130, 2)) is None


def test_a_split_inside_the_window_keeps_the_member_out():
    dates = [f"2026-{m:02d}-{d:02d}" for m in range(3, 9) for d in range(1, 23)][:130]
    closes = _line(130, 5)
    split = closes[:100] + [c / 2 for c in closes[100:]]
    assert clean_series(dates, closes, "OK") is not None
    assert clean_series(dates, split, "SPLIT") is None
