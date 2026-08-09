"""Tool call scorer implementation for evalite.

Checks actual.metadata["tool_calls"] for an entry matching an expected
tool name (and optionally, expected args). A missing "tool_calls" key is
treated as no tool calls rather than an error.
"""

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import Score


class ToolCallScorer:
    """
    Checks actual.metadata["tool_calls"] (a list of {"name": str, "args": dict})
    for an entry where name == expected_tool. If expected_args is provided,
    that entry's args must also equal expected_args exactly.
    Score.value = 1.0 if passed else 0.0.
    """

    def __init__(self, expected_tool: str, expected_args: dict | None = None) -> None:
        """Store the tool name (and optional args) to check for.

        Args:
            expected_tool: The tool name that must appear in tool_calls.
            expected_args: If provided, the matching entry's args must
                equal this exactly.
        """
        self.expected_tool = expected_tool
        self.expected_args = expected_args

    async def score(
        self,
        input: str,
        expected: dict,
        actual: AgentResponse,
    ) -> Score:
        """Score the actual response by checking its tool_calls metadata.

        Args:
            input: The input given to the agent (unused for this scorer).
            expected: Dict of expected values (unused for this scorer).
            actual: The agent's response.

        Returns:
            A Score with passed/value/reasoning.
        """
        tool_calls = actual.metadata.get("tool_calls", [])

        passed = False
        for call in tool_calls:
            if call.get("name") != self.expected_tool:
                continue
            if self.expected_args is not None and call.get("args") != self.expected_args:
                continue
            passed = True
            break

        value = 1.0 if passed else 0.0
        reasoning = (
            f"tool {self.expected_tool!r} called with matching args"
            if passed
            else f"tool {self.expected_tool!r} not called with matching args"
        )

        return Score(passed=passed, value=value, reasoning=reasoning)
