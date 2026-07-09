"""
Session lifecycle state-machine transitions.

Operates on SessionRecord (the persistable layer) so that both foreground
runners and background workers can share the same logic without requiring
a full WorkflowSession.

Input staging (projecting raw inputs onto GraphState) is NOT this class's
job — that belongs to SessionInputProjector.  This class only manages
execution state transitions: begin → complete | fail.
"""
from mas.graph.state.graph_state import GraphState
from mas.session.repository.repository import SessionRepository
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.status import SessionStatus
from mas.session.domain.constants import CANCELLED_TAG, CANCELLED_STATUS_MESSAGE
from mas.session.domain.exceptions import SessionAlreadyCancelledError


class SessionLifecycle:
    """
    Owns the begin / complete / fail transitions of a SessionRecord.

    Stateless — all state lives in the SessionRecord and the repository.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    def begin(
        self,
        record: SessionRecord,
        scope: str,
    ) -> None:
        """
        Start execution: bind scope into run context, mark RUNNING, persist.

        Called AFTER inputs have already been staged by SessionInputProjector.
        Raises SessionAlreadyCancelledError if the session was cancelled
        before the workflow started, causing the runner to abort early.
        """
        if record.status == SessionStatus.CANCELLED:
            raise SessionAlreadyCancelledError(record.run_id)
        record.update_context(scope=scope)
        record.status = SessionStatus.RUNNING
        self._repo.save(record)

    def complete(
        self,
        record: SessionRecord,
        final_state: GraphState,
    ) -> None:
        """
        Post-execution: attach final state, mark COMPLETED, persist.
        No-op if session is already in terminal CANCELLED state.

        Re-fetches the record from the database so that fields updated
        externally during execution (e.g. ``hitl_overrides`` set via
        the approval-rule API) are not overwritten by this stale
        in-memory copy.
        """
        if record.status == SessionStatus.CANCELLED:
            return
        current = self._repo.fetch(record.run_id)
        current.graph_state = final_state
        current.run_context = current.run_context.mark_finished()
        current.status = SessionStatus.COMPLETED
        self._repo.save(current)

    def fail(
        self,
        record: SessionRecord,
        error: Exception,
    ) -> None:
        """
        On error: mark FAILED, persist.
        No-op if session is already in terminal CANCELLED state.

        Re-fetches the record (same rationale as ``complete``).
        """
        if record.status == SessionStatus.CANCELLED:
            return
        current = self._repo.fetch(record.run_id)
        current.run_context = current.run_context.mark_finished()
        current.status = SessionStatus.FAILED
        self._repo.save(current)

    def cancel(
        self,
        record: SessionRecord,
    ) -> None:
        """
        Cancel execution: mark CANCELLED, persist. Idempotent.
        Stamps metadata.cancelled so the frontend can show the
        cancellation notice when revisiting the session.
        """
        if record.status == SessionStatus.CANCELLED:
            return
        record.run_context = record.run_context.mark_finished()
        record.status = SessionStatus.CANCELLED
        record.metadata.tags[CANCELLED_TAG] = "true"
        record.metadata.status_message = CANCELLED_STATUS_MESSAGE
        msgs = record.graph_state.messages
        if msgs:
            updated_meta = {**msgs[-1].metadata, "is_cancelled": True}
            msgs[-1] = msgs[-1].model_copy(update={"metadata": updated_meta})
        self._repo.save(record)
