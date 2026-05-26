"""
Lightweight, persistable representation of a session.

Contains only the data needed for storage and retrieval —
no runtime artifacts (no graph plan, no executable graph, no node instances).

Used by:
  - create_session: build a record cheaply without compiling a graph
  - SessionRepository: typed save/fetch interface
  - SessionLifecycle: mutate status/state and persist
  - BackgroundLifecycleHandler: avoid expensive full-session hydration
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from mas.core.identity import Identity
from mas.core.execution_context import ExecutionContext
from mas.graph.state.graph_state import GraphState
from mas.session.domain.models import SessionMeta
from mas.session.domain.status import SessionStatus


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    identity: Identity
    blueprint_id: str
    run_context: ExecutionContext
    metadata: SessionMeta = Field(default_factory=SessionMeta)
    graph_state: GraphState = Field(default_factory=GraphState)
    status: SessionStatus = SessionStatus.PENDING

    @property
    def engine_handle(self) -> str | None:
        """The background workflow handle (Temporal workflow ID, Celery task ID, etc.)."""
        return self.run_context.engine_handle

    def update_context(self, **updates) -> None:
        """Apply updates to the frozen ExecutionContext."""
        self.run_context = self.run_context.model_copy(update=updates)
