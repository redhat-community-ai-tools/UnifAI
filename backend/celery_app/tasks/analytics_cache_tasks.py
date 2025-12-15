"""
Celery tasks for refreshing analytics cache in the background.
"""
from datetime import datetime, timedelta, timezone
from global_utils.celery_app import CeleryApp
from utils.analytics import (
    get_workflow_analytics,
    get_cache_collection,
    CACHE_TTL,
    get_task_tracker
)
from shared.logger import logger


@CeleryApp().app.task(bind=True)
def refresh_analytics_cache(self, time_range="all"):
    """
    Refresh analytics cache for a specific time range.
    This task runs in the background via Celery when cache is MISS or about to expire.
    
    IMPORTANT: This task fetches and caches data directly using WorkflowAnalytics.
    It does NOT call get_analytics_overview() to avoid infinite task cascades.
    
    Args:
        time_range: 'today', '7days', '30days', or 'all'
    """
    cache_key = f"overview:{time_range}"
    
    try:
        logger.info(f"Refreshing analytics cache for time_range={time_range}")
        
        # Fetch fresh data directly using WorkflowAnalytics (bypasses provider's task-queueing logic)
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
        
        # Update cache directly
        cache_collection = get_cache_collection()
        
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
        
        # Mark task as completed in task tracker
        task_tracker = get_task_tracker()
        task_tracker.mark_task_completed(cache_key)
        
        logger.info(f"Successfully cached analytics data for time_range={time_range}")
        return {"status": "success", "time_range": time_range}
        
    except Exception as e:
        # Mark task as completed even on error (to prevent stuck tasks)
        try:
            task_tracker = get_task_tracker()
            task_tracker.mark_task_completed(cache_key)
        except Exception:
            pass
        
        logger.error(f"Failed to refresh analytics cache: {str(e)}", exc_info=True)
        raise

