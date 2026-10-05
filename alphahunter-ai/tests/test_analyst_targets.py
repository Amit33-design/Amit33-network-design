"""Offline: analyst targets are shown only when there is real coverage."""
import math

from backend.analyst_targets import targets_from_info


def test_a_covered_stock_gets_a_target_block():
    t = targets_from_info({"targetMeanPrice": 54.2, "targetHighPrice": 70, "targetLowPrice": 38,
                           "targetMedianPrice": 55, "numberOfAnalystOpinions": 12, "currency": "USD"})
    assert t == {"mean": 54.2, "high": 70.0, "low": 38.0, "median": 55.0, "analysts": 12, "currency": "USD"}


def test_no_coverage_is_none_not_zero():
    assert targets_from_info({"targetMeanPrice": math.nan, "numberOfAnalystOpinions": 5}) is None
    assert targets_from_info({"targetMeanPrice": 20, "numberOfAnalystOpinions": 0}) is None
    assert targets_from_info({}) is None and targets_from_info(None) is None
