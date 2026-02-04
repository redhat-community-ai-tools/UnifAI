"""MongoDB adapter for PipelineRepository port."""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pymongo.collection import Collection

from core.pipeline.domain.model import PipelineRecord, PipelineStatus
from core.pipeline.domain.repository import PipelineRepository
from shared.logger import logger


class MongoPipelineRepository(PipelineRepository):
    """MongoDB implementation of the PipelineRepository port."""

    def __init__(self, collection: Collection):
        self._col = collection

    def find_by_id(self, pipeline_id: str) -> Optional[PipelineRecord]:
        """Get pipeline record by ID."""
        doc = self._col.find_one({"pipeline_id": pipeline_id})
        return self._to_model(doc) if doc else None

    def save(self, record: PipelineRecord) -> None:
        """Insert or update pipeline record (upsert by pipeline_id)."""
        doc = self._to_document(record)
        self._col.update_one(
            {"pipeline_id": record.pipeline_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": record.created_at}
            },
            upsert=True,
        )

    def update_status(self, pipeline_id: str, status: PipelineStatus) -> bool:
        """Update pipeline status. Returns True if updated."""
        now = datetime.utcnow()
        update_fields: Dict[str, Any] = {
            "status": status.value,
            "last_updated": now,
        }

        # Calculate processing time when done
        if status == PipelineStatus.DONE:
            doc = self._col.find_one({"pipeline_id": pipeline_id})
            if doc:
                created_at = doc.get("created_at", now)
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                processing_time = (now - created_at).total_seconds()
                update_fields["stats.processing_time"] = processing_time

        result = self._col.update_one(
            {"pipeline_id": pipeline_id},
            {"$set": update_fields}
        )
        return result.modified_count > 0

    def get_stats_batch(self, pipeline_ids: List[str]) -> Dict[str, PipelineRecord]:
        """Batch fetch pipeline records for enrichment."""
        if not pipeline_ids:
            return {}

        docs = self._col.find(
            {"pipeline_id": {"$in": pipeline_ids}},
            {"pipeline_id": 1, "status": 1, "stats": 1, "source_type": 1,
             "created_at": 1, "last_updated": 1, "metadata": 1}
        )

        return {doc["pipeline_id"]: self._to_model(doc) for doc in docs}

    def delete(self, pipeline_id: str) -> int:
        """Delete pipeline(s). Returns count deleted."""
        try:
            # Support regex for related pipelines (e.g., sub-pipelines)
            result = self._col.delete_many({"pipeline_id": {"$regex": f"^{pipeline_id}"}})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting pipeline {pipeline_id}: {e}")
            return 0

    def increment_stats(self, pipeline_id: str, stats_updates: Dict[str, Any]) -> bool:
        """Increment pipeline statistics atomically using $inc."""
        if not stats_updates:
            return True

        inc_fields = {f"stats.{k}": v for k, v in stats_updates.items()}
        inc_fields["last_updated"] = datetime.utcnow()

        result = self._col.update_one(
            {"pipeline_id": pipeline_id},
            {
                "$inc": {k: v for k, v in inc_fields.items() if k != "last_updated"},
                "$set": {"last_updated": inc_fields["last_updated"]},
            }
        )
        return result.modified_count > 0

    def get_source_stats(self, source_type: str) -> Dict[str, Any]:
        """Get aggregated statistics for a specific source type."""
        pipeline = [
            {"$match": {"source_type": source_type}},
            {"$group": {
                "_id": "$source_type",
                "total_pipelines": {"$sum": 1},
                "active_pipelines": {"$sum": {"$cond": [{"$eq": ["$status", PipelineStatus.ACTIVE.value]}, 1, 0]}},
                "completed_pipelines": {"$sum": {"$cond": [{"$eq": ["$status", PipelineStatus.DONE.value]}, 1, 0]}},
                "failed_pipelines": {"$sum": {"$cond": [{"$eq": ["$status", PipelineStatus.FAILED.value]}, 1, 0]}},
                "pending_pipelines": {"$sum": {"$cond": [{"$eq": ["$status", PipelineStatus.PENDING.value]}, 1, 0]}},
                "latest_update": {"$max": "$last_updated"}
            }}
        ]
        
        result = list(self._col.aggregate(pipeline))
        if result:
            stats = result[0]
            stats.pop("_id", None)
            return stats
        
        return {
            "total_pipelines": 0,
            "active_pipelines": 0,
            "completed_pipelines": 0,
            "failed_pipelines": 0,
            "pending_pipelines": 0,
            "latest_update": None
        }

    # --- Mapping methods ---
    def _to_model(self, doc: Dict[str, Any]) -> PipelineRecord:
        """Convert MongoDB document to domain model."""
        return PipelineRecord.from_dict(doc)

    def _to_document(self, record: PipelineRecord) -> Dict[str, Any]:
        """Convert domain model to MongoDB document."""
        doc = record.to_dict()
        doc.pop("created_at", None)  # Handled separately in upsert
        return doc
