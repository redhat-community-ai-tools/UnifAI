from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Google Generative AI LLM."""
    TYPE = "google_genai"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Google Generative AI LLM",
    description="Google Generative AI (Gemini) configuration for LLM interactions",
    tags=["llm", "google", "gemini", "genai", "chat"],
)

