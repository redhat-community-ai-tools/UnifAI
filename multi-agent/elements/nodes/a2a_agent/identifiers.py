"""
A2A Agent Node Identifiers
"""

from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the A2A Agent node."""
    TYPE = "a2a_agent_node"


@dataclass(frozen=True)
class Meta:
    """Human-readable metadata about the element."""
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="A2A Agent Node",
    description="Agent node that delegates work to remote agent via A2A protocol",
    tags=[
        "agent",
        "node",
        "a2a",
        "remote",
        "delegation",
        "streaming",
    ],
)

