"""Point-in-time universe, reconstructed from git history.

Survivorship bias is the hardest thing to fix in a study like the doubler
analysis, because the correction needs to know what the universe looked like
in the PAST — including the names that have since disappeared. Paid datasets
sell exactly this. We do not have one.

But the daily workflow has been committing `universe_1b_revenue.csv` for a
while, and git keeps every version. That history IS a point-in-time universe,
accumulating for free. This module reads it.

Two honest limits, both reported rather than hidden:

  * it only goes back as far as the first commit of the file, so today it
    covers days rather than years. `coverage()` says so, and callers are
    expected to refuse to correct for survivorship until it is deep enough.
  * a ticker leaving the universe is not proof of delisting. It may have
    dropped below the revenue floor, changed symbol, or been acquired. It is
    a proxy, and `dropped_between` labels it as one.

Reading git is the only impure part and it is isolated in `_git`.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

UNIVERSE_PATH = "screener/universe_1b_revenue.csv"


def _git(args: list[str], repo: str) -> str:
    return subprocess.run(["git", "-C", repo] + args, capture_output=True,
                          text=True, timeout=60).stdout


def _parse_tickers(csv_text: str) -> set[str]:
    out = set()
    for i, line in enumerate(csv_text.splitlines()):
        if i == 0 and line.lower().startswith("ticker"):
            continue
        t = line.split(",")[0].strip().upper()
        if t and t.replace("-", "").replace(".", "").isalnum():
            out.add(t)
    return out


def snapshots(repo: str, path: str = UNIVERSE_PATH,
              max_commits: int = 400) -> dict[str, set[str]]:
    """{ISO date: universe on that date}, one entry per commit of the file."""
    log = _git(["log", f"-{max_commits}", "--follow", "--format=%H %ad",
                "--date=short", "--", path], repo)
    out: dict[str, set[str]] = {}
    for line in log.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        sha, date = parts
        if date in out:              # keep the first (latest) commit per day
            continue
        text = _git(["show", f"{sha}:{path}"], repo)
        tickers = _parse_tickers(text)
        if tickers:
            out[date] = tickers
    return out


@dataclass
class Coverage:
    days: int
    first: str | None
    last: str | None
    usable_for_horizon: bool
    note: str


def coverage(snaps: dict[str, set[str]], horizon_days: int = 252) -> Coverage:
    """Is there enough history to correct a study over this horizon?"""
    if not snaps:
        return Coverage(0, None, None, False, "no universe history found")
    dates = sorted(snaps)
    import datetime as dt
    span = (dt.date.fromisoformat(dates[-1]) - dt.date.fromisoformat(dates[0])).days
    ok = span >= horizon_days * 1.5        # calendar days, generously
    return Coverage(
        span, dates[0], dates[-1], ok,
        (f"{span} calendar days of universe history ({dates[0]} to {dates[-1]}). "
         + ("Enough to build point-in-time universes for this horizon."
            if ok else
            f"NOT enough for a {horizon_days}-session horizon — a study run "
            f"against this would still be survivor-only. It accumulates daily.")),
    )


def as_of(snaps: dict[str, set[str]], date: str) -> set[str]:
    """The universe as it stood on or before `date`."""
    usable = [d for d in sorted(snaps) if d <= date]
    return set(snaps[usable[-1]]) if usable else set()


def dropped_between(snaps: dict[str, set[str]], start: str, end: str) -> set[str]:
    """Tickers present at `start` and gone by `end`.

    A PROXY for failure, not a delisting record: a name can leave because
    revenue fell under the floor, it was acquired, or its symbol changed.
    """
    a, b = as_of(snaps, start), as_of(snaps, end)
    return a - b


def survivorship_gap(snaps: dict[str, set[str]], start: str, end: str) -> dict:
    """How much of the universe vanished — the size of what a study is missing."""
    a = as_of(snaps, start)
    gone = dropped_between(snaps, start, end)
    rate = len(gone) / len(a) if a else 0.0
    return {
        "universe_at_start": len(a),
        "dropped": len(gone),
        "drop_rate_%": round(rate * 100, 2),
        "examples": sorted(gone)[:15],
        "caveat": ("Leaving the universe is not proof of failure — a name can "
                   "drop below the revenue floor, be acquired, or change symbol."),
    }
