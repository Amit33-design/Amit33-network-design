"""Price history for the walk-forward test of the Analysis verdict.

Fetches ~3 years of daily OHLCV for a fixed, reproducible sample — the
dashboard watchlist plus a seeded random draw from the scan universe — and
SPY, and writes it as JSON for api/_verdict_eval.js (run by
frontend/scripts/verdict-eval.mjs). Every series goes through
validate_bars(): a ticker with a split-shaped jump or unusable data is left
out rather than letting one bad bar fake a crash or a moonshot.

    python -m backend.verdict_data OUT.json [--sample 250]
"""
from __future__ import annotations

import argparse
import json
import random

from backend.data_quality import validate_bars
from backend.utils.universe import is_common_share, load_universe
from backend.watchlist import all_tickers

SEED = 42          # same sample every week, so results move with the market, not the draw


def sample_tickers(universe: list[str], watch: list[str], n: int, seed: int = SEED) -> list[str]:
    """Watchlist first, then a seeded draw from the rest. Pure."""
    pool = sorted({t for t in universe if is_common_share(t)} - set(watch))
    draw = random.Random(seed).sample(pool, min(n, len(pool)))
    return list(dict.fromkeys(watch + draw))


def usable(dates: list[str], closes: list[float], ticker: str) -> bool:
    rep = validate_bars(dates, closes, ticker=ticker)
    if rep.quality == "unusable" or len(rep.clean_closes) < 300:
        return False
    return not any(f.get("kind") == "possible_split" for f in rep.flags)


def main() -> None:  # pragma: no cover - network
    import yfinance as yf

    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--sample", type=int, default=250)
    a = ap.parse_args()

    tickers = sample_tickers(load_universe(), all_tickers(), a.sample)
    out: dict[str, dict] = {}
    for i in range(0, len(tickers) + 1, 100):
        chunk = (["SPY"] if i == 0 else []) + tickers[i:i + 100]
        if not chunk:
            continue
        df = yf.download(chunk, period="3y", auto_adjust=True, progress=False,
                         threads=True, group_by="ticker")
        for t in chunk:
            try:
                sub = (df[t] if len(chunk) > 1 else df).dropna()
            except Exception:
                continue
            dates = [d.strftime("%Y-%m-%d") for d in sub.index]
            c = [float(x) for x in sub["Close"]]
            if t != "SPY" and not usable(dates, c, t):
                continue
            out[t] = {"dates": dates, "o": [float(x) for x in sub["Open"]],
                      "h": [float(x) for x in sub["High"]], "l": [float(x) for x in sub["Low"]],
                      "c": c, "v": [float(x) for x in sub["Volume"]]}
    with open(a.out, "w") as f:
        json.dump(out, f)
    print(f"verdict data: {len(out) - 1} tickers + SPY -> {a.out}")


if __name__ == "__main__":  # pragma: no cover
    main()
