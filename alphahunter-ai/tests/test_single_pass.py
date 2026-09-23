"""The daily pipeline must fetch each ticker exactly once.

Four separate passes over ~1,900 tickers — each sleeping per ticker, and
re-fetching because the 15-minute cache expired mid-scan — exceeded the job's
60-minute timeout. Every run from 18 Sep was cancelled and nothing was
committed for nine days, while the workflow page showed only "cancelled".
"""
import math

import numpy as np
import pandas as pd
import pytest

from backend.scanners import runner
from backend.utils.market_data import StockSnapshot


def _hist(start, daily, vol, seed, n=320):
    rng = np.random.default_rng(seed)
    px, out = start, []
    for _ in range(n):
        px *= math.exp(daily + rng.normal(0, vol))
        out.append(px)
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame({"Open": out, "High": [p * 1.01 for p in out],
                         "Low": [p * 0.99 for p in out], "Close": out,
                         "Volume": [6_000_000] * n}, index=idx)


INFO = {"totalRevenue": 4e9, "financialCurrency": "USD", "revenueGrowth": 0.35,
        "earningsGrowth": 0.4, "grossMargins": 0.6, "operatingMargins": 0.2,
        "freeCashflow": 1e9, "heldPercentInstitutions": 0.7,
        "recommendationMean": 2.0, "numberOfAnalystOpinions": 15,
        "targetMeanPrice": 200.0}


class FakeMarketData:
    """Counts network fetches so the test can assert on them."""
    fetches: dict[str, int] = {}

    def __init__(self, *a, **k):
        self.period = "260d"
        self._seen: set[str] = set()

    def is_cached(self, ticker):
        return ticker in FakeMarketData.fetches

    def snapshot(self, ticker):
        FakeMarketData.fetches[ticker] = FakeMarketData.fetches.get(ticker, 0) + 1
        profiles = {
            "LEADER": (50.0, 0.0035, 0.012),   # growth
            "WILD": (300.0, -0.004, 0.05),     # moonshot
            "CALM": (100.0, 0.0002, 0.004),
            "SPY": (500.0, 0.0004, 0.008),
        }
        start, daily, vol = profiles.get(ticker, (80.0, 0.0, 0.015))
        return StockSnapshot(ticker, _hist(start, daily, vol, hash(ticker) % 97), INFO)

    def sentiment_bundle(self, ticker):
        return {}

    def history(self, *a, **k):
        return None

    def options_chain(self, *a, **k):
        return None


@pytest.fixture
def fake_env(monkeypatch):
    FakeMarketData.fetches = {}
    sleeps = []
    monkeypatch.setattr(runner, "MarketData", FakeMarketData)
    monkeypatch.setattr(runner, "load_universe",
                        lambda: ["LEADER", "WILD", "CALM", "AAA", "BBB"])
    monkeypatch.setattr(runner.time, "sleep", lambda s: sleeps.append(s))
    # Scoring also builds a MarketData internally in some paths.
    import backend.scoring.composite as comp
    monkeypatch.setattr(comp, "MarketData", FakeMarketData, raising=False)
    return sleeps


def test_every_ticker_is_fetched_exactly_once(fake_env):
    runner.run_all_screens()
    universe = ["LEADER", "WILD", "CALM", "AAA", "BBB"]
    for t in universe:
        assert FakeMarketData.fetches.get(t) == 1, (
            f"{t} fetched {FakeMarketData.fetches.get(t)} times — a second pass "
            f"over the universe is what timed the daily job out")


def test_sleep_happens_only_on_real_fetches(fake_env):
    runner.run_all_screens()
    # One per universe ticker at most; never per screen per ticker.
    assert len(fake_env) <= 5


def test_every_screen_is_produced_from_the_one_pass(fake_env):
    out = runner.run_all_screens()
    for key in ("crash", "opportunity", "growth", "moonshot"):
        assert key in out and isinstance(out[key], list)
    stats = out["_stats"][0]
    assert stats["tickers"] == 5
    assert stats["network_fetches"] == 5


def test_run_daily_no_longer_rescans_the_universe():
    """Guard the regression at the source: run_daily must not call any of the
    per-screen runners that each loop over the whole universe."""
    import pathlib
    src = (pathlib.Path(__file__).parent.parent / "backend" / "run_daily.py").read_text()
    for fn in ("run_scan(", "run_opportunity_scan(", "run_growth_scan(",
               "run_moonshot_scan("):
        assert fn not in src, (
            f"run_daily calls {fn} — each of those is a full pass over the "
            f"universe, and four of them exceeded the job timeout")
    assert "run_all_screens(" in src
