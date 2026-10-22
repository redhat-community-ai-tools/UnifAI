from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MemoryArgs(BaseModel):
    operation: Literal["read", "write"] = Field(
        ..., description="'write' stores a durable fact, decision or note; 'read' retrieves the most relevant ones.",
    )
    text: Optional[str] = Field(None, description="The memory to store. Required for 'write'.")
    query: Optional[str] = Field(
        None, description="What to look for. Required for 'read'; an empty query returns the most recent memories.",
    )
    kind: str = Field("fact", description="Optional label of a written memory, e.g. 'fact' or 'decision'.")
    top_k: Optional[int] = Field(None, gt=0, le=50, description="Maximum number of memories returned by 'read'.")


class MemoryEntry(BaseModel):
    id: str
    text: str
    kind: str = "fact"
    score: Optional[float] = None


class MemoryResponse(BaseModel):
    success: bool
    operation: str
    created: Optional[bool] = None
    memories: Optional[List[MemoryEntry]] = None
    error: Optional[str] = None

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)
