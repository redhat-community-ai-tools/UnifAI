from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Memory tool."""
    TYPE = "memory"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Memory",
    description="Read and write durable memories shared by every run of one scope (for example a project)",
    tags=["tool", "memory", "scope", "mongo", "qdrant", "embedding"],
)
