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
