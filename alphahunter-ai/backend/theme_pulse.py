"""Theme pulse: where money is flowing, measured on each theme's own stocks.

The investment thesis measured a theme's sentiment with its nearest ETF. For
some themes that ETF is the wrong group: "Power for AI data centers" was
benchmarked against XLU, which is mostly regulated utilities — so VST read as
"leading a group rotating out" when the group it actually belongs to may have
been doing something else entirely. The honest group is the theme's members.

This builds an equal-weight basket per theme — the explicit tickers in
api/_themes.js plus every profiled company whose industry resolves to it — and
measures it: 1- and 3-month return, vs the S&P over the same bars, and breadth
(the share of members above their 50-day average, which says whether a move
is broad or carried by one or two names). Output: frontend/public/themes.json,
read by the thesis and the Dashboard.

Theme definitions come from api/_themes.js via backend/themes_def.json
(`npm run themes:export`); vitest fails if the two drift. Everything except
`build` is pure and tested offline.

    python -m backend.theme_pulse
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from statistics import median

from backend.data_quality import validate_bars

HERE = os.path.dirname(os.path.abspath(__file__))
DEFS = os.path.join(HERE, "themes_def.json")
PUBLIC = os.path.join(os.path.dirname(HERE), "frontend", "public")
OUT = os.path.join(PUBLIC, "themes.json")

MIN_MEMBERS = 4          # below this a "basket" is one or two stocks; use the ETF
MAX_MEMBERS = 30         # explicit tickers first, then the largest by market cap
TONE_SPREAD = 5.0        # pp vs SPY over 3 months to call a group leading/lagging


def load_defs(path: str = DEFS) -> list[dict]:
    with open(path) as f:
        return json.load(f)["themes"]


def _norm(s: str | None) -> str:
    s = (s or "").lower().replace("—", " - ").replace("–", " - ")
    return re.sub(r"\s+", " ", s).strip()


def resolve(ticker: str, industry: str | None, defs: list[dict]) -> str | None:
    """Same order as resolveTheme() in api/_themes.js: ticker, then industry.
    (The sector fallback is not a theme and has no basket.)"""
    t = (ticker or "").upper()
    for d in defs:
        if t in d["tickers"]:
            return d["key"]
    ind = _norm(industry)
    if ind:
        for d in defs:
            if any(re.search(p, ind) for p in d["industries"]):
                return d["key"]
    return None


def members(defs: list[dict], profiles: dict) -> dict[str, list[str]]:
    """Theme key -> member tickers: explicit list first, then profiled
    companies whose industry maps to the theme, largest first."""
    by_key: dict[str, list[str]] = {d["key"]: list(d["tickers"]) for d in defs}
    extra: dict[str, list[tuple[float, str]]] = {}
    explicit = {t for d in defs for t in d["tickers"]}
    for t, p in profiles.items():
        if t in explicit:
            continue
        k = resolve(t, p.get("industry"), defs)
        if k:
            extra.setdefault(k, []).append((p.get("market_cap") or 0, t))
    for k, lst in extra.items():
        by_key[k] += [t for _, t in sorted(lst, reverse=True)]
    return {k: v[:MAX_MEMBERS] for k, v in by_key.items()}


def _ret(c: list[float], n: int) -> float | None:
    if len(c) <= n or not c[-1 - n]:
        return None
    return (c[-1] / c[-1 - n] - 1) * 100


def basket(closes: dict[str, list[float]], spy: list[float] | None) -> dict | None:
    """Equal-weight stats over the members that have enough clean history."""
    rows = []
    for t, c in closes.items():
        if not c or len(c) < 64:
            continue
        sma50 = sum(c[-50:]) / 50
        rows.append({"t": t, "r1": _ret(c, 21), "r3": _ret(c, 63), "above50": c[-1] > sma50})
    rows = [r for r in rows if r["r1"] is not None and r["r3"] is not None]
    if len(rows) < MIN_MEMBERS:
        return None
    r1 = sum(r["r1"] for r in rows) / len(rows)
    r3 = sum(r["r3"] for r in rows) / len(rows)
    s3 = _ret(spy, 63) if spy else None
    s1 = _ret(spy, 21) if spy else None
    vs = r3 - s3 if s3 is not None else None
    ranked = sorted(rows, key=lambda r: r["r1"], reverse=True)
    return {
        "n": len(rows),
        "ret_1m": round(r1, 1), "ret_3m": round(r3, 1),
        "median_1m": round(median(r["r1"] for r in rows), 1),
        "vs_spy_1m": round(r1 - s1, 1) if s1 is not None else None,
        "vs_spy_3m": round(vs, 1) if vs is not None else None,
        "breadth_50d": round(sum(r["above50"] for r in rows) / len(rows), 2),
        "tone": (1 if vs is not None and vs >= TONE_SPREAD
                 else -1 if vs is not None and vs <= -TONE_SPREAD else 0),
        "leaders": [{"ticker": r["t"], "ret_1m": round(r["r1"], 1)} for r in ranked[:3]],
        "laggards": [{"ticker": r["t"], "ret_1m": round(r["r1"], 1)} for r in ranked[-3:][::-1]],
    }


def clean_series(dates: list[str], closes: list[float], ticker: str) -> list[float] | None:
    """validate_bars() first (AGENTS.md §8). A split-shaped jump inside the
    3-month window would be read as a crash or a moonshot, so the member is
    left out rather than allowed to swing the basket."""
    rep = validate_bars(dates, closes, ticker=ticker)
    if rep.quality == "unusable" or len(rep.clean_closes) < 64:
        return None
    window = set(rep.clean_dates[-64:])
    if any(f.get("kind") == "possible_split" and f.get("date") in window for f in rep.flags):
        return None
    c = rep.clean_closes
    return c[:-1] if rep.is_stale else c


def build(out_path: str = OUT) -> dict:  # pragma: no cover - network
    import yfinance as yf

    defs = load_defs()
    try:
        with open(os.path.join(PUBLIC, "profiles.json")) as f:
            profiles = json.load(f).get("profiles", {})
    except Exception:
        profiles = {}
    mem = members(defs, profiles)
    tickers = sorted({t for v in mem.values() for t in v} | {"SPY"})

    series: dict[str, list[float]] = {}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        try:
            df = yf.download(chunk, period="6mo", auto_adjust=True, progress=False,
                             threads=True, group_by="ticker")
        except Exception:
            continue
        for t in chunk:
            try:
                col = (df[t]["Close"] if len(chunk) > 1 else df["Close"]).dropna()
            except Exception:
                continue
            c = clean_series([d.strftime("%Y-%m-%d") for d in col.index],
                             [float(v) for v in col.values], t)
            if c:
                series[t] = c

    spy = series.get("SPY")
    themes = []
    for d in defs:
        b = basket({t: series[t] for t in mem[d["key"]] if t in series}, spy)
        themes.append({"key": d["key"], "name": d["name"], "etf": d["etf"],
                       "growth": d["growth"], "members": mem[d["key"]], "basket": b})
    out = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "spy_1m": round(_ret(spy, 21), 1) if spy else None,
        "spy_3m": round(_ret(spy, 63), 1) if spy else None,
        "themes": themes,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    live = sum(1 for t in themes if t["basket"])
    print(f"themes.json: {live}/{len(themes)} themes with a basket")
    return out


if __name__ == "__main__":  # pragma: no cover
    build()
