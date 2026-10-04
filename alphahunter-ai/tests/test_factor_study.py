"""Offline: the factor lab finds a planted effect, ignores noise, and never
looks ahead."""
import datetime as dt
import random

from backend.factor_study import (CANDIDATE_T, earnings_factors, price_factors, spearman,
                                  study, verdict_for)


def _calendar(n):
    out, d = [], dt.date(2023, 1, 2)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def _universe(group_drift: bool, n_days=620, groups=8, per_group=10, seed=3):
    rnd = random.Random(seed)
    cal = _calendar(n_days)
    prices = {"SPY": {"dates": cal, "c": [100 * (1.0003 ** i) for i in range(n_days)]}}
    themes = {}
    for g in range(groups):
        # Persistent group drift: group g trends at its own rate all along.
        drift = (g - groups / 2) * 0.0012 if group_drift else 0.0
        for j in range(per_group):
            p, c = 50.0, []
            for _ in range(n_days):
                p *= 1 + drift + rnd.gauss(0, 0.02)
                c.append(p)
            t = f"G{g}S{j}"
            prices[t] = {"dates": cal, "c": c}
            themes[t] = f"g{g}"
    return {"prices": prices, "themes": themes, "earnings": {}}


def _get(res, key, h=20):
    return next(f for f in res["factors"] if f["key"] == key)[f"h{h}"]


def test_a_planted_group_effect_is_found_and_confirmed_out_of_sample():
    res = study(_universe(group_drift=True))
    g = _get(res, "group_mom_3m")
    assert g["verdict"] == "candidate", g
    assert g["t"] >= CANDIDATE_T and g["second_half"]["t"] > 1


def test_pure_noise_produces_no_candidate():
    res = study(_universe(group_drift=False, seed=11))
    for f in res["factors"]:
        for h in (20, 60):
            assert f[f"h{h}"]["verdict"] != "candidate", (f["key"], h, f[f"h{h}"])


def test_an_earnings_report_counts_only_after_its_date():
    cal = _calendar(300)
    c = [100.0] * 300
    spy = [100.0] * 300
    k = 200
    future = [{"date": cal[k + 5], "surprise_pct": 25.0}]
    assert earnings_factors(future, cal, c, spy, k)["eps_surprise"] is None
    same_day = [{"date": cal[k], "surprise_pct": 25.0}]           # not strictly before
    assert earnings_factors(same_day, cal, c, spy, k)["eps_surprise"] is None
    past = [{"date": cal[k - 10], "surprise_pct": 25.0}]
    assert earnings_factors(past, cal, c, spy, k)["eps_surprise"] == 25.0
    stale = [{"date": cal[k - 100], "surprise_pct": 25.0}]         # older than 63 sessions
    assert earnings_factors(stale, cal, c, spy, k)["eps_surprise"] is None


def test_price_factors_use_no_future_bars():
    c = [100 + i for i in range(400)]
    a = price_factors(c, 300)
    crashed = c[:301] + [1.0] * 99
    assert price_factors(crashed, 300) == a


def test_wrong_sign_is_reported_not_adopted():
    st = {"t": -3.1, "first_half": {"t": -2.0}, "second_half": {"t": -2.5}}
    v, why = verdict_for(st, +1)
    assert v == "wrong_sign" and "OPPOSITE" in why
    assert verdict_for(st, -1)[0] == "candidate"     # a factor EXPECTED to be negative


def test_spearman_basics():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


def test_revisions_say_collecting_until_enough_logs_mature():
    from backend.factor_study import revision_study
    data = _universe(group_drift=False)
    cal = data["prices"]["SPY"]["dates"]
    logs = [{"date": cal[-30], "estimates": {t: {"rev_30d_pct": 1.0, "rev_90d_pct": 2.0, "net_up_30d": 1}
                                             for t in data["prices"] if t != "SPY"}}]
    r = revision_study(logs, data)
    assert r["logs"] == 1
    for f in r["factors"]:
        assert f["h20"]["verdict"] == "collecting" and f["h60"]["verdict"] == "collecting"


def test_estimate_log_fields():
    from backend.estimate_log import revision_fields

    class Frame:
        def __init__(self, rows): self.rows = rows
        @property
        def loc(self): return self.rows
    trend = Frame({"0y": {"current": 5.5, "30daysAgo": 5.0, "90daysAgo": 4.4}})
    revs = Frame({"0y": {"upLast30days": 7, "downLast30days": 2}})
    f = revision_fields(trend, revs)
    assert round(f["rev_30d_pct"], 6) == 10.0 and round(f["rev_90d_pct"], 2) == 25.0
    assert f["net_up_30d"] == 5
    assert revision_fields(None, None) == {"rev_30d_pct": None, "rev_90d_pct": None, "net_up_30d": None}


def test_earnings_rows_keep_only_reported():
    import math
    from backend.factor_data import earnings_rows

    class TS:
        def __init__(self, s): self.s = s
        def strftime(self, _): return self.s

    class DF:
        def __init__(self, rows): self.rows = rows
        def __len__(self): return len(self.rows)
        def iterrows(self): return iter(self.rows)
    df = DF([(TS("2026-11-01"), {"Reported EPS": math.nan, "Surprise(%)": math.nan}),   # upcoming
             (TS("2026-08-01"), {"Reported EPS": 1.2, "Surprise(%)": 8.5}),
             (TS("2026-05-01"), {"Reported EPS": 1.0, "Surprise(%)": math.nan})])
    assert earnings_rows(df) == [{"date": "2026-05-01", "surprise_pct": None},
                                 {"date": "2026-08-01", "surprise_pct": 8.5}]


def test_next_earnings_is_the_first_unreported_date_from_today():
    import math
    from backend.factor_data import calendar_entry, next_earnings

    class TS:
        def __init__(self, s): self.s = s
        def strftime(self, _): return self.s

    class DF:
        def __init__(self, rows): self.rows = rows
        def __len__(self): return len(self.rows)
        def iterrows(self): return iter(self.rows)
    df = DF([(TS("2027-01-28"), {"Reported EPS": math.nan}),
             (TS("2026-10-30"), {"Reported EPS": math.nan}),
             (TS("2026-07-30"), {"Reported EPS": 1.1})])
    assert next_earnings(df, "2026-10-04") == "2026-10-30"
    assert next_earnings(df, "2026-11-01") == "2027-01-28"
    assert next_earnings(DF([]), "2026-10-04") is None
    e = calendar_entry([{"date": "2026-07-30", "surprise_pct": 4.2}], "2026-10-30")
    assert e == {"next": "2026-10-30", "last": {"date": "2026-07-30", "surprise_pct": 4.2}}
    old = calendar_entry([{"date": "2022-08-24", "surprise_pct": 22.7}], "2027-02-19", "2026-10-04")
    assert old == {"next": "2027-02-19", "last": None}     # a 2022 report is not "the last result"
