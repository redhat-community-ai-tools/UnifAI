"""
Analytics cache utilities.

Contains cache configuration and helper functions for MongoDB cache management.
"""

from utils.analytics.workflow_analytics import WorkflowAnalytics

# Cache configuration
CACHE_COLLECTION = "analytics_cache"
CACHE_TTL = 60  # 60 seconds

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

