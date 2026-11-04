from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from mas.resources.deletion.mode import DeleteMode


class BlueprintUsageDetail(BaseModel):
    """A blueprint that references the target resource."""

    id: str
    name: str


class ResourceUsageDetail(BaseModel):
    """A resource that nests the target resource in its config."""

    id: str
    name: str
    category: Optional[str] = None
    type: Optional[str] = None


class UsageCheckResult(BaseModel):
    """Whether a resource is referenced and how it may be force-deleted."""

    in_use: bool
    category: Optional[str] = None
    allowed_mode: Optional[DeleteMode] = None
    blueprints: List[BlueprintUsageDetail] = Field(default_factory=list)
    resources: List[ResourceUsageDetail] = Field(default_factory=list)
