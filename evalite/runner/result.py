"""Result models for evaluation runs.

`Score` is the value a `Scorer` returns for a single case. It is
intentionally minimal: a pass/fail flag, a normalized value in [0, 1]
for aggregation, and optional free-text reasoning for human review.

`CaseResult` and `RunResult` (aggregate, multi-case results) are added
in a later wave and are not part of this module yet.
"""

from pydantic import BaseModel, Field


class Score(BaseModel):
    """The outcome of scoring a single agent response against a case.

    passed: whether the response satisfies the scorer's pass/fail bar.
    value: a normalized score in [0.0, 1.0], for aggregation across cases.
    reasoning: optional human-readable explanation (e.g. from an LLM judge).
    """

    passed: bool
    value: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
