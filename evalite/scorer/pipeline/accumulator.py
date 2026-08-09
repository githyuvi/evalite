"""Accumulator stage of PipelineScorer (ADR-007 Decision 5).

An `Accumulator` folds a sequence of per-turn `Score`s (produced during a
multi-turn conversation) into a single final `Score`. Per-turn scores are
always written to storage regardless of accumulation mode; the accumulator
is an optional layer on top used to summarize a whole conversation.
"""

from typing import Any, Protocol

from evalite.runner.result import Score


class Accumulator(Protocol):
    """Structural contract for folding per-turn Scores into a final Score."""

    def initial(self) -> Any:
        """Return the starting accumulator state."""
        ...

    def update(self, state: Any, turn_score: Score) -> Any:
        """Fold one turn's Score into state, returning the new state."""
        ...

    def finalize(self, state: Any, total_turns: int) -> Score:
        """Compute the final Score from the accumulated state."""
        ...


class DefaultAccumulator:
    """Averages score.value across turns. passed = average >= 1.0.

    State is a dict `{"total_value": float, "count": int}` representing a
    running sum of per-turn `Score.value` and the number of turns folded
    in so far. `update` does not mutate the passed-in state; it returns a
    new dict.
    """

    def initial(self) -> Any:
        """Return a zeroed running-sum state."""
        return {"total_value": 0.0, "count": 0}

    def update(self, state: Any, turn_score: Score) -> Any:
        """Add turn_score.value to the running total and increment count."""
        return {
            "total_value": state["total_value"] + turn_score.value,
            "count": state["count"] + 1,
        }

    def finalize(self, state: Any, total_turns: int) -> Score:
        """Compute the average value across total_turns and pass/fail it.

        Guards against division by zero: if total_turns is 0, returns
        value=0.0, passed=False rather than dividing by zero.
        """
        if total_turns == 0:
            return Score(passed=False, value=0.0, reasoning="Averaged 0 per-turn scores.")

        average = state["total_value"] / total_turns
        average = max(0.0, min(1.0, average))

        return Score(
            passed=average >= 1.0,
            value=average,
            reasoning=f"Averaged {total_turns} per-turn scores.",
        )
