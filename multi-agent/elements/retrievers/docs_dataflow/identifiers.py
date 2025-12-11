from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    TYPE = "docs_dataflow"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Docs Dataflow Retriever",
    description="Retrieves document passages via Dataflow vector database",
    tags=["retriever", "docs", "dataflow", "vector", "search"],
)

