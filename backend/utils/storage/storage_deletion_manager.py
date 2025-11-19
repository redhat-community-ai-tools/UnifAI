from typing import List, Dict, Any, Optional
from .vector_storage import VectorStorage
from utils.storage.mongo.mongo_storage import MongoStorage 
from shared.logger import logger

class SourceDeletionManager:
    def __init__(self, vector_storage: VectorStorage, mstore: MongoStorage):
        self.vector_storage = vector_storage
        self.mstore = mstore

    def _get_source_info(self, source_id: str) -> Dict[str, Any]:
        """Get source information before deletion."""
        try:
            return self.mstore.get_source_info(source_id)
        except Exception as e:
            logger.warning(f"Could not retrieve source info for {source_id}: {e}")
            return {}

    def _delete_from_vector_storage(self, source_id: str, source_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete source from vector storage.
        Returns:
            Dictionary with deletion results from vector storage
        """
        logger.info(f"Step 1: Deleting from vector storage - source {source_id}")
        try:
            return self.vector_storage.delete_source(source_id, source_type)
        except Exception as e:
            logger.error(f"Vector storage deletion failed for source {source_id}: {e}")
            return {"success": False, "error": str(e), "embeddings_deleted": 0}

    def _delete_from_mongodb(self, source_id: str) -> Dict[str, Any]:
        """
        Delete source from MongoDB storage.
        
        Returns:
            Dictionary with deletion results from MongoDB
        """
        logger.info(f"Step 2: Deleting from MongoDB - source {source_id}")
        try:
            return self.mstore.sources.delete(source_id)
        except Exception as e:
            logger.error(f"MongoDB deletion failed for source {source_id}: {e}")
            return {"success": False, "error": str(e), "source_deleted": False}

    def _delete_related_pipelines(self, source_id: str, source_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete related pipelines for the source.
        
        Returns:
            Dictionary with pipeline deletion results
        """
        pipeline_prefix = f"{source_type.lower()}_{source_id}" if source_type else source_id
        logger.info(f"Step 3: Pipeline cleanup for source {source_id}")
        try:
            return self.mstore.pipelines.delete(pipeline_prefix)
        except Exception as e:
            logger.error(f"Pipeline deletion failed for source {source_id}: {e}")
            return {"success": False, "error": str(e), "pipelines_deleted": 0}

    def _build_failure_result(self, source_id: str, source_name: str, source_type: Optional[str], 
                             qdrant_result: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """Build result dictionary for failed deletion scenarios."""
        return {
            "source_id": source_id,
            "source_name": source_name,
            "success": False,
            "error": reason,
            "embeddings_deleted": qdrant_result.get("embeddings_deleted", 0)
        }

    def _build_success_result(self, source_id: str, source_name: str, source_type: Optional[str],
                             qdrant_result: Dict[str, Any], mongo_result: Dict[str, Any], 
                             pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build result dictionary for successful deletion scenarios."""
        overall_success = (
            qdrant_result.get("success", False) and 
            mongo_result.get("success", False) and 
            pipeline_result.get("success", False)
        )
        
        # Check for inconsistent state
        if qdrant_result.get("success", False) and not mongo_result.get("success", False):
            logger.warning(f"Inconsistent state detected: vector storage deletion succeeded but MongoDB deletion failed for source {source_id}")
        
        result = {
            "source_id": source_id,
            "source_name": source_name,
            "success": overall_success,
            "embeddings_deleted": qdrant_result.get("embeddings_deleted", 0),
            "pipelines_deleted": pipeline_result.get("pipelines_deleted", 0)
        }
        
        if overall_success:
            logger.info(f"✅ Successfully deleted source {source_name} ({source_id}) from all systems")
        else:
            logger.warning(f"⚠️  Partial deletion of source {source_name} ({source_id})")
            result["error"] = "Partial deletion - some components failed"
        
        return result

    def delete_source(self, source_id: str, source_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a source from both vector storage and MongoDB storage with transaction-like behavior.
        
        Args:
            source_id: The ID of the source to delete
            source_type: Optional source type for filtering
            
        Returns:
            Dictionary with comprehensive deletion results
        """ 
        try:
            # Get source info before deletion
            source_info = self._get_source_info(source_id)
            source_name = source_info.get("source_name", "Unknown")
            actual_source_type = source_info.get("source_type", source_type)
            
            # Step 1: Delete from vector storage first (critical step)
            qdrant_result = self._delete_from_vector_storage(source_id, actual_source_type)
            
            # Check if vector storage deletion was successful
            if not qdrant_result.get("success", False):
                logger.error(f"Vector storage deletion failed for source {source_id}. Aborting MongoDB deletion to maintain consistency.")
                return self._build_failure_result(source_id, source_name, actual_source_type, 
                                                 qdrant_result, "Vector storage deletion failed")
            
            # Step 2: Delete from MongoDB (only if Qdrant succeeded)
            mongo_result = self._delete_from_mongodb(source_id)
            
            # Step 3: Delete related pipelines (continue even if MongoDB fails for cleanup)
            pipeline_result = self._delete_related_pipelines(source_id, actual_source_type)
            
            # Build and return comprehensive result
            return self._build_success_result(source_id, source_name, actual_source_type,
                                            qdrant_result, mongo_result, pipeline_result)
            
        except Exception as e:
            logger.error(f"❌ Failed to delete source {source_id}: {e}")
            return {
                "source_id": source_id,
                "source_name": "Unknown",
                "success": False,
                "error": str(e),
                "embeddings_deleted": 0
            }
