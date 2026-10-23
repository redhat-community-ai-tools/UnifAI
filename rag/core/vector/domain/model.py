"""Vector domain models."""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class VectorChunk:
    """Domain model for a vector chunk to be stored."""
    text: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None  # Generated if not provided


@dataclass
class SearchResult:
    """Domain model for a vector search result."""
    id: str
    score: float
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


VISIBILITY_PRIVATE = "private"
VISIBILITY_SHARED = "shared"
VISIBILITY_PUBLIC = "public"


@dataclass(frozen=True)
class AccessScope:
    """Who is searching: their own sources, plus shared sources whose ACL groups they belong to.

    A shared source with no ACL groups is visible to nobody but its owner (fail closed).
    """
    owner_id: str
    groups: frozenset = frozenset()
