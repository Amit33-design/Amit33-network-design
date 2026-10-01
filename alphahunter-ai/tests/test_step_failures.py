"""Offline: a failing post-scan step is recorded and annotated, never silent."""
from backend import run_daily
from backend.run_daily import stale_feeds, step_failed


def test_a_failed_step_is_recorded_and_emits_a_github_warning(capsys):
    run_daily.STEP_FAILURES.clear()
    step_failed("Paper portfolio", TypeError("'<' not supported between instances of 'dict' and 'dict'"))
    out = capsys.readouterr().out
    assert "::warning title=run_daily step failed: Paper portfolio::TypeError" in out
    assert run_daily.STEP_FAILURES == [{"step": "Paper portfolio",
                                        "error": "TypeError: '<' not supported between instances of 'dict' and 'dict'"}]
    run_daily.STEP_FAILURES.clear()


def test_stale_feeds_flags_a_feed_that_stopped_updating():
    feeds = {"snapshot": {"date": "2026-09-30"}, "growth": {"date": "2026-09-30"},
             "paper": {"date": "2026-09-13"}, "weekend": {"date": "2026-09-26"},
             "broken": {"date": None}}
    assert stale_feeds(feeds, "2026-09-30") == ["broken", "paper"]
