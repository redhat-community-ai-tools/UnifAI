"""
Distributed cache lock using MongoDB for preventing thundering herd.

Uses MongoDB atomic operations to implement distributed locking
across multiple workers/processes.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import pymongo
from shared.logger import logger
from utils.analytics.cache import get_cache_collection
from config.constants import Collection

# Lock configuration
LOCK_TTL = 30  # Lock expires after 30 seconds (safety mechanism)
LOCK_COLLECTION = Collection.ANALYTICS_CACHE_LOCKS.value


class CacheLock:
    """Distributed lock for cache refresh operations."""
    
    def __init__(self):
        cache_collection = get_cache_collection()
        # Use same database as cache
        self.db = cache_collection.database
        self.lock_collection = self.db[LOCK_COLLECTION]
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create TTL index for auto-cleanup of expired locks."""
        try:
            self.lock_collection.create_index(
                "expires_at",
                expireAfterSeconds=0,
                name="expires_at_ttl"
            )
        except Exception:
            pass  # Index might already exist
    
    def acquire(self, cache_key: str, timeout: int = 30) -> bool:
        """
        Try to acquire a lock for the given cache key.
        
        Args:
            cache_key: The cache key to lock (e.g., "overview:all")
            timeout: Lock timeout in seconds (default: 30)
        
        Returns:
            True if lock acquired, False otherwise
        """
        lock_key = f"lock:{cache_key}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=timeout)
        
        try:
            # Try to insert lock document (atomic operation)
            result = self.lock_collection.insert_one({
                "_id": lock_key,
                "cache_key": cache_key,
                "acquired_at": now,
                "expires_at": expires_at,
                "worker_id": f"{datetime.now().timestamp()}"  # Unique identifier
            })
            
            if result.inserted_id:
                logger.info(f"Acquired cache lock for {cache_key}")
                return True
            else:
                return False
                
        except pymongo.errors.DuplicateKeyError:
            # Lock already exists - check if expired
            existing_lock = self.lock_collection.find_one({"_id": lock_key})
            if existing_lock:
                lock_expires = existing_lock.get("expires_at")
                if isinstance(lock_expires, datetime):
                    if lock_expires.tzinfo is None:
                        lock_expires = lock_expires.replace(tzinfo=timezone.utc)
                    if now > lock_expires:
                        # Lock expired, try to remove and acquire
                        self.lock_collection.delete_one({"_id": lock_key})
                        return self.acquire(cache_key, timeout)
            
            logger.debug(f"Lock already held for {cache_key}")
            return False
    
    def release(self, cache_key: str) -> bool:
        """
        Release the lock for the given cache key.
        
        Args:
            cache_key: The cache key to unlock
        
        Returns:
            True if lock released, False otherwise
        """
        lock_key = f"lock:{cache_key}"
        try:
            result = self.lock_collection.delete_one({"_id": lock_key})
            if result.deleted_count > 0:
                logger.info(f"Released cache lock for {cache_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error releasing lock for {cache_key}: {str(e)}")
            return False
    
    def is_locked(self, cache_key: str) -> bool:
        """
        Check if a lock exists for the given cache key.
        
        Args:
            cache_key: The cache key to check
        
        Returns:
            True if locked, False otherwise
        """
        lock_key = f"lock:{cache_key}"
        lock_doc = self.lock_collection.find_one({"_id": lock_key})
        
        if not lock_doc:
            return False
        
        # Check if lock is expired
        expires_at = lock_doc.get("expires_at")
        if expires_at:
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    # Lock expired, clean it up
                    self.lock_collection.delete_one({"_id": lock_key})
                    return False
        
        return True
    
    def wait_for_lock(self, cache_key: str, max_wait: int = 5, check_interval: float = 0.1) -> bool:
        """
        Wait for lock to be released (with timeout).
        
        Args:
            cache_key: The cache key to wait for
            max_wait: Maximum seconds to wait (default: 5)
            check_interval: Seconds between checks (default: 0.1)
        
        Returns:
            True if lock released, False if timeout
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if not self.is_locked(cache_key):
                return True
            time.sleep(check_interval)
        
        return False


# Singleton instance
_cache_lock = None


def get_cache_lock() -> CacheLock:
    """Get singleton CacheLock instance."""
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = CacheLock()
    return _cache_lock

