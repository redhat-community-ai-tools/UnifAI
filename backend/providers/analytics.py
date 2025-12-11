"""
Analytics provider for workflow session statistics.

Contains business logic for analyzing workflow sessions from MongoDB.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List
from global_utils.celery_app.helpers import send_task
from shared.logger import logger
from utils.analytics import get_workflow_analytics, get_cache_collection, CACHE_TTL


def get_analytics_overview(time_range: str = "all"):
    """
    Get comprehensive analytics overview with MongoDB caching.
    
    Uses MongoDB as shared cache across all workers.
    Triggers Celery background refresh when cache is about to expire (stale-while-revalidate).
    
    Args:
        time_range: 'today', '7days', '30days', or 'all' (default: 'all')
    
    Returns:
        Dict containing all analytics overview data
    """
    cache_key = f"overview:{time_range}"
    cache_collection = get_cache_collection()
    
    # Try to get from MongoDB cache
    cache_doc = cache_collection.find_one({"_id": cache_key})
    
    if cache_doc:
        # Check if cache is still valid
        expires_at = cache_doc.get("expires_at")
        if expires_at and datetime.now(timezone.utc) < expires_at:
            # Cache HIT - return cached data
            # Trigger background refresh if cache is about to expire (stale-while-revalidate)
            time_until_expiry = (expires_at - datetime.now(timezone.utc)).total_seconds()
            if time_until_expiry < 10:  # Less than 10 seconds until expiry
                try:
                    send_task(
                        task_name="celery_app.tasks.analytics_cache_tasks.refresh_analytics_cache",
                        celery_queue="analytics_queue",
                        time_range=time_range
                    )
                except Exception as e:
                    logger.warning(f"Failed to trigger cache refresh: {str(e)}")
            
            return cache_doc["data"]
    
    # Cache MISS or expired - fetch fresh data
    analytics = get_workflow_analytics()
    
    overview = {
        "total_stats": analytics.get_total_stats(),
        "status_breakdown": analytics.get_status_breakdown(),
        "time_stats": analytics.get_time_based_stats(),
        "active_today": analytics.get_active_users_today(),
        "active_7days": analytics.get_active_users(days=7),
        "active_30days": analytics.get_active_users(days=30),
        "top_users": analytics.get_user_activity(limit=10),
        "top_blueprints": analytics.get_blueprint_usage(limit=10, time_range=time_range),
        "time_series": analytics.get_time_series_activity(time_range=time_range),
        "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }
    
    # Store in MongoDB cache (synchronous write for immediate availability)
    cache_doc = {
        "_id": cache_key,
        "data": overview,
        "time_range": time_range,
        "cached_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(seconds=CACHE_TTL)
    }
    
    cache_collection.replace_one(
        {"_id": cache_key},
        cache_doc,
        upsert=True
    )
    
    # Create TTL index if it doesn't exist (auto-delete expired documents)
    try:
        cache_collection.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        pass  # Index might already exist
    
    # Trigger background refresh for all time ranges on cache miss
    try:
        send_task(
            task_name="celery_app.tasks.analytics_cache_tasks.refresh_all_analytics_cache",
            celery_queue="analytics_queue"
        )
    except Exception as e:
        logger.warning(f"Failed to trigger cache refresh: {str(e)}")
    
    return overview


def get_active_users_data(days: int = 7):
    """
    Get active users for the specified number of days.
    
    Args:
        days: Number of days to look back (default: 7)
    
    Returns:
        Dict with active_users list, days, and count
    """
    analytics = get_workflow_analytics()
    active_users = analytics.get_active_users(days=days)
    
    return {
        "days": days,
        "active_users": active_users,
        "count": len(active_users)
    }


def get_user_activity_data(limit: int = 15):
    """
    Get detailed user activity breakdown.
    
    Args:
        limit: Number of top users to return (default: 15)
    
    Returns:
        Dict with user_activity list and count
    """
    analytics = get_workflow_analytics()
    user_activity = analytics.get_user_activity(limit=limit)
    
    return {
        "user_activity": user_activity,
        "count": len(user_activity)
    }


def get_blueprint_usage_data(limit: int = 10):
    """
    Get most used blueprints.
    
    Args:
        limit: Number of top blueprints to return (default: 10)
    
    Returns:
        Dict with blueprint_usage list and count
    """
    analytics = get_workflow_analytics()
    blueprint_usage = analytics.get_blueprint_usage(limit=limit)
    
    return {
        "blueprint_usage": blueprint_usage,
        "count": len(blueprint_usage)
    }


