"""
Temporal DTO models.

Serializable parameter objects for workflows and activities.
These are the transport-layer data contracts for Temporal SDK.

With pydantic_data_converter configured on the client, Temporal
natively handles model_dump/model_validate for all Pydantic fields.

Shared by both inbound (worker/activities/workflows) and outbound
(executor/submitter) Temporal adapters.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from mas.engine.domain.models import GraphDefinition
from mas.graph.models.step_context import StepContext
from mas.graph.state.graph_state import GraphState
from mas.core.execution_context import ExecutionContext


# ── Workflow params ──────────────────────────────────────────────────

class GraphExecutionParams(BaseModel):
    """Input to GraphTraversalWorkflow."""
    state: GraphState = Field(default_factory=GraphState)
    graph_definition: GraphDefinition = Field(default_factory=GraphDefinition)
    session_id: str = ""
    execution_context: ExecutionContext = Field(default_factory=ExecutionContext)


class SessionWorkflowParams(BaseModel):
    """Input to SessionWorkflow (parent workflow).

    Carries the session execution context (for lifecycle activities)
    and the nested graph execution params (for the child
    GraphTraversalWorkflow).  The workflow owns the full lifecycle:
    begin → execute → complete/fail.

    Inputs are already staged into the SessionRecord before the
    workflow starts — no raw inputs are passed here.
    """
    run_id: str
    execution_context: ExecutionContext = Field(default_factory=ExecutionContext)
    graph_execution_params: GraphExecutionParams = Field(default_factory=GraphExecutionParams)


# ── Activity params ──────────────────────────────────────────────────

class ExecuteNodeParams(BaseModel):
    """Input to the execute_graph_node activity."""
    node_uid: str
    node_blueprint: Dict[str, Any] = Field(default_factory=dict)
    step_context: Optional[StepContext] = None
    state: GraphState = Field(default_factory=GraphState)
    session_id: str = ""
    execution_context: ExecutionContext = Field(default_factory=ExecutionContext)


class EvaluateConditionParams(BaseModel):
    """Input to the evaluate_condition activity."""
    condition_rid: str
    condition_blueprint: Dict[str, Any] = Field(default_factory=dict)
    step_context: Optional[StepContext] = None
    state: GraphState = Field(default_factory=GraphState)


class BeginSessionParams(BaseModel):
    """Input to the begin_session activity.

    Inputs are already staged — this only transitions QUEUED → RUNNING.
    """
    run_id: str
    execution_context: ExecutionContext = Field(default_factory=ExecutionContext)


class CompleteSessionParams(BaseModel):
    """Input to the complete_session activity."""
    run_id: str
    final_state: GraphState = Field(default_factory=GraphState)


class FailSessionParams(BaseModel):
    """Input to the fail_session activity."""
    run_id: str
    error_message: str = ""


class CancelSessionParams(BaseModel):
    """Input to the cancel_session activity."""
    run_id: str
