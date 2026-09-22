"""Offline tests for company-profile summarising."""
from backend.build_profiles import _clean_summary


def test_a_short_summary_is_left_alone():
    assert _clean_summary("Makes rockets.") == "Makes rockets."


def test_whitespace_is_normalised():
    assert _clean_summary("Makes\n  rockets.\t Sells them.") == "Makes rockets. Sells them."


def test_a_long_summary_is_cut_at_a_sentence_not_mid_word():
    body = ("Acme Corporation designs and sells widgets. " * 30)
    out = _clean_summary(body)
    assert len(out) < len(body)
    assert out.endswith("…")
    # The character before the ellipsis should end a sentence, not a word.
    assert out[:-2].rstrip().endswith(".")


def test_a_long_summary_with_no_sentence_break_still_truncates():
    out = _clean_summary("x" * 2000)
    assert out.endswith("…") and len(out) < 700


def test_missing_input_is_handled():
    assert _clean_summary(None) is None
    assert _clean_summary("") is None
