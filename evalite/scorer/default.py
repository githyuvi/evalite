"""Default scorer implementation for evalite.

Checks whether every value in `expected` appears as a substring in actual.content.
Case-insensitive matching. Passes if all expected values are found.
"""

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import Score


class DefaultScorer:
    """
    Checks whether every value in `expected` appears as a substring in actual.content.
    Case-insensitive. Passes if all expected values are found.
    Score.value = found_count / total_expected_count.
    """

    def _flatten_expected(self, expected: dict) -> list[str]:
        """Recursively flatten all leaf values in expected dict to strings.

        Only leaf values are included (no dict keys), converted to str().

        Args:
            expected: The expected dict, possibly nested.

        Returns:
            A list of string values from all leaves in the dict.
        """
        flattened = []

        def _recurse(obj):
            if isinstance(obj, dict):
                for value in obj.values():
                    _recurse(value)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _recurse(item)
            else:
                flattened.append(str(obj))

        _recurse(expected)
        return flattened

    async def score(
        self,
        input: str,
        expected: dict,
        actual: AgentResponse,
    ) -> Score:
        """Score the actual response against expected values.

        Checks whether each expected value appears as a case-insensitive
        substring in actual.content.

        Args:
            input: The input given to the agent (unused for this scorer).
            expected: Dict of expected values. Nested dicts are flattened.
            actual: The agent's response.

        Returns:
            A Score with passed/value/reasoning.
        """
        # Flatten expected dict to get all leaf values
        flattened = self._flatten_expected(expected)

        # Handle empty expected dict (vacuously true)
        if not flattened:
            return Score(passed=True, value=1.0, reasoning="0/0 expected values found")

        # Convert actual.content to lowercase for case-insensitive comparison
        actual_lower = actual.content.lower()

        # Count how many expected values are found in actual content
        found_count = 0
        for expected_value in flattened:
            if expected_value.lower() in actual_lower:
                found_count += 1

        total_expected = len(flattened)
        value = found_count / total_expected
        passed = value == 1.0

        reasoning = f"{found_count}/{total_expected} expected values found"

        return Score(passed=passed, value=value, reasoning=reasoning)
