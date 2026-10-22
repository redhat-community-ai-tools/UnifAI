from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MemoryArgs(BaseModel):
    operation: Literal["read", "write", "set_fact", "get_fact", "list_facts"] = Field(
        ...,
        description=(
            "'write' stores a free-text memory and 'read' retrieves the most relevant ones; "
            "'set_fact' stores a structured JSON value under 'key' (replacing any previous value), "
            "'get_fact' returns it, 'list_facts' lists the latest facts."
        ),
    )
    key: Optional[str] = Field(None, description="Fact key. Required for 'set_fact' and 'get_fact'.")
    value: Optional[Any] = Field(None, description="Fact value, any JSON value. Required for 'set_fact'.")
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
    author: Optional[str] = None
    agent: Optional[str] = None
    session_id: Optional[str] = None
    classification: Optional[str] = None
    created_at: Optional[str] = None


class FactEntry(BaseModel):
    key: str
    value: Any = None
    author: Optional[str] = None
    agent: Optional[str] = None
    session_id: Optional[str] = None
    classification: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryResponse(BaseModel):
    success: bool
    operation: str
    created: Optional[bool] = None
    memories: Optional[List[MemoryEntry]] = None
    facts: Optional[List[FactEntry]] = None
    error: Optional[str] = None

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)
