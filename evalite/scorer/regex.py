"""Regex scorer implementation for evalite.

Checks whether a regex pattern matches anywhere in actual.content.
"""

import re

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import Score


class RegexScorer:
    """
    Checks whether `pattern` matches anywhere in actual.content via re.search.
    Score.value = 1.0 if a match is found, else 0.0.
    """

    def __init__(self, pattern: str, flags: int = 0) -> None:
        """Store the pattern and flags to search with.

        Args:
            pattern: The regex pattern to search for.
            flags: Optional re flags (e.g. re.IGNORECASE).
        """
        self.pattern = pattern
        self.flags = flags

    async def score(
        self,
        input: str,
        expected: dict,
        actual: AgentResponse,
    ) -> Score:
        """Score the actual response by searching for the pattern.

        Args:
            input: The input given to the agent (unused for this scorer).
            expected: Dict of expected values (unused for this scorer).
            actual: The agent's response.

        Returns:
            A Score with passed/value/reasoning.
        """
        match = re.search(self.pattern, actual.content, self.flags)
        passed = match is not None
        value = 1.0 if passed else 0.0
        reasoning = (
            f"pattern {self.pattern!r} matched"
            if passed
            else f"pattern {self.pattern!r} did not match"
        )

        return Score(passed=passed, value=value, reasoning=reasoning)
