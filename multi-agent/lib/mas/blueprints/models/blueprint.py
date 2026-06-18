"""
Domain model for a Blueprint document.

This module is a zero-dependency Pydantic layer.  It must NOT import
anything from the adapter or application layers — it sits at the very
centre of the hexagonal architecture.

GENIE-1336: Added `version` field to `BlueprintDocument` for Optimistic
Concurrency Control (OCC).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Identity lives in the shared kernel; re-exported here for backwards
# compatibility so that ``from mas.blueprints.models.blueprint import Identity``
# continues to work across the codebase.
from mas.core.identity.models import Identity, IdentityType  # noqa: F401
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class NodeRef(BaseModel):
    """Lightweight reference to a node within a plan."""

    uid: str
    label: Optional[str] = None

    model_config = {"frozen": True}


class ConditionRef(BaseModel):
    """Reference to a conditional branch target."""

    uid: str
    condition: Optional[str] = None

    model_config = {"frozen": True}


class StepMeta(BaseModel):
    """Metadata attached to each step in the execution plan."""

    label: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class StepDef(BaseModel):
    """A single step definition within a blueprint plan."""

    uid: str
    tool: str
    config: Dict[str, Any] = Field(default_factory=dict)
    next: List[NodeRef] = Field(default_factory=list)
    conditions: List[ConditionRef] = Field(default_factory=list)
    meta: StepMeta = Field(default_factory=StepMeta)

    model_config = {"frozen": True}


class BlueprintResource(BaseModel):
    """An external resource (e.g. file, dataset) referenced by the blueprint."""

    rid: str
    label: Optional[str] = None
    required: bool = True

    model_config = {"frozen": True}


class ResourceSpec(BaseModel):
    """Typed resource requirement list embedded in the spec."""

    resources: List[BlueprintResource] = Field(default_factory=list)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Draft & Spec
# ---------------------------------------------------------------------------


class BlueprintDraft(BaseModel):
    """
    Mutable form submitted by the frontend to create or update a blueprint.
    All fields are optional so partial updates are supported.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    plan: Optional[List[Dict[str, Any]]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    resources: Optional[ResourceSpec] = None
    metadata: Optional[Dict[str, Any]] = None


class BlueprintSpec(BaseModel):
    """
    The canonical spec stored inside a blueprint document.
    The schema is intentionally open (extra fields are preserved) to support
    forward-compatibility as the execution engine evolves.
    """

    name: str = ""
    description: str = ""
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Read projections
# ---------------------------------------------------------------------------


class BlueprintSummary(BaseModel):
    """
    Lightweight projection used in listing endpoints.
    Does NOT include `spec_dict` — only metadata fields.
    """

    blueprint_id: str
    identity: Identity
    name: str = ""
    description: str = ""
    created_at: Any
    updated_at: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)


class BlueprintExecutionStats(BaseModel):
    """Aggregate statistics for executions of this blueprint."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_duration_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class BlueprintDocument(BaseModel):
    """
    Full blueprint aggregate root as stored in MongoDB.

    ``version`` is used for Optimistic Concurrency Control (OCC).
    Every successful ``update_with_version`` call atomically increments it.
    Existing documents without the field default to version=1 at read time.
    """

    blueprint_id: str
    identity: Optional[Identity] = None
    created_at: Any
    updated_at: Any
    spec_dict: Dict[str, Any] = Field(default_factory=dict)
    rid_refs: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # GENIE-1336 — Optimistic Concurrency Control
    version: int = Field(default=1, ge=1)

    model_config = {"extra": "allow"}
