from evalite.agent.protocol import AgentAdapter, AgentResponse


class ConformingAgent:
    """Has an async `send(self, messages)` method — should satisfy AgentAdapter."""

    async def send(self, messages: list[dict]) -> AgentResponse:
        return AgentResponse(content="ok")


class NonConformingAgent:
    """Has no `send` method at all — should NOT satisfy AgentAdapter."""

    async def greet(self, messages: list[dict]) -> AgentResponse:
        return AgentResponse(content="ok")


def test_conforming_agent_satisfies_protocol():
    agent = ConformingAgent()
    assert isinstance(agent, AgentAdapter)


def test_non_conforming_agent_does_not_satisfy_protocol():
    agent = NonConformingAgent()
    assert not isinstance(agent, AgentAdapter)
