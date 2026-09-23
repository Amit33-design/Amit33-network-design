"""The registry of screens that write dated results — and must be measured.

Three times now a screen has shipped and gone unmeasured: growth wrote no
dated file at all, and moonshot wrote one that the paper portfolio never read.
Both times the screen looked finished and quietly had no track record, which
is the worst failure mode this product has, because an unmeasured screen is
indistinguishable from a validated one on screen.

The cause is that "add a screen" touched several files and "measure a screen"
touched a different one. So the list lives here, once, and the paper portfolio
reads it rather than hardcoding globs. There is a test asserting that every
dated results file `run_daily` writes appears below — adding a fourth screen
without measurement wiring now fails the suite instead of shipping silently.
"""
from __future__ import annotations

# screen name -> glob for its dated results files in results/
# DATED files only: <name>_YYYY-MM-DD.json. A bare `moonshot_*.json` also
# matched `moonshot_full.json` — the 62,202-row research study — so the loop
# that "judges every screen" was reading a research file as if it were a day's
# picks. Research outputs live beside scan outputs in results/, so the pattern
# has to be strict enough to tell them apart.
_DATE = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"

SCREENS: dict[str, str] = {
    "crash": f"alphahunter_{_DATE}.json",
    "growth": f"growth_{_DATE}.json",
    "moonshot": f"moonshot_{_DATE}.json",
}


def globs() -> list[str]:
    return list(SCREENS.values())


def name_for(profile: str | None) -> str:
    """Map a recommendation's `metrics.profile` onto a screen name.

    The oversold scanner emits two profiles ("opportunity" for the loose
    pullback tier and nothing for the strict crash tier), so both land on
    "crash" unless reported separately.
    """
    if profile in SCREENS:
        return profile
    return "opportunity" if profile == "opportunity" else "crash"
