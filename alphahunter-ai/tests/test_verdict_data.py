"""Offline: the verdict test's sample is reproducible and clean."""
from backend.verdict_data import sample_tickers, usable


def test_sample_is_reproducible_watchlist_first_and_common_shares_only():
    uni = [f"T{i:03d}" for i in range(100)] + ["GRABW", "HBANZ"]
    a = sample_tickers(uni, ["AAPL", "T005"], 20)
    assert a == sample_tickers(uni, ["AAPL", "T005"], 20)          # same draw every week
    assert a[:2] == ["AAPL", "T005"] and len(a) == 22 and len(set(a)) == 22   # watchlist + 20 drawn, no duplicates
    assert "GRABW" not in a and "HBANZ" not in a


def test_a_split_shaped_series_is_left_out():
    dates = [f"d{i:04d}" for i in range(320)]
    smooth = [100 + i * 0.1 for i in range(320)]
    split = smooth[:200] + [x / 2 for x in smooth[200:]]
    assert usable(dates, smooth, "OK")
    assert not usable(dates, split, "SPLIT")
    assert not usable(dates[:100], smooth[:100], "SHORT")
