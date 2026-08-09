"""JSON path scorer implementation for evalite.

Parses actual.content as JSON and resolves a minimal, dependency-free
JSONPath-like expression against it, comparing the resolved value to an
expected value. Malformed input (invalid JSON, unresolvable path) is
treated as a failure rather than raising, matching DefaultScorer's
tolerance of malformed input.
"""

import json
from typing import Any

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import Score


class JsonPathScorer:
    """
    Parses actual.content as JSON and resolves `path` (a minimal subset of
    JSONPath: "$.a.b[0].c") against it, comparing the resolved value to
    `expected_value`.
    Score.value = 1.0 if the resolved value equals expected_value, else 0.0.
    """

    def __init__(self, path: str, expected_value: Any) -> None:
        """Store the path to resolve and the value to compare against.

        Args:
            path: A path string like "$.result.status" or "$.items[0].name".
            expected_value: The value the resolved path should equal.
        """
        self.path = path
        self.expected_value = expected_value

    def _resolve(self, data: Any) -> tuple[bool, Any]:
        """Resolve self.path against data.

        Args:
            data: The parsed JSON value to resolve the path against.

        Returns:
            A tuple of (resolved, value). If the path could not be
            resolved, resolved is False and value is None.
        """
        segments = self.path.split(".")
        if not segments or segments[0] != "$":
            return False, None

        current = data
        for segment in segments[1:]:
            key = segment
            index: int | None = None

            if segment.endswith("]") and "[" in segment:
                bracket_pos = segment.index("[")
                key = segment[:bracket_pos]
                index_str = segment[bracket_pos + 1 : -1]
                if not index_str.lstrip("-").isdigit():
                    return False, None
                index = int(index_str)

            if not isinstance(current, dict) or key not in current:
                return False, None
            current = current[key]

            if index is not None:
                if not isinstance(current, list):
                    return False, None
                if index < 0 or index >= len(current):
                    return False, None
                current = current[index]

        return True, current

    async def score(
        self,
        input: str,
        expected: dict,
        actual: AgentResponse,
    ) -> Score:
        """Score the actual response by resolving the JSON path.

        Args:
            input: The input given to the agent (unused for this scorer).
            expected: Dict of expected values (unused for this scorer).
            actual: The agent's response.

        Returns:
            A Score with passed/value/reasoning.
        """
        try:
            data = json.loads(actual.content)
        except json.JSONDecodeError:
            return Score(
                passed=False, value=0.0, reasoning="actual.content is not valid JSON"
            )

        resolved, value = self._resolve(data)
        if not resolved:
            return Score(
                passed=False,
                value=0.0,
                reasoning=f"path {self.path!r} did not resolve",
            )

        passed = value == self.expected_value
        score_value = 1.0 if passed else 0.0
        reasoning = (
            f"path {self.path!r} resolved to {value!r}, expected {self.expected_value!r}"
        )

        return Score(passed=passed, value=score_value, reasoning=reasoning)
