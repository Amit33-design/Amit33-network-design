"""Factor lab: which ingredients actually predict a stock's next month or quarter?

The Analysis verdict was measured and found to carry no information: none of
its chart ingredients (trend score, RSI, MACD, 200-day, 6/12-month return…)
ranked the next 20 or 60 sessions better than chance. Re-weighting them would
only fit noise. This tests DIFFERENT kinds of ingredients — each a published
anomaly with its own reason to work — with the same discipline, so only what
survives can go into the verdict:

  group momentum     theme basket's 3/6-month return (industry momentum)
  relative strength  the stock vs its own group over 3 months
  earnings surprise  last reported EPS surprise % (post-earnings drift)
  earnings reaction  the stock vs SPY across its last report (the market's verdict)
  12-1 momentum      12-month return skipping the latest month
  52-week high       price / 52-week high (George & Hwang)
  1-week reversal    last week's return (expected NEGATIVE)
  lottery (MAX)      biggest daily gain in a month (expected NEGATIVE)
  volatility         60-day volatility (low-vol anomaly; expected NEGATIVE)

Discipline, all enforced here:
- Point-in-time. Every factor at a cutoff uses only bars up to that cutoff; an
  earnings report counts only once its date is strictly before the cutoff.
- Date-level statistics. Rank-IC is computed across stocks on each cutoff date
  and averaged; t is across dates and OVERLAP-CORRECTED (cutoffs every STEP
  sessions with 20/60-session outcomes share returns — see exit_judged).
- Multiple testing. ~10 factors are tested, so "candidate" needs |t| >= 2.5.
- Out of sample. The cutoff dates are split in half; a candidate must show the
  expected sign in BOTH halves, not just on the full period.
- Expected sign is stated before looking. A "significant" effect in the wrong
  direction is reported as such, never quietly flipped into a new rule.

Pure: takes already-fetched data (backend/factor_data.py fetches it in CI).
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from statistics import mean

STEP = 10
HORIZONS = (20, 60)
MIN_NAMES = 20            # stocks needed on a date for a cross-sectional IC
CANDIDATE_T = 2.5         # ~10 factors tested at once
LEAD_T = 2.0
MIN_GROUP_PEERS = 3

# (key, hypothesis shown to the user, expected sign of the IC)
FACTORS: list[tuple[str, str, int]] = [
    ("group_mom_3m", "Stocks in groups that led over 3 months keep leading (industry momentum)", +1),
    ("group_mom_6m", "Stocks in groups that led over 6 months keep leading", +1),
    ("rel_to_group_3m", "The leaders within their own group keep leading", +1),
    ("eps_surprise", "A bigger last earnings surprise is followed by drift the same way", +1),
    ("earn_reaction", "The market's reaction to the last report continues (post-earnings drift)", +1),
    ("mom_12_1", "12-month winners, skipping the last month, keep winning", +1),
    ("high52_prox", "Stocks near their 52-week high outperform (anchoring)", +1),
    ("rev_1w", "Last week's losers bounce, winners give back (short-term reversal)", -1),
    ("max_1m", "Lottery-like stocks — a huge one-day gain — underperform", -1),
    ("vol_60", "Calmer stocks beat volatile ones (low-volatility anomaly)", -1),
]


# ----------------------------------------------------------------- utilities
def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):                      # average ranks for ties
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    rx, ry = _rank(xs), _rank(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def t_stat(vals: list[float], overlap: float = 1.0) -> float | None:
    n = len(vals)
    if n < 3:
        return None
    m = mean(vals)
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))
    return round(m / (sd / math.sqrt(n)) / overlap, 2) if sd > 0 else None


def overlap(h: int, step: int = STEP) -> float:
    return math.sqrt(max(1.0, h / step))


# ------------------------------------------------------------------ factors
def align(series: dict, calendar: list[str]) -> list[float | None]:
    """Closes on the SPY calendar; None where the stock did not trade."""
    m = dict(zip(series["dates"], series["c"]))
    return [m.get(d) for d in calendar]


def _ret(c: list, k: int, back: int, skip: int = 0) -> float | None:
    a, b = k - skip, k - back
    if b < 0 or c[a] is None or c[b] is None or not c[b]:
        return None
    return c[a] / c[b] - 1


def price_factors(c: list, k: int) -> dict:
    """Price-only factors at index k, from bars 0..k only."""
    out = {"mom_12_1": _ret(c, k, 252, 21), "rev_1w": _ret(c, k, 5)}
    win = [x for x in c[max(0, k - 251):k + 1] if x]
    out["high52_prox"] = (c[k] / max(win)) if (c[k] and len(win) >= 200) else None
    rets = [c[i] / c[i - 1] - 1 for i in range(max(1, k - 59), k + 1)
            if c[i] and c[i - 1]]
    out["max_1m"] = max(rets[-21:]) if len(rets) >= 21 else None
    if len(rets) >= 50:
        m = mean(rets)
        out["vol_60"] = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    else:
        out["vol_60"] = None
    return out


def earnings_factors(events: list[dict], calendar: list[str], c: list, spy: list,
                     k: int, max_age: int = 63) -> dict:
    """The most recent report strictly before the cutoff and within max_age
    sessions: its EPS surprise, and the stock's move vs SPY across it."""
    d = calendar[k]
    past = [e for e in events if e.get("date") and e["date"] < d]
    if not past:
        return {"eps_surprise": None, "earn_reaction": None}
    e = max(past, key=lambda x: x["date"])
    # First session after the report date, and the last one before it.
    after = bisect_right(calendar, e["date"])
    before = bisect_left(calendar, e["date"]) - 1
    if after > k or before < 0:
        before = None if before < 0 else before
    if after > k or k - after > max_age:
        return {"eps_surprise": None, "earn_reaction": None}
    surprise = e.get("surprise_pct")
    reaction = None
    if before is not None and c[before] and c[after] and spy[before] and spy[after]:
        reaction = (c[after] / c[before] - 1) - (spy[after] / spy[before] - 1)
    return {"eps_surprise": surprise, "earn_reaction": reaction}


