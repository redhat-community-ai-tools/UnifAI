from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import uuid4
from datetime import datetime
from pydantic import BaseModel, Field, Extra

from mas.core.identity import Identity
# ─────────────────────────────────────────────────────────────────────────────
#  Blueprint execution statistics (aggregated across all sessions)
# ─────────────────────────────────────────────────────────────────────────────

class BlueprintExecutionStats(BaseModel):
    """
    Pre-aggregated execution statistics for a single blueprint.

    Returned by the repository layer with raw metrics computed via
    database aggregation. The service layer transforms these into
    BlueprintUsage models with additional fields (name lookup, success rate %).
    """
    blueprint_id: str = Field(..., description="Blueprint identifier")
    total_runs: int = Field(0, description="Total number of executions")
    completed_runs: int = Field(0, description="Number of COMPLETED executions")
    failed_runs: int = Field(0, description="Number of FAILED executions")
    last_run: Optional[str] = Field(None, description="ISO timestamp of most recent execution")
    avg_duration_ms: Optional[float] = Field(None, description="Average duration in milliseconds")
    users: List[str] = Field(default_factory=list, description="Distinct runner identities as ``type:id`` strings (e.g. ``user:alice``, ``team:acme``)")

# -----------------------------------------------------------------------------
# Import the *catalog* specs (single source of truth for field validation)
# -----------------------------------------------------------------------------
from mas.elements.nodes.types import NodeSpec
from mas.elements.llms.types import LLMsSpec
from mas.elements.retrievers.types import RetrieversSpec
from mas.elements.conditions.types import ConditionSpec
from mas.elements.tools.types import ToolsSpec
from mas.elements.providers.types import ProviderSpec
from mas.elements.auths.types import AuthSpec
from mas.core.ref.models import Ref, NodeRef, ConditionRef

# ─────────────────────────────────────────────────────────────────────────────
# Author-time helper types
# ─────────────────────────────────────────────────────────────────────────────
T = TypeVar("T", bound=BaseModel)


class BlueprintResource(BaseModel, Generic[T]):
    """A resource entry in a blueprint (may have inline config or $ref)."""
    rid: Ref
    name: str | None = None
    type: str | None = None
    config: T | None = None

    class Config:
        extra = Extra.forbid


class ResourceSpec(BaseModel, Generic[T]):
    rid: Ref
    name: str
    type: str = Field(..., description="Element type identifier")
    config: T

    class Config:
        extra = Extra.forbid


# ─────────────────────────────────────────────────────────────────────────────
#  Graph plan
# ─────────────────────────────────────────────────────────────────────────────
class StepMeta(BaseModel):
    description: str = ""
    display_name: str = ""
    tags: List[str] = []

    class Config:
        extra = Extra.forbid


class StepDef(BaseModel):
    uid: str = Field(  # step id (local)
        default_factory=lambda: f"s_{uuid4().hex[:8]}"
    )
    after: str | List[str] | None = None  # depends-on
    node: NodeRef  # <-- node reference
    exit_condition: ConditionRef | None = None
    branches: dict | None = None
    meta: StepMeta = Field(default_factory=StepMeta)

    class Config:
        extra = Extra.forbid


# ─────────────────────────────────────────────────────────────────────────────
#  Blueprint summary (lightweight view – no spec details)
# ─────────────────────────────────────────────────────────────────────────────
class BlueprintSummary(BaseModel):
    """Lightweight view of a blueprint for listing -- no spec details."""
    blueprint_id: str
    identity: Identity
    name: str = "Untitled blueprint"
    description: str = ""
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
#  Top-level blueprints
# ─────────────────────────────────────────────────────────────────────────────
class BlueprintDraft(BaseModel):
    """UI-authorable document (may contain $refs)."""
    providers: List[BlueprintResource[ProviderSpec]] = []
    llms: List[BlueprintResource[LLMsSpec]] = []
    retrievers: List[BlueprintResource[RetrieversSpec]] = []
    tools: List[BlueprintResource[ToolsSpec]] = []
    nodes: List[BlueprintResource[NodeSpec]] = []
    conditions: List[BlueprintResource[ConditionSpec]] = []
    auths: List[BlueprintResource[AuthSpec]] = []

    plan: List[StepDef]

    name: str = "Untitled blueprint"
    description: str = ""

    class Config:
        extra = Extra.forbid


class BlueprintSpec(BaseModel):
    """What the graph-builder composer consumes – every $ref resolved."""
    providers: List[ResourceSpec[ProviderSpec]]
    llms: List[ResourceSpec[LLMsSpec]]
    retrievers: List[ResourceSpec[RetrieversSpec]]
    tools: List[ResourceSpec[ToolsSpec]]
    nodes: List[ResourceSpec[NodeSpec]]
    conditions: List[ResourceSpec[ConditionSpec]] = []
    auths: List[ResourceSpec[AuthSpec]] = []

    plan: List[StepDef]

    name: str
    description: str

    class Config:
        extra = Extra.forbid


# ─────────────────────────────────────────────────────────────────────────────
#  Blueprint document (DB-level wrapper returned by APIs)
# ─────────────────────────────────────────────────────────────────────────────
class BlueprintDocument(BaseModel):
    """
    Represents a stored blueprint document as returned by the API.
    Wraps the spec_dict together with its database-level metadata.
    """
    blueprint_id: str
    identity: Identity
    created_at: Any = None
    updated_at: Any = None
    spec_dict: Dict[str, Any]
    rid_refs: List[str] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = Extra.ignore
