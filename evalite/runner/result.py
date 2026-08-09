"""Result models for evaluation runs.

`Score` is the value a `Scorer` returns for a single case. It is
intentionally minimal: a pass/fail flag, a normalized value in [0, 1]
for aggregation, and optional free-text reasoning for human review.

`CaseResult` is the outcome of running a single test case (one
iteration) through the agent and scoring it. `RunResult` aggregates
`CaseResult`s across an entire test set run.
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


class CaseResult(BaseModel):
    """The outcome of running a single test case through the agent.

    case_id: identifier of the test case this result belongs to.
    iteration: which repetition of the case this is (for cases run
        multiple times, e.g. to measure flakiness).
    input: the input given to the agent for this case.
    actual: the agent's actual response/output.
    score: the `Score` produced by the scorer for this case.
    passed: whether the runner considers this case a pass. Set
        independently of `score.passed` by the runner (e.g. it may
        factor in additional pass/fail logic beyond the scorer).
    duration_ms: how long this case took to run, in milliseconds.
    """

    case_id: str
    iteration: int
    input: str
    actual: str
    score: Score
    passed: bool
    duration_ms: float


class RunResult(BaseModel):
    """The aggregate outcome of running an entire test set.

    test_set_name: name of the test set that was run.
    total: total number of cases run.
    passed: number of cases that passed.
    failed: number of cases that failed.
    pass_rate: passed / total, in [0.0, 1.0]. Computed and set by the
        caller (e.g. the runner) rather than derived automatically.
    case_results: the individual `CaseResult` for each case run.
    duration_ms: total duration of the run, in milliseconds.
    """

    test_set_name: str
    total: int
    passed: int
    failed: int
    pass_rate: float = Field(ge=0.0, le=1.0)
    case_results: list[CaseResult]
    duration_ms: float
