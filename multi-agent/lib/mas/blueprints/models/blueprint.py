"""
Domain model for a Blueprint document.

This module is a zero-dependency Pydantic layer.  It must NOT import
anything from the adapter or application layers — it sits at the very
centre of the hexagonal architecture.

GENIE-1336: Added `version` field to `BlueprintDocument` for Optimistic
Concurrency Control (OCC).
"""

from __future__ import annotations

from typing import Any

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
    label: str | None = None

    model_config = {"frozen": True}


class ConditionRef(BaseModel):
    """Reference to a conditional branch target."""

    uid: str
    condition: str | None = None

    model_config = {"frozen": True}


class StepMeta(BaseModel):
    """Metadata attached to each step in the execution plan."""

    label: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class StepDef(BaseModel):
    """A single step definition within a blueprint plan."""

    uid: str
    tool: str
    config: dict[str, Any] = Field(default_factory=dict)
    next: list[NodeRef] = Field(default_factory=list)
    conditions: list[ConditionRef] = Field(default_factory=list)
    meta: StepMeta = Field(default_factory=StepMeta)

    model_config = {"frozen": True}


class BlueprintResource(BaseModel):
    """An external resource (e.g. file, dataset) referenced by the blueprint."""

    rid: str
    label: str | None = None
    required: bool = True

    model_config = {"frozen": True}


class ResourceSpec(BaseModel):
    """Typed resource requirement list embedded in the spec."""

    resources: list[BlueprintResource] = Field(default_factory=list)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Draft & Spec
# ---------------------------------------------------------------------------


class BlueprintDraft(BaseModel):
    """
    Mutable form submitted by the frontend to create or update a blueprint.
    All fields are optional so partial updates are supported.
    """

    name: str | None = None
    description: str | None = None
    plan: list[dict[str, Any]] | None = None
    nodes: list[dict[str, Any]] | None = None
    resources: ResourceSpec | None = None
    metadata: dict[str, Any] | None = None


class BlueprintSpec(BaseModel):
    """
    The canonical spec stored inside a blueprint document.
    The schema is intentionally open (extra fields are preserved) to support
    forward-compatibility as the execution engine evolves.
    """

    name: str = ""
    description: str = ""
    plan: list[dict[str, Any]] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)

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
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)


class BlueprintExecutionStats(BaseModel):
    """Aggregate statistics for executions of this blueprint."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_duration_ms: float | None = None


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
    identity: Identity | None = None
    created_at: Any
    updated_at: Any
    spec_dict: dict[str, Any] = Field(default_factory=dict)
    rid_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # GENIE-1336 — Optimistic Concurrency Control
    version: int = Field(default=1, ge=1)

    model_config = {"extra": "allow"}
