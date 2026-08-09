"""Test case data model.

Per ADR-005, Pydantic v2 models are the canonical in-memory format for test
cases. YAML files are the on-disk format for teams who want to manage test
cases in version control; a loader (elsewhere) validates YAML against these
models and surfaces clear error messages at load time rather than at run
time.
"""

from pydantic import BaseModel, ConfigDict


class ExpectedOutput(BaseModel):
    """The expected result of running a test case.

    Deliberately schema-less beyond `extra="allow"`: what counts as
    "expected" (task completion, a specific tool call, an exact string,
    ...) is defined per-project by scorers, not by this library. Any
    fields the user supplies are accepted and passed through to scorers.
    """

    model_config = ConfigDict(extra="allow")


class TestCase(BaseModel):
    """A single agent invocation to evaluate.

    id: stable identifier for the case, used in reports and reruns.
    input: the prompt/message sent to the agent under test.
    expected: the expected output, checked by scorers.
    tags: free-form labels for filtering/grouping (e.g. "happy_path").
    iterations: number of times to run this case (for flaky/non-deterministic
        agents); defaults to 1.
    """

    id: str
    input: str
    expected: ExpectedOutput
    tags: list[str] = []
    iterations: int = 1


class TestSet(BaseModel):
    """A named collection of test cases, typically loaded from one YAML file."""

    name: str
    cases: list[TestCase]