def group_factors(ticker: str, group: list[str], aligned: dict, k: int) -> dict:
    """Equal-weight return of the stock's theme peers (leave-one-out), and the
    stock's 3-month return relative to it."""
    out = {"group_mom_3m": None, "group_mom_6m": None, "rel_to_group_3m": None}
    peers = [t for t in group if t != ticker and t in aligned]
    for key, back in (("group_mom_3m", 63), ("group_mom_6m", 126)):
        rs = [r for r in (_ret(aligned[p], k, back) for p in peers) if r is not None]
        if len(rs) >= MIN_GROUP_PEERS:
            out[key] = mean(rs)
    own = _ret(aligned[ticker], k, 63)
    if own is not None and out["group_mom_3m"] is not None:
        out["rel_to_group_3m"] = own - out["group_mom_3m"]
    return out


# --------------------------------------------------------------- the study
def cross_sections(data: dict, step: int = STEP) -> list[dict]:
    """Per cutoff date: every stock's factors and forward alphas."""
    spy_s = data["prices"]["SPY"]
    cal = spy_s["dates"]
    spy = spy_s["c"]
    aligned = {t: align(s, cal) for t, s in data["prices"].items() if t != "SPY"}
    themes = data.get("themes", {})
    groups: dict[str, list[str]] = {}
    for t, th in themes.items():
        if th and t in aligned:
            groups.setdefault(th, []).append(t)
    earnings = data.get("earnings", {})

    out = []
    for k in range(252, len(cal) - min(HORIZONS), step):
        rows = []
        for t, c in aligned.items():
            if c[k] is None:
                continue
            f = price_factors(c, k)
            f.update(earnings_factors(earnings.get(t, []), cal, c, spy, k))
            th = themes.get(t)
            f.update(group_factors(t, groups.get(th, []), aligned, k) if th
                     else {"group_mom_3m": None, "group_mom_6m": None, "rel_to_group_3m": None})
            fwd = {}
            for h in HORIZONS:
                if k + h < len(cal) and c[k + h] and spy[k + h]:
                    fwd[h] = (c[k + h] / c[k] - 1) - (spy[k + h] / spy[k] - 1)
            if fwd:
                rows.append({"ticker": t, "f": f, "fwd": fwd})
        out.append({"date": cal[k], "rows": rows})
    return out


