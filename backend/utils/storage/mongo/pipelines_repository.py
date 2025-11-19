from typing import Dict, List, Any
from pymongo.collection import Collection
from shared.logger import logger

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

    def delete(self, pipeline_id: str) -> Dict[str, Any]:
        """Delete pipeline documents by ID (supports regex for related pipelines)."""
        try:
            result = self.col.delete_many({"pipeline_id": {"$regex": f"^{pipeline_id}"}})
            return {
                "success": True,
                "pipelines_deleted": result.deleted_count
            }
        except Exception as e:
            logger.error(f"Error deleting pipeline {pipeline_id}: {e}")
            return {"success": False, "error": str(e)} 