"""
Celery tasks for refreshing analytics cache in the background.
"""
from global_utils.celery_app import CeleryApp
from providers.analytics import get_analytics_overview
from shared.logger import logger


@CeleryApp().app.task(bind=True)
def refresh_analytics_cache(self, time_range="all"):
    """
    Refresh analytics cache for a specific time range.
    This task runs in the background via Celery.
    
    Args:
        time_range: 'today', '7days', '30days', or 'all'
    """
    try:
        logger.info(f"Refreshing analytics cache for time_range={time_range}")
        
        # Use provider function to get and cache analytics overview
        # This ensures consistency with the endpoint logic
        overview = get_analytics_overview(time_range)
        
        logger.info(f"Successfully cached analytics data for time_range={time_range}")
        return {"status": "success", "time_range": time_range}
        
    except Exception as e:
        logger.error(f"Failed to refresh analytics cache: {str(e)}", exc_info=True)
        raise


@CeleryApp().app.task(bind=True)
def refresh_all_analytics_cache(self):
    """
    Refresh cache for all time ranges.
    Called periodically to keep cache warm.
    """
    time_ranges = ["all", "today", "7days", "30days"]
    results = []
    
    for time_range in time_ranges:
        try:
            result = refresh_analytics_cache.delay(time_range)
            results.append({"time_range": time_range, "task_id": result.id})
        except Exception as e:
            logger.error(f"Failed to queue cache refresh for {time_range}: {str(e)}")
            results.append({"time_range": time_range, "error": str(e)})
    
    return results

