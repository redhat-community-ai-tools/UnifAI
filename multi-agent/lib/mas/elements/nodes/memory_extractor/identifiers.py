from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Memory Extractor node."""
    TYPE = "memory_extractor_node"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Memory Extractor Node",
    description="Extracts durable facts and memories from the session transcript into a memory tool",
    tags=["node", "memory", "extraction", "llm"],
)
