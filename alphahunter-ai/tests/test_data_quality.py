"""Offline tests for the price-series validation layer."""
import pytest

from backend.data_quality import validate_bars


def _series(n=60, start=100.0, step=1.0):
    return ([f"2026-01-{i + 1:02d}" if i < 31 else f"2026-02-{i - 30:02d}"
             for i in range(n)],
            [start + i * step for i in range(n)],
            [1_000_000.0] * n)


def test_a_clean_series_passes_untouched():
    d, c, v = _series()
    r = validate_bars(d, c, v, ticker="OK")
    assert r.quality == "ok" and r.dropped == 0 and not r.flags
    assert r.display_close == c[-1] and r.display_date == d[-1]


def test_impossible_values_are_dropped():
    d, c, v = _series(10)
    c[3] = 0.0          # zero close
    c[5] = -12.0        # negative close
    c[7] = None         # missing
    r = validate_bars(d, c, v, ticker="BAD")
    assert r.dropped == 3
    assert all(x > 0 for x in r.clean_closes)


def test_a_ten_x_spike_in_the_latest_bar_is_quarantined():
    """The dangerous case: the bad bar is the one on the dashboard."""
    d, c, v = _series(40)
    good_prev = c[-2]
    c[-1] = c[-2] * 10          # injected spike
    r = validate_bars(d, c, v, ticker="SPIKE")

    assert r.quality == "stale"
    assert r.display_close == good_prev      # falls back to the last good bar
    assert r.display_date == d[-2]
    assert any(f["kind"] in ("possible_split", "out_of_band") for f in r.flags)


def test_a_spike_in_the_middle_is_flagged_but_does_not_quarantine():
    """Only a bad LATEST bar affects what gets displayed."""
    d, c, v = _series(40)
    c[20] = c[19] * 8
    r = validate_bars(d, c, v, ticker="MID")
    assert r.flags                            # noticed
    assert r.quality == "ok"                  # but today's price is fine
    assert r.display_close == c[-1]


def test_a_clean_split_ratio_is_labelled_a_split_not_corruption():
    """A 2:1 move is a corporate action. Calling it corrupt data sends you
    looking for the wrong problem."""
    d, c, v = _series(40)
    for i in range(20, 40):
        c[i] = c[i] / 2                       # unadjusted 2:1 split
    r = validate_bars(d, c, v, ticker="SPLIT")
    kinds = {f["kind"] for f in r.flags}
    assert "possible_split" in kinds
    assert any("2:1 split" in f["detail"] for f in r.flags)


def test_an_internally_consistent_but_high_series_is_NOT_flagged():
    """The MU case, and the honest limit of this layer. A series that drifts
    smoothly from $861 to $1,043 has no internal evidence of error, so nothing
    fires — detecting a wrong LEVEL needs a second source, not a consistency
    check."""
    dates = [f"2026-08-{i + 1:02d}" for i in range(30)]
    closes = [861, 869, 911, 950, 972, 1012, 941, 937, 974, 967, 910, 933, 938,
              935, 933, 959, 933, 956, 958, 1017, 1000, 1028, 977, 975, 924,
              928, 927, 978, 1016, 1043]
    r = validate_bars(dates, [float(x) for x in closes], ticker="MU")

    assert r.quality == "ok"
    assert not r.flags
    assert r.display_close == 1043.0


def test_a_series_too_short_to_judge_is_unusable():
    r = validate_bars(["2026-01-01"], [100.0], ticker="THIN")
    assert r.quality == "unusable"
    assert r.display_close is None


def test_the_report_serialises_for_the_api():
    d, c, v = _series(40)
    c[-1] = c[-2] * 12
    out = validate_bars(d, c, v, ticker="X").to_dict()
    assert out["data_quality"] == "stale"
    assert out["display_close"] == pytest.approx(c[-2])
    assert isinstance(out["flags"], list) and out["flags"]


def test_a_genuine_crash_is_flagged_but_never_quarantined():
    """The most damaging thing this layer could do is replace a real -45% day
    with yesterday's price. Big moves are reported; only split-shaped jumps
    and out-of-band levels are quarantined."""
    d, c, v = _series(40)
    c[-1] = c[-2] * 0.56            # -44%, not near any split ratio
    r = validate_bars(d, c, v, ticker="CRASH")

    assert r.quality == "ok"                     # the price still displays
    assert r.display_close == pytest.approx(c[-1])
    assert any(f["kind"] == "suspicious_jump" for f in r.flags)   # but noted


def test_the_sanity_band_excludes_the_bar_it_is_judging():
    """Including the suspect bar let a 10x spike define the range it was
    compared against, so it could never be out of band."""
    d, c, v = _series(40)
    c[-1] = c[-2] * 25              # far outside any split ratio
    r = validate_bars(d, c, v, ticker="ABSURD")
    assert any(f["kind"] == "out_of_band" for f in r.flags)
    assert r.quality == "stale"
