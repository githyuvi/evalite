"""Multi-turn conversation test case model.

Per ADR-007, `ConversationTestCase` is the multi-turn counterpart to the
single-turn `TestCase` (see `evalite.testcase.models`). It is a single,
constructor-driven class: every multi-turn feature (dynamic driving,
scoring, accumulation) is opt-in via constructor arguments, most with
sensible defaults so a zero-config case is valid.

This module only covers construction/validation of the model. Precedence
resolution between `accumulate`/`accumulator` and between `driver`/
`turn_inputs` is runtime behavior implemented by the runner, not enforced
here (ADR-007, Decision 1).

Note on `driver`/`scorer` typing: both `ConversationDriver` and `Scorer`
are plain `Protocol`s, not `runtime_checkable` (see `evalite/scorer/base.py`
for why `Scorer` deliberately isn't). Under `arbitrary_types_allowed=True`,
pydantic builds an `isinstance` check for non-pydantic field types, which
raises at class-definition time for a non-`runtime_checkable` Protocol.
`Annotated[..., SkipValidation]` opts these two fields out of pydantic
validation (any value is accepted as-is) while keeping the precise type in
the annotation for static type checkers and documentation.
"""

from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, SkipValidation

from evalite.scorer.base import Scorer


class ConversationDriver(Protocol):
    """Structural contract for anything that can drive a conversation on
    behalf of the test user.

    Named `ConversationDriver` rather than "Test User Agent" to avoid
    colliding with "Agent," which in this framework refers to the system
    under test (see ADR-007, Decision 2).

    Like `Scorer` and `AgentAdapter`, this is a `Protocol`: implementations
    never need to import from this library to satisfy the contract, and
    both methods are async (ADR-002) since generating the next message or
    deciding whether to continue may require an LLM call.
    """

    async def next_message(self, history: list[dict], response: str) -> str: ...

    async def should_continue(self, history: list[dict], response: str) -> bool: ...


class ConversationTestCase(BaseModel):
    """A multi-turn conversation to run against an agent system (AS).

    id: stable identifier for the case, used in reports and reruns.
    initial_message: the first message sent to the agent under test.
    expected_outcomes: outcomes checked by the scorer across the
        conversation.

    driver: dynamic conversation driver; if provided, it generates each
        follow-up message and decides when the conversation ends.
    turn_inputs: static sequence of follow-up messages, used only when no
        `driver` is provided. If neither is provided, the conversation is
        a single follow-up turn (ADR-007, Decision 1).

    scorer: scorer used to score each turn; defaults to `DefaultScorer`
        (a simple keyword matcher) when not provided, so scoring works
        without an LLM API key (ADR-007, Decision 4). The default is
        applied by the runner, not this model — `None` here means "use
        the runner's default."
    accumulate: if True and no `accumulator` is given, the runner uses the
        built-in `DefaultAccumulator` to combine per-turn scores into a
        final score.
    accumulator: custom accumulator; overrides `accumulate` when provided
        (ADR-007, Decision 1). Intended type is `Accumulator`, a Protocol
        landing shortly in `evalite/scorer/pipeline/accumulator.py` (not
        yet committed as of this task) — typed as `Any | None` for now
        since that module doesn't exist yet to import from.

    max_turns: upper bound on turns for a single conversation run.
    iterations: number of times to run the full conversation.
    timeout_per_turn: optional per-turn timeout, in seconds.
    tags: free-form labels for filtering/grouping (e.g. "happy_path").
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    initial_message: str
    expected_outcomes: list[str]

    driver: Annotated[ConversationDriver | None, SkipValidation] = None
    turn_inputs: list[str] | None = None

    scorer: Annotated[Scorer | None, SkipValidation] = None
    accumulate: bool = False
    accumulator: Any | None = None  # intended type: Accumulator (evalite.scorer.pipeline.accumulator, not yet added)

    max_turns: int = 10
    iterations: int = 1
    timeout_per_turn: float | None = None
    tags: list[str] = []
