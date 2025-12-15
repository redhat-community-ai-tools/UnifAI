"""
Analytics cache utilities.

Contains cache configuration and helper functions for MongoDB cache management.
"""

from utils.analytics.workflow_analytics import WorkflowAnalytics
from config.constants import Collection

# Cache configuration
CACHE_COLLECTION = Collection.ANALYTICS_CACHE.value
CACHE_TTL = 300  # 300 seconds (5 minutes)

# Singleton cache collection access
_cache_collection = None


def get_cache_collection():
    """
    Get MongoDB cache collection (singleton pattern).
    
    Returns:
        MongoDB collection for analytics cache
    """
    global _cache_collection
    if _cache_collection is None:
        analytics = WorkflowAnalytics()
        _cache_collection = analytics.db[CACHE_COLLECTION]
    return _cache_collection

