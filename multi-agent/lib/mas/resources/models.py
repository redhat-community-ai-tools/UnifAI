from datetime import datetime
from typing import Dict, Any, List, Optional, Annotated
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator
from mas.core.enums import ResourceCategory
from mas.core.field_hints import HiddenHint
from mas.core.identity import Identity


class Resource(BaseModel):
    """
    One persisted element in the user's Library.
    
    cfg_dict is plain JSON; we do NOT store the Pydantic instance.
    """
    rid: str = Field(default_factory=lambda: uuid4().hex, json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    identity: Identity = Field(json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    category: ResourceCategory = Field(json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    type: str = Field(json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    name: str
    version: int = Field(default=1, json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    cfg_dict: Dict[str, Any] = Field(json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    nested_refs: List[str] = Field(default_factory=list, json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    contributed_by: Optional[str] = Field(default=None, json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    created: datetime = Field(default_factory=datetime.utcnow, json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())
    updated: datetime = Field(default_factory=datetime.utcnow, json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints())


class ResourceQuery(BaseModel):
    """Query object for finding resources with pagination and filtering."""
    identity: Identity = Field(..., description="Owner identity to filter resources")
    category: Optional[ResourceCategory] = Field(None, description="Resource category filter")
    type: Optional[str] = Field(None, description="Resource type filter")

    limit: Annotated[int, Field(50, ge=1, le=1000, description="Number of results to return")]
    offset: Annotated[int, Field(0, ge=0, description="Number of results to skip")]

    sort_by: str = Field("created", description="Field to sort by")
    sort_order: Annotated[str, Field("desc", pattern="^(asc|desc)$", description="Sort direction")]

    @classmethod
    @field_validator('sort_by')
    def validate_sort_by(cls, v: str) -> str:
        allowed_fields = {'created', 'updated', 'name', 'type', 'category'}
        if v not in allowed_fields:
            raise ValueError(f"sort_by must be one of: {allowed_fields}")
        return v
