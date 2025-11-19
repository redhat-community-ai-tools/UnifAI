from typing import Optional, Dict, List, Any
from pymongo.collection import Collection
from datetime import datetime
from .utils import make_json_safe
from shared.logger import logger

class SourcesRepository:
    """Repository for managing source documents in MongoDB."""
    
    def __init__(self, col: Collection):
        self.col = col

    def get_all(self, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all sources, optionally filtered by type."""
        query = {"source_type": source_type.upper()} if source_type else {}
        return list(self.col.find(query))

    def get_by_query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get sources by custom query."""
        return list(self.col.find(query, {"_id": 0}))

    def get_info(self, source_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific source."""
        try:
            doc = self.col.find_one({"source_id": source_id})
            if not doc:
                return {"success": False, "message": f"Source {source_id} not found"}
            return {
                "success": True,
                "source_name": doc.get("source_name", "Unknown"),
                "source_type": doc.get("source_type", "Unknown"),
                "source_info": make_json_safe(doc)
            }
        except Exception as e:
            logger.error(f"Error fetching source {source_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_info_by_pipeline_id(self, pipeline_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific source by pipeline_id."""
        try:
            doc = self.col.find_one({"pipeline_id": pipeline_id})
            if not doc:
                return {"success": False, "message": f"Source with pipeline_id {pipeline_id} not found"}
            return {
                "success": True,
                "source_name": doc.get("source_name", "Unknown"),
                "source_type": doc.get("source_type", "Unknown"),
                "source_id": doc.get("source_id"),
                "source_info": make_json_safe(doc)
            }
        except Exception as e:
            logger.error(f"Error fetching source by pipeline_id {pipeline_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_info_by_source_id(self, source_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific source by source_id."""
        try:
            doc = self.col.find_one({"source_id": source_id})
            if not doc:
                return {"success": False, "message": f"Source with source_id {source_id} not found"}
            return {
                "success": True,
                "source_name": doc.get("source_name", "Unknown"),
                "source_type": doc.get("source_type", "Unknown"),
                "source_id": doc.get("source_id"),
                "source_info": make_json_safe(doc),
                "pipeline_id": doc.get("pipeline_id")
            }
        except Exception as e:
            logger.error(f"Error fetching source by source_id {source_id}: {e}")
            return {"success": False, "error": str(e)}   

    def upsert_summary(self, source_id: str, source_name: str, source_type: str,
                       upload_by: str, pipeline_id: str, type_data: Optional[Dict[str, Any]] = None):
        """Create or update a source summary."""
        now = datetime.utcnow()
        update = {"last_sync_at": now}
        if type_data:
            update["type_data"] = type_data

        self.col.update_one(
            {"pipeline_id": pipeline_id},
            {
                "$set": update,
                "$setOnInsert": {
                    "source_id": source_id,
                    "source_name": source_name,
                    "source_type": source_type,
                    "upload_by": upload_by,
                    "pipeline_id": pipeline_id,
                    "created_at": now
                }
            },
            upsert=True
        )

    def delete(self, source_id: str) -> Dict[str, Any]:
        """Delete a source by ID."""
        try:
            result = self.col.delete_one({"source_id": source_id})
            return {
                "success": True,
                "source_deleted": result.deleted_count > 0,
                "documents_deleted": result.deleted_count
            }
        except Exception as e:
            logger.error(f"Error deleting source {source_id}: {e}")
            return {"success": False, "error": str(e)} 