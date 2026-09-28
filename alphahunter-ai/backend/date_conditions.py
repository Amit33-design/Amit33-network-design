"""Are the good scan dates predictable from the market on the day?

The corrected track record has a small positive average alpha that is not
distinguishable from luck (t < 1 across dates), and only about a quarter of
scan dates beat SPY — a few big days carry the average. If something knowable
ON THE PICK DATE separates those days from the rest (the market's trend, a
market-wide pullback, fear, how many names the screen caught), that is a real
"act today / sit today out" rule. If nothing does, the product should say so
rather than imply one.

Each condition splits the scan dates in two using only data available on the
pick date. Both halves are summarised on DATE-level alpha (same-day picks share
one market), and the halves are compared with a Welch t-statistic. Four
conditions are tested, so the bar for calling a difference real is raised
(|t| >= NOTABLE_T, and both halves need MIN_SIDE_DATES dates) — test enough
splits of 60 dates and one will look significant by chance.

Pure; tested offline.
"""
from __future__ import annotations

from statistics import mean, median, stdev

NOTABLE_T = 2.5
SUGGESTIVE_T = 2.0      # would pass a single test, not four — a lead, not a rule
MIN_SIDE_DATES = 10


def _series_before(series: dict[str, float], date: str, n: int) -> list[float]:
    """The last n closes on or before `date` (no look-ahead)."""
    ds = [d for d in sorted(series) if d <= date][-n:]
    return [series[d] for d in ds]


def _flags(date: str, spy: dict, vix: dict, picks: int, picks_median: float) -> dict:
    s51 = _series_before(spy, date, 51)
    s6 = _series_before(spy, date, 6)
    v = _series_before(vix, date, 1) if vix else []
    return {
        "spy_uptrend": (s51[-1] > sum(s51[-50:]) / 50) if len(s51) >= 50 else None,
        "spy_down_week": ((s6[-1] / s6[0] - 1) * 100 <= -1.0) if len(s6) == 6 else None,
        "vix_elevated": (v[-1] >= 20) if v else None,
        "broad_selloff": picks >= picks_median if picks_median else None,
    }


CONDITIONS = [
    ("spy_uptrend", "S&P above its 50-day average on the pick date"),
    ("spy_down_week", "S&P down 1%+ over the prior week (market-wide pullback)"),
    ("vix_elevated", "VIX at 20 or higher (fear elevated)"),
    ("broad_selloff", "The screen caught more names than usual (broad selloff)"),
]


def _side(alphas: list[float], trades: int) -> dict:
    n = len(alphas)
    m = mean(alphas) if alphas else None
    t = None
    if n >= 3:
        sd = stdev(alphas)
        t = round(m / (sd / n ** 0.5), 2) if sd > 0 else None
    return {"dates": n, "trades": trades,
            "avg_alpha_%": round(m, 2) if m is not None else None,
            "alpha_t": t,
            "dates_beating_spy": round(sum(a > 0 for a in alphas) / n, 3) if n else None}


def _welch(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(b) < 3:
        return None
    va, vb = stdev(a) ** 2 / len(a), stdev(b) ** 2 / len(b)
    if va + vb <= 0:
        return None
    return round((mean(a) - mean(b)) / (va + vb) ** 0.5, 2)


def analyse(trades: list[dict], spy: dict[str, float], vix: dict[str, float] | None = None) -> dict:
    """Split scan dates by each condition and compare date-level alpha."""
    by_date: dict[str, list[float]] = {}
    for t in trades:
        if t.get("spy_%") is not None and t.get("picked"):
            by_date.setdefault(t["picked"], []).append(t["return_%"] - t["spy_%"])
    if not by_date:
        return {"conditions": [], "note": "no closed trades"}
    counts = {d: len(v) for d, v in by_date.items()}
    med = median(counts.values())
    flags = {d: _flags(d, spy, vix or {}, counts[d], med) for d in by_date}

    out = []
    for key, question in CONDITIONS:
        yes = [d for d in by_date if flags[d][key] is True]
        no = [d for d in by_date if flags[d][key] is False]
        ay = [mean(by_date[d]) for d in yes]
        an = [mean(by_date[d]) for d in no]
        diff_t = _welch(ay, an)
        enough = len(yes) >= MIN_SIDE_DATES and len(no) >= MIN_SIDE_DATES
        notable = bool(enough and diff_t is not None and abs(diff_t) >= NOTABLE_T)
        if not enough:
            verdict = f"Too few dates on one side ({len(yes)} vs {len(no)}) to compare."
        elif notable:
            better = "when it holds" if diff_t > 0 else "when it does not"
            verdict = f"Picks did measurably better {better} (t = {diff_t})."
        elif enough and diff_t is not None and abs(diff_t) >= SUGGESTIVE_T:
            better = "when it holds" if diff_t > 0 else "when it does not"
            verdict = (f"Suggestive: picks did better {better} (t = {diff_t}), but below the "
                       f"{NOTABLE_T} bar for {len(CONDITIONS)} tests. A lead to keep watching, not a rule.")
        else:
            verdict = f"No measurable difference (t = {diff_t}) — this condition does not predict good days."
        out.append({
            "key": key, "question": question,
            "yes": _side(ay, sum(counts[d] for d in yes)),
            "no": _side(an, sum(counts[d] for d in no)),
            "diff_t": diff_t, "notable": notable, "verdict": verdict,
            "suggestive": bool(enough and not notable and diff_t is not None
                               and abs(diff_t) >= SUGGESTIVE_T),
        })
    return {
        "conditions": out,
        "method": ("Each scan date's average alpha (picks judged at their exit plan, vs SPY "
                   "over the same days), split by a condition known on the pick date. "
                   f"Notable needs |t| >= {NOTABLE_T} and {MIN_SIDE_DATES}+ dates each side, "
                   f"because {len(CONDITIONS)} splits are tested."),
    }
