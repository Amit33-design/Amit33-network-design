"""Offline tests for pick-list concentration."""
import pytest

from backend.concentration import UNKNOWN, analyse, from_records


def test_a_spread_list_reads_as_many_bets():
    picks = [("A", "Technology"), ("B", "Healthcare"), ("C", "Energy"),
             ("D", "Financials"), ("E", "Industrials")]
    c = analyse(picks)
    assert c.count == 5
    assert c.effective_bets == 5.0
    assert c.concentrated is False
    assert "spread across 5 sectors" in c.note


def test_the_real_top_eight_is_called_out():
    """5 of 8 in one sector is roughly two bets, not eight."""
    picks = [(t, "Technology") for t in "ABCDE"] + [
        ("F", "Communication Services"), ("G", "Healthcare"),
        ("H", "Consumer Cyclical")]
    c = analyse(picks)

    assert c.count == 8
    assert c.top_sector == "Technology" and c.top_sector_share == 0.625
    assert 2.0 < c.effective_bets < 2.6          # eight names, ~2.3 bets
    assert c.concentrated is True
    assert "goes together" in c.note


def test_an_all_one_sector_list_is_one_bet():
    c = analyse([(t, "Technology") for t in "ABCDEF"])
    assert c.effective_bets == 1.0
    assert c.concentrated is True
    assert c.top_sector_share == 1.0


def test_duplicate_tickers_count_once():
    """A name appearing twice is not two bets."""
    c = analyse([("A", "Technology"), ("A", "Technology"), ("B", "Energy")])
    assert c.count == 2
    assert c.effective_bets == 2.0


def test_unclassified_names_do_not_masquerade_as_a_sector():
    """'62% Unclassified' is not a concentration finding, it is missing data,
    and reporting it as concentration would be nonsense."""
    c = analyse([("A", None), ("B", ""), ("C", None), ("D", "Energy")])
    assert c.top_sector == UNKNOWN
    assert "could not be classified" in c.note
    assert "sells off" not in c.note


def test_a_single_pick_is_a_single_bet():
    c = analyse([("A", "Energy")])
    assert c.effective_bets == 1.0 and c.concentrated is True


def test_an_empty_list_is_handled():
    c = analyse([])
    assert c.count == 0 and c.note == "no picks to analyse"


def test_moderate_concentration_below_the_threshold_passes():
    picks = [("A", "Tech"), ("B", "Tech"), ("C", "Health"), ("D", "Energy"),
             ("E", "Financials"), ("F", "Industrials")]
    c = analyse(picks)
    assert c.top_sector_share == pytest.approx(1 / 3, abs=0.01)
    assert c.concentrated is False


def test_from_records_prefers_the_profile_sector_then_falls_back():
    records = [{"ticker": "A"}, {"ticker": "B", "rel_strength": {"sector": "Energy"}}]
    profiles = {"A": {"sector": "Technology"}}
    c = from_records(records, profiles)
    sectors = {d["sector"] for d in c.by_sector}
    assert sectors == {"Technology", "Energy"}


def test_the_read_serialises():
    d = analyse([(t, "Technology") for t in "ABCDE"]).to_dict()
    for k in ("count", "effective_bets", "top_sector", "concentrated", "note"):
        assert k in d