def _factor_stats(sections: list[dict], key: str, h: int) -> dict | None:
    ics, spreads, dates = [], [], []
    for s in sections:
        pts = [(r["f"][key], r["fwd"][h]) for r in s["rows"]
               if r["f"].get(key) is not None and h in r["fwd"]]
        if len(pts) < MIN_NAMES:
            continue
        ic = spearman([p[0] for p in pts], [p[1] for p in pts])
        if ic is None:
            continue
        pts.sort(key=lambda p: p[0])
        q = max(1, len(pts) // 5)
        spreads.append(mean(p[1] for p in pts[-q:]) - mean(p[1] for p in pts[:q]))
        ics.append(ic)
        dates.append(s["date"])
    if len(ics) < 6:
        return None
    ov = overlap(h)
    half = len(ics) // 2
    return {
        "dates": len(ics),
        "ic": round(mean(ics), 4),
        "t": t_stat(ics, ov),
        "spread_pp": round(mean(spreads) * 100, 2),       # top minus bottom quintile
        "spread_t": t_stat(spreads, ov),
        "first_half": {"ic": round(mean(ics[:half]), 4), "t": t_stat(ics[:half], ov)},
        "second_half": {"ic": round(mean(ics[half:]), 4), "t": t_stat(ics[half:], ov)},
        "period": [dates[0], dates[-1]],
    }


def verdict_for(stats: dict | None, sign: int) -> tuple[str, str]:
    """Classify one factor at one horizon. Pure."""
    if not stats or stats["t"] is None:
        return "insufficient", "Not enough dates with data to test."
    t = stats["t"] * sign                    # positive = the expected direction
    h1 = (stats["first_half"]["t"] or 0) * sign
    h2 = (stats["second_half"]["t"] or 0) * sign
    if t >= CANDIDATE_T and h1 > 0 and h2 >= 1.0:
        return "candidate", (f"Works in the expected direction (t = {stats['t']}) and held up in the "
                             f"second half on its own (t = {stats['second_half']['t']}).")
    if t >= LEAD_T:
        return "lead", (f"Expected direction (t = {stats['t']}) but below the {CANDIDATE_T} bar for "
                        f"{len(FACTORS)} factors, or not confirmed in both halves.")
    if t <= -CANDIDATE_T:
        return "wrong_sign", (f"Significant in the OPPOSITE direction to the hypothesis (t = {stats['t']}). "
                              f"Reported, not adopted: a reversed rule found by looking is a data-mined one.")
    return "no_signal", f"No measurable effect (t = {stats['t']})."


def study(data: dict, step: int = STEP) -> dict:
    sections = cross_sections(data, step)
    results = []
    for key, hypothesis, sign in FACTORS:
        entry = {"key": key, "hypothesis": hypothesis, "expected_sign": sign}
        for h in HORIZONS:
            st = _factor_stats(sections, key, h)
            v, why = verdict_for(st, sign)
            entry[f"h{h}"] = {**(st or {}), "verdict": v, "why": why}
        results.append(entry)
    names = {r["ticker"] for s in sections for r in s["rows"]}
    return {
        "factors": results,
        "cutoffs": len(sections),
        "stocks": len(names),
        "period": [sections[0]["date"], sections[-1]["date"]] if sections else None,
        "method": (f"Rank-IC across stocks on each cutoff (every {step} sessions), averaged over "
                   f"dates; t overlap-corrected; 'candidate' needs |t| >= {CANDIDATE_T} in the "
                   "expected direction and confirmation in the second half on its own. "
                   "Alpha = return minus SPY over the same sessions."),
    }


# ------------------------------------------------- analyst revisions (forward)
REVISION_FACTORS: list[tuple[str, str, int]] = [
    ("rev_30d_pct", "Stocks whose EPS estimates were raised over 30 days outperform", +1),
    ("rev_90d_pct", "Stocks whose EPS estimates were raised over 90 days outperform", +1),
    ("net_up_30d", "More analysts raising than cutting in 30 days predicts outperformance", +1),
]
MIN_MATURED_LOGS = 6


def revision_study(logs: list[dict], data: dict) -> dict:
    """Forward test of the weekly estimate logs (backend/estimate_log.py).

    Each log is entered at the close of the first session AFTER its date
    (estimates are known when logged; buying the next close is conservative).
    Until MIN_MATURED_LOGS logs have a full outcome the answer is "collecting",
    never an early guess."""
    spy_s = data["prices"]["SPY"]
    cal, spy = spy_s["dates"], spy_s["c"]
    aligned = {t: align(s, cal) for t, s in data["prices"].items() if t != "SPY"}
    sections = []
    for log in sorted(logs, key=lambda x: x.get("date", "")):
        k = bisect_right(cal, log.get("date", ""))
        if k >= len(cal):
            continue
        rows = []
        for t, f in (log.get("estimates") or {}).items():
            c = aligned.get(t)
            if not c or c[k] is None:
                continue
            fwd = {h: (c[k + h] / c[k] - 1) - (spy[k + h] / spy[k] - 1)
                   for h in HORIZONS if k + h < len(cal) and c[k + h] and spy[k + h]}
            if fwd:
                rows.append({"ticker": t, "f": f, "fwd": fwd})
        sections.append({"date": cal[k], "rows": rows})
    out = {"logs": len(logs), "factors": []}
    for key, hypothesis, sign in REVISION_FACTORS:
        entry = {"key": key, "hypothesis": hypothesis, "expected_sign": sign}
        for h in HORIZONS:
            matured = [s for s in sections if sum(1 for r in s["rows"] if h in r["fwd"]) >= MIN_NAMES]
            if len(matured) < MIN_MATURED_LOGS:
                entry[f"h{h}"] = {"verdict": "collecting", "matured_logs": len(matured),
                                  "why": f"{len(matured)} of {MIN_MATURED_LOGS} weekly logs have a full "
                                         f"{h}-session outcome yet. Forward test — no backfill exists."}
                continue
            # Weekly logs are 5 sessions apart; correct for that, not the 10-session STEP.
            st = _factor_stats_step(matured, key, h, step=5)
            v, why = verdict_for(st, sign)
            entry[f"h{h}"] = {**(st or {}), "verdict": v, "why": why, "matured_logs": len(matured)}
        out["factors"].append(entry)
    return out


def _factor_stats_step(sections, key, h, step):
    st = _factor_stats(sections, key, h)
    if st:      # re-apply the overlap correction for this spacing
        ratio = overlap(h, step) / overlap(h)
        for k in ("t", "spread_t"):
            if st.get(k) is not None:
                st[k] = round(st[k] / ratio, 2)
        for half in ("first_half", "second_half"):
            if st[half].get("t") is not None:
                st[half]["t"] = round(st[half]["t"] / ratio, 2)
    return st


def main() -> None:  # pragma: no cover - CI entrypoint
    import datetime as dt
    import glob
    import json
    import os
    import sys

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(sys.argv[1]) as f:
        data = json.load(f)
    out = study(data)
    logs = []
    for p in sorted(glob.glob(os.path.join(here, "results", "estimates_[0-9]*.json"))):
        try:
            with open(p) as f:
                logs.append(json.load(f))
        except Exception:
            continue
    out["revisions"] = revision_study(logs, data)
    out["generated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    path = os.path.join(here, "frontend", "public", "factor_study.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"factor study: {out['stocks']} stocks, {out['cutoffs']} cutoffs, {out['period']}")
    for fct in out["factors"]:
        for h in HORIZONS:
            r = fct[f"h{h}"]
            print(f"  {fct['key']:16} {h}d  IC {r.get('ic')}  t {r.get('t')}  "
                  f"halves {r.get('first_half', {}).get('t')}/{r.get('second_half', {}).get('t')}  "
                  f"spread {r.get('spread_pp')}pp  -> {r['verdict']}")
    print(f"  revisions: {out['revisions']['logs']} logs")


if __name__ == "__main__":  # pragma: no cover
    main()
