from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Deep Agent node."""
    TYPE = "deep_agent_node"


@dataclass(frozen=True)
class Meta:
    """Human-readable metadata about the element."""
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Deep Agent Node",
    description="Agent node powered by LangChain Deep Agents with built-in planning, "
                "context management, and subagent delegation",
    tags=[
        "agent",
        "node",
        "deep_agent",
        "langchain",
        "planning",
        "subagents",
    ],
)
