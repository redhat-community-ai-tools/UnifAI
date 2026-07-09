from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Anthropic (Claude) LLM."""
    TYPE = "anthropic"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Anthropic LLM",
    description="Anthropic (Claude) Messages API configuration for LLM interactions",
    tags=["llm", "anthropic", "claude", "chat"],
)
