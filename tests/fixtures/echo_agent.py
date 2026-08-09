# This file does NOT import from evalite — validates ADR-001
from dataclasses import dataclass, field

@dataclass
class AgentResponse:
    content: str
    metadata: dict = field(default_factory=dict)

class Agent:
    async def send(self, messages: list[dict]) -> AgentResponse:
        last = messages[-1]["content"] if messages else ""
        return AgentResponse(content=last)
