"""The guard that stops a screen from shipping without a track record."""
import pathlib
import re

from backend.screens import SCREENS, globs, name_for


def test_every_dated_results_file_run_daily_writes_is_registered():
    """This is the whole point of the registry. Growth shipped writing no
    dated file; moonshot wrote one nothing read. Both looked finished and had
    no measurable record, which is indistinguishable from a validated screen
    when you are looking at the dashboard."""
    src = (pathlib.Path(__file__).parent.parent / "backend" / "run_daily.py").read_text()

    # Matches: os.path.join(RESULTS_DIR, f"growth_{today}.json")
    written = set(re.findall(r'RESULTS_DIR,\s*f"([a-z_]+)_\{today\}\.json"', src))
    assert written, "expected run_daily to write dated results files"

    registered = {g.replace("_*.json", "") for g in globs()}
    missing = written - registered
    assert not missing, (
        f"{sorted(missing)} write dated results but are not in SCREENS, so the "
        f"paper portfolio will never judge them. Add them to backend/screens.py.")


def test_the_paper_portfolio_reads_the_registry_not_hardcoded_globs():
    src = (pathlib.Path(__file__).parent.parent / "backend"
           / "paper_portfolio.py").read_text()
    assert "from .screens import globs" in src
    assert "growth_*.json" not in src, "globs belong in the registry, not here"


def test_profiles_map_onto_screen_names():
    assert name_for("growth") == "growth"
    assert name_for("moonshot") == "moonshot"
    assert name_for("opportunity") == "opportunity"
    assert name_for(None) == "crash"
    assert name_for("something_new") == "crash"


def test_the_registry_is_not_empty_and_globs_are_well_formed():
    assert len(SCREENS) >= 3
    assert all(g.endswith("_*.json") for g in globs())
    assert len(set(globs())) == len(globs()), "duplicate globs would double-count picks"
