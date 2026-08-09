"""Tests for the Accumulator Protocol and DefaultAccumulator (ADR-007 Decision 5)."""

from evalite.runner.result import Score
from evalite.scorer.pipeline.accumulator import DefaultAccumulator


def test_initial_returns_zeroed_state():
    accumulator = DefaultAccumulator()
    state = accumulator.initial()

    assert state["total_value"] == 0.0
    assert state["count"] == 0


def test_update_accumulates_across_multiple_turns():
    accumulator = DefaultAccumulator()
    state = accumulator.initial()

    turn_scores = [
        Score(passed=True, value=1.0),
        Score(passed=False, value=0.0),
        Score(passed=True, value=0.8),
    ]

    for turn_score in turn_scores:
        state = accumulator.update(state, turn_score)

    final = accumulator.finalize(state, total_turns=3)

    assert final.value == (1.0 + 0.0 + 0.8) / 3
    assert final.passed is False


def test_all_turns_passing_with_value_one_gives_full_average():
    accumulator = DefaultAccumulator()
    state = accumulator.initial()

    turn_scores = [
        Score(passed=True, value=1.0),
        Score(passed=True, value=1.0),
    ]

    for turn_score in turn_scores:
        state = accumulator.update(state, turn_score)

    final = accumulator.finalize(state, total_turns=2)

    assert final.value == 1.0
    assert final.passed is True


def test_finalize_with_zero_turns_does_not_raise():
    accumulator = DefaultAccumulator()
    state = accumulator.initial()

    final = accumulator.finalize(state, total_turns=0)

    assert final.value == 0.0
    assert final.passed is False
