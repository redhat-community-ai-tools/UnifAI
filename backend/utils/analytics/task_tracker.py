"""
Track in-progress Celery tasks to prevent duplicate task execution.

Uses MongoDB to track which cache refresh tasks are currently running.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import pymongo
from shared.logger import logger
from utils.analytics.cache import get_cache_collection
from config.constants import Collection

# Task tracking configuration
TASK_TRACKING_TTL = 60  # Tasks expire after 60 seconds
TASK_COLLECTION = Collection.ANALYTICS_CACHE_TASKS.value


class TaskTracker:
    """Track in-progress cache refresh tasks."""
    
    def __init__(self):
        cache_collection = get_cache_collection()
        self.db = cache_collection.database
        self.task_collection = self.db[TASK_COLLECTION]
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create TTL index for auto-cleanup of expired task records."""
        try:
            self.task_collection.create_index(
                "expires_at",
                expireAfterSeconds=0,
                name="expires_at_ttl"
            )
            # Index for quick lookups
            self.task_collection.create_index(
                "cache_key",
                name="cache_key_idx"
            )
        except Exception:
            pass  # Indexes might already exist
    
    def mark_task_started(self, cache_key: str, task_id: Optional[str] = None) -> bool:
        """
        Mark that a task has started for the given cache key.
        
        Args:
            cache_key: The cache key (e.g., "overview:all")
            task_id: Optional Celery task ID
        
        Returns:
            True if marked (first to mark), False if already exists
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=TASK_TRACKING_TTL)
        
        try:
            # Try to insert task record (atomic operation)
            result = self.task_collection.insert_one({
                "_id": cache_key,
                "cache_key": cache_key,
                "task_id": task_id,
                "started_at": now,
                "expires_at": expires_at
            })
            
            if result.inserted_id:
                logger.info(f"Marked task started for {cache_key}, task_id={task_id}")
                return True
            return False
            
        except pymongo.errors.DuplicateKeyError:
            # Task already tracked
            logger.debug(f"Task already tracked for {cache_key}")
            return False
    
    def is_task_running(self, cache_key: str) -> bool:
        """
        Check if a task is currently running for the given cache key.
        
        Args:
            cache_key: The cache key to check
        
        Returns:
            True if task is running, False otherwise
        """
        task_doc = self.task_collection.find_one({"_id": cache_key})
        
        if not task_doc:
            return False
        
        # Check if task record is expired
        expires_at = task_doc.get("expires_at")
        if expires_at:
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    # Task record expired, clean it up
                    self.task_collection.delete_one({"_id": cache_key})
                    return False
        
        return True
    
    def update_task_id(self, cache_key: str, task_id: str) -> bool:
        """
        Update the task_id for an existing task record.
        
        Args:
            cache_key: The cache key
            task_id: The Celery task ID
        
        Returns:
            True if updated, False otherwise
        """
        try:
            result = self.task_collection.update_one(
                {"_id": cache_key},
                {"$set": {"task_id": task_id}}
            )
            if result.modified_count > 0:
                logger.info(f"Updated task_id for {cache_key}, task_id={task_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating task_id for {cache_key}: {str(e)}")
            return False
    
    def mark_task_completed(self, cache_key: str) -> bool:
        """
        Mark that a task has completed for the given cache key.
        
        Args:
            cache_key: The cache key
        
        Returns:
            True if removed, False otherwise
        """
        try:
            result = self.task_collection.delete_one({"_id": cache_key})
            if result.deleted_count > 0:
                logger.info(f"Marked task completed for {cache_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking task completed for {cache_key}: {str(e)}")
            return False


# Singleton instance
_task_tracker = None


def get_task_tracker() -> TaskTracker:
    """Get singleton TaskTracker instance."""
    global _task_tracker
    if _task_tracker is None:
        _task_tracker = TaskTracker()
    return _task_tracker

