from datetime import datetime
from typing import Dict, List, Optional
from config.constants import PipelineStatus, SourceType


class MongoDBPipelineRepository:
    """
    MongoDB-based repository for pipeline monitoring data.
    
    This class handles interaction with MongoDB for storing and retrieving
    pipeline monitoring information.
    """
    
    def __init__(self, mongo_client, database_name: str = "pipeline_monitoring"):
        """
        Initialize the MongoDB pipeline repository.
        
        Args:
            mongo_client: MongoDB client instance
            database_name: Name of the MongoDB database to use
        """
        self.client = mongo_client
        self.db = self.client[database_name]
        self.pipelines = self.db.pipelines
        self.metrics = self.db.metrics
        self.errors = self.db.errors
        self.logs = self.db.logs
        
        # Ensure indexes for performance
        self.pipelines.create_index("pipeline_id", unique=True)
        self.metrics.create_index("pipeline_id")
        self.errors.create_index("pipeline_id")
        self.logs.create_index([("source_type", 1), ("timestamp", -1)])
    
    def save_pipeline(self, pipeline_data: Dict) -> None:
        """
        Save or update pipeline information.
        
        Args:
            pipeline_data: Dictionary containing pipeline information
        """
        self.pipelines.update_one(
            {"pipeline_id": pipeline_data["pipeline_id"]},
            {"$set": pipeline_data},
            upsert=True
        )
    
    def save_metrics(self, metrics_data: Dict) -> None:
        """
        Save pipeline metrics.
        
        Args:
            metrics_data: Dictionary containing pipeline metrics
        """
        metrics_data["timestamp"] = datetime.now()
        self.metrics.insert_one(metrics_data)
    
    def save_error(self, error_data: Dict) -> None:
        """
        Save pipeline error information.
        
        Args:
            error_data: Dictionary containing error information
        """
        error_data["timestamp"] = datetime.now()
        self.errors.insert_one(error_data)
    
    def save_log_entry(self, log_data: Dict) -> None:
        """
        Save a log entry.
        
        Args:
            log_data: Dictionary containing log information
        """
        self.logs.insert_one(log_data)
    
    def get_pipeline(self, pipeline_id: str) -> Optional[Dict]:
        """
        Get pipeline information by ID.
        
        Args:
            pipeline_id: The ID of the pipeline to retrieve
            
        Returns:
            Pipeline information or None if not found
        """
        return self.pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": 0})
    
    def get_pipelines_by_status(self, status: PipelineStatus, source_type: Optional[SourceType] = None) -> List[Dict]:
        """
        Get pipelines by status and optionally by source type.
        
        Args:
            status: The status to filter by
            source_type: Optional source type to filter by
            
        Returns:
            List of pipeline information dictionaries
        """
        query = {"status": status.value}
        if source_type:
            query["source_type"] = source_type.value
            
        return list(self.pipelines.find(query, {"_id": 0}))
    
    def get_pipeline_metrics(self, pipeline_id: str, limit: int = 100) -> List[Dict]:
        """
        Get metrics for a specific pipeline.
        
        Args:
            pipeline_id: The ID of the pipeline
            limit: Maximum number of metrics entries to return
            
        Returns:
            List of metrics dictionaries
        """
        return list(self.metrics.find(
            {"pipeline_id": pipeline_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
    
    def get_pipeline_errors(self, pipeline_id: str, limit: int = 100) -> List[Dict]:
        """
        Get errors for a specific pipeline.
        
        Args:
            pipeline_id: The ID of the pipeline
            limit: Maximum number of error entries to return
            
        Returns:
            List of error dictionaries
        """
        return list(self.errors.find(
            {"pipeline_id": pipeline_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
    
    def get_recent_logs(self, source_type: SourceType, limit: int = 10) -> List[Dict]:
        """
        Get recent logs for a specific source type.
        
        Args:
            source_type: The source type to filter by
            limit: Maximum number of log entries to return
            
        Returns:
            List of log dictionaries
        """
        return list(self.logs.find(
            {"source_type": source_type.value},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
    
    def get_source_stats(self, source_type: SourceType) -> Dict:
        """
        Get aggregated statistics for a specific source type.
        
        Args:
            source_type: The source type to get statistics for
            
        Returns:
            Dictionary containing aggregated statistics
        """
        pipeline = [
            {"$match": {"source_type": source_type.value}},
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
        
        result = list(self.pipelines.aggregate(pipeline))
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
        
    def get_pipeline_by_query(self, query: object) -> List[Dict]:
        """
        Get pipelines for a specific query.
        
        Args:
            query: The mongo query to execute
            
        Returns:
            List of pipelines dictionaries
        """
        return list(self.pipelines.find(query, {"_id": 0}).sort("created_at", -1))
        
    def delete_pipeline(self, pipeline_id: str) -> bool:
        """
        Set pipeline as deleted.
        
        Args:
            type: The datasource type
            limit: Maximum number of pipelines entries to return
            
        Returns:
            List of pipelines dictionaries
        """
        result = self.pipelines.update_one({"pipeline_id": pipeline_id}, {"$set": {"deleted": True}})
        return result.modified_count > 0