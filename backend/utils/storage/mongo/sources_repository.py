import re
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

    def get_paginated(
        self,
        field_path: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
        search_regex: Optional[str] = None,
        match_filter: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: int = -1,
    ) -> Dict[str, Any]:
        """
        Generic paginated query for any field or full documents.
        
        Args:
            field_path: Dot-notation path to field (e.g. "tags", "metadata.category"). 
                        None returns full documents.
            cursor: Pagination cursor (skip count as string)
            limit: Number of items to return
            search_regex: Regex pattern to filter results
            match_filter: Additional match conditions (e.g. {"source_type": "DOCUMENT"})
            sort_by: Field to sort by (defaults to "_id" for fields, "created_at" for docs)
            sort_order: 1 for ascending, -1 for descending
            
        Returns:
            {"data": [...], "nextCursor": str|None, "hasMore": bool, "total": int}
        """
        skip = int(cursor) if cursor and cursor.isdigit() else 0
        pipeline = []
        
        start_anchored = f"^{re.escape(search_regex)}" if search_regex else None
        
        # Base match filter
        if match_filter:
            pipeline.append({"$match": match_filter})
        
        if field_path:
            # DISTINCT VALUES MODE - extract unique values from a field
            pipeline.append({"$unwind": f"${field_path}"})
            
            if start_anchored:
                pipeline.append({"$match": {field_path: {"$regex": start_anchored, "$options": "i"}}})
            else:
                pipeline.append({"$match": {field_path: {"$exists": True, "$ne": None, "$ne": ""}}})
            
            pipeline.append({"$group": {"_id": f"${field_path}"}})
            pipeline.append({"$sort": {"_id": sort_order if sort_order else 1}})
        else:
            # FULL DOCUMENTS MODE
            if start_anchored:
                pipeline.append({"$match": {"source_name": {"$regex": start_anchored, "$options": "i"}}})
            
            sort_field = sort_by or "created_at"
            pipeline.append({"$sort": {sort_field: sort_order}})
        
        # Build data pipeline stages
        data_pipeline = [{"$skip": skip}, {"$limit": limit}]
        
        # Facet for pagination
        pipeline.append({
            "$facet": {
                "metadata": [{"$count": "total"}],
                "data": data_pipeline
            }
        })
        
        try:
            result = list(self.col.aggregate(pipeline))
            
            total = 0
            items = []
            
            if result and result[0]:
                facet = result[0]
                if facet.get("metadata"):
                    total = facet["metadata"][0]["total"]
                
                if field_path:
                    items = [item["_id"] for item in facet.get("data", [])]
                else:
                    items = facet.get("data", [])
            
            next_cursor = str(skip + len(items)) if (skip + len(items)) < total else None
            
            return {
                "data": items,
                "nextCursor": next_cursor,
                "hasMore": next_cursor is not None,
                "total": total
            }
        except Exception as e:
            logger.error(f"Error in paginated query (field={field_path}): {e}")
            return {"data": [], "nextCursor": None, "hasMore": False, "total": 0}

    def upsert_summary(self, source_id: str, source_name: str, source_type: str,
                       upload_by: str, pipeline_id: str, type_data: Optional[Dict[str, Any]] = None, tags: List[str] = None):
        """Create or update a source summary."""
        now = datetime.utcnow()
        update = {"last_sync_at": now, "tags": tags if tags is not None else []}
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

    def update(self, source_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a source by ID with provided fields."""
        try:
            result = self.col.update_one(
                {"source_id": source_id},
                {"$set": updates}
            )
            if result.matched_count == 0:
                return {"success": False, "message": f"Source {source_id} not found"}
            return {"success": True, "modified": result.modified_count > 0}
        except Exception as e:
            logger.error(f"Error updating source {source_id}: {e}")
            return {"success": False, "error": str(e)} 