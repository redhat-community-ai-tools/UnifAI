from typing import Dict, List, Any, Optional
from pymongo.collection import Collection
from shared.logger import logger
from datetime import datetime, timezone

class PipelinesRepository:
    """Repository for managing pipeline documents in MongoDB."""
    
    def __init__(self, col: Collection):
        self.col = col

    def get_stats(self, pipeline_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive pipeline statistics for given pipeline IDs."""
        if not pipeline_ids:
            return {}

        elements = self.col.find(
            {"pipeline_id": {"$in": pipeline_ids}},
            {"pipeline_id": 1, "status": 1, "stats": 1}
        )

        result = {}
        for element in elements:
            pid = element["pipeline_id"]
            stats = element.get("stats", {}) or {}
            result[pid] = {
                "status": element.get("status"),
                "documents_retrieved": stats.get("documents_retrieved", 0),
                "chunks_generated": stats.get("chunks_generated", 0),
                "embeddings_created": stats.get("embeddings_created", 0),
                "api_calls": stats.get("api_calls", 0),
                "processing_time": stats.get("processing_time", 0.0)
            }
        return result

    def delete(self, filter_query: Dict[str, Any]) -> Dict[str, Any]:
        """Generic delete for pipelines by arbitrary filter or pattern."""
        try:
            result = self.col.delete_many(filter_query or {})
            return {"success": True, "pipelines_deleted": result.deleted_count}
        except Exception as e:
            logger.error(f"Error deleting pipelines with filter {filter_query}: {e}")
            return {"success": False, "error": str(e)} 

    def get_status(self, pipeline_id: str) -> Optional[str]:
        """Get the current status for a pipeline by id."""
        doc = self.col.find_one({"pipeline_id": pipeline_id}, {"status": 1, "_id": 0})
        return None if not doc else doc.get("status")

    def update_status(self, pipeline_id: str, new_status: str) -> bool:
        """Update status and last_updated for a pipeline."""
        now = datetime.now(timezone.utc)
        result = self.col.update_one(
            {"pipeline_id": pipeline_id},
            {"$set": {"status": new_status, "last_updated": now}}
        )
        return result.modified_count > 0

    def update(self, filter_query: Dict[str, Any], update_ops: Any, many: bool = False, upsert: bool = False) -> Dict[str, Any]:
        """Generic update for pipelines."""
        try:
            if many:
                result = self.col.update_many(filter_query or {}, update_ops, upsert=upsert)
            else:
                result = self.col.update_one(filter_query or {}, update_ops, upsert=upsert)
            return {
                "success": True,
                "matched": result.matched_count if hasattr(result, "matched_count") else None,
                "modified": result.modified_count if hasattr(result, "modified_count") else None,
                "upserted_id": getattr(result, "upserted_id", None)
            }
        except Exception as e:
            logger.error(f"Error updating pipelines with filter {filter_query}: {e}")
            return {"success": False, "error": str(e)}