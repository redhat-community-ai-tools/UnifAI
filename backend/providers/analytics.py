"""
Analytics provider for workflow session statistics.

Contains business logic for analyzing workflow sessions from MongoDB.
"""

from datetime import datetime, timedelta, timezone
from global_utils.celery_app.helpers import send_task
from shared.logger import logger
from utils.analytics import (
    get_workflow_analytics,
    get_cache_collection,
    CACHE_TTL,
    get_cache_lock,
    get_task_tracker
)


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
        if expires_at:
            # Ensure expires_at is timezone-aware (MongoDB might return naive datetime)
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    # Naive datetime - assume UTC
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at:
                now = datetime.now(timezone.utc)
                time_until_expiry = (expires_at - now).total_seconds()
                if now < expires_at:
                    # Cache HIT - return cached data
                    # Trigger background refresh if cache is about to expire (stale-while-revalidate)
                    logger.info(f"Cache HIT for time_range={time_range}, expires in {time_until_expiry:.1f}s")
                    if time_until_expiry < 10:  # Less than 10 seconds until expiry
                        logger.info(f"Cache expiring soon ({time_until_expiry:.1f}s), triggering background refresh")
                        # Check task tracker to avoid duplicate tasks
                        task_tracker = get_task_tracker()
                        if not task_tracker.is_task_running(cache_key):
                            try:
                                # Mark task as started before queueing (prevents duplicates)
                                task_tracker.mark_task_started(cache_key)
                                task_result = send_task(
                                    task_name="celery_app.tasks.analytics_cache_tasks.refresh_analytics_cache",
                                    celery_queue="analytics_queue",
                                    time_range=time_range
                                )
                                # Update task_id after queueing (if available)
                                if task_result:
                                    task_id = getattr(task_result, 'id', None)
                                    if task_id:
                                        task_tracker.update_task_id(cache_key, task_id)
                                    logger.info(f"Queued cache refresh task for time_range={time_range}, task_id={task_id}")
                                else:
                                    logger.info(f"Queued cache refresh task for time_range={time_range}, task_id=None")
                            except Exception as e:
                                logger.error(f"Failed to trigger cache refresh: {str(e)}", exc_info=True)
                        else:
                            logger.debug(f"Cache refresh task already running for {cache_key}, skipping")
                    
                    return cache_doc["data"]
                else:
                    logger.info(f"Cache EXPIRED for time_range={time_range} (expired {abs(time_until_expiry):.1f}s ago)")
    
    # Cache MISS or expired - use distributed lock to prevent thundering herd
    logger.info(f"Cache MISS for time_range={time_range}, attempting to acquire lock")
    
    cache_lock = get_cache_lock()
    task_tracker = get_task_tracker()
    
    # Try to acquire lock (only one user will succeed)
    lock_acquired = cache_lock.acquire(cache_key, timeout=30)
    
    if lock_acquired:
        # This user won the race - they will do the work
        logger.info(f"Lock acquired for {cache_key}, fetching fresh data")
        
        try:
            # Check if task is already running (shouldn't be, but double-check)
            if not task_tracker.is_task_running(cache_key):
                # Mark task as started before queueing (prevents duplicates)
                task_tracker.mark_task_started(cache_key)
                try:
                    task_result = send_task(
                        task_name="celery_app.tasks.analytics_cache_tasks.refresh_analytics_cache",
                        celery_queue="analytics_queue",
                        time_range=time_range
                    )
                    # Update task_id after queueing (if available)
                    if task_result:
                        task_id = getattr(task_result, 'id', None)
                        if task_id:
                            task_tracker.update_task_id(cache_key, task_id)
                        logger.info(f"Queued cache refresh task for time_range={time_range}, task_id={task_id}")
                    else:
                        logger.info(f"Queued cache refresh task for time_range={time_range}, task_id=None")
                except Exception as e:
                    logger.error(f"Failed to trigger cache refresh task: {str(e)}", exc_info=True)
            
            # Fetch fresh data synchronously for this request (user gets immediate response)
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
            
            # Update cache synchronously for immediate availability
            cached_at = datetime.now(timezone.utc)
            expires_at = cached_at + timedelta(seconds=CACHE_TTL)
            
            cache_doc = {
                "_id": cache_key,
                "data": overview,
                "time_range": time_range,
                "cached_at": cached_at,
                "expires_at": expires_at
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
            
            # Release lock so other users can proceed
            cache_lock.release(cache_key)
            logger.info(f"Lock released for {cache_key}, cache updated")
            
            return overview
            
        except Exception as e:
            # Release lock on error
            cache_lock.release(cache_key)
            logger.error(f"Error fetching analytics data: {str(e)}", exc_info=True)
            raise
    else:
        # Lock already held - another user is refreshing, wait for them
        logger.info(f"Lock already held for {cache_key}, waiting for refresh to complete")
        
        # Wait for lock to be released (max 5 seconds)
        lock_released = cache_lock.wait_for_lock(cache_key, max_wait=5, check_interval=0.1)
        
        if lock_released:
            # Lock released, check cache again
            logger.info(f"Lock released for {cache_key}, checking cache")
            cache_doc = cache_collection.find_one({"_id": cache_key})
            
            if cache_doc:
                expires_at = cache_doc.get("expires_at")
                if expires_at:
                    if isinstance(expires_at, datetime):
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                    
                    if expires_at:
                        now = datetime.now(timezone.utc)
                        if now < expires_at:
                            # Cache is now valid, return it
                            logger.info(f"Cache HIT after waiting for {cache_key}")
                            return cache_doc["data"]
        
        # If we get here, either timeout or cache still invalid
        # Fallback: fetch data ourselves (shouldn't happen often)
        logger.warning(f"Timeout waiting for lock or cache still invalid for {cache_key}, fetching directly")
        
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
        
        # Update cache
        cached_at = datetime.now(timezone.utc)
        expires_at = cached_at + timedelta(seconds=CACHE_TTL)
        
        cache_doc = {
            "_id": cache_key,
            "data": overview,
            "time_range": time_range,
            "cached_at": cached_at,
            "expires_at": expires_at
        }
        
        cache_collection.replace_one(
            {"_id": cache_key},
            cache_doc,
            upsert=True
        )
        
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


