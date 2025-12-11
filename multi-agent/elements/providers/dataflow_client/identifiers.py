from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    TYPE = "dataflow_client"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Dataflow Provider",
    description="Client for querying vector database and document metadata via Dataflow service",
    tags=["provider", "dataflow", "vector", "documents", "retrieval"],
)

