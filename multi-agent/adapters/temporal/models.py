"""
Temporal DTO models.

Serializable parameter objects for workflows and activities.
These are the transport-layer data contracts for Temporal SDK.

With pydantic_data_converter configured on the client, Temporal
natively handles model_dump/model_validate for all Pydantic fields.

Shared by both inbound (worker/activities/workflows) and outbound
(executor/submitter) Temporal adapters.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from mas.scheduling.models import RunOutcome as RunOutcome
from mas.engine.domain.models import GraphDefinition
from mas.graph.models.step_context import StepContext
from mas.graph.state.graph_state import GraphState
from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.scheduling.models import PromptSource
from mas.session.execution.ports import ScheduledExecutionParams


# ── Workflow params ──────────────────────────────────────────────────

class GraphExecutionParams(BaseModel):
    """Input to GraphTraversalWorkflow."""
    state: GraphState = Field(default_factory=GraphState)
    graph_definition: GraphDefinition = Field(default_factory=GraphDefinition)
    session_id: str = ""
    execution_context: ExecutionContext = Field(default_factory=ExecutionContext)
    request_id: Optional[str] = None


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
    request_id: Optional[str] = None

    def to_scheduled_execution_params(self) -> ScheduledExecutionParams:
        """Map transport DTO → domain VO for ScheduledRunOps."""
        gep = self.graph_execution_params
        return ScheduledExecutionParams(
            run_id=self.run_id,
            execution_context=self.execution_context,
            graph_state=gep.state,
            graph_definition=gep.graph_definition,
        )

    @classmethod
    def from_scheduled_execution_params(
        cls, params: ScheduledExecutionParams,
    ) -> SessionWorkflowParams:
        """Map domain VO → transport DTO for SessionWorkflow."""
        return cls(
            run_id=params.run_id,
            execution_context=params.execution_context,
            graph_execution_params=GraphExecutionParams(
                state=params.graph_state,
                graph_definition=params.graph_definition,
                session_id=params.run_id,
                execution_context=params.execution_context,
            ),
        )


# ── Activity params ──────────────────────────────────────────────────

class ExecuteNodeParams(BaseModel):
    """Input to the execute_graph_node activity."""
    node_uid: str
    node_blueprint: Dict[str, Any] = Field(default_factory=dict)
    step_context: Optional[StepContext] = None
    state: GraphState = Field(default_factory=GraphState)
    session_id: str = ""
    execution_context: ExecutionContext = Field(default_factory=ExecutionContext)
    request_id: Optional[str] = None


class EvaluateConditionParams(BaseModel):
    """Input to the evaluate_condition activity."""
    condition_rid: str
    condition_blueprint: Dict[str, Any] = Field(default_factory=dict)
    step_context: Optional[StepContext] = None
    state: GraphState = Field(default_factory=GraphState)
    request_id: Optional[str] = None


class BeginSessionParams(BaseModel):
    """Input to the begin_session activity.

    Inputs are already staged — this only transitions QUEUED → RUNNING.
    """
    run_id: str
    execution_context: ExecutionContext = Field(default_factory=ExecutionContext)
    request_id: Optional[str] = None


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


# ── Scheduled session params ─────────────────────────────────────────

class ScheduledSessionParams(BaseModel):
    """Input to ScheduledSessionWorkflow (triggered by Temporal Schedule)."""
    schedule_id: str
    blueprint_id: str
    identity: Identity
    inputs: Dict[str, Any] = Field(default_factory=dict)
    source: PromptSource = PromptSource.MANUAL
    dedupe_key: Optional[str] = None
    credential_user_id: str = ""
    request_id: Optional[str] = None


# ── Consolidated scheduled session params ─────────────────────────────

class ProvisionResult(BaseModel):
    """Output of the provision_scheduled_session activity."""
    session_id: str
    params: SessionWorkflowParams


class RecordOutcomeParams(BaseModel):
    """Input to the record_scheduled_outcome activity."""
    schedule_id: str
    session_id: str
    outcome: RunOutcome
    started_at: str
    failure_reason: Optional[str] = None
