"""
Claude Agent Node Identifiers
"""

from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Claude Agent node."""
    TYPE = "claude_agent_node"


class EffortLevel(str, Enum):
    """Controls how much effort Claude puts into reasoning."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


@dataclass(frozen=True)
class Meta:
    """Human-readable metadata about the element."""
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Claude Agent Node",
    description="Agent node powered by Claude Agent SDK for autonomous code-level tasks",
    tags=[
        "agent",
        "node",
        "claude",
        "sdk",
        "autonomous",
        "coding",
    ],
)
