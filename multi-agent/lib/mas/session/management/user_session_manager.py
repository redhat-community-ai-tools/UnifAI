import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional
from mas.core.platform_config import PlatformConfig
from mas.session.repository.repository import SessionRepository
from mas.session.storage.ports import SessionStorageCleaner
from mas.session.building.workflow_session_factory import WorkflowSessionFactory
from mas.session.domain.workflow_session import WorkflowSession
from mas.session.domain.session_record import SessionRecord
from mas.core.execution_context import ExecutionContext
from mas.core.dto import GroupedCount
from mas.graph.state.graph_state import GraphState
from mas.session.domain.status import SessionStatus
from mas.blueprints.service import BlueprintService
from mas.session.domain.models import SessionChat, SessionMeta, TimeSeriesPoint, SystemAnalyticsData
from mas.session.domain.dto import SessionListFilter
from mas.session.domain.constants import DEFAULT_SESSION_PAGE_SIZE
from mas.session.domain.exceptions import BlueprintNotFoundError
from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity

logger = logging.getLogger(__name__)


class UserSessionManager:
    """
    High-level CRUD for user sessions.
    SRP: only creates, loads, and lists sessions.
    """

    def __init__(
            self,
            repository: SessionRepository,
            session_factory: WorkflowSessionFactory,
            blueprint_service: BlueprintService,
            platform_config: Optional[PlatformConfig] = None,
            storage_cleaner: Optional[SessionStorageCleaner] = None,
    ):
        self._repo = repository
        self._factory = session_factory
        self._bp_service = blueprint_service
        self._platform_config = platform_config or PlatformConfig()
        self._storage_cleaner = storage_cleaner

    def blueprint_exists(self, blueprint_id: str) -> bool:
        """Check if blueprint exists without loading it."""
        return self._bp_service.exists(blueprint_id)

    def get_blueprint_metadata(self, blueprint_id: str) -> Dict[str, Any]:
        """Get blueprint metadata dict, empty dict if not found."""
        if not blueprint_id:
            return {}
        try:
            bp_doc = self._bp_service.get_blueprint_draft_doc(blueprint_id)
            return bp_doc.metadata
        except KeyError:
            return {}

    def get_blueprint_name(self, blueprint_id: str) -> str:
        """Get blueprint display name, falling back to blueprint_id if not found."""
        try:
            doc = self._bp_service.get_blueprint_draft_doc(blueprint_id)
            return doc.spec_dict.get("name", blueprint_id)
        except KeyError:
            return blueprint_id

    # ---- Create (lightweight — no graph compilation) ----

    def create_session(
            self,
            identity: Identity,
            blueprint_id: str,
            metadata: SessionMeta = None,
            *,
            run_id: str | None = None,
    ) -> str:
        """Create a session record and return its run_id.

        When *run_id* is supplied the caller is requesting idempotent
        creation (e.g. a Temporal activity retry).  The session repo
        uses ``upsert=True`` so a duplicate write for the same
        ``run_id`` harmlessly replaces the existing document.
        """
        if not self.blueprint_exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)

        session_meta = metadata or SessionMeta()
        if session_meta.source == "schedule" and not session_meta.title:
            bp_name = self.get_blueprint_name(blueprint_id)
            session_meta.title = f"{bp_name} — {datetime.utcnow().strftime('%b %d %H:%M UTC')}"
        run_id = run_id or str(uuid.uuid4())
        ctx = ExecutionContext(
            session_id=run_id,
            identity=identity,
            engine_name=self._factory.engine_name,
        )

        record = SessionRecord(
            run_id=run_id,
            identity=identity,
            blueprint_id=blueprint_id,
            run_context=ctx,
            metadata=session_meta,
            graph_state=GraphState(),
            status=SessionStatus.PENDING,
        )
        self._repo.save(record)
        return record.run_id

    # ---- Read ----

    def get_record(self, run_id: str) -> SessionRecord:
        """Lightweight fetch — returns typed SessionRecord, no graph build."""
        return self._repo.fetch(run_id)

    def save_record(self, record: SessionRecord) -> None:
        """Persist an already-loaded record (e.g. after context updates)."""
        self._repo.save(record)

    def get_chat(self, run_id: str) -> SessionChat:
        """Projected fetch — only messages and output from graph state."""
        return self._repo.fetch_chat(run_id)

    def get_session(self, run_id: str) -> WorkflowSession:
        """Full build — compiles runtime plan + executable graph from the record."""
        record = self.get_record(run_id)

        if not self.blueprint_exists(record.blueprint_id):
            raise BlueprintNotFoundError(record.blueprint_id, session_id=run_id)

        # caller.identity=record.identity ensures built-in resources resolve
        # with the session owner's configured overlay (from
        # /builtin.configure) rather than always falling back to raw
        # defaults.
        blueprint_spec = self._bp_service.load_resolved(
            record.blueprint_id, caller=CallerScope(identity=record.identity),
        )
        return self._factory.build_session(record, blueprint_spec)

    def list_sessions_ids(self, identity: Identity) -> List[str]:
        """All run_ids belonging to this user."""
        return self._repo.list_runs(identity)

    def list_docs(self, identity: Identity, filters: Optional[SessionListFilter] = None) -> List[Mapping[str, Any]]:
        """Raw documents for bulk listing (all sessions, no pagination)."""
        return self._repo.list_docs(identity, filters=filters)

    def list_docs_paginated(
        self,
        identity: Identity,
        skip: int = 0,
        limit: int = DEFAULT_SESSION_PAGE_SIZE,
        filters: Optional[SessionListFilter] = None,
    ) -> List[Mapping[str, Any]]:
        """Raw documents for bulk listing (paginated), with newest sessions first."""
        return self._repo.list_docs_paginated(identity, skip=skip, limit=limit, filters=filters)

    def find_by_schedule_id(self, schedule_id: str, *, limit: int = 20) -> List[Mapping[str, Any]]:
        """Return recent session documents triggered by a given schedule/prompt ID."""
        return self._repo.find_by_schedule_id(schedule_id, limit=limit)

    def delete_session(self, run_id: str) -> bool:
        """Delete a session by run_id. Returns True if deleted, False if not found."""
        deleted = self._repo.delete(run_id)
        if deleted:
            self._cleanup_session_storage(run_id)
        return deleted

    def _cleanup_session_storage(self, run_id: str) -> None:
        """Delegate storage cleanup to the injected adapter."""
        if self._storage_cleaner:
            self._storage_cleaner.cleanup(run_id)

    # ---------- statistics ----------

    def count(self, identity: Identity, filter: Optional[SessionListFilter] = None) -> int:
        """Count sessions matching filter criteria for a user."""
        return self._repo.count(identity, filter)

    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group sessions by specified fields and return counts.
        Performs efficient server-side grouping via the repository.
        
        Args:
            user_id: The user ID to filter by
            group_by: List of field names to group by (e.g., ["blueprint_id"])
            filter: Optional additional filter criteria
            
        Returns:
            List of GroupedCount DTOs with grouped field values and count.
        """
        return self._repo.group_count(identity, group_by, filter)

# ---------- Statistics (system-wide for admin analytics) ----------

    def count_system(self, since: Optional[datetime] = None) -> int:
        """Count all sessions system-wide (no user_id constraint)."""
        return self._repo.count_system(since)

    def get_distinct_identities(self, since: Optional[datetime] = None) -> List[Dict[str, str]]:
        """Get distinct (type, id) pairs from all sessions."""
        return self._repo.get_distinct_identities(since)

    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """Group all sessions by specified fields and return counts (system-wide)."""
        return self._repo.group_count_system(group_by, since)

    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """Get session activity data grouped by appropriate time intervals."""
        return self._repo.get_session_activity_series(since)

    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """Get aggregated system analytics data for admin dashboards."""
        return self._repo.get_system_analytics(since)