"""`adapters/mock_summaries.py` — the shared fake-summary corpus."""

from __future__ import annotations

from graphrev.adapters.mock_summaries import MOCK_SUMMARIES, fallback_summary


def test_corpus_has_the_fifteen_hand_written_entries() -> None:
    assert len(MOCK_SUMMARIES) == 15
    assert "main" in MOCK_SUMMARIES
    assert "mem_copy_block" in MOCK_SUMMARIES


def test_corpus_entries_are_short_and_long_pairs() -> None:
    for short, long_ in MOCK_SUMMARIES.values():
        assert isinstance(short, str) and short
        assert isinstance(long_, str) and long_
        assert len(short) <= 120


def test_fallback_summary_is_deterministic_for_the_same_inputs() -> None:
    a = fallback_summary("some_unknown_fn", 0x401000, has_code_c=True, callee_count=3)
    b = fallback_summary("some_unknown_fn", 0x401000, has_code_c=True, callee_count=3)
    assert a == b


def test_fallback_summary_varies_by_name() -> None:
    a = fallback_summary("fn_a", 0x401000, has_code_c=True, callee_count=0)
    b = fallback_summary("fn_b", 0x401000, has_code_c=True, callee_count=0)
    assert a != b


def test_fallback_summary_short_is_clamped_to_one_row() -> None:
    short, _long = fallback_summary("x" * 50, 0x1000, has_code_c=False, callee_count=0)
    assert len(short) <= 120
