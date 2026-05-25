import pymongo
from pymongo.collection import Collection
from typing import List, Mapping, Any, Dict, Optional
from datetime import datetime, timezone, timedelta
import logging

from mas.session.repository.repository import SessionRepository
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.models import SessionChat, TimeSeriesPoint, SystemAnalyticsData
from mas.blueprints.models.blueprint import BlueprintExecutionStats
from mas.session.domain.status import SessionStatus
from mas.core.identity import Identity
from mas.core.dto import GroupedCount
from global_utils.utils.time_utils import format_utc_iso
from outbound.mongo.helpers import identity_q

logger = logging.getLogger(__name__)


class MongoSessionRepository(SessionRepository):
    """
    MongoDB-backed SessionRepository.

    Queries owner-scoped data by both ``identity.type`` and ``identity.id``
    so that user-owned and team-owned sessions are properly isolated.
    """

    _IDENTITY_TYPE_FIELD = "identity.type"
    _IDENTITY_ID_FIELD = "identity.id"
    _TIME_FIELD = "run_context.started_at"
    _STATUS_FIELD = "status"
    _BLUEPRINT_FIELD = "blueprint_id"
    _RUN_ID_FIELD = "run_id"
    _OWNER_ALIAS = "owner_id"
    _MAX_TIME_SERIES_POINTS = 1000

    def __init__(
            self,
            mongodb_port: str = "27017",
            mongodb_ip: str = "localhost",
            db_name: str = "UnifAI",
            collection_name: str = "workflow_sessions",
    ):
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        client = pymongo.MongoClient(mongo_uri)
        db = client[db_name]
        self._col: Collection = db[collection_name]
        self._ensure_indexes()

    # ---------- Index Management ----------

    def _ensure_indexes(self) -> None:
        """Create indexes for all query patterns. Safe to call multiple times."""
        self._col.create_index(
            [
                (self._IDENTITY_TYPE_FIELD, pymongo.ASCENDING),
                (self._IDENTITY_ID_FIELD, pymongo.ASCENDING),
                (self._RUN_ID_FIELD, pymongo.ASCENDING),
            ],
            unique=True,
            background=True,
        )

        self._col.create_index(
            [(self._RUN_ID_FIELD, pymongo.ASCENDING)],
            unique=True,
            background=True,
            name="uq_session_run_id",
        )

        self._col.create_index(
            [(self._TIME_FIELD, pymongo.DESCENDING)],
            background=True,
        )

        self._col.create_index(
            [
                (self._IDENTITY_TYPE_FIELD, pymongo.ASCENDING),
                (self._IDENTITY_ID_FIELD, pymongo.ASCENDING),
                (self._TIME_FIELD, pymongo.DESCENDING),
            ],
            background=True,
        )

    # ---------- Core CRUD Operations ----------

    def save(self, record: SessionRecord) -> None:
        doc = record.model_dump(mode="json")
        self._col.replace_one(
            {
                self._IDENTITY_TYPE_FIELD: record.identity.type.value,
                self._IDENTITY_ID_FIELD: record.identity.id,
                self._RUN_ID_FIELD: record.run_id,
            },
            doc,
            upsert=True,
        )

    def fetch(self, run_id: str) -> SessionRecord:
        doc = self._col.find_one({self._RUN_ID_FIELD: run_id}, {"_id": 0})
        if not doc:
            raise KeyError(f"No session for {run_id}")
        return SessionRecord.model_validate(doc)

    def fetch_chat(self, run_id: str) -> SessionChat:
        doc = self._col.find_one(
            {self._RUN_ID_FIELD: run_id},
            {"_id": 0, "graph_state.messages": 1, "graph_state.output": 1,
             "status": 1, "metadata.status_message": 1},
        )
        if not doc:
            raise KeyError(f"No session for {run_id}")
        gs = doc.get("graph_state", {})
        gs["status"] = doc.get("status")
        gs["status_message"] = doc.get("metadata", {}).get("status_message")
        return SessionChat.model_validate(gs)

    def list_runs(self, identity: Identity) -> List[str]:
        cursor = self._col.find(
            identity_q(identity),
            {self._RUN_ID_FIELD: 1, "_id": 0},
        )
        return [d[self._RUN_ID_FIELD] for d in cursor]

    def list_docs(self, identity: Identity) -> List[Mapping[str, Any]]:
        """Return all session documents for a user in a single query."""
        return list(self._col.find(identity_q(identity), {"_id": 0}))

    def delete(self, run_id: str) -> bool:
        """Delete a session by run_id. Returns True if deleted, False if not found."""
        result = self._col.delete_one({self._RUN_ID_FIELD: run_id})
        return result.deleted_count > 0

    def delete_by_identity(self, identity: Identity) -> int:
        """Delete all sessions owned by the given identity. Returns count."""
        result = self._col.delete_many(identity_q(identity))
        return result.deleted_count

    # ---------- Owner-scoped Statistics ----------

    def count(self, identity: Identity, filter: Dict[str, Any]) -> int:
        # Identity keys must not be overridden by caller-supplied filter.
        query = {**filter, **identity_q(identity)}
        return self._col.count_documents(query)

    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group documents by specified fields and return counts.
        Uses MongoDB aggregation for efficient server-side grouping.

        Args:
            user_id: The user ID to filter by
            group_by: List of field names to group by
            filter: Optional additional filter criteria

        Returns:
            List of GroupedCount DTOs with grouped field values and count.
        """
        match = {**(filter or {}), **identity_q(identity)}
        return self._aggregate_group_count(match, group_by)

    # ---------- System-wide Statistics (for admin analytics) ----------

    def count_system(self, since: Optional[datetime] = None) -> int:
        """Count all sessions system-wide, optionally filtered by time."""
        return self._col.count_documents(self._time_match(since))

    def get_distinct_identities(self, since: Optional[datetime] = None) -> List[Dict[str, str]]:
        """Get distinct (type, id) pairs, optionally filtered by time."""
        pipeline = [
            {"$match": self._time_match(since)},
            {"$group": {
                "_id": {
                    "type": f"${self._IDENTITY_TYPE_FIELD}",
                    "id": f"${self._IDENTITY_ID_FIELD}",
                },
            }},
        ]
        return [doc["_id"] for doc in self._col.aggregate(pipeline)]

    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """Group all sessions by specified fields and return counts (system-wide)."""
        return self._aggregate_group_count(self._time_match(since), group_by)

    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """
        Get session activity data grouped by appropriate time intervals.

        Automatically determines granularity:
        - Less than 1 day -> hourly
        - 1 to 30 days -> daily
        - Over 30 days or all time -> monthly
        """
        now = datetime.now(timezone.utc)
        truncate_unit = self._determine_granularity(since, now)

        pipeline = [
            {"$match": self._time_match(since, require_exists=True)},
            {"$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": {"$dateFromString": {"dateString": f"${self._TIME_FIELD}"}},
                        "unit": truncate_unit
                    }
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}},
            {"$limit": self._MAX_TIME_SERIES_POINTS}
        ]

        try:
            return [
                TimeSeriesPoint(period=doc["_id"], count=doc["count"])
                for doc in self._col.aggregate(pipeline, allowDiskUse=True)
            ]
        except Exception as e:
            logger.warning(f"Failed to get session activity series: {e}")
            return []

    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """
        Get aggregated system analytics using MongoDB $facet.

        Optimizations:
        - Pre-filters by time BEFORE $facet (single collection scan)
        - 3 facets computed in parallel (user+status, user+blueprint, blueprint_stats)
        - Uses allowDiskUse for large datasets
        """
        pipeline = [
            {"$match": self._time_match(since)},
            {"$facet": {
                "user_status": self._owner_status_facet(),
                "user_blueprint": self._owner_blueprint_facet(),
                "blueprint_stats": self._blueprint_stats_facet(),
            }}
        ]

        try:
            results = list(self._col.aggregate(pipeline, allowDiskUse=True))
            if not results:
                return SystemAnalyticsData()

            facet = results[0]

            return SystemAnalyticsData(
                user_status_counts=self._to_grouped_counts(facet.get("user_status", [])),
                user_blueprint_counts=self._to_grouped_counts(facet.get("user_blueprint", [])),
                blueprint_stats=self._to_blueprint_stats(facet.get("blueprint_stats", [])),
            )
        except Exception as e:
            logger.warning(f"Failed to get system analytics: {e}")
            return SystemAnalyticsData()

    # ---------- Facet Definitions ----------

    def _owner_status_facet(self) -> list:
        """Group sessions by identity (type+id) and status."""
        return [
            {"$group": {
                "_id": {
                    self._IDENTITY_TYPE_FIELD: f"${self._IDENTITY_TYPE_FIELD}",
                    self._IDENTITY_ID_FIELD: f"${self._IDENTITY_ID_FIELD}",
                    self._STATUS_FIELD: f"${self._STATUS_FIELD}"
                },
                "count": {"$sum": 1}
            }}
        ]

    def _owner_blueprint_facet(self) -> list:
        """Group sessions by identity (type+id) and blueprint."""
        return [
            {"$group": {
                "_id": {
                    self._IDENTITY_TYPE_FIELD: f"${self._IDENTITY_TYPE_FIELD}",
                    self._IDENTITY_ID_FIELD: f"${self._IDENTITY_ID_FIELD}",
                    self._BLUEPRINT_FIELD: f"${self._BLUEPRINT_FIELD}"
                },
                "count": {"$sum": 1}
            }}
        ]

    def _blueprint_stats_facet(self) -> list:
        """Aggregate execution metrics per blueprint."""
        return [
            {"$group": {
                "_id": f"${self._BLUEPRINT_FIELD}",
                "total_runs": {"$sum": 1},
                "completed_runs": {
                    "$sum": {
                        "$cond": [
                            {"$eq": [f"${self._STATUS_FIELD}", SessionStatus.COMPLETED.value]},
                            1,
                            0
                        ]
                    }
                },
                "failed_runs": {
                    "$sum": {
                        "$cond": [
                            {"$eq": [f"${self._STATUS_FIELD}", SessionStatus.FAILED.value]},
                            1,
                            0
                        ]
                    }
                },
                "last_run": {"$max": f"${self._TIME_FIELD}"},
                "avg_duration_ms": {
                    "$avg": {
                        "$cond": [
                            {"$and": [
                                {"$ne": ["$run_context.finished_at", None]},
                                {"$ne": ["$run_context.finished_at", ""]},
                                {"$ne": [f"${self._TIME_FIELD}", None]},
                                {"$ne": [f"${self._TIME_FIELD}", ""]},
                            ]},
                            {"$subtract": [
                                {"$dateFromString": {"dateString": "$run_context.finished_at"}},
                                {"$dateFromString": {"dateString": f"${self._TIME_FIELD}"}}
                            ]},
                            None
                        ]
                    }
                },
                "users": {
                    "$addToSet": {
                        "$concat": [
                            f"${self._IDENTITY_TYPE_FIELD}",
                            ":",
                            f"${self._IDENTITY_ID_FIELD}",
                        ]
                    }
                }
            }}
        ]

    @staticmethod
    def _to_blueprint_stats(docs: List[Dict]) -> List[BlueprintExecutionStats]:
        """Transform blueprint_stats facet results to typed domain models."""
        return [
            BlueprintExecutionStats(
                blueprint_id=doc["_id"],
                total_runs=doc.get("total_runs", 0),
                completed_runs=doc.get("completed_runs", 0),
                failed_runs=doc.get("failed_runs", 0),
                last_run=doc.get("last_run"),
                avg_duration_ms=doc.get("avg_duration_ms"),
                users=doc.get("users", [])
            )
            for doc in docs
        ]

    # ---------- Private Helpers ----------

    def _time_match(
        self,
        since: Optional[datetime],
        require_exists: bool = False
    ) -> Dict[str, Any]:
        """
        Build a MongoDB match filter for time-based queries.

        Args:
            since: Cutoff datetime (None = no time filter)
            require_exists: If True, also require the time field to exist
                            (needed for $dateFromString in time series)
        """
        if since is None:
            return {self._TIME_FIELD: {"$exists": True}} if require_exists else {}

        cutoff = format_utc_iso(since)
        return {self._TIME_FIELD: {"$gte": cutoff}}

    def _aggregate_group_count(
        self,
        match: Dict[str, Any],
        group_by: List[str]
    ) -> List[GroupedCount]:
        """Shared aggregation logic for both user-scoped and system-wide grouping."""
        group_id = {}
        for field in group_by:
            if field in (self._OWNER_ALIAS, "user_id"):
                # Disambiguate user vs team when ids collide (same as analytics facets).
                group_id[self._OWNER_ALIAS] = f"${self._IDENTITY_ID_FIELD}"
                group_id[self._IDENTITY_TYPE_FIELD] = f"${self._IDENTITY_TYPE_FIELD}"
            else:
                group_id[field] = f"${field}"

        pipeline = [
            {"$match": match},
            {"$group": {"_id": group_id, "count": {"$sum": 1}}}
        ]

        return self._to_grouped_counts(
            list(self._col.aggregate(pipeline, allowDiskUse=True))
        )

    @staticmethod
    def _determine_granularity(since: Optional[datetime], now: datetime) -> str:
        """
        Determine the $dateTrunc unit for time series grouping.

        Returns appropriate granularity:
        - Hourly for < 1 day
        - Daily for 1-30 days
        - Monthly for > 30 days or all-time
        """
        if since is None:
            return "month"

        delta = now - since
        if delta < timedelta(days=1):
            return "hour"
        if delta <= timedelta(days=30):
            return "day"
        return "month"

    @staticmethod
    def _to_grouped_counts(docs: List[Dict]) -> List[GroupedCount]:
        """Transform MongoDB aggregation results to GroupedCount DTOs."""
        return [GroupedCount(fields=doc["_id"], count=doc["count"]) for doc in docs]
