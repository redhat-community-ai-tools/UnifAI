from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the OpenAI LLM."""
    TYPE = "openai"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="OpenAI LLM",
    description=(
        "Official OpenAI API using the Responses endpoint (/v1/responses). "
        "Supports GPT-5+ and o-series models with tool calling and configurable "
        "reasoning effort. For older models or OpenAI-compatible servers (vLLM, etc.), "
        "use the 'OpenAI Compatible LLM' provider instead."
    ),
    tags=["llm", "openai", "gpt-5", "responses-api", "reasoning"],
)
