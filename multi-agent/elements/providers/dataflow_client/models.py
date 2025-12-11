"""
Response models for Dataflow API.
"""
from typing import List, Optional, ClassVar
from pydantic import BaseModel


class TagOption(BaseModel):
    """Single tag option from available tags response."""
    label: str
    value: str


class AvailableTagsResponse(BaseModel):
    """Response from /api/docs/available.tags.get"""
    options: List[TagOption]
    nextCursor: Optional[str] = None
    hasMore: bool = False
    total: int = 0


class DocumentInfo(BaseModel):
    """Single document info from available docs response."""
    name: str
    id: str


class AvailableDocsResponse(BaseModel):
    """Response from /api/docs/available.docs.get"""
    documents: List[DocumentInfo]
    nextCursor: Optional[str] = None
    hasMore: bool = False
    total: int = 0


class QueryMatchResult(BaseModel):
    """Single match result from query."""
    content: str
    score: float
    metadata: dict = {}


class QueryMatchResponse(BaseModel):
    """Response from /api/docs/query.match"""
    matches: List[QueryMatchResult]
    total: int = 0


class HealthResponse(BaseModel):
    """Response from /api/health/"""
    STATUS_OK: ClassVar[str] = "ok"

    message: str
    status: str

    @property
    def is_healthy(self) -> bool:
        return self.status == self.STATUS_OK

