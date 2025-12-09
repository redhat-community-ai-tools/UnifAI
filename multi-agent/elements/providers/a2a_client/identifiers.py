from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for A2A Agent Provider."""
    TYPE = "a2a_agent"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="A2A Provider",
    description="Remote A2A agent communication via A2A protocol",
    tags=["provider", "a2a", "agent", "agent-to-agent"],
)
