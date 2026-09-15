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
SCREENS: dict[str, str] = {
    # The original oversold/crash screen. Its files are the ones every older
    # study reads, so the glob stays as-is.
    "crash": "alphahunter_*.json",
    "growth": "growth_*.json",
    "moonshot": "moonshot_*.json",
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
