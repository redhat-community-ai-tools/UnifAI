import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from mas.session.management.user_session_manager import UserSessionManager
from mas.session.execution.foreground_runner import ForegroundSessionRunner
from mas.session.execution.input_projector import SessionInputProjector
from mas.session.execution.ports import BackgroundSessionEngine, SubmitSessionRequest
from mas.session.domain.status import SessionStatus
from mas.session.domain.workflow_session import WorkflowSession
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.dto import SessionListItem
from mas.session.domain.models import SessionChat, SessionMeta, TimeSeriesPoint, SystemAnalyticsData
from mas.session.domain.exceptions import BlueprintNotFoundError
from mas.core.identity import Identity
from mas.core.dto import GroupedCount

logger = logging.getLogger(__name__)

class SessionService:
    """
    Application use-case boundary for session lifecycle.

    Every entry point (run / stream / submit) follows the same two-phase pattern:
      1. STAGE  — project inputs onto the record and persist (via projector)
      2. EXECUTE — hydrate session and run the graph (foreground or background)
    """

    def __init__(
        self,
        manager: UserSessionManager,
        foreground_runner: ForegroundSessionRunner,
        input_projector: SessionInputProjector,
        background_engine: Optional[BackgroundSessionEngine] = None,
    ):
        self._manager = manager
        self._foreground = foreground_runner
        self._projector = input_projector
        self._engine = background_engine

    def create(
        self,
        identity: Identity,
        blueprint_id: str,
        metadata: Dict[str, Any] | SessionMeta | None = None,
        *,
        run_id: str | None = None,
    ) -> str:
        """
        Create a new session record and return its run_id.
        Lightweight — no graph compilation or blueprint resolution.

        When *run_id* is supplied the session is created with that
        deterministic key, making the call safe under activity retries.
        """
        return self._manager.create_session(
            identity=identity,
            blueprint_id=blueprint_id,
            metadata=SessionMeta.model_validate(metadata or {}),
            run_id=run_id,
        )

    # ---- Two-phase execution entry points ----

    def run(
        self,
        session_id: str,
        inputs: Dict[str, Any],
        scope: str = "public",
        stream: bool = False,
        logged_in_user: str = "",
    ) -> Any:
        """
        Execute the session graph.

        When *stream* is False, blocks until completion and returns the
        final ``GraphState``.

        When *stream* is True, returns an ``Iterator`` of channel events.
        The execution runs on a background thread; lifecycle transitions
        are handled internally by the runner.

        ``hitl_enabled`` is read from the session's metadata so nodes
        configured with ``hitl_mode: dynamic`` can check it at runtime.
        """
        self._stage(session_id, inputs, logged_in_user=logged_in_user)
        session = self._manager.get_session(session_id)
        return self._foreground.run(
            session=session,
            scope=scope,
            stream=stream,
        )

    def submit(self, session_id: str, inputs: Dict[str, Any],
               scope: str = "public", logged_in_user: str = "") -> str:
        """
        Non-blocking submit: stage inputs, then start a background workflow
        and return its handle/ID immediately (HTTP 202 pattern).

        The engine handle is persisted atomically with input staging
        (before the workflow starts), eliminating the race window where
        a cancel request could arrive before the handle is in Mongo.

        ``hitl_enabled`` is read from the session's metadata so nodes
        configured with ``hitl_mode: dynamic`` can check it at runtime.
        """
        if self._engine is None:
            raise TypeError(
                "No BackgroundSessionEngine configured — "
                "submit() is not available for this engine."
            )
        record = self._manager.get_record(session_id)
        handle = self._engine.generate_handle(session_id)
        record.update_context(engine_handle=handle)
        self._projector.apply(record, inputs or {}, logged_in_user=logged_in_user)

        session = self._manager.get_session(session_id)
        hitl = session.record.metadata.hitl_enabled
        execution_ctx = (session.run_context
                         .with_scope(scope)
                         .with_hitl(hitl))
        request = SubmitSessionRequest(execution_context=execution_ctx)
        self._engine.submit(session, request)

        return handle

    def cancel(self, session_id: str) -> bool:
        """Request cancellation of a running or queued background session.

        Only checks eligibility and delegates to the adapter.  The actual
        lifecycle transition (CANCELLED status, channel close) happens inside
        the workflow's CancelledError handler via BackgroundLifecycleHandler,
        keeping lifecycle ownership in a single place.

        Returns True if cancellation was requested, False if the session
        is not in a cancellable state or the engine call failed.
        """
        if self._engine is None:
            raise TypeError(
                "No BackgroundSessionEngine configured — "
                "cancel() is not available for this engine."
            )
        record = self._manager.get_record(session_id)
        if record.status not in (SessionStatus.QUEUED, SessionStatus.RUNNING):
            return False
        handle = record.engine_handle
        if handle is None:
            return False
        try:
            self._engine.cancel(handle)
        except Exception:
            logger.warning(
                "Failed to cancel background workflow %s for session %s",
                handle, session_id, exc_info=True,
            )
            return False
        return True

    # ---- Private staging ----

    _BUSY_STATUSES = frozenset({"QUEUED", "RUNNING"})

    def _stage(
        self,
        session_id: str,
        inputs: Dict[str, Any],
        logged_in_user: str = "",
    ) -> None:
        """Project raw inputs onto the record and persist (QUEUED).

        Clears any stale engine_handle from a previous background run
        so that cancel() won't target a dead workflow if this session
        is now being executed via the foreground run() path.

        ``hitl_enabled`` is read from the session's metadata and stamped
        into the ExecutionContext so nodes configured with
        ``hitl_mode: dynamic`` can check it at runtime.

        Raises ValueError if the session is already executing.
        """
        record = self._manager.get_record(session_id)
        record.update_context(engine_handle=None)
        if record.status.name in self._BUSY_STATUSES:
            raise ValueError(
                f"Session {session_id} is already {record.status.name} — "
                f"wait for it to finish before submitting again."
            )
        self._projector.apply(record, inputs or {}, logged_in_user=logged_in_user)
        record.run_context = record.run_context.with_hitl(record.metadata.hitl_enabled)
        self._manager.save_record(record)

    def list_for_user(self, identity: Identity) -> list:
        """
        List all sessions created by a user.
        """
        return self._manager.list_sessions_ids(identity)

    def get(self, run_id: str) -> WorkflowSession:
        """
        Fetch a fully hydrated session by its run_id.
        """
        return self._manager.get_session(run_id)

    def get_record(self, run_id: str) -> SessionRecord:
        """
        Fetch a lightweight session record (no graph build).
        """
        return self._manager.get_record(run_id)

    def get_status(self, run_id: str) -> str:
        """
        Get the status of a session by its run_id.
        """
        record = self._manager.get_record(run_id)
        return record.status.name

    def get_state(self, run_id: str) -> Dict[str, Any]:
        """
        Get the full graph state of a session by its run_id.
        """
        record = self._manager.get_record(run_id)
        return record.graph_state.model_dump(mode="json")

    def get_meta(self, run_id: str) -> SessionMeta:
        """Return the persisted metadata for a session."""
        record = self._manager.get_record(run_id)
        return record.metadata

    def update_meta(self, run_id: str, meta: SessionMeta) -> SessionMeta:
        """Whole-replace the session metadata and persist.

        The caller is expected to send the *complete* desired state so that
        whatever the GUI considers canonical is reflected atomically — no
        partial-update merge is performed.
        """
        record = self._manager.get_record(run_id)
        record.metadata = meta
        self._manager.save_record(record)
        return record.metadata

    def get_chat(self, run_id: str) -> SessionChat:
        """
        Get only messages and output for a session (lightweight, projected from DB).
        """
        return self._manager.get_chat(run_id)

    def get_runs_by_schedule(self, schedule_id: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        """Return formatted run history for a given schedule/prompt ID."""
        docs = self._manager.find_by_schedule_id(schedule_id, limit=limit)
        return [
            {
                "session_id": d.get("run_id"),
                "status": d.get("status", "UNKNOWN"),
                "started_at": d.get("run_context", {}).get("started_at"),
                "metadata": d.get("metadata", {}),
            }
            for d in docs
        ]

    def get_session_detail(self, session_id: str, identity: Identity) -> dict:
        """Combined session retrieval: status + meta + chat + blueprint name.

        Used by the ``session.get`` endpoint to serve deep-link navigation
        in a single round-trip.
        """
        record = self._manager.get_record(session_id)
        if not record.identity.owns(identity):
            raise PermissionError(
                f"Session {session_id} not owned by {identity.id}"
            )

        status = record.status.name
        meta = record.metadata
        chat = self._manager.get_chat(session_id)
        blueprint_name = self._manager.get_blueprint_name(record.blueprint_id)

        created_at = getattr(record, "created_at", None)
        completed_at = getattr(record, "completed_at", None)

        return {
            "sessionId": session_id,
            "blueprintId": record.blueprint_id,
            "blueprintName": blueprint_name,
            "status": status,
            "meta": meta.model_dump(mode="json"),
            "createdAt": created_at.isoformat() if created_at else None,
            "completedAt": completed_at.isoformat() if completed_at else None,
            "chat": chat.model_dump(mode="json"),
        }

    def list_user_sessions(self, identity: Identity) -> list:
        """
        List all sessions created by a user (metadata only, no messages).
        """
        docs = self._manager.list_docs(identity)
        items = []

        for doc in docs:
            blueprint_id = doc.get("blueprint_id", "")
            blueprint_exists = self._manager.blueprint_exists(blueprint_id) if blueprint_id else False
            bp_metadata = self._manager.get_blueprint_metadata(blueprint_id) if blueprint_exists else {}

            public_usage_scope = False
            if blueprint_exists and blueprint_id:
                source = doc.get("metadata", {}).get("source", "")
                if source == "public_link":
                    public_usage_scope = bp_metadata.get("usageScope") == "public"

            item = SessionListItem.from_doc(doc, blueprint_exists=blueprint_exists, public_usage_scope=public_usage_scope, blueprint_metadata=bp_metadata)
            items.append(item.model_dump())

        return items

    def get_user_blueprints(self, identity: Identity) -> List[str]:
        """
        Get all blueprints created by a user.
        """
        docs = self._manager.list_docs(identity)
        return list({d.get("blueprint_id") for d in docs})

    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group sessions by specified fields and return counts.
        Performs efficient server-side grouping via the session manager.
        """
        return self._manager.group_count(identity, group_by, filter)

    def count(self, identity: Identity, filter: Dict[str, Any] = None) -> int:
        """Count sessions matching filter criteria for a user."""
        return self._manager.count(identity, filter)

    def delete(self, run_id: str) -> bool:
        """
        Delete a session by run_id. Returns True if deleted, False if not found.
        """
        return self._manager.delete_session(run_id)

# ---------- System-wide methods (for admin analytics) ----------

    def count_system(self, since: Optional[datetime] = None) -> int:
        """
        Count all sessions system-wide (no user_id constraint).
        """
        return self._manager.count_system(since)

    def get_distinct_identities(self, since: Optional[datetime] = None) -> List[Dict[str, str]]:
        """Get distinct (type, id) pairs from all sessions."""
        return self._manager.get_distinct_identities(since)

    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """
        Group all sessions by specified fields and return counts (system-wide).
        No user_id constraint — for admin analytics.
        """
        return self._manager.group_count_system(group_by, since)

    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """
        Get session activity data grouped by appropriate time intervals.
        For admin analytics dashboards.
        """
        return self._manager.get_session_activity_series(since)

    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """
        Get aggregated system analytics data for admin dashboards.
        """
        return self._manager.get_system_analytics(since)
