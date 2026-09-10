from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the OpenAI-compatible LLM."""
    TYPE = "openai_compatible"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="OpenAI Compatible LLM",
    description=(
        "OpenAI-compatible API (vLLM, LocalAI, Ollama, etc.) using the "
        "Chat Completions endpoint (/v1/chat/completions)."
    ),
    tags=["llm", "openai", "vllm", "chat", "compatible"],
)
