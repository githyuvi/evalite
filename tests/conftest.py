import pytest
from evalite.agent.protocol import AgentResponse


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def sample_agent_response():
    return AgentResponse(content="test response")
