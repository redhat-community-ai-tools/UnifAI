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
    This task runs in the background via Celery when cache is MISS or about to expire.
    
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

